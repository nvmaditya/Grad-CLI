"""
Slug resolution for GradBot.

Parses a slug like ``practice/arrays/two_sum`` or ``submit/trees/inorder@v2``
and resolves it to a git origin URL + metadata for fetching via git.

Slug format is fixed: ``{mode}/{topic}/{problem}[@ref]``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# ── Default repository configuration ───────────────────────────────────
GRADBOT_PUBLIC_REPO = os.getenv(
    "GRADBOT_PUBLIC_REPO", "GradBot/gradbot-problems-public"
)
# Older installs exported these. Submit does not read them.
GRADBOT_PRIVATE_REPO = os.getenv(
    "GRADBOT_PRIVATE_REPO", "GradBot/gradbot-problems-private"
)
GRADBOT_TOKEN = os.getenv("GRADBOT_TOKEN")

# Local storage for git clones (replaces tarball cache)
GRADBOT_LOCAL_DIR = Path(
    os.getenv("GRADBOT_LOCAL_DIR", Path.home() / ".gradbot" / "local")
)

# Slug pattern: mode/topic/problem[@ref]
_SLUG_PATTERN = re.compile(
    r"^(?P<mode>practice|submit)"
    r"/(?P<topic>[a-zA-Z0-9_-]+)"
    r"/(?P<problem>[a-zA-Z0-9_-]+)"
    r"(?:@(?P<ref>[a-zA-Z0-9._/-]+))?$"
)


class SlugError(Exception):
    """Raised when a slug is malformed or unresolvable."""
    pass


@dataclass(frozen=True, slots=True)
class ResolvedSlug:
    """Fully resolved slug with all metadata needed for git-based fetching."""

    mode: Literal["practice", "submit"]
    topic: str
    problem: str
    ref: str               # git ref (branch/tag/commit) — defaults to "main"
    repo: str              # e.g. "GradBot/gradbot-problems-public"
    token: str | None      # GitHub PAT (only for private repos)
    raw_slug: str          # the original slug string

    @property
    def git_origin(self) -> str:
        """
        Git clone URL (HTTPS).

        Hidden tests are not cloned, so a token is never placed in the URL.
        """
        return f"https://github.com/{self.repo}.git"

    @property
    def local_path(self) -> Path:
        """Path where the local git clone is stored."""
        return GRADBOT_LOCAL_DIR / self.repo.replace("/", os.sep)

    @property
    def problem_path(self) -> str:
        """Relative path within the repo to the problem directory."""
        return f"{self.topic}/{self.problem}"

    @property
    def cache_key(self) -> str:
        """Unique key for identifying this resolved slug."""
        return f"{self.mode}/{self.topic}/{self.problem}/{self.ref}"


def parse_slug(slug: str) -> dict:
    """
    Parse a raw slug string into its components.

    Args:
        slug: e.g. "practice/arrays/two_sum" or "submit/trees/inorder@v2"

    Returns:
        Dict with keys: mode, topic, problem, ref (or None)

    Raises:
        SlugError: if the slug doesn't match the expected format
    """
    match = _SLUG_PATTERN.match(slug.strip())
    if not match:
        raise SlugError(
            f"Hmm, '{slug}' doesn't look right.\n"
            f"Slugs should look like: practice/arrays/two_sum\n"
            f"  or: submit/trees/inorder@v2\n"
            f"The format is: {{practice|submit}}/{{topic}}/{{problem}}[@ref]"
        )
    parts = match.groupdict()
    if parts["ref"] is None:
        parts["ref"] = "main"
    return parts


def resolve(slug: str) -> ResolvedSlug:
    """
    Resolve a slug string to a full ResolvedSlug with git origin URL.

    Args:
        slug: e.g. "practice/arrays/two_sum"

    Returns:
        ResolvedSlug with all fields populated

    Raises:
        SlugError: if the slug is malformed or a private repo is accessed without a token
    """
    parts = parse_slug(slug)
    mode = parts["mode"]
    ref = parts["ref"]

    # Practice clones the public samples repo. Submit never clones hidden tests.
    if mode != "practice":
        raise SlugError(
            "Submit does not download hidden tests.\n"
            "Use: gradbot submit <slug>\n"
            "Practice on this computer with: gradbot run <slug>"
        )
    repo = GRADBOT_PUBLIC_REPO
    token = None

    return ResolvedSlug(
        mode=mode,
        topic=parts["topic"],
        problem=parts["problem"],
        ref=ref,
        repo=repo,
        token=token,
        raw_slug=slug.strip(),
    )
