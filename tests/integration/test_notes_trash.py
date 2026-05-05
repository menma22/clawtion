"""Integration tests for Note and Trash services."""


import pytest


@pytest.mark.asyncio
class TestNoteServiceIntegration:
    async def test_create_note_creates_db_record(self, db_manager, vault_path) -> None:
        """Verify creating a note inserts a document record."""
        from unittest.mock import AsyncMock

        from clawtion.core.note.service import NoteService

        indexing_service = AsyncMock()
        service = NoteService(db_manager, vault_path, indexing_service)

        result = await service.create(
            title="Test Note",
            content="# Hello\n\nWorld",
            folder="notes",
            tags=["test"],
        )

        assert result["title"] == "Test Note"
        assert result["folder_path"] == "notes/"
        assert "document_id" in result

        # Verify DB record exists
        row = await db_manager.execute_one(
            "SELECT * FROM documents WHERE document_id = :id",
            {"id": result["document_id"]},
        )
        assert row is not None
        assert row["title"] == "Test Note"

    async def test_get_note_retrieves_record(self, db_manager, vault_path) -> None:
        """Verify retrieving a note by ID."""
        from unittest.mock import AsyncMock

        from clawtion.core.note.service import NoteService

        indexing_service = AsyncMock()
        service = NoteService(db_manager, vault_path, indexing_service)

        created = await service.create(
            title="Get Test", content="Content here", folder=""
        )

        retrieved = await service.get(created["document_id"])
        assert retrieved["title"] == "Get Test"
        assert retrieved["content"] == "Content here"

    async def test_update_note(self, db_manager, vault_path) -> None:
        """Verify updating a note changes content."""
        from unittest.mock import AsyncMock

        from clawtion.core.note.service import NoteService

        indexing_service = AsyncMock()
        service = NoteService(db_manager, vault_path, indexing_service)

        created = await service.create(
            title="Update Test", content="Original", folder=""
        )
        updated = await service.update(created["document_id"], content="Updated content")
        assert updated["success"] is True

        retrieved = await service.get(created["document_id"])
        assert retrieved["content"] == "Updated content"

    async def test_list_notes(self, db_manager, vault_path) -> None:
        """Verify listing notes with filters."""
        from unittest.mock import AsyncMock

        from clawtion.core.note.service import NoteService

        indexing_service = AsyncMock()
        service = NoteService(db_manager, vault_path, indexing_service)

        await service.create(title="Note A", content="A", folder="tech")
        await service.create(title="Note B", content="B", folder="tech")
        await service.create(title="Note C", content="C", folder="personal")

        all_notes = await service.list_notes()
        assert len(all_notes) >= 3

        tech_notes = await service.list_notes(folder="tech/")
        assert len(tech_notes) >= 2

    async def test_list_folders(self, db_manager, vault_path) -> None:
        """Verify folder listing."""
        from unittest.mock import AsyncMock

        from clawtion.core.note.service import NoteService

        indexing_service = AsyncMock()
        service = NoteService(db_manager, vault_path, indexing_service)

        await service.create(title="N1", content="c", folder="tech")
        await service.create(title="N2", content="c", folder="personal")

        folders = await service.list_folders()
        assert "tech/" in folders or "tech" in folders

    async def test_delete_note_soft(self, db_manager, vault_path) -> None:
        """Verify soft delete marks document as deleted."""
        from unittest.mock import AsyncMock

        from clawtion.core.note.service import NoteService

        indexing_service = AsyncMock()
        service = NoteService(db_manager, vault_path, indexing_service)

        created = await service.create(title="Delete Me", content="x", folder="")
        result = await service.delete(created["document_id"], permanent=False)

        assert result["success"] is True

        # Verify soft-deleted
        row = await db_manager.execute_one(
            "SELECT is_deleted FROM documents WHERE document_id = :id",
            {"id": created["document_id"]},
        )
        assert row["is_deleted"] is True


@pytest.mark.asyncio
class TestTrashServiceIntegration:
    async def test_trash_list(self, db_manager, vault_path) -> None:
        """Verify trash listing shows deleted items."""
        from unittest.mock import AsyncMock

        from clawtion.core.note.service import NoteService
        from clawtion.core.trash.service import TrashService

        indexing_service = AsyncMock()
        note_service = NoteService(db_manager, vault_path, indexing_service)
        trash_service = TrashService(db_manager, vault_path)

        created = await note_service.create(title="Trash Test", content="y", folder="")
        await note_service.delete(created["document_id"], permanent=False)

        items = await trash_service.list_items()
        assert len(items) >= 1

    async def test_trash_restore(self, db_manager, vault_path) -> None:
        """Verify restoring from trash."""
        from unittest.mock import AsyncMock

        from clawtion.core.note.service import NoteService
        from clawtion.core.trash.service import TrashService

        indexing_service = AsyncMock()
        note_service = NoteService(db_manager, vault_path, indexing_service)
        trash_service = TrashService(db_manager, vault_path)

        created = await note_service.create(title="Restore Me", content="z", folder="")
        await note_service.delete(created["document_id"], permanent=False)

        items = await trash_service.list_items()
        assert len(items) >= 1

        result = await trash_service.restore(items[0]["trash_id"])
        assert result["success"] is True
