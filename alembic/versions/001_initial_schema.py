"""Initial database schema for clawtion.

Creates all core tables:
- documents       : file-level metadata and indexing state
- document_chunks : chunked content with vector embeddings
- indexing_queue  : async job queue for indexing operations
- trash           : soft-deleted file recovery
- vault_settings  : per-vault key/value configuration

Also creates:
- pgvector extension (vector type, HNSW index)
- pg_trgm extension (trigram-based text search)
- GIN indexes on JSONB and tsvector columns
- B-tree indexes on common filter columns
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === Extensions ===
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # === documents table ===
    op.create_table(
        "documents",
        # Identifiers
        sa.Column("document_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # File information
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("folder_path", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("file_extension", sa.String(length=10), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        # Change detection
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        # Metadata
        sa.Column("tags", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("wikilinks", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        # Indexing state
        sa.Column("total_chunks", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("has_file_level", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_coarse_level", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_fine_level", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_indexed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Lifecycle
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("document_id"),
        sa.UniqueConstraint("file_path"),
    )

    # === indexes for documents ===
    op.create_index("idx_documents_folder", "documents", ["folder_path"])
    op.create_index("idx_documents_extension", "documents", ["file_extension"])
    op.create_index("idx_documents_deleted", "documents", ["is_deleted", "deleted_at"])
    op.create_index("idx_documents_updated", "documents", [sa.text("updated_at DESC")])

    # GIN index on tags JSONB
    op.execute(
        "CREATE INDEX idx_documents_tags ON documents USING GIN (tags)"
    )

    # === document_chunks table ===
    op.create_table(
        "document_chunks",
        # Identifiers
        sa.Column("chunk_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        # Granularity
        sa.Column("chunk_level", sa.String(length=10), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_total", sa.Integer(), nullable=False),
        # Hierarchy
        sa.Column("parent_chunk_id", sa.UUID(), nullable=True),
        # Structure
        sa.Column("heading_path", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        # Content
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_with_context", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        # Vector embedding
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("embedding_model", sa.String(length=50), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("embedded_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Metrics
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        # Metadata
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        # Timestamps
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("chunk_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_chunk_id"], ["document_chunks.chunk_id"], ondelete="SET NULL"),
        sa.UniqueConstraint("document_id", "chunk_level", "chunk_index"),
    )

    # Generated tsvector column for full-text search
    op.execute(
        "ALTER TABLE document_chunks "
        "ADD COLUMN tsvector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED"
    )

    # === indexes for document_chunks ===
    # HNSW index for vector similarity search
    op.execute(
        "CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 128)"
    )

    # GIN index for full-text search
    op.execute(
        "CREATE INDEX idx_chunks_tsvector ON document_chunks USING GIN (tsvector)"
    )

    # B-tree indexes
    op.create_index("idx_chunks_doc_level", "document_chunks", ["document_id", "chunk_level", "chunk_index"])
    op.create_index("idx_chunks_level", "document_chunks", ["chunk_level"])
    op.create_index("idx_chunks_parent", "document_chunks", ["parent_chunk_id"])
    op.create_index("idx_chunks_hash", "document_chunks", ["content_hash"])

    # === indexing_queue table ===
    op.create_table(
        "indexing_queue",
        sa.Column("queue_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("progress", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_retries", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("error_history", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("queue_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="CASCADE"),
    )

    op.create_index("idx_queue_status", "indexing_queue", ["status", sa.text("priority DESC"), sa.text("created_at")])
    op.create_index("idx_queue_document", "indexing_queue", ["document_id"])

    # === trash table ===
    op.create_table(
        "trash",
        sa.Column("trash_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("original_document_id", sa.UUID(), nullable=False),
        sa.Column("original_file_path", sa.Text(), nullable=False),
        sa.Column("original_content", sa.Text(), nullable=False),
        sa.Column("original_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("auto_purge_at", sa.TIMESTAMP(timezone=True), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("trash_id"),
    )

    op.create_index("idx_trash_purge", "trash", ["auto_purge_at"])

    # === vault_settings table ===
    op.create_table(
        "vault_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    """Remove all tables and extensions created in upgrade()."""
    op.drop_table("vault_settings")
    op.drop_table("trash")
    op.drop_table("indexing_queue")
    op.drop_table("document_chunks")
    op.drop_table("documents")

    # Extensions are kept on downgrade (other tables may depend on them).
    # op.execute("DROP EXTENSION IF EXISTS vector")
    # op.execute("DROP EXTENSION IF EXISTS pg_trgm")
