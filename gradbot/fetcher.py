"""
Test suite fetcher for GradBot.

Fetches problem suites from the public samples repo with a shallow git fetch.

Local clones are stored at ``$GRADBOT_LOCAL_DIR/{owner}/{repo}/`` and updated
on each run (unless ``--offline``). A network failure falls back to the copy
of the *same* ref downloaded earlier; a missing repo or ref never does.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from gradbot.git import GitError, checkout_cached, clone_or_update, has_cached
from gradbot.resolver import ResolvedSlug

logger = logging.getLogger("gradbot.fetcher")

# Substrings of git's stderr, lowercased.
_NETWORK_SIGNS = (
    "could not resolve host",
    "failed to connect",
    "connection refused",
    "connection timed out",
    "operation timed out",
    "network is unreachable",
    "timed out after",
    "ssl",
)
_MISSING_REF_SIGNS = ("couldn't find remote ref", "not our ref", "no such remote ref")
_MISSING_REPO_SIGNS = (
    "not found",
    "does not appear to be a git repository",
    "could not read username",
    "authentication failed",
    "403",
    "401",
)


class FetchError(Exception):
    """Raised when fetching a test suite fails irrecoverably."""
    pass


def fetch(resolved: ResolvedSlug, offline: bool = False) -> Path:
    """
    Fetch the problem suite for a resolved slug using git.

    Args:
        resolved: A fully resolved slug from ``resolver.resolve()``
        offline: If True, only use the copy of this ref downloaded earlier

    Returns:
        Path to the problem suite directory (the folder containing suite.yaml)

    Raises:
        FetchError: if the suite cannot be fetched or found
    """
    local_path = resolved.local_path

    try:
        clone_or_update(
            origin=resolved.git_origin,
            local_path=local_path,
            branch=resolved.ref,
            offline=offline,
        )
    except GitError as e:
        if offline:
            raise FetchError(
                "You're in offline mode, but GradBot doesn't have a downloaded copy "
                f"of '{resolved.raw_slug}'.\n"
                "Connect to the internet and try again without --offline."
            ) from e
        if _kind(e) == "network" and has_cached(local_path, resolved.ref):
            print(
                "⚠️  Couldn't reach the problem repo. Using the copy downloaded earlier "
                "(it might be out of date).",
                file=sys.stderr,
            )
            logger.debug("fetch failed: %s %s", e, e.stderr)
            checkout_cached(local_path, resolved.ref)
        else:
            _raise_fetch_error(e, resolved)

    problem_dir = local_path / resolved.topic / resolved.problem
    if not problem_dir.is_dir():
        raise FetchError(
            f"Couldn't find the problem '{resolved.problem_path}' in {resolved.repo} "
            f"(ref {resolved.ref}).\n"
            "Double-check the slug, and check GRADBOT_PUBLIC_REPO points at your course's samples repo."
        )

    return problem_dir


def fetch_local(suite_dir: Path) -> Path:
    """
    'Fetch' a local problem suite (for dev mode).

    Simply validates that the directory exists and contains the expected files.

    Raises:
        FetchError: if the directory doesn't look like a valid suite
    """
    suite_dir = Path(suite_dir).resolve()

    if not suite_dir.is_dir():
        raise FetchError(f"Directory not found: {suite_dir}")

    if not (suite_dir / "suite.yaml").exists():
        raise FetchError(
            f"Missing suite.yaml in {suite_dir}\n"
            "Every problem suite needs a suite.yaml file."
        )

    if not (suite_dir / "checks.py").exists():
        raise FetchError(
            f"Missing checks.py in {suite_dir}\n"
            "Every problem suite needs a checks.py file with test checks."
        )

    return suite_dir


def _kind(error: GitError) -> str:
    text = f"{error} {error.stderr}".lower()
    if any(sign in text for sign in _MISSING_REF_SIGNS):
        return "missing-ref"
    if any(sign in text for sign in _NETWORK_SIGNS) or "timed out" in str(error).lower():
        return "network"
    if any(sign in text for sign in _MISSING_REPO_SIGNS):
        return "missing-repo"
    return "other"


def _raise_fetch_error(git_error: GitError, resolved: ResolvedSlug) -> None:
    """Convert a GitError to a user-friendly FetchError."""
    kind = _kind(git_error)
    logger.debug("git failed (%s): %s\n%s", kind, git_error, git_error.stderr)

    if kind == "network":
        raise FetchError(
            "Couldn't connect to download the problem.\n\n"
            "Things to try:\n"
            "  • Check your internet connection\n"
            "  • If you've run this problem before, add --offline\n"
            "  • Ask your teacher for help if the problem persists"
        ) from git_error
    if kind == "missing-ref":
        raise FetchError(
            f"Couldn't find '{resolved.ref}' in {resolved.repo}.\n"
            "Use a branch name, a tag, or a full 40-character commit hash after @."
        ) from git_error
    if kind == "missing-repo":
        raise FetchError(
            f"Couldn't find the problem repo {resolved.repo}.\n"
            "Check GRADBOT_PUBLIC_REPO: it should be the public samples repo your teacher gave you.\n"
            "Practice repos are public, so no login is needed."
        ) from git_error
    raise FetchError(
        f"Something went wrong downloading the problem.\n"
        f"Error: {git_error}\n{git_error.stderr}".rstrip()
    ) from git_error
