"""Add namespace support.

Creates the ``namespaces`` table and adds ``namespace_id`` to
``document_chunks`` with a foreign key that sets NULL on delete.

Revision ID: 002
Revises: 001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === namespaces table ===
    op.create_table(
        "namespaces",
        sa.Column("namespace_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("namespace_id"),
        sa.UniqueConstraint("name"),
    )

    # === add namespace_id to document_chunks ===
    op.add_column(
        "document_chunks",
        sa.Column(
            "namespace_id",
            sa.UUID(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_chunks_namespace",
        "document_chunks",
        "namespaces",
        ["namespace_id"],
        ["namespace_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_chunks_namespace",
        "document_chunks",
        ["namespace_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_chunks_namespace", table_name="document_chunks")
    op.drop_constraint("fk_chunks_namespace", "document_chunks", type_="foreignkey")
    op.drop_column("document_chunks", "namespace_id")
    op.drop_table("namespaces")
