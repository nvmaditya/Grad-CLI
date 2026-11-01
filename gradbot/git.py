"""
Git CLI wrapper for GradBot.

A thin wrapper around git commands via subprocess. GradBot uses git directly
(shallow clones, fetch, checkout) instead of downloading tarballs.

``clone_or_update()`` does:
    git init → git remote add origin → git fetch --depth 1 → git checkout → git reset --hard
"""

from __future__ import annotations

import logging
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
            timeout=timeout,
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


def clone_or_update(
    origin: str,
    local_path: Path,
    branch: str = "main",
    offline: bool = False,
) -> Path:
    """
    Create or update a local shallow clone of a git repo.

    Steps:
    1. If ``local_path`` doesn't exist: ``git init`` + ``git remote add origin``
    2. If not offline: ``git fetch origin --depth 1 <branch>``
    3. ``git checkout -f -B <branch> origin/<branch>``
    4. ``git reset --hard HEAD``

    Args:
        origin: the git remote URL (HTTPS with optional token)
        local_path: where to store the local clone
        branch: the git branch/ref to fetch
        offline: if True, skip fetch and use whatever is already local

    Returns:
        The local_path

    Raises:
        GitError: if any git operation fails
    """
    local_path = Path(local_path)

    # Step 1: Initialize repo if it doesn't exist
    if not local_path.exists():
        if offline:
            raise GitError(
                "You're in offline mode, but GradBot hasn't downloaded "
                "this problem suite before.\n"
                "Connect to the internet and try again without --offline."
            )
        local_path.mkdir(parents=True, exist_ok=True)
        run_git("init", str(local_path))
        run_git("remote", "add", "origin", origin, cwd=local_path)

    # Step 2: Fetch latest (unless offline)
    if not offline:
        # Update origin URL in case the token changed
        try:
            run_git("remote", "set-url", "origin", origin, cwd=local_path)
        except GitError:
            # If remote doesn't exist yet (shouldn't happen, but be safe)
            run_git("remote", "add", "origin", origin, cwd=local_path)

        run_git(
            "fetch", "origin", "--depth", "1", branch,
            cwd=local_path,
            timeout=60,
        )

    # Step 3: Checkout the branch
    # Tolerate checkout failure (e.g., when branch doesn't exist locally in offline mode)
    try:
        run_git(
            "checkout", "-f", "-B", branch, f"origin/{branch}",
            cwd=local_path,
        )
    except GitError as e:
        if offline:
            # In offline mode, try to just use whatever HEAD we have
            logger.warning("Checkout failed in offline mode: %s", e)
        else:
            raise

    # Step 4: Ensure local copy matches remote exactly
    run_git("reset", "--hard", "HEAD", cwd=local_path)

    return local_path
