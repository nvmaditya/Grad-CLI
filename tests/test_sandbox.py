"""Sandbox argv and optional docker execution. No Docker daemon required."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gradbot.api import _get_context, clear_context, run, set_context
from gradbot.compiler import CompileResult, compile_solution
from gradbot.errors import UserError
from gradbot.loader import CheckFunction, SuiteConfig
from gradbot.runner import run_suite
from gradbot.sandbox import IMAGES, JAVA_RELEASE, container_argv, ensure_image
from tests.toolchains import needs_jdk, with_marks


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
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args == (command,)
    assert kwargs["input"] == "1\n"
    assert kwargs["timeout"] == 3
    assert kwargs["cwd"] == str(tmp_path)


@patch("gradbot.api.subprocess.run")
def test_run_docker_sandbox_uses_container_argv(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    command = ["python", "solution.py"]
    set_context(tmp_path, command, tmp_path, sandbox="docker")
    try:
        run(input="")
    finally:
        clear_context()

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    argv = args[0]
    name = argv[argv.index("--name") + 1]
    assert name.startswith("gradbot-")
    assert argv == container_argv(tmp_path, command, name=name)
    assert kwargs["input"] == ""
    assert kwargs["timeout"] == 5.0


# ── the command that reaches Docker (no daemon needed) ────────────────


def _docker_argv(tmp_path, compile_result, monkeypatch, timeout=False):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if timeout and cmd[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"), output=b"", stderr=b"")
        return MagicMock(stdout="", stderr="", returncode=0)

    monkeypatch.setattr("gradbot.api.subprocess.run", fake_run)

    def check():
        import gradbot
        gradbot.run(input="4\n")

    run_suite(
        SuiteConfig(name="T", topic="T"),
        [CheckFunction(func=check, name="c", slug="c")],
        tmp_path,
        compile_result,
        "practice",
        sandbox="docker",
    )
    return calls


def _after_image(argv: list[str], image: str) -> list[str]:
    return argv[argv.index(image) + 1 :]


def test_docker_python_command_uses_container_paths(tmp_path, monkeypatch):
    (tmp_path / "solution.py").write_text("print(input())\n", encoding="utf-8")
    argv = _docker_argv(tmp_path, compile_solution(tmp_path), monkeypatch)[0]

    assert _after_image(argv, IMAGES["python"]) == ["python", "/work/solution.py"]
    assert str(tmp_path) not in " ".join(_after_image(argv, IMAGES["python"]))


def test_docker_forwards_stdin(tmp_path, monkeypatch):
    (tmp_path / "solution.py").write_text("print(input())\n", encoding="utf-8")
    argv = _docker_argv(tmp_path, compile_solution(tmp_path), monkeypatch)[0]
    assert "-i" in argv[: argv.index(IMAGES["python"])]


def test_docker_c_binary_runs_from_work(tmp_path, monkeypatch):
    (tmp_path / "solution").write_bytes(b"\x7fELF")
    result = CompileResult(success=True, language="c", binary_path=str(tmp_path / "solution"))
    argv = _docker_argv(tmp_path, result, monkeypatch)[0]
    assert _after_image(argv, IMAGES["c"]) == ["/work/solution"]


def test_docker_java_runs_the_class_from_work(tmp_path, monkeypatch):
    (tmp_path / "Solution.class").write_bytes(b"\xca\xfe")
    result = CompileResult(success=True, language="java", binary_path="Solution")
    argv = _docker_argv(tmp_path, result, monkeypatch)[0]
    assert _after_image(argv, IMAGES["java"]) == ["java", "-cp", "/work", "Solution"]


def test_docker_limits_and_privileges(tmp_path, monkeypatch):
    (tmp_path / "solution.py").write_text("print(1)\n", encoding="utf-8")
    argv = _docker_argv(tmp_path, compile_solution(tmp_path), monkeypatch)[0]
    head = argv[: argv.index(IMAGES["python"])]
    assert head[head.index("--network") + 1] == "none"
    assert "--memory" in head and "--pids-limit" in head
    assert "no-new-privileges" in head


def test_docker_timeout_kills_the_container(tmp_path, monkeypatch):
    (tmp_path / "solution.py").write_text("while True: pass\n", encoding="utf-8")
    calls = _docker_argv(tmp_path, compile_solution(tmp_path), monkeypatch, timeout=True)
    name = calls[0][calls[0].index("--name") + 1]
    assert calls[1] == ["docker", "kill", name]


def test_ensure_image_pulls_only_when_missing(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return MagicMock(returncode=1 if cmd[1] == "image" else 0, stdout="", stderr="")

    monkeypatch.setattr("gradbot.sandbox.subprocess.run", fake_run)
    ensure_image("python:3.12-slim")
    assert calls == [
        ["docker", "image", "inspect", "python:3.12-slim"],
        ["docker", "pull", "python:3.12-slim"],
    ]


def test_ensure_image_without_docker_is_a_clear_error(monkeypatch):
    def missing(cmd, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr("gradbot.sandbox.subprocess.run", missing)
    with pytest.raises(UserError, match="needs Docker"):
        ensure_image("python:3.12-slim")


def test_docker_mode_links_c_statically(tmp_path, monkeypatch):
    seen: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        seen.append(list(cmd))
        return MagicMock(returncode=0, stdout="", stderr="")

    (tmp_path / "solution.c").write_text("int main(void){return 0;}\n", encoding="utf-8")
    monkeypatch.setattr("gradbot.compiler.subprocess.run", fake_run)
    compile_solution(tmp_path, for_docker=True)
    assert "-static" in seen[0]


_JAVA_MAIN = "public class Solution { public static void main(String[] a) {} }\n"


def _javac_argv(tmp_path, monkeypatch, *, for_docker: bool, stderr: str = "", returncode: int = 0):
    seen: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        seen.append(list(cmd))
        return MagicMock(returncode=returncode, stdout="", stderr=stderr)

    (tmp_path / "Solution.java").write_text(_JAVA_MAIN, encoding="utf-8")
    monkeypatch.setattr("gradbot.compiler.subprocess.run", fake_run)
    compile_solution(tmp_path, for_docker=for_docker)
    return seen[0]


def test_the_java_release_is_the_image_jre():
    assert JAVA_RELEASE == 21
    assert IMAGES["java"] == "eclipse-temurin:21-jre"


def test_docker_mode_compiles_java_for_the_image_jre(tmp_path, monkeypatch):
    assert _javac_argv(tmp_path, monkeypatch, for_docker=True)[:3] == ["javac", "--release", "21"]


def test_local_mode_compiles_java_for_the_host_jdk(tmp_path, monkeypatch):
    assert "--release" not in _javac_argv(tmp_path, monkeypatch, for_docker=False)


def test_a_javac_too_old_for_the_image_is_a_grader_error(tmp_path, monkeypatch):
    # Not the student's compile error: their code never reached the compiler.
    with pytest.raises(UserError, match="JDK 21 or newer"):
        _javac_argv(
            tmp_path, monkeypatch, for_docker=True, returncode=2,
            stderr="error: release version 21 not supported\nUsage: javac <options> <source files>\n",
        )


@with_marks(needs_jdk)
def test_docker_mode_class_files_are_java_21(tmp_path):
    (tmp_path / "Solution.java").write_text(_JAVA_MAIN, encoding="utf-8")
    assert compile_solution(tmp_path, for_docker=True).success
    header = (tmp_path / "Solution.class").read_bytes()[:8]
    assert header[:4] == bytes.fromhex("cafebabe")
    assert int.from_bytes(header[6:8], "big") == 65  # Java 21
