"""Integration test fixtures.

Provides a real PostgreSQL + pgvector database via testcontainers,
or falls back to an environment-configured database URL.
"""

import os

import pytest
import pytest_asyncio


@pytest.fixture(scope="session")
def db_url() -> str:
    """Return the database URL for integration tests.

    Priority:
    1. CLAWTION_TEST_DB_URL environment variable
    2. Default local pgvector container URL
    """
    return os.environ.get(
        "CLAWTION_TEST_DB_URL",
        "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion_test",
    )


@pytest_asyncio.fixture
async def db_manager(db_url: str):
    """Create a connected DatabaseManager for a test.

    Drops and recreates the public schema before each test
    to ensure isolation.
    """
    from clawtion.core.db.connection import DatabaseManager

    manager = DatabaseManager(db_url)
    await manager.connect()

    # Clean schema for test isolation
    await manager.execute("DROP SCHEMA IF EXISTS public CASCADE")
    await manager.execute("CREATE SCHEMA public")
    await manager.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await manager.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Create tables directly via SQLAlchemy metadata (avoids Alembic asyncio.run() issue)
    from sqlalchemy.ext.asyncio import create_async_engine

    from clawtion.core.db.models import Base

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    # Manually create tsvector column (SQLAlchemy create_all doesn't handle
    # Computed GENERATED ALWAYS columns correctly for asyncpg)
    await manager.execute(
        "ALTER TABLE document_chunks "
        "ADD COLUMN IF NOT EXISTS tsvector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED"
    )
    await manager.execute("CREATE INDEX IF NOT EXISTS idx_chunks_tsvector ON document_chunks USING GIN (tsvector)")

    yield manager

    await manager.disconnect()


@pytest_asyncio.fixture
async def search_service(db_manager):
    """Create a SearchService with a mock embedder for testing."""
    from unittest.mock import AsyncMock

    from clawtion.core.embedding.client import EmbeddingResult
    from clawtion.core.search.service import SearchService

    embedder = AsyncMock()
    embedder.model_name = "test-model"
    embedder.dimensions = 768

    async def mock_embed_query(query: str) -> EmbeddingResult:
        return EmbeddingResult(
            embedding=[0.1] * 768,
            model="test-model",
            dimensions=768,
            token_count=10,
        )

    embedder.embed_query = mock_embed_query

    async def mock_embed_document(content: str) -> EmbeddingResult:
        return EmbeddingResult(
            embedding=[0.1] * 768,
            model="test-model",
            dimensions=768,
            token_count=10,
        )

    embedder.embed_document = mock_embed_document

    service = SearchService(db_manager, embedder)
    return service


@pytest_asyncio.fixture
async def vault_path(tmp_path):
    """Create a temporary vault directory with sample files."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create a sample markdown file
    note_dir = vault / "notes"
    note_dir.mkdir()
    (note_dir / "test.md").write_text(
        """# Test Note

## Overview

This is a test note about vector databases and RAG systems.

## Details

PostgreSQL with pgvector enables efficient vector similarity search.
Hybrid search combines semantic and keyword approaches using RRF.

### Technical Info

The HNSW index provides fast approximate nearest neighbor search.
Cosine similarity is used for vector comparison.
""",
        encoding="utf-8",
    )

    # Create a subfolder with another file
    tech_dir = vault / "tech"
    tech_dir.mkdir()
    (tech_dir / "rag.md").write_text(
        """# RAG Knowledge

## Chunking Strategies

Semantic chunking preserves meaning by splitting at natural boundaries.

## Search Methods

Reciprocal Rank Fusion (RRF) with k=60 is the standard approach.
""",
        encoding="utf-8",
    )

    return str(vault)
