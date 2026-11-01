"""Edge cases across modules: rendering, CLI error paths, zip and roster parsing, sandbox failures."""

from __future__ import annotations

import io
import os
import subprocess
import zipfile

import pytest

from gradbot import cli
from gradbot.errors import UserError
from gradbot.policy import PolicyError, add_roster_entry, parse_roster, safe_source_files
from gradbot.reporter import _supports_color, render
from gradbot.result import CheckResult, SuiteResult

# ── reporter ──────────────────────────────────────────────────────────


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_colour_follows_no_color_and_the_terminal(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert _supports_color(io.StringIO()) is False
    if os.name == "posix":
        assert _supports_color(_Tty()) is True
    monkeypatch.setenv("NO_COLOR", "1")
    assert _supports_color(_Tty()) is False


def _suite(*checks: CheckResult, mode: str = "practice") -> SuiteResult:
    return SuiteResult(problem="Two Sum", topic="Arrays", mode=mode, checks=list(checks))  # type: ignore[arg-type]


def _render(suite: SuiteResult, verbose: bool = False) -> str:
    buf = io.StringIO()
    render(suite, verbose=verbose, no_color=True, stream=buf)
    return buf.getvalue()


def _fail(**extra) -> CheckResult:
    return CheckResult(
        name="basic", slug="basic", status="fail", description="basic", hint="Use a hash map",
        cause="Expected '0 1', got '1 0'", log=["Expected: '0 1'"], **extra,
    )


def test_verbose_practice_shows_cause_and_log():
    out = _render(_suite(_fail()), verbose=True)
    assert "Cause: Expected '0 1', got '1 0'" in out
    assert "│ Expected: '0 1'" in out


def test_verbose_submit_mode_never_shows_cause_or_log():
    out = _render(_suite(_fail(), mode="submit"), verbose=True)
    assert "Use a hash map" in out
    assert "Expected" not in out


def test_error_status_shows_the_hint_and_cause_only_when_verbose():
    error = CheckResult(name="broken", slug="b", status="error", description="b",
                        hint="Ask your teacher", cause="RuntimeError: x")
    assert "RuntimeError" not in _render(_suite(error))
    assert "Error: RuntimeError: x" in _render(_suite(error), verbose=True)


def test_empty_suite_renders_a_zero_score():
    out = _render(_suite())
    assert "Score: 0 / 0" in out


def test_long_and_unicode_check_names_render():
    long = CheckResult(name="très long — " * 20, slug="l", status="pass", description="l")
    out = _render(_suite(long))
    assert "très long — " in out
    assert "Accepted" in out


def test_score_with_no_points_is_zero():
    assert _suite(CheckResult(name="c", slug="c", status="pass", description="c", points=0)).score == 0.0


# ── CLI error paths ───────────────────────────────────────────────────


def _exit(argv: list[str]) -> int:
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    return exc.value.code


def test_legacy_command_with_a_missing_solution_folder(tmp_path, capsys):
    assert _exit(["practice/arrays/two_sum", "--solution", str(tmp_path / "nope")]) == 1
    assert "Solution directory not found" in capsys.readouterr().out


def test_legacy_dev_with_a_missing_suite(tmp_path, capsys):
    assert _exit(["--dev", str(tmp_path / "nope"), "--solution", str(tmp_path)]) == 1
    assert "Directory not found" in capsys.readouterr().out


def test_dev_subcommand_with_a_missing_suite(tmp_path, capsys):
    assert _exit(["dev", str(tmp_path / "nope"), "--solution", str(tmp_path)]) == 1
    assert "Directory not found" in capsys.readouterr().out


def test_run_subcommand_refuses_submit_slugs(tmp_path, capsys):
    assert _exit(["run", "submit/arrays/two_sum", "--solution", str(tmp_path)]) == 1
    assert "practice only" in capsys.readouterr().out


def test_missing_git_is_explained(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "no-bin"))
    assert _exit(["run", "arrays/two_sum", "--solution", str(tmp_path)]) == 1
    assert "needs Git" in capsys.readouterr().out


def test_ctrl_c_exits_130_without_a_traceback(monkeypatch, capsys):
    def interrupted(argv):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_dispatch", interrupted)
    assert _exit(["run", "arrays/two_sum"]) == 130
    assert "cancelled" in capsys.readouterr().out


def test_unexpected_error_with_verbose_prints_the_details(monkeypatch, capsys):
    def boom(argv):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(cli, "_dispatch", boom)
    assert _exit(["run", "arrays/two_sum", "--verbose"]) == 1
    out = capsys.readouterr()
    assert "unexpected problem" in out.out
    assert "RuntimeError: kaboom" in out.out + out.err


