"""Unit tests for chunking algorithms."""

from clawtion.core.indexing.chunker import (
    Chunk,
    build_context,
    chunk_file_level,
    is_code_block,
    is_table,
    merge_short_adjacent,
    split_by_markdown_headings,
    split_by_paragraphs,
)


class TestChunkFileLevel:
    def test_within_limit(self) -> None:
        content = "Short note content. " * 50  # ~200 chars
        chunks = chunk_file_level(content, max_tokens=1500)
        assert len(chunks) == 1
        assert chunks[0].level == "file"
        assert chunks[0].chunk_index == 0
        assert chunks[0].chunk_total == 1
        assert chunks[0].content == content

    def test_exceeds_limit(self) -> None:
        # Create content that exceeds 1500 tokens (~6000+ chars for English)
        content = "A" * 10000
        chunks = chunk_file_level(content, max_tokens=100)
        assert len(chunks) == 0

    def test_has_content_hash(self) -> None:
        content = "Test content"
        chunks = chunk_file_level(content, max_tokens=1500)
        assert len(chunks[0].content_hash) == 64  # SHA-256 hex digest

    def test_different_content_different_hash(self) -> None:
        chunks1 = chunk_file_level("Content A", max_tokens=1500)
        chunks2 = chunk_file_level("Content B", max_tokens=1500)
        assert chunks1[0].content_hash != chunks2[0].content_hash

    def test_same_content_same_hash(self) -> None:
        chunks1 = chunk_file_level("Same content", max_tokens=1500)
        chunks2 = chunk_file_level("Same content", max_tokens=1500)
        assert chunks1[0].content_hash == chunks2[0].content_hash


class TestBuildContext:
    def test_basic_context(self) -> None:
        result = build_context(
            folder_path="tech/rag",
            title="agentic",
            heading_path="Hybrid Search > RRF",
            content="Reciprocal Rank Fusion is...",
        )
        assert "folder: tech/rag" in result
        assert "file: agentic" in result
        assert "section: Hybrid Search > RRF" in result
        assert "text: Reciprocal Rank Fusion is..." in result

    def test_no_heading(self) -> None:
        result = build_context(
            folder_path="notes",
            title="diary",
            heading_path=None,
            content="Today's notes...",
        )
        assert "section:" not in result


class TestSplitByMarkdownHeadings:
    def test_h1_headings(self) -> None:
        content = "# Heading 1\nContent of section 1.\n\n# Heading 2\nContent of section 2."
        sections = split_by_markdown_headings(content)
        assert len(sections) >= 1

    def test_h2_h3_headings(self) -> None:
        content = "## Subsection A\nContent A.\n\n### Sub-subsection\nContent B."
        sections = split_by_markdown_headings(content)
        assert len(sections) >= 1

    def test_no_headings(self) -> None:
        content = "Just plain text without any headings."
        sections = split_by_markdown_headings(content)
        assert len(sections) >= 1

    def test_empty_content(self) -> None:
        sections = split_by_markdown_headings("")
        assert len(sections) <= 1


class TestSplitByParagraphs:
    def test_single_paragraph(self) -> None:
        result = split_by_paragraphs("Single paragraph.")
        assert len(result) == 1

    def test_multiple_paragraphs(self) -> None:
        result = split_by_paragraphs("Para 1.\n\nPara 2.\n\nPara 3.")
        assert len(result) == 3

    def test_empty_content(self) -> None:
        result = split_by_paragraphs("")
        assert result == []

    def test_single_newline_not_split(self) -> None:
        result = split_by_paragraphs("Line 1.\nLine 2.\nLine 3.")
        assert len(result) == 1


class TestIsCodeBlock:
    def test_fenced_code_block(self) -> None:
        assert is_code_block("```python\nprint('hello')\n```") is True

    def test_not_code_block(self) -> None:
        assert is_code_block("Regular paragraph.") is False

    def test_inline_code(self) -> None:
        assert is_code_block("`inline code`") is False


class TestIsTable:
    def test_markdown_table(self) -> None:
        # is_table checks all lines start with | and has separator row
        text = "| Col1 |\n| --- |\n| A |"
        assert is_table(text) is True

    def test_not_table(self) -> None:
        assert is_table("Regular paragraph.") is False


class TestMergeShortAdjacent:
    def test_no_merge_needed(self) -> None:
        # Chunks with token_count above target_min should NOT be merged
        c1 = Chunk(
            level="coarse", content="A" * 600, content_with_context="",
            content_hash="h1", chunk_index=0, chunk_total=2, token_count=300,
        )
        c2 = Chunk(
            level="coarse", content="B" * 600, content_with_context="",
            content_hash="h2", chunk_index=1, chunk_total=2, token_count=300,
        )
        result = merge_short_adjacent([c1, c2], target_min=200)
        assert len(result) == 2

    def test_merge_short_chunks(self) -> None:
        c1 = Chunk(
            level="coarse", content="Short.", content_with_context="",
            content_hash="h1", chunk_index=0, chunk_total=2, token_count=2,
        )
        c2 = Chunk(
            level="coarse", content="Also short.", content_with_context="",
            content_hash="h2", chunk_index=1, chunk_total=2, token_count=2,
        )
        result = merge_short_adjacent([c1, c2], target_min=200)
        assert len(result) == 1

    def test_empty_list(self) -> None:
        result = merge_short_adjacent([], target_min=200)
        assert result == []

    def test_single_chunk(self) -> None:
        c1 = Chunk(
            level="coarse", content="A", content_with_context="",
            content_hash="h1", chunk_index=0, chunk_total=1, token_count=1,
        )
        result = merge_short_adjacent([c1], target_min=200)
        assert len(result) == 1
