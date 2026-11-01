"""A local HTTP server that answers like GitHub and a course App. Records every request."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class Reply:
    status: int = 200
    body: object = field(default_factory=dict)   # dict/list -> JSON, str/bytes -> raw
    content_type: str = "application/json"


Route = Callable[[Request], Reply]


class FakeServer:
    """Routes are keyed by (method, path). A list of replies is served in order."""

    def __init__(self) -> None:
        self.requests: list[Request] = []
        self._routes: dict[tuple[str, str], Route | list[Reply]] = {}
        server = self

        class Handler(BaseHTTPRequestHandler):
            def _serve(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                req = Request(self.command, self.path, dict(self.headers), self.rfile.read(length))
                server.requests.append(req)
                reply = server._reply(req)
                payload = reply.body
                if isinstance(payload, (dict, list)):
                    data = json.dumps(payload).encode()
                elif isinstance(payload, str):
                    data = payload.encode()
                else:
                    data = bytes(payload)  # type: ignore[arg-type]
                self.send_response(reply.status)
                self.send_header("Content-Type", reply.content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_DELETE = do_PUT = do_PATCH = _serve

            def log_message(self, *args: object) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )

    def route(self, method: str, path: str, reply: Route | Reply | list[Reply]) -> None:
        if isinstance(reply, Reply):
            reply = [reply]
        self._routes[(method, path)] = reply

    def _reply(self, req: Request) -> Reply:
        path = req.path.split("?", 1)[0]
        handler = self._routes.get((req.method, path))
        if handler is None:
            return Reply(404, {"message": "Not Found"})
        if callable(handler):
            return handler(req)
        if len(handler) > 1:
            return handler.pop(0)
        return handler[0]

    def __enter__(self) -> FakeServer:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def dead_url() -> str:
    """A URL on a port nothing listens on."""
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"
