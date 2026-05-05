"""Integration tests for database schema and migrations."""

import pytest


@pytest.mark.asyncio
class TestDatabaseSchema:
    async def test_tables_exist(self, db_manager) -> None:
        """Verify all required tables are created after migration."""
        query = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        rows = await db_manager.execute(query, {})
        tables = {r["table_name"] for r in rows}

        expected = {"documents", "document_chunks", "indexing_queue", "trash", "vault_settings"}
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    async def test_documents_table_columns(self, db_manager) -> None:
        """Verify documents table has all required columns."""
        query = """
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'documents'
        """
        rows = await db_manager.execute(query, {})
        columns = {r["column_name"] for r in rows}

        required = {
            "document_id", "file_path", "folder_path", "title",
            "file_extension", "file_size_bytes", "content_hash",
            "tags", "wikilinks", "metadata", "total_chunks",
            "has_file_level", "has_coarse_level", "has_fine_level",
            "last_indexed_at", "is_deleted", "deleted_at",
            "created_at", "updated_at",
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    async def test_document_chunks_table_columns(self, db_manager) -> None:
        """Verify document_chunks table has all required columns."""
        query = """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'document_chunks'
        """
        rows = await db_manager.execute(query, {})
        columns = {r["column_name"] for r in rows}

        required = {
            "chunk_id", "document_id", "chunk_level", "chunk_index",
            "chunk_total", "content", "content_with_context",
            "content_hash", "embedding", "embedding_model",
            "embedding_dimensions", "token_count", "char_count",
            "heading_path", "metadata", "created_at",
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    async def test_indexing_queue_table_columns(self, db_manager) -> None:
        """Verify indexing_queue table has all required columns."""
        query = """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'indexing_queue'
        """
        rows = await db_manager.execute(query, {})
        columns = {r["column_name"] for r in rows}

        required = {
            "queue_id", "document_id", "file_path", "operation",
            "status", "progress", "priority", "retry_count",
            "max_retries", "last_error", "error_history",
            "created_at", "started_at", "completed_at",
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    async def test_vector_extension_installed(self, db_manager) -> None:
        """Verify pgvector extension is installed."""
        rows = await db_manager.execute(
            "SELECT extname FROM pg_extension WHERE extname = 'vector'", {}
        )
        assert len(rows) == 1
        assert rows[0]["extname"] == "vector"

    async def test_document_insert(self, db_manager) -> None:
        """Verify we can insert and retrieve a document."""
        import uuid

        doc_id = str(uuid.uuid4())
        await db_manager.execute(
            """INSERT INTO documents (document_id, file_path, folder_path,
               title, file_extension, file_size_bytes, content_hash)
               VALUES (:id, :path, :folder, :title, :ext, :size, :hash)""",
            {
                "id": doc_id,
                "path": "notes/test.md",
                "folder": "notes/",
                "title": "test",
                "ext": "md",
                "size": 100,
                "hash": "abc123",
            },
        )

        row = await db_manager.execute_one(
            "SELECT * FROM documents WHERE document_id = :id", {"id": doc_id}
        )
        assert row is not None
        assert row["file_path"] == "notes/test.md"
        assert row["title"] == "test"
        assert row["is_deleted"] is False

    async def test_unique_file_path(self, db_manager) -> None:
        """Verify file_path uniqueness constraint."""
        import uuid

        doc_id1 = str(uuid.uuid4())
        doc_id2 = str(uuid.uuid4())

        await db_manager.execute(
            """INSERT INTO documents (document_id, file_path, folder_path,
               title, file_extension, file_size_bytes, content_hash)
               VALUES (:id, :path, :folder, :title, :ext, :size, :hash)""",
            {
                "id": doc_id1, "path": "notes/unique.md", "folder": "notes/",
                "title": "unique", "ext": "md", "size": 100, "hash": "abc",
            },
        )

        with pytest.raises(Exception):  # noqa: B017 — testing DB constraint violation
            await db_manager.execute(
                """INSERT INTO documents (document_id, file_path, folder_path,
                   title, file_extension, file_size_bytes, content_hash)
                   VALUES (:id, :path, :folder, :title, :ext, :size, :hash)""",
                {
                    "id": doc_id2, "path": "notes/unique.md", "folder": "notes/",
                    "title": "unique2", "ext": "md", "size": 200, "hash": "def",
                },
            )

    async def test_vault_settings(self, db_manager) -> None:
        """Verify vault_settings table works."""
        await db_manager.execute(
            "INSERT INTO vault_settings (key, value) VALUES (:key, :value)",
            {"key": "test_key", "value": '{"enabled": true}'},
        )

        row = await db_manager.execute_one(
            "SELECT * FROM vault_settings WHERE key = :key", {"key": "test_key"}
        )
        assert row is not None
        assert row["key"] == "test_key"
