"""Shared fixtures. Every test runs with a clean GRADBOT_* environment."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_gradbot_env(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """Keep tests off the developer's real config, token, and clone cache."""
    for key in list(os.environ):
        if key.startswith("GRADBOT_") or key == "NO_COLOR":
            monkeypatch.delenv(key, raising=False)
    home = tmp_path_factory.mktemp("gradbot-home")
    monkeypatch.setenv("GRADBOT_CONFIG_DIR", str(home))
    monkeypatch.setenv("GRADBOT_LOCAL_DIR", str(home / "local"))
    yield home


@pytest.fixture
def gradbot_home(_isolated_gradbot_env: Path) -> Path:
    """The per-test config directory (GRADBOT_CONFIG_DIR)."""
    return _isolated_gradbot_env
