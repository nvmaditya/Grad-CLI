# SPDX-License-Identifier: GPL-3.0-only
"""Every environment variable GradBot reads, in one place.

Values are read when a command runs, not when a module is imported, so a
test or a wrapper script can change them between calls. ``.env.example``
documents the same list; ``tests/test_config.py`` keeps the two in step.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PUBLIC_REPO = "nvmaditya/gradbot-course-samples"


@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    needed_by: str          # the commands that read it
    required: bool          # True: those commands stop without it
    default: str | None
    description: str


VARIABLES: tuple[Variable, ...] = (
    Variable("GRADBOT_PUBLIC_REPO", "grade run", False, DEFAULT_PUBLIC_REPO,
             "Public samples repo for practice: owner/repo on GitHub, a git URL, or a local path."),
    Variable("GRADBOT_LOCAL_DIR", "grade run", False, "~/.gradbot/local",
             "Where practice clones are cached."),
    Variable("GRADBOT_CONFIG_DIR", "grade login, grade submit", False, "~/.gradbot",
             "Where the login token is stored."),
    Variable("GRADBOT_CLIENT_ID", "grade login", True, None,
             "Client id of the course's GitHub OAuth app (device flow, scope read:user)."),
    Variable("GRADBOT_SUBMIT_URL", "grade submit", True, None,
             "HTTPS endpoint of the course App that receives a submission zip."),
    Variable("GRADBOT_APP_TOKEN", "grade roster add, grade reset", True, None,
             "Faculty GitHub token. Never give this to students."),
    Variable("GRADBOT_SUBMISSIONS_REPO", "grade reset", True, None,
             "owner/repo that holds the one-submit slot refs."),
    Variable("NO_COLOR", "all commands", False, None,
             "Any value turns off coloured output (https://no-color.org)."),
)

_OWNER_REPO = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+$")
_URL_PREFIXES = ("https://", "http://", "ssh://", "git://", "file://", "git@")


class ConfigError(Exception):
    """A required setting is missing or malformed."""


@dataclass(frozen=True, slots=True)
class Settings:
    public_repo: str
    local_dir: Path
    config_dir: Path
    client_id: str | None
    submit_url: str | None
    app_token: str | None
    submissions_repo: str | None

    @property
    def token_file(self) -> Path:
        return self.config_dir / "github_token"


def load(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    home = Path.home() / ".gradbot"
    return Settings(
        public_repo=_public_repo(_get(env, "GRADBOT_PUBLIC_REPO") or DEFAULT_PUBLIC_REPO),
        local_dir=Path(_get(env, "GRADBOT_LOCAL_DIR") or home / "local").expanduser(),
        config_dir=Path(_get(env, "GRADBOT_CONFIG_DIR") or home).expanduser(),
        client_id=_get(env, "GRADBOT_CLIENT_ID"),
        submit_url=_get(env, "GRADBOT_SUBMIT_URL"),
        app_token=_get(env, "GRADBOT_APP_TOKEN"),
        submissions_repo=_get(env, "GRADBOT_SUBMISSIONS_REPO"),
    )


def require(value: str | None, name: str, why: str) -> str:
    """Return ``value`` or stop with a message that names the variable and why it's needed."""
    if not value:
        raise ConfigError(f"{name} is not set. {why}")
    return value


def is_owner_repo(value: str) -> bool:
    return bool(_OWNER_REPO.match(value)) and ".." not in value


def is_url_or_path(value: str) -> bool:
    return value.startswith(_URL_PREFIXES) or Path(value).is_absolute()


def _public_repo(value: str) -> str:
    if is_owner_repo(value) or is_url_or_path(value):
        return value
    raise ConfigError(
        f"GRADBOT_PUBLIC_REPO is '{value}'. It must be owner/repo "
        f"(for example {DEFAULT_PUBLIC_REPO}), a git URL, or an absolute path."
    )


def _get(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name, "").strip()
    return value or None
