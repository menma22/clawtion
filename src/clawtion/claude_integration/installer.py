"""Claude Code integration installer for clawtion.

Handles the installation, uninstallation, and status-checking of Claude Code
integration files that allow the clawtion knowledge base to be accessed from
within Claude Code through sub-agents, skills, and MCP server configuration.

Files managed by this installer:

- ``~/.claude/agents/clawtion-knowledge.md``  — sub-agent definition
- ``~/.claude/skills/clawtion-search/SKILL.md`` — skill definition
- ``~/.claude.json``  — MCP server configuration (``mcpServers.clawtion``)
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import structlog

from clawtion.config.loader import get_config

logger = structlog.get_logger("clawtion.claude_integration")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENTS_DIR = Path.home() / ".claude" / "agents"
SKILLS_DIR = Path.home() / ".claude" / "skills" / "clawtion-search"
CLAUDE_JSON = Path.home() / ".claude.json"

SUBAGENT_FILENAME = "clawtion-knowledge.md"
SKILL_FILENAME = "SKILL.md"

# Template file paths within the clawtion package
_PKG_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _PKG_DIR / "templates"

SUBAGENT_SOURCE = _TEMPLATES_DIR / "subagent.md"
SKILL_SOURCE = _TEMPLATES_DIR / "skill.md"


# ---------------------------------------------------------------------------
# Installer class
# ---------------------------------------------------------------------------


class ClaudeIntegrationInstaller:
    """Install / uninstall / inspect Claude Code integration files.

    Args:
        vault_path: Absolute path to the clawtion vault directory.
        config:     Application configuration dictionary (from ``get_config()``).
    """

    def __init__(self, vault_path: str, config: dict[str, Any]) -> None:
        self._vault_path = vault_path
        self._config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self) -> dict[str, Any]:
        """Install all Claude Code integration files.

        Creates:
        - ``~/.claude/agents/clawtion-knowledge.md``
        - ``~/.claude/skills/clawtion-search/SKILL.md``
        - Adds ``clawtion`` entry to ``~/.claude.json`` MCP config

        Returns:
            A dict summarising what was installed / updated.
        """
        results: dict[str, Any] = {
            "subagent": None,
            "skill": None,
            "mcp_config": None,
        }

        results["subagent"] = self._write_subagent_definition()
        results["skill"] = self._write_skill_definition()
        results["mcp_config"] = self._update_claude_config()

        logger.info("claude_integration_installed", results=results)
        return results

    def uninstall(self) -> dict[str, Any]:
        """Remove all Claude Code integration files.

        Does **not** modify ``~/.claude.json`` outside of the ``clawtion``
        MCP server section — other MCP servers are preserved.

        Returns:
            A dict summarising what was removed.
        """
        results: dict[str, Any] = {
            "subagent": None,
            "skill": None,
            "mcp_config": None,
        }

        results["subagent"] = self._remove_file(AGENTS_DIR / SUBAGENT_FILENAME)
        results["skill"] = self._remove_file(SKILLS_DIR / SKILL_FILENAME)
        results["mcp_config"] = self._remove_from_claude_config()

        # Remove the skill directory if it is now empty
        skill_dir = SKILLS_DIR
        if skill_dir.exists() and not any(skill_dir.iterdir()):
            skill_dir.rmdir()
            logger.info("removed_empty_skill_dir", path=str(skill_dir))

        logger.info("claude_integration_uninstalled", results=results)
        return results

    def is_installed(self) -> dict[str, Any]:
        """Check which integration files are present on disk.

        Returns:
            A dict with boolean statuses and file paths for each component.
        """
        subagent_path = AGENTS_DIR / SUBAGENT_FILENAME
        skill_path = SKILLS_DIR / SKILL_FILENAME
        config_ok = self._check_claude_config()

        return {
            "subagent": {
                "installed": subagent_path.exists(),
                "path": str(subagent_path),
            },
            "skill": {
                "installed": skill_path.exists(),
                "path": str(skill_path),
            },
            "mcp_config": {
                "installed": config_ok,
                "path": str(CLAUDE_JSON),
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _backup_existing(self, path: Path) -> None:
        """Rename an existing file to ``<name>.backup.<timestamp>``."""
        if not path.exists():
            return
        import time

        ts = int(time.time())
        backup = path.with_name(f"{path.name}.backup.{ts}")
        shutil.copy2(path, backup)
        logger.info("backed_up_existing", original=str(path), backup=str(backup))

    def _remove_file(self, path: Path) -> dict[str, Any]:
        """Delete a single file, returning a status dict."""
        if path.exists():
            path.unlink()
            logger.info("removed_file", path=str(path))
            return {"removed": True, "path": str(path)}
        return {"removed": False, "path": str(path), "reason": "not_found"}

    # ------------------------------------------------------------------
    # Sub-agent
    # ------------------------------------------------------------------

    def _write_subagent_definition(self) -> dict[str, Any]:
        """Copy the sub-agent template to ``~/.claude/agents/``.

        Returns:
            Status dict with path and whether a backup was created.
        """
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        dest = AGENTS_DIR / SUBAGENT_FILENAME

        if dest.exists():
            self._backup_existing(dest)

        if SUBAGENT_SOURCE.exists():
            shutil.copy2(str(SUBAGENT_SOURCE), str(dest))
        else:
            # Fallback: write built-in content (should not normally happen)
            content = self._builtin_subagent_content()
            dest.write_text(content, encoding="utf-8")

        logger.info("wrote_subagent", path=str(dest))
        return {"path": str(dest), "backup_created": False}

    # ------------------------------------------------------------------
    # Skill
    # ------------------------------------------------------------------

    def _write_skill_definition(self) -> dict[str, Any]:
        """Copy the skill template to ``~/.claude/skills/clawtion-search/``.

        Returns:
            Status dict with path and whether a backup was created.
        """
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        dest = SKILLS_DIR / SKILL_FILENAME

        if dest.exists():
            self._backup_existing(dest)

        if SKILL_SOURCE.exists():
            shutil.copy2(str(SKILL_SOURCE), str(dest))
        else:
            content = self._builtin_skill_content()
            dest.write_text(content, encoding="utf-8")

        logger.info("wrote_skill", path=str(dest))
        return {"path": str(dest), "backup_created": False}

    # ------------------------------------------------------------------
    # MCP config (~/.claude.json)
    # ------------------------------------------------------------------

    def _resolve_db_url(self) -> str:
        """Return the database URL from config or environment."""
        url = self._config.get("database", {}).get("url")
        if url:
            return url
        # Fallback to env or default
        return os.environ.get(
            "CLAWTION_DB_URL",
            "postgresql://localhost:5432/clawtion",
        )

    def _resolve_vault_path(self) -> str:
        """Return the vault path from config or environment."""
        return os.environ.get("CLAWTION_VAULT") or self._vault_path

    def _read_claude_json(self) -> dict[str, Any]:
        """Read and parse ``~/.claude.json``, returning an empty dict on error."""
        if not CLAUDE_JSON.exists():
            return {}
        try:
            raw = CLAUDE_JSON.read_text(encoding="utf-8")
            return dict(json.loads(raw))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("failed_to_read_claude_json", error=str(exc))
            return {}

    def _write_claude_json(self, data: dict[str, Any]) -> None:
        """Atomically write the claude.json config file."""
        tmp = CLAUDE_JSON.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(CLAUDE_JSON)

    def _update_claude_config(self) -> dict[str, Any]:
        """Add / update the ``clawtion`` section in ``mcpServers``.

        Merges with any existing MCP server entries — other servers are
        preserved untouched.

        Returns:
            Status dict indicating whether the config was created or updated.
        """
        config = self._read_claude_json()
        mcp_servers = config.setdefault("mcpServers", {})

        clawtion_entry = {
            "command": "clawtion",
            "args": ["mcp-serve"],
            "env": {
                "CLAWTION_VAULT": self._resolve_vault_path(),
                "CLAWTION_DB_URL": self._resolve_db_url(),
            },
        }

        was_present = "clawtion" in mcp_servers
        mcp_servers["clawtion"] = clawtion_entry
        self._write_claude_json(config)

        action = "updated" if was_present else "created"
        logger.info("mcp_config_updated", action=action)
        return {
            "action": action,
            "path": str(CLAUDE_JSON),
        }

    def _remove_from_claude_config(self) -> dict[str, Any]:
        """Remove the ``clawtion`` entry from ``mcpServers``.

        Other MCP servers and config keys are preserved.

        Returns:
            Status dict.
        """
        config = self._read_claude_json()
        mcp_servers = config.get("mcpServers", {})

        if "clawtion" not in mcp_servers:
            return {"removed": False, "reason": "not_found"}

        del mcp_servers["clawtion"]

        # Clean up empty mcpServers dict
        if not mcp_servers:
            config.pop("mcpServers", None)

        self._write_claude_json(config)
        logger.info("mcp_config_removed")
        return {"removed": True, "path": str(CLAUDE_JSON)}

    def _check_claude_config(self) -> bool:
        """Return ``True`` if the clawtion MCP entry exists in ``~/.claude.json``."""
        config = self._read_claude_json()
        mcp_servers = config.get("mcpServers", {})
        return "clawtion" in mcp_servers

    # ------------------------------------------------------------------
    # Built-in content fallbacks  (used when template files are missing)
    # ------------------------------------------------------------------

    @staticmethod
    def _builtin_subagent_content() -> str:
        """Return the sub-agent definition as a string."""
        return """\
