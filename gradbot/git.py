"""
Git CLI wrapper for GradBot.

A thin wrapper around git commands via subprocess. GradBot uses git directly
(shallow clones, fetch, checkout) instead of downloading tarballs.

``clone_or_update()`` does:
    git init → git remote add origin → git fetch --depth 1 <ref>
    → git update-ref refs/gradbot-cache/<ref> FETCH_HEAD → git checkout --detach

Each requested ref (branch, tag or full commit hash) gets its own cache ref,
so ``--offline`` and a network failure can only ever reuse the same ref.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("gradbot.git")


class GitError(Exception):
    """Raised when a git command fails."""

    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message)
        self.stderr = stderr


def run_git(
    *args: str,
    cwd: str | Path | None = None,
    timeout: int = 60,
) -> str:
    """
    Run a git command and return its stdout.

    Args:
        *args: git subcommand and arguments (e.g. "init", "/path/to/repo")
        cwd: working directory for the command
        timeout: maximum seconds to wait

    Returns:
        The stdout output from git (stripped)

    Raises:
        GitError: if the command fails or times out
    """
    cmd = ["git", *args]
    logger.debug("Running: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=_git_env(),
        )
    except FileNotFoundError:
        raise GitError(
            "Git is not installed or not in PATH.\n"
            "Ask your teacher to install Git on this computer."
        ) from None
    except subprocess.TimeoutExpired:
        raise GitError(
            f"Git command timed out after {timeout} seconds.\n"
            "Check your internet connection and try again."
        ) from None

    if result.returncode != 0:
        stderr = result.stderr.strip()
        logger.debug("Git stderr: %s", stderr)
        raise GitError(
            f"Git command failed: {' '.join(cmd)}",
            stderr=stderr,
        )

    output = result.stdout.strip()
    if output:
        logger.debug("Git stdout: %s", output[:200])
    return output


def ensure_git_installed() -> None:
    """
    Check that git is available on the system.

    Raises:
        GitError: with a friendly message if git is not installed
    """
    try:
        run_git("--version", timeout=5)
    except GitError:
        raise GitError(
            "GradBot needs Git to download test suites, but Git isn't installed.\n"
            "Ask your teacher to install Git:\n"
            "  • Windows: https://git-scm.com/download/win\n"
            "  • macOS:   brew install git\n"
            "  • Linux:   sudo apt install git"
        ) from None


CACHE_REF_PREFIX = "refs/gradbot-cache/"


def _git_env() -> dict[str, str]:
    """Never let git stop and wait for a username or password on the terminal."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    return env


def _cache_ref(ref: str) -> str:
    # "/" is escaped so "feature" and "feature/x" can both be cached.
    return CACHE_REF_PREFIX + ref.replace("%", "%25").replace("/", "%2F")


def has_cached(local_path: Path, ref: str) -> bool:
    """True if ``ref`` was fetched into ``local_path`` before."""
    if not (Path(local_path) / ".git").is_dir():
        return False
    try:
        run_git("rev-parse", "--verify", "--quiet", f"{_cache_ref(ref)}^{{commit}}", cwd=local_path)
    except GitError:
        return False
    return True


def checkout_cached(local_path: Path, ref: str) -> Path:
    """Check out the copy of ``ref`` fetched earlier.

    Raises:
        GitError: if ``ref`` was never fetched into ``local_path``
    """
    if not has_cached(local_path, ref):
        raise GitError(f"No downloaded copy of '{ref}' in {local_path}")
    run_git("checkout", "-q", "-f", "--detach", f"{_cache_ref(ref)}^{{commit}}", cwd=local_path)
    run_git("clean", "-q", "-fdx", cwd=local_path)
    return Path(local_path)


def clone_or_update(
    origin: str,
    local_path: Path,
    branch: str = "main",
    offline: bool = False,
) -> Path:
    """
    Create or update a local shallow clone of a git repo at one ref.

    Args:
        origin: the git remote URL or path
        local_path: where to store the local clone
        branch: the branch, tag, or full commit hash to fetch
        offline: if True, skip fetch and use the copy of that ref fetched earlier

    Returns:
        The local_path

    Raises:
        GitError: if any git operation fails. A failed first fetch removes the
            folder it created, so it is never mistaken for a cache later.
    """
    local_path = Path(local_path)
    ref = branch

    if offline:
        if not has_cached(local_path, ref):
            raise GitError(
                "You're in offline mode, but GradBot hasn't downloaded "
                f"'{ref}' of this problem repo before.\n"
                "Connect to the internet and try again without --offline."
            )
        return checkout_cached(local_path, ref)

    created = not (local_path / ".git").is_dir()
    try:
        if created:
            local_path.mkdir(parents=True, exist_ok=True)
            run_git("init", "-q", str(local_path))
            run_git("remote", "add", "origin", origin, cwd=local_path)
        else:
            run_git("remote", "set-url", "origin", origin, cwd=local_path)

        run_git("fetch", "-q", "--depth", "1", "origin", ref, cwd=local_path, timeout=120)
        run_git("update-ref", _cache_ref(ref), "FETCH_HEAD", cwd=local_path)
    except GitError:
        if created:
            shutil.rmtree(local_path, ignore_errors=True)
        raise

    return checkout_cached(local_path, ref)
