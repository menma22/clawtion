"""Add pg_trgm GIN index on document_chunks.content for partial-match search.

Revision ID: 004
Revises: 003
Create Date: 2026-05-08
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm "
        "ON document_chunks USING GIN (content gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_content_trgm")
