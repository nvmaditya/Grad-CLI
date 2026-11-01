"""Probe which compilers really work on this machine.

`shutil.which` is not enough: macOS ships /usr/bin/javac and /usr/bin/java
stubs that exist on PATH and fail when run without a JDK installed.
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess

import pytest


@functools.cache
def works(*argv: str) -> bool:
    if shutil.which(argv[0]) is None:
        return False
    try:
        done = subprocess.run(argv, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def has_gcc() -> bool:
    return works("gcc", "--version")


def has_gxx() -> bool:
    return works("g++", "--version")


def has_jdk() -> bool:
    return works("javac", "-version") and works("java", "-version")


def has_docker() -> bool:
    return works("docker", "info")


# CI sets GRADBOT_REQUIRE_TOOLCHAINS=gcc,g++,jdk (or docker) so a runner that
# lost a toolchain fails loudly instead of skipping those tests and going green.
_PROBES = {"gcc": has_gcc, "g++": has_gxx, "jdk": has_jdk, "docker": has_docker}
_REQUIRED = [n for n in os.environ.get("GRADBOT_REQUIRE_TOOLCHAINS", "").split(",") if n.strip()]
_unknown = [n for n in _REQUIRED if n not in _PROBES]
_missing = [n for n in _REQUIRED if n in _PROBES and not _PROBES[n]()]
if _unknown or _missing:
    raise RuntimeError(
        f"GRADBOT_REQUIRE_TOOLCHAINS: unknown {_unknown}, not working here {_missing}"
    )

needs_gcc = pytest.mark.skipif(not has_gcc(), reason="gcc is not available")
needs_gxx = pytest.mark.skipif(not has_gxx(), reason="g++ is not available")
needs_jdk = [
    pytest.mark.java,
    pytest.mark.skipif(not has_jdk(), reason="no working JDK (javac -version failed)"),
]
needs_docker = [
    pytest.mark.docker,
    pytest.mark.skipif(not has_docker(), reason="no working Docker daemon"),
]


def with_marks(marks: list):
    """Apply a list of marks as one decorator."""

    def decorate(func):
        for mark in marks:
            func = mark(func)
        return func

    return decorate
