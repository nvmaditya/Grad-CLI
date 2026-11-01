"""Run a student program in Docker: no network, one mount, resource limits.

Used by the grader workflow (``--sandbox docker``). The work directory is
mounted at ``/work`` and the command uses container paths, never host paths.
C and C++ are linked statically in this mode, so the binary does not depend
on the host's glibc matching the image's. Java is compiled with
``--release JAVA_RELEASE``, so a newer host JDK still writes class files the
image's JRE can load.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from gradbot.errors import UserError

logger = logging.getLogger("gradbot.sandbox")

CONTAINER_WORKDIR = "/work"

# The Java image's JRE version. Docker-mode Java is compiled for it.
JAVA_RELEASE = 21

IMAGES = {
    "python": "python:3.12-slim",
    "c": "debian:bookworm-slim",
    "cpp": "debian:bookworm-slim",
    "java": f"eclipse-temurin:{JAVA_RELEASE}-jre",
}

# Per container. Generous for DSA solutions; a fork bomb or a runaway
# allocation stops here instead of taking down the runner.
_LIMITS = ["--memory", "512m", "--pids-limit", "256", "--cpus", "1"]


def container_command(language: str, entry: str) -> list[str]:
    """The command inside the container for an entry file (or Java class) in /work."""
    if language == "python":
        return ["python", f"{CONTAINER_WORKDIR}/{entry}"]
    if language in ("c", "cpp"):
        return [f"{CONTAINER_WORKDIR}/{entry}"]
    if language == "java":
        return ["java", "-cp", CONTAINER_WORKDIR, entry]
    raise ValueError(f"no sandbox command for {language}")


def container_argv(
    work_dir: Path,
    command: list[str],
    image: str = IMAGES["python"],
    name: str | None = None,
) -> list[str]:
    """Argv for ``docker run`` of ``command`` with only ``work_dir`` mounted at ``/work``."""
    host = Path(work_dir).resolve()
    argv = [
        "docker",
        "run",
        "--rm",
        "-i",  # forward stdin: the program reads its input from it
        "--network",
        "none",
        *_LIMITS,
        "--security-opt",
        "no-new-privileges",
        "-e",
        "PYTHONIOENCODING=utf-8",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-v",
        f"{host}:{CONTAINER_WORKDIR}",
        "-w",
        CONTAINER_WORKDIR,
    ]
    if name:
        argv += ["--name", name]
    if hasattr(os, "getuid"):
        # Not root inside the container, and files it writes stay deletable.
        argv += ["--user", f"{os.getuid()}:{os.getgid()}"]
    return [*argv, image, *command]


def kill(name: str) -> None:
    """Stop a container whose ``docker run`` client timed out. Best effort."""
    try:
        subprocess.run(["docker", "kill", name], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("could not kill container %s: %s", name, exc)


def ensure_image(image: str) -> None:
    """Pull ``image`` now, so the download never counts against a check's timeout."""
    try:
        present = subprocess.run(
            ["docker", "image", "inspect", image], capture_output=True, timeout=60,
        ).returncode == 0
        if present:
            return
        pulled = subprocess.run(
            ["docker", "pull", image], capture_output=True, text=True, timeout=900,
        )
    except FileNotFoundError:
        raise UserError("--sandbox docker needs Docker, and the docker command was not found.") from None
    except subprocess.TimeoutExpired:
        raise UserError(f"Timed out pulling the Docker image {image}.") from None
    if pulled.returncode != 0:
        raise UserError(f"Couldn't pull the Docker image {image}: {pulled.stderr.strip()[:300]}")