---
name: clawtion-knowledge
description: |
  User's personal knowledge base search agent.
  Use when the user asks about their own notes, documents, past records,
  or anything stored in their clawtion vault.
  Examples: "what did I write about RAG?", "find my notes on X",
  "what do I know about Y?"
tools:
  - mcp__clawtion__semantic_search
  - mcp__clawtion__keyword_search
  - mcp__clawtion__hybrid_search
  - mcp__clawtion__metadata_filter
  - mcp__clawtion__get_file_chunks
  - mcp__clawtion__get_neighbor_chunks
  - mcp__clawtion__list_folders
  - mcp__clawtion__list_notes
  - mcp__clawtion__get_note
model: sonnet
memory: project
---

You are clawtion-knowledge, a specialized agent for searching the user's
personal knowledge base stored in their clawtion vault.

# Your Role

The main agent has delegated a knowledge retrieval task to you. Your job:
1. Understand what the user is looking for
2. Choose appropriate search strategy
3. Execute search using clawtion MCP tools
4. Return a clean, organized summary to the main agent

# Decision Framework

## Choose search method based on query type

- **Specific terms, names, exact phrases** → keyword_search first
- **Conceptual, abstract questions** → semantic_search
- **Mixed queries (most common)** → hybrid_search
- **Filtered by folder/tag/date** → metadata_filter + above

