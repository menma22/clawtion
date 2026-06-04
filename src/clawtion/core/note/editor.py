"""Note content editing utilities for surgical section updates.

Provides :class:`NoteEditor` with methods to find and replace content
within sections identified by heading, and to append content at specific
positions in a note file.
"""

from __future__ import annotations

import os
import re
from typing import Any

from clawtion.utils.exceptions import ClawtionError
from clawtion.utils.logging import get_logger

logger = get_logger(__name__)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class NoteEditor:
    """Surgical note content editing via heading-based section targeting.

    Operates directly on Markdown files in the vault.  Designed to work
    alongside :class:`~clawtion.core.note.service.NoteService` — the
    editor handles file-level content manipulation, while the service
    manages metadata and indexing.

    Constructor DI:
        ``vault_path``: Absolute path to the vault root directory.
    """

    def __init__(self, vault_path: str) -> None:
        self._vault_path = vault_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_section(
        self,
        file_path: str,
        target_heading: str,
        new_content: str,
        match_context: str | None = None,
    ) -> dict[str, Any]:
        """Update the content under a specific heading in a note file.

        The method locates the target heading, replaces everything between
        it and the next heading of equal or higher level, and writes the
        result back to disk.  If *match_context* is provided and multiple
        headings match, the one whose surrounding context contains the
        context string is chosen.

        Args:
            file_path: Path relative to the vault root (e.g.
                ``"tech/rag/graphrag.md"``).
            target_heading: The heading text to find (without the ``#``
                prefix).  Matching is case-insensitive.
            new_content: The new Markdown content to place under the heading.
            match_context: Optional string that must appear in the section
                content to disambiguate multiple matching headings.

        Returns:
            A dict with:
                - ``"success"``: bool
                - ``"section_start_line"``: line number of the heading
                - ``"section_end_line"``: line number of the next heading
                - ``"characters_replaced"``: length of old content

        Raises:
            ClawtionError: If the file does not exist, the heading is not
                found, or context does not disambiguate.
        """
        abs_path = self._resolve_path(file_path)
        lines = self._read_lines(abs_path)
        heading_index = self._find_heading_position(lines, target_heading, match_context)

        if heading_index is None:
            candidates = self._find_all_heading_lines(lines, target_heading)
            msg = f"Heading '{target_heading}' not found in {file_path}."
            if candidates:
                candidate_texts = ", ".join(f"'{lines[c].strip()}'" for c in candidates[:5])
                msg += f" Did you mean: {candidate_texts}?"
            raise ClawtionError(
                code="HEADING_NOT_FOUND",
                message=msg,
                details={
                    "file_path": file_path,
                    "target_heading": target_heading,
                    "match_context": match_context,
                    "candidates": [lines[c].strip() for c in candidates[:10]],
                },
            )

        # Determine section boundaries
        heading_level = self._heading_level(lines[heading_index])
        section_start = heading_index + 1  # first line after heading

        section_end = len(lines)  # default: end of file
        for i in range(heading_index + 1, len(lines)):
            if self._is_heading(lines[i]) and self._heading_level(lines[i]) <= heading_level:
                section_end = i
                break

        # Capture old content (strip trailing empty lines)
        old_lines = lines[section_start:section_end]
        while old_lines and old_lines[-1].strip() == "":
            old_lines = old_lines[:-1]
        old_content = "".join(old_lines)

        # Preserve heading line and surround with blank lines for clean formatting
        heading_line = lines[heading_index]
        new_lines = [*lines[:heading_index], heading_line, "", new_content.strip(), "", *lines[section_end:]]

        self._write_lines(abs_path, new_lines)

        logger.info(
            "Section updated",
            file_path=file_path,
            heading=target_heading,
            chars_replaced=len(old_content),
        )
        return {
            "success": True,
            "section_head_line": heading_index,
            "section_end_line": section_end,
            "characters_replaced": len(old_content),
        }

    def append_content(
        self,
        file_path: str,
        content: str,
        position: str = "end",
        target_heading: str | None = None,
    ) -> dict[str, Any]:
        """Append content to a note file.

        Args:
            file_path: Path relative to the vault root.
            content: The Markdown content to append.
            position: Where to append.  One of:
                - ``"end"``: at the end of the file (default).
                - ``"after_heading"``: immediately after the target heading.
                - ``"before_heading"``: immediately before the target heading.
            target_heading: Required when *position* is not ``"end"``.
                The heading text to anchor the insertion.

        Returns:
            A dict with:
                - ``"success"``: bool
                - ``"insertion_line"``: line number where content was inserted
                - ``"appended_lines"``: number of lines added

        Raises:
            ClawtionError: If the file does not exist or parameters are
                invalid.
        """
        abs_path = self._resolve_path(file_path)
        lines = self._read_lines(abs_path)

        insertion_line: int
        if position == "end":
            insertion_line = len(lines)
        elif position in ("after_heading", "before_heading"):
            if target_heading is None:
                raise ClawtionError(
                    code="MISSING_TARGET_HEADING",
                    message="target_heading is required when position is not 'end'.",
                )
            heading_idx = self._find_heading_position(lines, target_heading)
            if heading_idx is None:
                raise ClawtionError(
                    code="HEADING_NOT_FOUND",
                    message=f"Heading '{target_heading}' not found in {file_path}.",
                )
            if position == "after_heading":
                # Insert after the section content (before next heading of same level)
                heading_level = self._heading_level(lines[heading_idx])
                insertion_line = heading_idx + 1
                for i in range(heading_idx + 1, len(lines)):
                    if self._is_heading(lines[i]) and self._heading_level(lines[i]) <= heading_level:
                        insertion_line = i
                        break
                else:
                    insertion_line = len(lines)
            else:
                insertion_line = heading_idx
        else:
            raise ClawtionError(
                code="INVALID_POSITION",
                message=f"Invalid position '{position}'. Use 'end', 'after_heading', or 'before_heading'.",
            )

        # Insert content at the computed position
        new_lines = [*lines[:insertion_line], content.strip(), "", *lines[insertion_line:]]

        self._write_lines(abs_path, new_lines)

        appended_lines = len(new_lines) - len(lines)
        logger.info(
            "Content appended",
            file_path=file_path,
            position=position,
            heading=target_heading,
            lines_added=appended_lines,
        )
        return {
            "success": True,
            "insertion_line": insertion_line,
            "appended_lines": appended_lines,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, file_path: str) -> str:
        """Resolve a relative vault path to an absolute filesystem path."""
        abs_path = os.path.join(self._vault_path, file_path)
        if not os.path.exists(abs_path):
            raise ClawtionError(
                code="FILE_NOT_FOUND",
                message=f"File not found: {file_path}",
                details={"resolved_path": abs_path},
            )
        return abs_path

    @staticmethod
    def _read_lines(abs_path: str) -> list[str]:
        """Read a file into a list of lines (preserving original line endings)."""
        with open(abs_path, encoding="utf-8") as f:
            return f.readlines()

    @staticmethod
    def _write_lines(abs_path: str, lines: list[str]) -> None:
        """Write a list of lines back to a file."""
        # Ensure file ends with exactly one newline
        text = "".join(lines)
        text = text.rstrip("\n") + "\n"
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(text)

    @staticmethod
    def _is_heading(line: str) -> bool:
        """Return True if the line is a Markdown heading."""
        stripped = line.strip()
        return stripped.startswith("#") and _HEADING_RE.match(stripped) is not None

    @staticmethod
    def _heading_level(line: str) -> int:
        """Return the heading level (1-6)."""
        stripped = line.strip()
        match = _HEADING_RE.match(stripped)
        if match:
            return len(match.group(1))
        return 0

    def _find_heading_position(
        self,
        lines: list[str],
        heading: str,
        match_context: str | None = None,
    ) -> int | None:
        """Find the line index of a heading.

        Matching is case-insensitive.  If *match_context* is provided and
        multiple headings match, the one whose section content contains
        the context string is chosen.

        Args:
            lines: List of file lines.
            heading: Heading text to search for (without ``#`` prefix).
            match_context: Optional disambiguation string.

        Returns:
            The 0-based line index, or ``None`` if not found.
        """
        heading_lower = heading.strip().lower()
        matching_indices: list[int] = []

        for i, line in enumerate(lines):
            match = _HEADING_RE.match(line.strip())
            if match:
                heading_text = match.group(2).strip().lower()
                if heading_text == heading_lower:
                    matching_indices.append(i)

        if not matching_indices:
            return None
        if len(matching_indices) == 1:
            return matching_indices[0]
        if match_context is not None:
            # Disambiguate by searching for context in the section below each heading
            context_lower = match_context.lower()
            for idx in matching_indices:
                heading_lvl = self._heading_level(lines[idx])
                section_text = ""
                for j in range(idx + 1, len(lines)):
                    if self._is_heading(lines[j]) and self._heading_level(lines[j]) <= heading_lvl:
                        break
                    section_text += lines[j]
                if context_lower in section_text.lower():
                    return idx
            # No disambiguation possible; return the first match
            return matching_indices[0]

        # Multiple matches, no context; return the first
        return matching_indices[0]

    def _find_all_heading_lines(
        self,
        lines: list[str],
        heading: str,
    ) -> list[int]:
        """Find all headings containing *heading* as a substring (case-insensitive).

        This is used to provide helpful suggestions when the exact heading
        is not found.

        Args:
            lines: List of file lines.
            heading: The (partial) heading text to search for.

        Returns:
            List of 0-based line indices of candidate headings.
        """
        heading_lower = heading.strip().lower()
        candidates: list[int] = []
        for i, line in enumerate(lines):
            match = _HEADING_RE.match(line.strip())
            if match:
                heading_text = match.group(2).strip().lower()
                if heading_lower in heading_text:
                    candidates.append(i)
        return candidates
