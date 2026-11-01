# SPDX-License-Identifier: GPL-3.0-only
"""Commands that talk to GitHub or the course App: login, submit, roster add, reset, results.

Each function raises ``UserError`` with a message for the person at the
keyboard; the CLI prints it and exits 1. Nothing here grades hidden checks.
"""

from __future__ import annotations

import io
import json
import os
import re
import time
import urllib.parse
import zipfile
from collections.abc import Callable
from pathlib import Path

from gradbot import net
from gradbot.config import Settings, require, require_owner_repo
from gradbot.errors import UserError
from gradbot.policy import (
    _ALLOWED_EXTENSIONS,
    add_roster_entry,
    device_code_body,
    safe_source_files,
    slot_ref,
)

_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
_PROBLEM_RE = re.compile(r"^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+$")
_FORM = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# Folders that never hold a student's source.
_SKIP_DIRS = {"__pycache__", "node_modules", "build", "dist", "target", "venv"}


def problem_slug(slug: str) -> str:
    """``arrays/two_sum`` (a leading ``submit/`` is allowed). Anything else is refused."""
    clean = slug.strip().removeprefix("submit/")
    if not _PROBLEM_RE.match(clean):
        raise UserError(f"'{slug}' is not a problem slug. Use topic/problem, for example arrays/two_sum.")
    return clean


# ── login ─────────────────────────────────────────────────────────────


def save_login_token(token: str, config_dir: Path) -> Path:
    """Store the device token outside the solution directory, readable only by this user."""
    path = Path(config_dir) / "github_token"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token)
    os.chmod(path, 0o600)  # a file left by an older version may be wider
    return path