## Multi-step strategy

If first search returns few results or low scores:
1. Try alternative search method
2. Broaden query terms
3. Use list_folders to understand vault structure
4. Re-search with refined terms

## Result Synthesis

DO return to main agent:
- A concise summary of what was found
- Direct quotes only when essential
- File paths and chunk references for citation
- Structured info: "Found N notes across M files. Key themes: [...]"

DO NOT return to main agent:
- Raw search result JSON
- Diagnostic metadata (scores, embedding model info, execution time)
- Failed search attempts
- Full chunk contents unless the user explicitly needs them

# Output Format

## Summary
[2-3 sentence overview of findings]

## Key Findings
- [Finding 1] (source: `folder/file.md`)
- [Finding 2] (source: `folder/file.md`)

## Relevant Files
1. `path/to/file.md` - [brief description]
2. `path/to/file2.md` - [brief description]

## Suggested Next Steps
[If appropriate: "User might want to read X for full context"]
"""

    @staticmethod
    def _builtin_skill_content() -> str:
        """Return the skill definition as a string."""
        return """\
---
name: clawtion-search
description: |
  User has a personal knowledge base in clawtion.
  When the user asks about their own notes, past writings, personal documents,
  or "what do I know about X", "what did I write about Y", "find my note on Z" -
  delegate to the clawtion-knowledge subagent rather than answering from
  general knowledge.
---

# clawtion Knowledge Search

The user has a personal knowledge base managed by clawtion (stored locally
with vector + keyword search capabilities).

## When to invoke clawtion-knowledge subagent

Trigger: any question that references the user's personal knowledge or notes:
- "what did I write about..."
- "find my notes on..."
- "what do I know about..."
- "search my notes for..."
- Reference to past discussions, learnings, or saved information
- Any time the user asks about their own thinking, decisions, or records

## How to invoke

Use the Task tool with subagent_type='clawtion-knowledge'. The subagent will:
1. Search the vault with appropriate strategy
2. Return organized results to you
3. Keep raw search noise out of your context

## What NOT to do

- Do NOT call clawtion MCP tools directly. Always delegate to the subagent.
- Do NOT try to answer from general knowledge if the question is about user's
  personal notes.
- Do NOT bypass the subagent even for "simple" lookups - the context isolation
  matters.
"""
