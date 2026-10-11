"""
Test suite fetcher for GradBot.

Fetches problem suites from GitHub using git shallow clones.

Local clones are stored at ``~/.gradbot/local/{owner}/{repo}/`` and updated
via ``git fetch`` on each run (unless ``--offline``).
"""

from __future__ import annotations

import sys
from pathlib import Path

from gradbot.git import GitError, clone_or_update
from gradbot.resolver import ResolvedSlug


class FetchError(Exception):
    """Raised when fetching a test suite fails irrecoverably."""
    pass


def fetch(resolved: ResolvedSlug, offline: bool = False) -> Path:
    """
    Fetch the problem suite for a resolved slug using git.

    Uses a shallow clone, then fetch and checkout.
    Caches local git repos at ``~/.gradbot/local/{owner}/{repo}/``.

    Args:
        resolved: A fully resolved slug from ``resolver.resolve()``
        offline: If True, only use the existing local clone (no network)

    Returns:
        Path to the problem suite directory
        (the folder containing suite.yaml and checks.py)

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
        # If we're online and failed, check if we have a stale local copy
        if not offline and local_path.exists():
            print(
                f"⚠️  Couldn't reach GitHub ({e}). Using cached tests "
                f"(they might be outdated).",
                file=sys.stderr,
            )
        elif offline and not local_path.exists():
            raise FetchError(
                "You're in offline mode, but GradBot doesn't have a cached copy "
                f"of '{resolved.raw_slug}'.\n"
                "Connect to the internet and try again without --offline."
            )
        else:
            _raise_fetch_error(e, resolved)

    # Locate the problem directory inside the repo
    problem_dir = local_path / resolved.topic / resolved.problem

    if not problem_dir.is_dir():
        raise FetchError(
            f"Couldn't find the problem '{resolved.topic}/{resolved.problem}' "
            f"in the repository.\n"
            "Double-check the slug and make sure the problem exists in the repo."
        )

    return problem_dir


def fetch_local(suite_dir: Path) -> Path:
    """
    'Fetch' a local problem suite (for --dev mode).

    Simply validates that the directory exists and contains the expected files.

    Args:
        suite_dir: Path to a local problem suite directory

    Returns:
        The same path if valid

    Raises:
        FetchError: if the directory doesn't look like a valid suite
    """
    suite_dir = Path(suite_dir).resolve()

    if not suite_dir.is_dir():
        raise FetchError(f"Directory not found: {suite_dir}")

    # Check for required files
    suite_yaml = suite_dir / "suite.yaml"
    checks_py = suite_dir / "checks.py"

    if not suite_yaml.exists():
        raise FetchError(
            f"Missing suite.yaml in {suite_dir}\n"
            "Every problem suite needs a suite.yaml file."
        )

    if not checks_py.exists():
        raise FetchError(
            f"Missing checks.py in {suite_dir}\n"
            "Every problem suite needs a checks.py file with test checks."
        )

    return suite_dir


def _raise_fetch_error(git_error: GitError, resolved: ResolvedSlug) -> None:
    """Convert a GitError to a user-friendly FetchError."""
    stderr = git_error.stderr.lower() if git_error.stderr else ""

    if "could not resolve host" in stderr or "unable to access" in stderr:
        raise FetchError(
            "Couldn't connect to GitHub to download the test suite.\n\n"
            "Things to try:\n"
            "  • Check your internet connection\n"
            "  • If you've run this problem before, try: GradBot --offline ...\n"
            "  • Ask your teacher for help if the problem persists"
        )
    elif "not found" in stderr or "does not appear to be a git repo" in stderr:
        raise FetchError(
            f"Couldn't find the test suite repository for '{resolved.raw_slug}'.\n"
            "Double-check the slug and make sure the problem exists."
        )
    elif "authentication" in stderr or "403" in stderr or "401" in stderr:
        raise FetchError(
            "GitHub authentication failed.\n"
            "Practice problems are public. Hidden tests are not downloaded to this computer."
        )
    else:
        raise FetchError(
            f"Something went wrong downloading the test suite.\n"
            f"Error: {git_error}\n\n"
            "Things to try:\n"
            "  • Check your internet connection\n"
            "  • If you've run this problem before, try: GradBot --offline ...\n"
            "  • Ask your teacher for help if the problem persists"
        )