def login(
    settings: Settings,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Path:
    """GitHub device flow with scope read:user. Returns where the token was saved."""
    client_id = require(
        settings.client_id, "GRADBOT_CLIENT_ID",
        "Ask your teacher for the course's GitHub OAuth app id.",
    )
    body = urllib.parse.urlencode(device_code_body(client_id)).encode()
    started_resp = net.request(f"{settings.github_url}/login/device/code", "POST", data=body, headers=_FORM)
    if not started_resp.ok:
        raise UserError(
            f"GitHub refused to start the login ({started_resp.status}). "
            "Check that GRADBOT_CLIENT_ID is your course's OAuth app id."
        )
    started = started_resp.json_object("device_code", "user_code", "verification_uri")
    print(f"Open {started['verification_uri']} and enter the code {started['user_code']}")
    print("Waiting for you to approve in the browser...")

    interval = _seconds(started.get("interval"), 5)
    deadline = clock() + _seconds(started.get("expires_in"), 900)
    poll_body = urllib.parse.urlencode({
        "client_id": client_id,
        "device_code": started["device_code"],
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }).encode()
    while clock() < deadline:
        sleep(interval)
        poll = net.request(
            f"{settings.github_url}/login/oauth/access_token", "POST", data=poll_body, headers=_FORM
        )
        payload = poll.json_object()
        if payload.get("access_token"):
            path = save_login_token(str(payload["access_token"]), settings.config_dir)
            print(f"Logged in. Token saved to {path}")
            return path
        error = payload.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval = _seconds(payload.get("interval"), interval + 5)
            continue
        if error == "expired_token":
            break
        if error == "access_denied":
            raise UserError("Login was cancelled in the browser. Run grade login again.")
        raise UserError(f"GitHub login failed: {error or net.snippet(poll.text)}")
    raise UserError("The login code expired before it was approved. Run grade login again.")


def _seconds(value: object, default: float) -> float:
    try:
        return max(0.0, float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


# ── submit ────────────────────────────────────────────────────────────


def collect_source_files(solution_dir: Path) -> dict[str, bytes]:
    """Source files under ``solution_dir``, by relative path. Skips .git, builds and practice checks."""
    root = Path(solution_dir)
    files: dict[str, bytes] = {}
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in _SKIP_DIRS)
        for name in sorted(names):
            path = Path(current) / name
            if name == "checks_hidden.py":
                raise UserError(
                    f"checks_hidden.py is in {path.parent}. Hidden checks never belong on a "
                    "student's computer; delete it and tell your teacher."
                )
            if name == "checks.py" or name.startswith(".") or path.is_symlink():
                continue
            if path.suffix.lower() in _ALLOWED_EXTENSIONS:
                files[path.relative_to(root).as_posix()] = path.read_bytes()
    if not files:
        raise UserError(f"GradBot found no source file (.py, .c, .cpp, .java) in {root}.")
    return files


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buf.getvalue()


def _require_https(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in _LOCAL_HOSTS):
        return
    raise UserError(
        f"GRADBOT_SUBMIT_URL must start with https:// (it is {url}). "
        "Your login token is sent with the submission."
    )


def submit(settings: Settings, slug: str, solution_dir: Path) -> None:
    """Zip the source files and POST them to the course App with the login token."""
    slug = problem_slug(slug)
    url = require(
        settings.submit_url, "GRADBOT_SUBMIT_URL",
        "Your teacher turns on graded submits by giving you this URL. "
        f"Until then, practice with: grade run {slug}",
    )
    _require_https(url)
    archive = _zip(collect_source_files(solution_dir))
    safe_source_files(archive)  # the same rules the App applies, checked before sending

    if not settings.token_file.is_file():
        raise UserError("You're not logged in. Run grade login first, then submit again.")
    token = settings.token_file.read_text(encoding="utf-8").strip()

    resp = net.request(
        url, "POST", data=archive, token=token, timeout=120,
        headers={"Content-Type": "application/zip", "X-Gradbot-Slug": slug},
    )
    reply = _reply_dict(resp)
    if resp.status in (401, 403):
        raise UserError("The course App did not accept your login. Run grade login again, then submit.")
    if not resp.ok or reply.get("accepted") is False:
        reason = reply.get("reason") or net.snippet(resp.text)
        raise UserError(f"The course App did not take this submit ({resp.status}): {reason}")
    print(f"✓ Submitted {slug}. {reply.get('reason') or net.snippet(resp.text)}")


def _reply_dict(resp: net.Response) -> dict:
    try:
        data = json.loads(resp.text)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


# ── faculty: roster add and reset ─────────────────────────────────────


def github_user(settings: Settings, login: str, token: str) -> dict:
    """``{"login": ..., "id": ...}`` as GitHub reports it. The typed login is only a lookup key."""
    if not _LOGIN_RE.match(login):
        raise UserError(f"'{login}' is not a GitHub login.")
    resp = net.request(f"{settings.github_api_url}/users/{login}", token=token)
    if resp.status == 404:
        raise UserError(f"No GitHub user named {login}.")
    if resp.status == 401:
        raise UserError("GitHub rejected GRADBOT_APP_TOKEN (401 Bad credentials). Check the token.")
    if not resp.ok:
        raise UserError(f"GitHub refused the lookup of {login} ({resp.status}): {net.snippet(resp.text)}")
    user = resp.json_object("login", "id")
    if isinstance(user["id"], bool) or not isinstance(user["id"], int):
        raise net.HttpError(f"Got an unexpected reply: {net.snippet(resp.text)}")
    return user


def roster_add(settings: Settings, login: str, roster: Path) -> None:
    token = require(
        settings.app_token, "GRADBOT_APP_TOKEN",
        "roster add asks GitHub for the student's numeric id with the faculty token.",
    )
    user = github_user(settings, login, token)
    print(f"GitHub says login {user['login']} has id {user['id']}. Writing that id.")
    current = roster.read_text(encoding="utf-8") if roster.is_file() else "students: []\n"
    updated = add_roster_entry(current, user["login"], user["id"])
    roster.write_text(updated, encoding="utf-8")
    print(f"Wrote {roster}")


def reset(settings: Settings, login: str, slug: str) -> None:
    """Delete the student's slot ref so they can submit once more."""
    token = require(
        settings.app_token, "GRADBOT_APP_TOKEN",
        "reset deletes the slot ref with the faculty token.",
    )
    repo = require_owner_repo(
        settings.submissions_repo, "GRADBOT_SUBMISSIONS_REPO",
        "reset deletes the slot ref in the submissions repo.",
    )
    slug = problem_slug(slug)
    user = github_user(settings, login, token)
    ref = slot_ref(slug, user["id"])
    # DELETE /repos/{repo}/git/refs/{name}; the slot ref already starts with "refs/".
    resp = net.request(f"{settings.github_api_url}/repos/{repo}/git/{ref}", "DELETE", token=token)
    if resp.status in (404, 422):
        raise UserError(f"There is no submit slot for {user['login']} on {slug}. Nothing to reset.")
    if resp.status == 401:
        raise UserError("GitHub rejected GRADBOT_APP_TOKEN (401 Bad credentials). Check the token.")
    if not resp.ok:
        raise UserError(f"GitHub refused to delete {ref} ({resp.status}): {net.snippet(resp.text)}")
    print(f"Reset {user['login']} (id {user['id']}): deleted {ref}. They can submit {slug} once more.")


# ── results ───────────────────────────────────────────────────────────


def strip_secrets(value: object) -> object:
    """Drop every ``cause`` and ``log`` key at any depth."""
    if isinstance(value, dict):
        return {k: strip_secrets(v) for k, v in value.items() if k not in {"cause", "log"}}
    if isinstance(value, list):
        return [strip_secrets(item) for item in value]
    return value


def results(path: Path) -> None:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise UserError(f"File not found: {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise UserError(f"Couldn't read {path}: {exc}") from None
    try:
        payload = json.loads(text)
    except ValueError:
        raise UserError(f"{path} is not valid JSON. Pass the file written by --output.") from None
    print(json.dumps(strip_secrets(payload), indent=2, ensure_ascii=False))
