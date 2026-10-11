"""Sandbox argv and optional docker execution. No Docker daemon required."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from gradbot.api import _get_context, clear_context, run, set_context
from gradbot.sandbox import container_argv


def test_container_argv_is_networkless_and_mounts_only_work(tmp_path: Path):
    command = ["python", "solution.py"]
    argv = container_argv(tmp_path, command)

    assert argv[:3] == ["docker", "run", "--rm"]
    assert argv[argv.index("--network") + 1] == "none"
    mounts = [argv[i + 1] for i, token in enumerate(argv) if token == "-v"]
    assert mounts == [f"{tmp_path.resolve()}:/work"]
    assert "--volume" not in argv
    assert "--mount" not in argv
    assert argv[argv.index("-w") + 1] == "/work"
    assert "GITHUB_TOKEN" not in " ".join(argv)
    assert argv[-len(command) :] == command
    assert argv[-len(command) - 1] == "python:3.12-slim"


def test_container_argv_custom_image_and_no_token_leak(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "super-secret")
    command = ["echo", "hi"]
    argv = container_argv(tmp_path, command, image="python:3.11-slim")

    assert argv[:3] == ["docker", "run", "--rm"]
    assert argv.count("-v") == 1
    assert "GITHUB_TOKEN" not in " ".join(argv)
    assert "super-secret" not in " ".join(argv)
    assert argv[-len(command) - 1 :] == ["python:3.11-slim", *command]


def test_set_context_sandbox_defaults_to_none(tmp_path: Path):
    set_context(tmp_path, ["python", "solution.py"], tmp_path)
    try:
        assert _get_context()["sandbox"] is None
    finally:
        clear_context()
    assert _get_context()["sandbox"] is None


def test_clear_context_drops_docker_sandbox(tmp_path: Path):
    set_context(tmp_path, ["python", "solution.py"], tmp_path, sandbox="docker")
    assert _get_context()["sandbox"] == "docker"
    set_context(tmp_path, ["python", "solution.py"], tmp_path)
    assert _get_context()["sandbox"] is None
    set_context(tmp_path, ["python", "solution.py"], tmp_path, sandbox="docker")
    clear_context()
    assert _get_context()["sandbox"] is None


@patch("gradbot.api.subprocess.run")
def test_run_without_sandbox_uses_subprocess_command(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(stdout="ok\n", stderr="", returncode=0)
    command = ["python", "solution.py"]
    set_context(tmp_path, command, tmp_path)
    try:
        result = run(input="1\n", timeout=3)
    finally:
        clear_context()

    assert result.stdout == "ok\n"
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        command,
        input="1\n",
        capture_output=True,
        text=True,
        timeout=3,
        cwd=str(tmp_path),
    )


@patch("gradbot.api.subprocess.run")
def test_run_docker_sandbox_uses_container_argv(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    command = ["python", "solution.py"]
    set_context(tmp_path, command, tmp_path, sandbox="docker")
    try:
        run(input="")
    finally:
        clear_context()

    mock_run.assert_called_once_with(
        container_argv(tmp_path, command),
        input="",
        capture_output=True,
        text=True,
        timeout=5.0,
        cwd=str(tmp_path),
    )
