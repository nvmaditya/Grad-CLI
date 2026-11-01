"""
Slug resolution for GradBot.

Parses a slug like ``practice/arrays/two_sum`` or ``practice/trees/inorder@v2``
and resolves it to a git origin URL + metadata for fetching via git.

Slug format is fixed: ``{mode}/{topic}/{problem}[@ref]``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from gradbot import config
from gradbot.errors import UserError
from gradbot.result import Mode

# Slug pattern: mode/topic/problem[@ref]. A ref may not start with "-" (it
# would reach git as an option) and may not contain "..".
_SLUG_PATTERN = re.compile(
    r"^(?P<mode>practice|submit)"
    r"/(?P<topic>[a-zA-Z0-9_-]+)"
    r"/(?P<problem>[a-zA-Z0-9_-]+)"
    r"(?:@(?P<ref>[a-zA-Z0-9_][a-zA-Z0-9._/-]*))?$"
)


class SlugError(UserError):
    """Raised when a slug is malformed or unresolvable."""
    pass


def _default_local_root() -> Path:
    return config.load().local_dir


@dataclass(frozen=True, slots=True)
class ResolvedSlug:
    """Fully resolved slug with all metadata needed for git-based fetching."""

    mode: Mode
    topic: str
    problem: str
    ref: str               # git ref (branch/tag/commit) — defaults to "main"
    repo: str              # owner/repo on GitHub, a git URL, or a local path
    raw_slug: str          # the original slug string
    local_root: Path = field(default_factory=_default_local_root)

    @property
    def git_origin(self) -> str:
        """
        Git clone URL.

        ``owner/repo`` means GitHub over HTTPS. A URL or path is used as given.
        Hidden tests are not cloned, so a token is never placed in the URL.
        """
        if config.is_owner_repo(self.repo):
            return f"https://github.com/{self.repo}.git"
        return self.repo

    @property
    def local_path(self) -> Path:
        """Path where the local git clone is stored."""
        if config.is_owner_repo(self.repo):
            owner, name = self.repo.split("/")
            return self.local_root / owner / name
        digest = hashlib.sha256(self.repo.encode("utf-8")).hexdigest()[:12]
        stem = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(self.repo.rstrip("/")).name) or "repo"
        return self.local_root / "_by_url" / f"{stem}-{digest}"

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
        slug: e.g. "practice/arrays/two_sum" or "practice/trees/inorder@v2"

    Returns:
        Dict with keys: mode, topic, problem, ref

    Raises:
        SlugError: if the slug doesn't match the expected format
    """
    match = _SLUG_PATTERN.match(slug.strip())
    if not match or ".." in (match.group("ref") or ""):
        raise SlugError(
            f"Hmm, '{slug}' doesn't look right.\n"
            f"Slugs should look like: practice/arrays/two_sum\n"
            f"  or: practice/trees/inorder@v2\n"
            f"The format is: {{practice|submit}}/{{topic}}/{{problem}}[@ref]"
        )
    parts = match.groupdict()
    if parts["ref"] is None:
        parts["ref"] = "main"
    return parts


def resolve(slug: str) -> ResolvedSlug:
    """
    Resolve a slug string to a full ResolvedSlug with git origin URL.

    Raises:
        SlugError: if the slug is malformed or asks for hidden tests
        ConfigError: if GRADBOT_PUBLIC_REPO is malformed
    """
    parts = parse_slug(slug)

    # Practice clones the public samples repo. Submit never clones hidden tests.
    if parts["mode"] != "practice":
        raise SlugError(
            "Submit does not download hidden tests.\n"
            "Use: grade submit <slug>\n"
            "Practice on this computer with: grade run <slug>"
        )
    settings = config.load()

    return ResolvedSlug(
        mode="practice",
        topic=parts["topic"],
        problem=parts["problem"],
        ref=parts["ref"],
        repo=settings.public_repo,
        raw_slug=slug.strip(),
        local_root=settings.local_dir,
    )
