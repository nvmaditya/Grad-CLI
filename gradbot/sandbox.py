"""Docker argv for running a student program with no network and one mount."""

from __future__ import annotations

from pathlib import Path


def container_argv(
    work_dir: Path,
    command: list[str],
    image: str = "python:3.12-slim",
) -> list[str]:
    """Argv for ``docker run`` of ``command`` with only ``work_dir`` mounted at ``/work``."""
    host = Path(work_dir).resolve()
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "-v",
        f"{host}:/work",
        "-w",
        "/work",
        image,
        *command,
    ]
