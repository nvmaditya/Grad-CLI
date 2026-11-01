# SPDX-License-Identifier: GPL-3.0-only
"""Small HTTPS client for GitHub and the course App. Standard library only."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from gradbot import __version__
from gradbot.errors import UserError

logger = logging.getLogger("gradbot.net")

TIMEOUT_SECONDS = 30
_SNIPPET = 300


class HttpError(UserError):
    """The server could not be reached, or answered with something unusable."""


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    text: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def json(self) -> object:
        try:
            return json.loads(self.text)
        except ValueError:
            raise HttpError(f"Got an unexpected reply (not JSON): {snippet(self.text)}") from None

    def json_object(self, *required: str) -> dict:
        """The body as a JSON object that has every key in ``required``."""
        data = self.json()
        if not isinstance(data, dict) or any(key not in data for key in required):
            raise HttpError(f"Got an unexpected reply: {snippet(self.text)}")
        return data


def request(
    url: str,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    token: str | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> Response:
    """Send one request. HTTP error statuses come back as a Response; network failures raise HttpError."""
    req_headers = {"User-Agent": f"gradbot/{__version__}", "Accept": "application/vnd.github+json"}
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    host = urllib.parse.urlsplit(url).netloc or url
    logger.debug("%s %s", method, url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(resp.status, resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return Response(exc.code, body)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        reason = getattr(exc, "reason", exc)
        raise HttpError(f"Couldn't reach {host}: {reason}. Check your internet connection.") from exc


def snippet(text: str) -> str:
    """At most a few hundred characters of a reply, on one line."""
    flat = " ".join(text.split())
    return flat if len(flat) <= _SNIPPET else flat[: _SNIPPET - 3] + "..."
