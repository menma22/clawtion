"""Git repository loader for clawtion indexer.

Clones remote Git repositories (shallow, depth=1) and indexes their
contents through the existing :class:`IndexingService` pipeline.
"""

from __future__ import annotations

import os
import re
import shutil
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from clawtion.utils.exceptions import ClawtionError
from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from .service import IndexingService

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default file patterns to index from cloned repositories
_DEFAULT_FILE_PATTERNS: list[str] = [
    "*.md",
    "*.txt",
    "*.rst",
    "*.py",
    "*.ts",
    "*.js",
    "*.json",
    "*.yaml",
    "*.yml",
    "*.toml",
    "*.html",
    "*.htm",
    "*.csv",
    "*.xml",
    "*.java",
    "*.go",
    "*.rs",
    "*.c",
    "*.cpp",
    "*.h",
    "*.sh",
    "*.sql",
    "*.r",
    "*.org",
    "*.adoc",
]

# Known Git hosting domains that accept shallow clones over HTTPS
_GIT_DOMAINS: set[str] = {
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "gitee.com",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitise_repo_name(repo_url: str) -> str:
    """Derive a safe directory name from a Git URL.

    Examples::

        https://github.com/user/my-repo.git  →  "github.com_user_my-repo"
        git@github.com:user/my-repo.git       →  "github.com_user_my-repo"
    """
    # Normalise SSH-style URLs to HTTPS-style for parsing
    url = repo_url
    if url.startswith("git@") or url.startswith("ssh://"):
        m = re.match(r"(?:git@|ssh://git@)([^:/]+)[:/](.+)", url)
        if m:
            url = f"https://{m.group(1)}/{m.group(2)}"

    parsed = urlparse(url)
    host = parsed.netloc or "unknown"
    path = parsed.path.strip("/")

    # Remove trailing .git
    if path.lower().endswith(".git"):
        path = path[:-4]

    # Replace non-alphanumeric characters with underscores
    safe_host = re.sub(r"[^a-zA-Z0-9]", "_", host)
    safe_path = re.sub(r"[^a-zA-Z0-9]", "_", path)

    # Limit total length to avoid filesystem issues
    name = f"{safe_host}_{safe_path}"
    if len(name) > 120:
        name = name[:120].rstrip("_")

    return name


def _is_git_url(repo_url: str) -> bool:
    """Check whether *repo_url* looks like a Git remote URL."""
    if repo_url.startswith(("https://", "http://", "git@", "ssh://")):
        return True
    if repo_url.endswith(".git"):
        return True
    parsed = urlparse(repo_url)
    return parsed.netloc in _GIT_DOMAINS


def _match_pattern(file_path: str, patterns: list[str]) -> bool:
    """Check if *file_path* matches any glob in *patterns*."""
    from fnmatch import fnmatch

    name = os.path.basename(file_path)
    return any(fnmatch(name, pattern) for pattern in patterns)


# ---------------------------------------------------------------------------
# GitLoader
# ---------------------------------------------------------------------------


class GitLoader:
    """Clone Git repositories and index their contents.

    Uses ``git`` CLI under the hood for maximum compatibility.

    Args:
        vault_path:   Absolute path to the clawtion vault root.
        indexing_service:  The :class:`IndexingService` instance to use for
                          file indexing.

    Usage::

        loader = GitLoader(vault_path, indexing_service)
        result = await loader.clone_and_index("https://github.com/user/repo.git")
    """

    def __init__(
        self,
        vault_path: str,
        indexing_service: IndexingService,
    ) -> None:
        self._vault_path = vault_path
        self._indexing_service = indexing_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def clone_and_index(
        self,
        repo_url: str,
        branch: str = "main",
        target_path: str | None = None,
        file_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Clone a repository (shallow, depth 1) and index matching files.

        Args:
            repo_url:      Git remote URL (HTTPS or SSH).
            branch:        Branch to clone (default ``"main"``).
            target_path:   Subdirectory inside ``vault_path/git/`` for the
                           clone.  Auto-derived from the URL when ``None``.
            file_patterns: Glob patterns for files to index.  Defaults to
                           :const:`_DEFAULT_FILE_PATTERNS`.

        Returns:
            A dictionary with the result summary::

                {
                    "repo_name": str,
                    "local_path": str,
                    "indexed": int,
                    "skipped": int,
                    "failed": int,
                    "errors": list[str],
                }

        Raises:
            ClawtionError: If the repository URL is invalid or the clone
                           fails.
        """
        if not _is_git_url(repo_url):
            raise ClawtionError(
                code="INVALID_GIT_URL",
                message=f"Invalid Git repository URL: {repo_url}",
            )

        patterns = file_patterns or _DEFAULT_FILE_PATTERNS
        repo_name = _sanitise_repo_name(repo_url)

        # Resolve local path
        git_root = os.path.join(self._vault_path, "git")
        local_path = os.path.join(
            git_root,
            target_path or repo_name,
        )

        if os.path.isdir(local_path):
            logger.info(
                "Repository already cloned, pulling latest",
                repo=repo_url,
                path=local_path,
            )
            return await self.update_indexed_repo(local_path, file_patterns=patterns)

        # Shallow clone
        os.makedirs(git_root, exist_ok=True)
        logger.info(
            "Cloning repository",
            repo=repo_url,
            branch=branch,
            target=local_path,
        )

        try:
            await self._run_git_clone(repo_url, branch, local_path)
        except Exception as e:
            # Clean up partial clone
            if os.path.isdir(local_path):
                shutil.rmtree(local_path, ignore_errors=True)
            raise ClawtionError(
                code="GIT_CLONE_FAILED",
                message=f"Failed to clone repository {repo_url}: {e}",
            ) from e

        # Index matching files
        return await self._index_repo_files(local_path, repo_url, repo_name, patterns)

    async def update_indexed_repo(
        self,
        repo_path: str,
        branch: str | None = None,
        file_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Pull the latest changes and re-index modified files.

        Args:
            repo_path:     Local path to the already-cloned repository.
            branch:        Branch to pull.  Detects the current branch when
                           ``None``.
            file_patterns: Glob patterns for files to index.  Defaults to
                           :const:`_DEFAULT_FILE_PATTERNS`.

        Returns:
            Same structure as :meth:`clone_and_index`.
        """
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            raise ClawtionError(
                code="NOT_GIT_REPOSITORY",
                message=f"Not a Git repository: {repo_path}",
            )

        resolved_branch = branch or await self._get_current_branch(repo_path)
        patterns = file_patterns or _DEFAULT_FILE_PATTERNS

        logger.info(
            "Pulling latest changes",
            path=repo_path,
            branch=resolved_branch,
        )

        try:
            await self._run_git_pull(repo_path, resolved_branch)
        except Exception as e:
            raise ClawtionError(
                code="GIT_PULL_FAILED",
                message=f"Failed to pull repository at {repo_path}: {e}",
            ) from e

        repo_name = os.path.basename(repo_path)
        return await self._index_repo_files(
            repo_path,
            repo_url="",
            repo_name=repo_name,
            patterns=patterns,
        )

    def get_indexed_repos(self) -> list[dict[str, Any]]:
        """List all Git repositories currently cloned under the vault.

        Returns:
            A list of dictionaries, each with::

                {
                    "name": str,
                    "path": str,
                    "remote": str | None,
                    "branch": str | None,
                }
        """
        git_root = os.path.join(self._vault_path, "git")
        if not os.path.isdir(git_root):
            return []

        repos: list[dict[str, Any]] = []
        for entry in os.listdir(git_root):
            repo_dir = os.path.join(git_root, entry)
            git_dir = os.path.join(repo_dir, ".git")
            if not os.path.isdir(git_dir):
                continue

            remote = self._get_remote_url(repo_dir)
            branch = self._get_current_branch_sync(repo_dir)

            repos.append({
                "name": entry,
                "path": repo_dir,
                "remote": remote,
                "branch": branch,
            })

        return repos

    async def remove_repo(self, repo_name_or_path: str) -> None:
        """Remove a cloned repository and its indexed documents.

        Args:
            repo_name_or_path: Short name or full path of the repo.
        """
        git_root = os.path.join(self._vault_path, "git")

        # Resolve the path if a short name is given
        repo_path = repo_name_or_path
        if not os.path.isdir(repo_path):
            candidate = os.path.join(git_root, repo_name_or_path)
            if os.path.isdir(candidate):
                repo_path = candidate

        if not os.path.isdir(repo_path) or not os.path.isdir(
            os.path.join(repo_path, ".git")
        ):
            raise ClawtionError(
                code="REPO_NOT_FOUND",
                message=f"Repository not found: {repo_name_or_path}",
            )

        # Collect files to remove
        file_paths: list[str] = []
        for root, _dirs, files in os.walk(repo_path):
            for file_name in files:
                file_abs = os.path.join(root, file_name)
                file_paths.append(file_abs)

        # Delete each file from the index (fire-and-forget with gather)
        import asyncio

        tasks = [
            self._indexing_service.delete_file(fp) for fp in file_paths
        ]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    logger.warning(
                        "Failed to remove file from index",
                        file=file_paths[i],
                        error=str(r),
                    )

        # Remove the directory
        shutil.rmtree(repo_path, ignore_errors=True)
        logger.info("Removed repository from vault", path=repo_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_git_clone(
        self,
        repo_url: str,
        branch: str,
        target_path: str,
    ) -> None:
        """Execute ``git clone --depth 1 --branch <branch> <url> <target>``."""
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            branch,
            repo_url,
            target_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            logger.error(
                "Git clone failed",
                repo=repo_url,
                branch=branch,
                error=error_msg,
            )
            raise ClawtionError(
                code="GIT_CLONE_FAILED",
                message=error_msg or f"git clone exited with code {proc.returncode}",
            )

        logger.info(
            "Repository cloned successfully",
            repo=repo_url,
            path=target_path,
        )

    async def _run_git_pull(self, repo_path: str, branch: str) -> None:
        """Execute ``git pull origin <branch>`` inside *repo_path*."""
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            repo_path,
            "pull",
            "origin",
            branch,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            logger.error(
                "Git pull failed",
                path=repo_path,
                branch=branch,
                error=error_msg,
            )
            raise ClawtionError(
                code="GIT_PULL_FAILED",
                message=error_msg or f"git pull exited with code {proc.returncode}",
            )

        logger.info("Repository updated successfully", path=repo_path)

    async def _index_repo_files(
        self,
        repo_path: str,
        repo_url: str,
        repo_name: str,
        patterns: list[str],
    ) -> dict[str, Any]:
        """Walk *repo_path* and index every file matching *patterns*."""
        stats: dict[str, Any] = {
            "repo_name": repo_name,
            "repo_url": repo_url,
            "local_path": repo_path,
            "indexed": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

        # Collect matching files
        matching_files: list[str] = []
        git_dir = os.path.join(repo_path, ".git")
        for root, dirs, files in os.walk(repo_path):
            # Skip .git directory
            dirs[:] = [d for d in dirs if os.path.join(root, d) != git_dir]
            for file_name in sorted(files):
                file_abs = os.path.join(root, file_name)
                if _match_pattern(file_abs, patterns):
                    matching_files.append(file_abs)

        # Index each file sequentially (conservative resource usage)
        for file_abs in matching_files:
            try:
                chunk_ids = await self._indexing_service.index_file(file_abs)
                if chunk_ids:
                    stats["indexed"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{os.path.basename(file_abs)}: {e}")
                logger.error(
                    "Failed to index file from Git repo",
                    file=file_abs,
                    error=str(e),
                )

        logger.info(
            "Git repo indexing completed",
            repo=repo_name,
            indexed=stats["indexed"],
            skipped=stats["skipped"],
            failed=stats["failed"],
        )

        return stats

    def _get_remote_url(self, repo_path: str) -> str | None:
        """Get the remote origin URL of a local Git repo."""
        git_dir = os.path.join(repo_path, ".git")
        config_path = os.path.join(git_dir, "config")
        if not os.path.isfile(config_path):
            return None

        try:
            with open(config_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("url = "):
                        return line[6:]
        except Exception:
            pass

        return None

    async def _get_current_branch(self, repo_path: str) -> str:
        """Get the currently checked-out branch name."""
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            repo_path,
            "rev-parse",
            "--abbrev-ref",
            "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await proc.communicate()
        return stdout.decode("utf-8", errors="replace").strip() or "main"

    def _get_current_branch_sync(self, repo_path: str) -> str | None:
        """Synchronous version of :meth:`_get_current_branch`."""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            branch = result.stdout.strip()
            return branch if branch else None
        except Exception:
            return None
