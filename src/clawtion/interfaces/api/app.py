"""FastAPI application factory for the clawtion REST API.

Creates and configures a FastAPI instance with:
- CORS middleware
- Request ID middleware
- Unified exception handler (ClawtionError -> structured JSON)
- Lifespan-based service initialisation / teardown
- Route registration under ``/api/v1/``
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Generic, TypeVar

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from clawtion.config.loader import get_config
from clawtion.config.secrets import get_secret
from clawtion.utils.exceptions import ClawtionError
from clawtion.utils.logging import setup_logging

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger("clawtion.api")

# ---------------------------------------------------------------------------
# Unified response / error models
# ---------------------------------------------------------------------------

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Wrapper for every successful API response."""

    data: T
    meta: dict[str, Any] | None = None


class APIError(BaseModel):
    """Shape of every error payload returned by the API."""

    code: str
    message: str
    details: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Service dependency helpers  (used by route Depends())
# ---------------------------------------------------------------------------

__all__ = [
    "APIError",
    "APIResponse",
    "create_app",
]


def _http_status_for(error_code: str) -> int:
    """Map a ``ClawtionError.code`` to an HTTP status code."""
    _map: dict[str, int] = {
        "DOCUMENT_NOT_FOUND": 404,
        "VALIDATION_ERROR": 422,
        "EMBEDDING_API_ERROR": 502,
        "INDEXING_ERROR": 500,
        "QUEUE_ERROR": 500,
        "QUEUE_FULL": 429,
        "VAULT_ERROR": 500,
        "INTERNAL_ERROR": 500,
    }
    return _map.get(error_code, 500)


# ---------------------------------------------------------------------------
# .env loader
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """Load .env file from project root or current directory into os.environ."""
    from pathlib import Path

    # Search for .env from current dir up to project root
    search_dir = Path.cwd()
    for _ in range(5):
        env_file = search_dir / ".env"
        if env_file.exists():
            with env_file.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
            logger.info("dotenv_loaded", path=str(env_file))
            return
        search_dir = search_dir.parent


# ---------------------------------------------------------------------------
# Lifespan  –  initialise / tear down services
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan: connect DB on start, disconnect on shutdown."""
    # ---- startup ---------------------------------------------------------
    setup_logging()

    # Load .env file from project root (ensures API keys are available)
    _load_dotenv()

    config = get_config()
    vault_path: str = config.get("vault", {}).get("path", "~/Documents/clawtion-vault")
    db_url: str = config.get("database", {}).get(
        "url", "postgresql://localhost:5432/clawtion"
    )

    # Database
    from clawtion.core.db.connection import DatabaseManager

    db = DatabaseManager(db_url)
    await db.connect()
    logger.info("database_connected", url=db_url)

    # Embedder
    gemini_api_key = get_secret("gemini_api_key")
    from clawtion.core.embedding.gemini import GeminiEmbeddingClient

    embedder = GeminiEmbeddingClient(api_key=gemini_api_key) if gemini_api_key else None

    # Services
    from clawtion.core.note.service import NoteService
    from clawtion.core.search.service import SearchService
    from clawtion.core.trash.service import TrashService
    from clawtion.core.indexing.queue import QueueManager
    from clawtion.core.indexing.service import IndexingService

    queue_manager = QueueManager(db)
    indexing_service = IndexingService(
        db=db,
        embedder=embedder,
        queue=queue_manager,
        vault_path=vault_path,
    ) if embedder else None

    search_service = SearchService(db, embedder)
    note_service = NoteService(db, vault_path, indexing_service=indexing_service)
    trash_service = TrashService(db, vault_path)

    app.state.db = db
    app.state.vault_path = vault_path
    app.state.search_service = search_service
    app.state.note_service = note_service
    app.state.trash_service = trash_service
    app.state.queue_manager = queue_manager
    app.state.embedder = embedder

    logger.info("api_started", vault=vault_path)

    yield

    # ---- shutdown --------------------------------------------------------
    await db.disconnect()
    logger.info("api_stopped")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and return a fully configured FastAPI application."""
    app = FastAPI(
        title="clawtion API",
        version="0.1.0",
        summary="REST API for clawtion knowledge base",
        description=(
            "clawtion is a local knowledge base that provides semantic, "
            "keyword, and hybrid search over your personal notes and documents."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # -- CORS -----------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Request-ID middleware ------------------------------------------------
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # -- Global exception handler for clawtion errors -------------------------
    @app.exception_handler(ClawtionError)
    async def clawtion_error_handler(
        request: Request,
        exc: ClawtionError,
    ) -> JSONResponse:
        status_code = _http_status_for(exc.code)
        payload = {
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        }
        return JSONResponse(status_code=status_code, content=payload)

    # -- Register routers -----------------------------------------------------
    from clawtion.interfaces.api.routes import notes, queue, search

    app.include_router(search.router, prefix="/api/v1")
    app.include_router(notes.router, prefix="/api/v1")
    app.include_router(queue.router, prefix="/api/v1")

    # -- Health / version -----------------------------------------------------
    @app.get("/health", tags=["system"])
    async def health() -> dict[str, Any]:
        db_ok = app.state.db.is_connected() if hasattr(app.state, "db") else False
        return {
            "status": "ok" if db_ok else "degraded",
            "version": "0.1.0",
            "database": "connected" if db_ok else "disconnected",
        }

    @app.get("/version", tags=["system"])
    async def version() -> dict[str, str]:
        return {"version": "0.1.0"}

    return app
