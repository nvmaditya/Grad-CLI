"""The check-author API: run(), expect_*(), file_exists(), CheckFailure."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

import gradbot
from gradbot.api import (
    CheckFailure,
    OutputMismatch,
    RunResult,
    _get_context,
    clear_context,
    expect_exit,
    expect_output,
    expect_sequence,
    file_exists,
    run,
    set_context,
)
from gradbot.compiler import compile_solution
from gradbot.loader import CheckFunction, SuiteConfig
from gradbot.runner import run_suite


@pytest.fixture
def program(tmp_path: Path):
    """Write a Python program and point the API context at it."""

    def _make(source: str) -> Path:
        path = tmp_path / "solution.py"
        path.write_text(source, encoding="utf-8")
        set_context(tmp_path, [sys.executable, str(path)], tmp_path)
        return path

    yield _make
    clear_context()


# ── run() ─────────────────────────────────────────────────────────────


def test_run_feeds_stdin_and_captures_stdout_and_stderr(program):
    program("import sys\ns = input()\nprint(s.upper())\nprint('warn', file=sys.stderr)\n")
    result = run(input="hello\n")
    assert result == RunResult(stdout="HELLO\n", stderr="warn\n", exit_code=0, timed_out=False)


def test_run_with_empty_input_reports_the_programs_failure(program):
    program("print(input())\n")
    result = run(input="")
    assert result.exit_code != 0
    assert "EOFError" in result.stderr
    assert result.timed_out is False


def test_run_passes_extra_arguments(program):
    program("import sys\nprint(' '.join(sys.argv[1:]))\n")
    assert run(args=["--fast", "x y"]).stdout == "--fast x y\n"


def test_run_reports_a_nonzero_exit_code(program):
    program("raise SystemExit(3)\n")
    assert run().exit_code == 3


def test_run_round_trips_a_megabyte_of_input(program):
    program("import sys\ndata = sys.stdin.read()\nprint(len(data))\n")
    big = "7 " * 500_000
    assert run(input=big).stdout.strip() == str(len(big))


def test_run_round_trips_unicode(program):
    program("print(input())\n")
    text = "héllo wörld — 你好 🙂"
    assert run(input=text + "\n").stdout == text + "\n"


def test_run_unicode_works_when_the_parent_locale_is_ascii(program, monkeypatch):
    # A Windows pipe or LANG=C makes a child Python default to a narrow
    # encoding; printing 你好 would then crash a correct solution.
    monkeypatch.setenv("PYTHONIOENCODING", "ascii")
    program("print(input())\n")
    result = run(input="你好\n")
    assert result.stdout == "你好\n", result.stderr


def test_run_hides_tokens_from_the_student_program(program, monkeypatch):
    # Faculty run `grade dev` on untrusted code with GRADBOT_APP_TOKEN set.
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "faculty-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "gh-secret")
    monkeypatch.setenv("MY_API_KEY", "key-secret")
    monkeypatch.setenv("SOME_PASSWORD", "pw-secret")
    program("import os\nprint(sorted(v for v in os.environ.values() if 'secret' in v))\n")
    assert run().stdout == "[]\n"


def test_run_keeps_ordinary_environment(program, monkeypatch):
    monkeypatch.setenv("GRADBOT_TEST_VISIBLE", "hello")
    program("import os\nprint(os.environ.get('GRADBOT_TEST_VISIBLE'))\n")
    assert run().stdout == "hello\n"


def test_run_replaces_invalid_utf8_instead_of_raising(program):
    program("import sys\nsys.stdout.buffer.write(b'ok \\xff\\xfe\\n')\n")
    result = run()
    assert result.stdout.startswith("ok ")
    assert "�" in result.stdout


def test_run_times_out_and_keeps_partial_output(program):
    program("import time\nprint('partial', flush=True)\ntime.sleep(30)\n")
    result = run(timeout=0.5)
    assert result.timed_out is True
    assert result.exit_code == -1
    assert "partial" in result.stdout


def test_run_without_a_program_is_a_check_failure():
    clear_context()
    with pytest.raises(CheckFailure, match="No program to run"):
        run(input="x")


def test_run_with_a_missing_executable_is_a_check_failure(tmp_path):
    set_context(tmp_path, [str(tmp_path / "does-not-exist")], tmp_path)
    try:
        with pytest.raises(CheckFailure, match="Couldn't run the program"):
            run()
    finally:
        clear_context()


def test_context_is_per_thread(tmp_path):
    seen: dict[str, object] = {}

    def worker(name: str, folder: Path) -> None:
        set_context(folder, ["prog", name], folder)
        seen[name] = _get_context()["run_command"]
        clear_context()

    threads = [
        threading.Thread(target=worker, args=(name, tmp_path / name)) for name in ("a", "b")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert seen == {"a": ["prog", "a"], "b": ["prog", "b"]}
    assert _get_context()["run_command"] is None


# ── expect_output() ───────────────────────────────────────────────────


def test_expect_output_exact_ignores_surrounding_whitespace():
    expect_output("  0 1\n", "0 1")


def test_expect_output_exact_mismatch_carries_expected_and_actual():
    with pytest.raises(OutputMismatch) as raised:
        expect_output("1 0", "0 1")
    assert raised.value.expected == "0 1"
    assert raised.value.actual == "1 0"
    assert raised.value.hint == "Your output doesn't match what was expected. Check the format!"


def test_expect_output_custom_hint_replaces_the_default():
    with pytest.raises(OutputMismatch) as raised:
        expect_output("x", "y", hint="Print the indexes")
    assert raised.value.hint == "Print the indexes"


def test_expect_output_contains_and_regex():
    expect_output("answer: 42\n", "42", mode="contains")
    expect_output("answer: 42\n", r"answer: \d+", mode="regex")
    with pytest.raises(OutputMismatch):
        expect_output("answer: 42\n", "43", mode="contains")
    with pytest.raises(OutputMismatch):
        expect_output("answer: x\n", r"\d+", mode="regex")


def test_expect_output_empty_strings():
    expect_output("", "")
    with pytest.raises(OutputMismatch):
        expect_output("", "0 1")


def test_expect_output_unicode():
    expect_output("你好 🙂\n", "你好 🙂")


def test_expect_output_unknown_mode_is_an_author_error():
    with pytest.raises(ValueError, match="Unknown match mode"):
        expect_output("a", "a", mode="fuzzy")  # type: ignore[arg-type]


def test_mismatch_message_is_truncated_for_long_output():
    with pytest.raises(OutputMismatch) as raised:
        expect_output("x" * 10_000, "y" * 10_000)
    assert len(str(raised.value)) < 200
    assert raised.value.actual == "x" * 10_000


# ── expect_exit(), expect_sequence(), file_exists() ───────────────────


def test_expect_exit():
    expect_exit(RunResult("", "", 0, False))
    expect_exit(RunResult("", "", 2, False), code=2)
    with pytest.raises(CheckFailure, match="Expected exit code 0, got 1"):
        expect_exit(RunResult("", "", 1, False))
    with pytest.raises(CheckFailure, match="timed out"):
        expect_exit(RunResult("", "", -1, True))


def test_expect_sequence_compares_tokens():
    expect_sequence("1 2\n3\n", [1, 2, 3])
    expect_sequence("", [])
    with pytest.raises(OutputMismatch) as raised:
        expect_sequence("3 2 1", [1, 2, 3])
    assert raised.value.expected == "1 2 3"
    assert raised.value.actual == "3 2 1"


def test_file_exists(tmp_path):
    (tmp_path / "out.txt").write_text("x", encoding="utf-8")
    set_context(tmp_path, ["prog"], tmp_path)
    try:
        file_exists("out.txt")
        with pytest.raises(CheckFailure, match="'missing.txt' not found"):
            file_exists("missing.txt")
    finally:
        clear_context()


def test_file_exists_without_context_is_an_internal_error():
    clear_context()
    with pytest.raises(CheckFailure, match="no working directory"):
        file_exists("x")


# ── through the runner ────────────────────────────────────────────────


def _grade(tmp_path: Path, source: str, check) -> gradbot.result.CheckResult:
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "solution.py").write_text(source, encoding="utf-8")
    result = run_suite(
        SuiteConfig(name="T", topic="T"),
        [CheckFunction(func=check, name="c", slug="c", hint="author hint")],
        sol,
        compile_solution(sol),
        "practice",
    )
    return result.checks[0]


def test_invalid_utf8_output_is_a_student_failure_not_a_grader_error(tmp_path):
    def check():
        gradbot.expect_output(gradbot.run().stdout, "0 1")

    outcome = _grade(tmp_path, "import sys\nsys.stdout.buffer.write(b'\\xff\\xfe\\n')\n", check)

    assert outcome.status == "fail"
    assert outcome.hint == "Your output doesn't match what was expected. Check the format!"