def test_user_errors_from_the_legacy_command_are_printed(monkeypatch, capsys, tmp_path):
    def refuse(args):
        raise UserError("plain message")

    monkeypatch.setattr(cli, "_run", refuse)
    assert _exit(["practice/arrays/two_sum"]) == 1
    assert "❌ plain message" in capsys.readouterr().out


# ── runner: setup failure ─────────────────────────────────────────────


def test_a_failure_while_preparing_a_check_is_a_grader_error(tmp_path, monkeypatch):
    from gradbot.compiler import compile_solution
    from gradbot.loader import CheckFunction, SuiteConfig
    from gradbot.runner import run_suite

    (tmp_path / "solution.py").write_text("print(1)\n", encoding="utf-8")

    def broken_copy(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("gradbot.runner.copy_solution", broken_copy)
    result = run_suite(
        SuiteConfig(), [CheckFunction(func=lambda: None, name="c", slug="c")],
        tmp_path, compile_solution(tmp_path), "practice",
    )
    assert result.checks[0].status == "error"
    assert result.checks[0].cause == "Setup error: OSError: disk full"


# ── submit zips ───────────────────────────────────────────────────────


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buf.getvalue()


@pytest.mark.parametrize(
    "name", ["/etc/passwd.py", "..\\evil.py", "a/../../evil.py", "src/.github/x.py", "lib/checks.py"],
)
def test_zip_paths_that_are_refused(name):
    with pytest.raises(PolicyError):
        safe_source_files(_zip({"solution.py": b"x", name: b"y"}))


def test_zip_keeps_nested_and_unicode_names_and_normalises_backslashes():
    files = safe_source_files(_zip({
        "solution.py": b"x", "lib\\helper.py": b"y", "über/naïve.py": b"z", "folder/": b"",
    }))
    assert files == {"solution.py": b"x", "lib/helper.py": b"y", "über/naïve.py": b"z"}


def test_zip_that_is_not_a_zip():
    with pytest.raises(PolicyError, match="bad zip"):
        safe_source_files(b"PK\x03\x04 not really")


# ── roster.yml ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("students: [unclosed", "not valid YAML"),
        ("- 1\n- 2\n", "mapping"),
        ("students: 5\n", "must be a list"),
        ("students:\n  - login: ada\n", "numeric GitHub id"),
        ("students:\n  - id: true\n", "numeric GitHub id"),
        ("students:\n  - id: '5'\n", "numeric GitHub id"),
    ],
)
def test_malformed_roster(text, match):
    with pytest.raises(PolicyError, match=match):
        parse_roster(text)


def test_empty_roster_and_replacing_a_row():
    assert parse_roster("") == set()
    text = add_roster_entry("students: []\n", "ada", 5)
    text = add_roster_entry(text, "Ada-Renamed", 5)
    assert parse_roster(text) == {5}
    assert "Ada-Renamed" in text and "login: ada\n" not in text


# ── sandbox failures ──────────────────────────────────────────────────


def test_pull_failure_and_timeout_are_user_errors(monkeypatch):
    from gradbot.sandbox import ensure_image

    def missing_image(cmd, **kwargs):
        if cmd[1] == "image":
            return subprocess.CompletedProcess(cmd, 1, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "manifest unknown")

    monkeypatch.setattr("gradbot.sandbox.subprocess.run", missing_image)
    with pytest.raises(UserError, match="manifest unknown"):
        ensure_image("nope:1")

    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 900)

    monkeypatch.setattr("gradbot.sandbox.subprocess.run", slow)
    with pytest.raises(UserError, match="Timed out pulling"):
        ensure_image("nope:1")


def test_kill_never_raises(monkeypatch):
    from gradbot.sandbox import kill

    def gone(cmd, **kwargs):
        raise OSError("docker vanished")

    monkeypatch.setattr("gradbot.sandbox.subprocess.run", gone)
    kill("gradbot-123")


def test_no_container_command_for_an_unknown_language():
    from gradbot.sandbox import container_command

    with pytest.raises(ValueError):
        container_command("rust", "main")


# ── fetch: an error git can't explain ─────────────────────────────────


def test_unclassified_git_failure_shows_gits_message(monkeypatch):
    from gradbot.fetcher import FetchError, fetch
    from gradbot.git import GitError
    from gradbot.resolver import resolve

    def odd(**kwargs):
        raise GitError("Git command failed: git fetch", stderr="fatal: index-pack failed")

    monkeypatch.setattr("gradbot.fetcher.clone_or_update", odd)
    with pytest.raises(FetchError, match="index-pack failed"):
        fetch(resolve("practice/arrays/two_sum"))


def test_results_on_a_folder_is_a_read_error(tmp_path, capsys):
    assert _exit(["results", str(tmp_path)]) == 1
    assert "Couldn't read" in capsys.readouterr().out

