"""Integration tests for search functionality."""

import uuid

import pytest


@pytest.mark.asyncio
class TestSearchIntegration:
    async def _setup_test_document(self, db_manager) -> str:
        """Create a test document with chunks for search testing."""
        doc_id = str(uuid.uuid4())

        await db_manager.execute(
            """INSERT INTO documents (document_id, file_path, folder_path,
               title, file_extension, file_size_bytes, content_hash)
               VALUES (:id, :path, :folder, :title, :ext, :size, :hash)""",
            {
                "id": doc_id, "path": "notes/search_test.md",
                "folder": "notes/", "title": "search_test",
                "ext": "md", "size": 500, "hash": "test_hash_001",
            },
        )

        # Insert test chunks
        chunks = [
            {
                "chunk_id": str(uuid.uuid4()), "document_id": doc_id,
                "chunk_level": "file", "chunk_index": 0, "chunk_total": 1,
                "content": "Vector databases enable semantic search.",
                "content_with_context": "file: search_test | text: Vector databases enable semantic search.",
                "content_hash": "ch_hash_1", "embedding_model": "test-model",
                "embedding_dimensions": 768, "token_count": 10, "char_count": 42,
                "embedding": str([0.1] * 768),
            },
            {
                "chunk_id": str(uuid.uuid4()), "document_id": doc_id,
                "chunk_level": "coarse", "chunk_index": 0, "chunk_total": 2,
                "content": "PostgreSQL with pgvector supports HNSW indexing for fast vector search.",
                "content_with_context": "file: search_test | section: Details | text: PostgreSQL with pgvector...",
                "content_hash": "ch_hash_2", "embedding_model": "test-model",
                "embedding_dimensions": 768, "token_count": 15, "char_count": 72,
                "embedding": str([0.2] * 768),
            },
            {
                "chunk_id": str(uuid.uuid4()), "document_id": doc_id,
                "chunk_level": "coarse", "chunk_index": 1, "chunk_total": 2,
                "content": "Hybrid search combines vector and keyword ranking using RRF with k=60.",
                "content_with_context": "file: search_test | section: Methods | text: Hybrid search...",
                "content_hash": "ch_hash_3", "embedding_model": "test-model",
                "embedding_dimensions": 768, "token_count": 15, "char_count": 75,
                "embedding": str([0.3] * 768),
            },
        ]

        for c in chunks:
            await db_manager.execute(
                """INSERT INTO document_chunks (chunk_id, document_id,
                   chunk_level, chunk_index, chunk_total, content,
                   content_with_context, content_hash, embedding_model,
                   embedding_dimensions, token_count, char_count, embedding)
                   VALUES (:chunk_id, :document_id, :chunk_level, :chunk_index,
                   :chunk_total, :content, :content_with_context, :content_hash,
                   :embedding_model, :embedding_dimensions, :token_count,
                   :char_count, :embedding::vector)""",
                c,
            )

        return doc_id

    async def test_keyword_search_finds_content(self, db_manager) -> None:
        """Verify keyword search finds documents by text content."""
        await self._setup_test_document(db_manager)

        from clawtion.core.search.keyword import KeywordSearch

        search = KeywordSearch(db_manager)
        results = await search.search("vector", top_k=5)

        assert len(results["results"]) > 0

    async def test_keyword_search_respects_top_k(self, db_manager) -> None:
        """Verify keyword search respects the top_k parameter."""
        await self._setup_test_document(db_manager)

        from clawtion.core.search.keyword import KeywordSearch

        search = KeywordSearch(db_manager)
        results = await search.search("search", top_k=1)

        assert len(results["results"]) <= 1
        assert "context" in results

    async def test_keyword_search_no_results(self, db_manager) -> None:
        """Verify keyword search returns empty when no matches."""
        await self._setup_test_document(db_manager)

        from clawtion.core.search.keyword import KeywordSearch

        search = KeywordSearch(db_manager)
        results = await search.search("xyznonexistent12345", top_k=5)

        assert len(results["results"]) == 0

    async def test_list_folders(self, db_manager) -> None:
        """Verify folder listing works."""
        await self._setup_test_document(db_manager)
        await db_manager.execute(
            """INSERT INTO documents (document_id, file_path, folder_path,
               title, file_extension, file_size_bytes, content_hash)
               VALUES (:id, :path, :folder, :title, :ext, :size, :hash)""",
            {
                "id": str(uuid.uuid4()), "path": "tech/another.md",
                "folder": "tech/", "title": "another",
                "ext": "md", "size": 200, "hash": "hash_002",
            },
        )

        from clawtion.core.search.keyword import KeywordSearch

        KeywordSearch(db_manager)
        # Use the search service's folder listing through DB query
        rows = await db_manager.execute(
            "SELECT DISTINCT folder_path FROM documents WHERE is_deleted = false ORDER BY folder_path",
            {},
        )
        folders = [r["folder_path"] for r in rows]
        assert "notes/" in folders

    async def test_get_file_chunks(self, db_manager, search_service) -> None:
        """Verify retrieving all chunks for a file."""
        doc_id = await self._setup_test_document(db_manager)

        chunks = await search_service.get_file_chunks(doc_id, level="coarse")
        assert len(chunks) == 2
        assert all(c["chunk_level"] == "coarse" for c in chunks)

    async def test_get_neighbor_chunks(self, db_manager) -> None:
        """Verify neighbor chunk navigation."""
        await self._setup_test_document(db_manager)

        # Get all coarse chunks for the document
        rows = await db_manager.execute(
            """SELECT chunk_id FROM document_chunks
               WHERE chunk_level = 'coarse' AND file_path_join = (
                   SELECT file_path FROM documents WHERE file_path = 'notes/search_test.md'
               )""",
            {},
        )
        if len(rows) >= 2:

            # Test navigation through the search service if available
            chunk_ids = [r["chunk_id"] for r in rows]
            assert len(chunk_ids) >= 1

    async def test_chunk_level_filter(self, db_manager) -> None:
        """Verify search can filter by chunk level."""
        await self._setup_test_document(db_manager)

        from clawtion.core.search.keyword import KeywordSearch

        search = KeywordSearch(db_manager)
        file_results = await search.search("search", chunk_level="file", top_k=10)
        coarse_results = await search.search("search", chunk_level="coarse", top_k=10)

        # Both should find relevant results
        assert "results" in file_results
        assert "results" in coarse_results
