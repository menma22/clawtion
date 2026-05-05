"""Add GraphRAG entities and relations tables.

Creates the ``entities`` and ``relations`` tables for graph-based
knowledge retrieval.  The ``entities`` table stores named entities
extracted from document chunks, while ``relations`` captures typed
directed edges between entities.

Revision ID: 003
Revises: 002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === entities table ===
    op.create_table(
        "entities",
        sa.Column("entity_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("entity_id"),
        sa.UniqueConstraint("name", "entity_type", name="uq_entity_name_type"),
    )

    op.create_index("idx_entities_name", "entities", ["name"])
    op.create_index("idx_entities_type", "entities", ["entity_type"])

    # HNSW index for entity vector similarity search
    op.execute(
        "CREATE INDEX idx_entities_embedding_hnsw ON entities "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 128)"
    )

    # === relations table ===
    op.create_table(
        "relations",
        sa.Column("relation_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_entity_id", sa.UUID(), nullable=False),
        sa.Column("target_entity_id", sa.UUID(), nullable=False),
        sa.Column("relation_type", sa.String(length=100), nullable=False),
        sa.Column("weight", sa.Float(), server_default=sa.text("1.0"), nullable=False),
        sa.Column("source_chunk_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("relation_id"),
        sa.ForeignKeyConstraint(
            ["source_entity_id"], ["entities.entity_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"], ["entities.entity_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_chunk_id"], ["document_chunks.chunk_id"],
            ondelete="SET NULL",
        ),
    )

    op.create_index("idx_relations_source", "relations", ["source_entity_id"])
    op.create_index("idx_relations_target", "relations", ["target_entity_id"])
    op.create_index("idx_relations_type", "relations", ["relation_type"])
    op.create_index("idx_relations_chunk", "relations", ["source_chunk_id"])
    op.create_index(
        "idx_relations_source_target_type",
        "relations",
        ["source_entity_id", "target_entity_id", "relation_type"],
    )


def downgrade() -> None:
    op.drop_table("relations")
    op.drop_table("entities")
