"""Database connection manager for clawtion.

Provides an async-compatible ``DatabaseManager`` built on top of
SQLAlchemy's ``create_async_engine`` / ``async_sessionmaker`` with
PGVector support out of the box.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseConnectionError(Exception):
    """Raised when the database cannot be reached or initialised."""


class DatabaseManager:
    """Async-compatible manager for a PostgreSQL + pgvector database.

    Usage::

        mgr = DatabaseManager("postgresql+asyncpg://user:pass@localhost:5432/db")
        await mgr.connect()
        try:
            async with mgr.get_session() as session:
                session.add(some_model)
                await session.commit()
        finally:
            await mgr.disconnect()

    Wraps :func:`sqlalchemy.ext.asyncio.create_async_engine` and
    :class:`~sqlalchemy.ext.asyncio.AsyncSession` with sensible defaults
    for connection pooling.
    """

    def __init__(
        self,
        db_url: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_recycle: int = 3600,
        echo: bool = False,
    ) -> None:
        """Initialise the manager without connecting.

        Args:
            db_url: Full database URL including scheme
                (e.g. ``postgresql+asyncpg://user:pass@host:port/db``).
            pool_size: Number of connections to maintain in the pool.
            max_overflow: Maximum overflow connections beyond pool_size.
            pool_recycle: Recycle connections after this many seconds.
            echo: Log all SQL statements when True (development only).
        """
        if not db_url.startswith("postgresql+asyncpg"):
            raise ValueError(
                f"Expected a postgresql+asyncpg:// URL, got: {db_url!r}",
            )
        self._db_url: str = db_url
        self._pool_size: int = pool_size
        self._max_overflow: int = max_overflow
        self._pool_recycle: int = pool_recycle
        self._echo: bool = echo
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    # -- Lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        """Create the async engine and session factory.

        Raises:
            DatabaseConnectionError: If the engine cannot be created or
                the database is unreachable.
        """
        try:
            self._engine = create_async_engine(
                self._db_url,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_recycle=self._pool_recycle,
                echo=self._echo,
                pool_pre_ping=True,
            )
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            # Verify connectivity immediately.
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            await self.disconnect()
            raise DatabaseConnectionError(
                f"Could not connect to database at {self._db_url!r}: {exc}",
            ) from exc

    async def disconnect(self) -> None:
        """Dispose of the engine and release all connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def is_connected(self) -> bool:
        """Return True if the engine has been created."""
        return self._engine is not None

    # -- Sessions ------------------------------------------------------------

    @contextlib.asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Yield an :class:`AsyncSession` as an async context manager.

        The session is automatically closed when the context exits.

        Example::

            async with mgr.get_session() as session:
                result = await session.execute(...)
        """
        if self._session_factory is None:
            raise DatabaseConnectionError(
                "DatabaseManager is not connected. Call .connect() first.",
            )
        session: AsyncSession
        async with self._session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Yield an :class:`AsyncSession` inside an open transaction.

        The transaction is committed on success and rolled back on
        exception.  The session is closed automatically.

        Example::

            async with mgr.transaction() as session:
                session.add(obj)   # auto-committed on success
                # rolled back if an exception is raised
        """
        if self._session_factory is None:
            raise DatabaseConnectionError(
                "DatabaseManager is not connected. Call .connect() first.",
            )
        session: AsyncSession
        async with self._session_factory() as session:
            try:
                async with session.begin():
                    yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    # -- Raw SQL helpers -----------------------------------------------------

    async def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Execute a raw SQL statement and return all rows.

        Args:
            query:  SQL statement (may contain ``:named`` parameters).
            params: Bound parameter dictionary.

        Returns:
            A list of result rows (each row is a lightweight
            :class:`~sqlalchemy.engine.Row` object). Returns empty list
            for DDL statements that produce no rows.
        """
        async with self.get_session() as session:
            result = await session.execute(text(query), params or {})
            await session.commit()
            if result.returns_rows:  # type: ignore[attr-defined]
                return list(result.mappings().all())
            return []

    async def execute_one(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a raw SQL statement and return exactly one row (or None).

        Args:
            query:  SQL statement (may contain ``:named`` parameters).
            params: Bound parameter dictionary.

        Returns:
            A single :class:`~sqlalchemy.engine.Row` object or None if no
            rows matched.
        """
        async with self.get_session() as session:
            result = await session.execute(text(query), params or {})
            await session.commit()
            if result.returns_rows:  # type: ignore[attr-defined]
                return result.mappings().first()
            return None

    # -- Engine access -------------------------------------------------------

    @property
    def engine(self) -> AsyncEngine:
        """Return the underlying :class:`AsyncEngine`.

        Raises:
            DatabaseConnectionError: If not connected.
        """
        if self._engine is None:
            raise DatabaseConnectionError(
                "DatabaseManager is not connected. Call .connect() first.",
            )
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Return the session factory.

        Raises:
            DatabaseConnectionError: If not connected.
        """
        if self._session_factory is None:
            raise DatabaseConnectionError(
                "DatabaseManager is not connected. Call .connect() first.",
            )
        return self._session_factory
