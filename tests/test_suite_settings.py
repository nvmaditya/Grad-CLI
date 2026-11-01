"""suite.yaml settings and --timeout change what a run does."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from gradbot.cli import main
from gradbot.loader import LoadError, load_suite_config
from gradbot.reporter import render
from gradbot.result import CheckResult, SuiteResult
from gradbot.visibility import student_payload

_SLOW = "import time\ntime.sleep(2)\nprint('done')\n"

_DEFAULT_TIMEOUT_CHECK = """\
import gradbot

@gradbot.check("finishes", points=1, hint="Too slow")
def test_finishes():
    result = gradbot.run()
    if result.timed_out:
        raise gradbot.CheckFailure("timed out", hint="Too slow")
    gradbot.expect_output(result.stdout, "done")
"""

_EXPLICIT_TIMEOUT_CHECK = """\
import gradbot

@gradbot.check("finishes", points=1)
def test_finishes():
    result = gradbot.run(timeout=10)
    gradbot.expect_output(result.stdout, "done")
"""


def _problem(tmp_path: Path, suite: str, checks: str, solution: str, filename: str = "solution.py"):
    prob = tmp_path / "prob"
    prob.mkdir()
    (prob / "suite.yaml").write_text(suite, encoding="utf-8")
    (prob / "checks.py").write_text(checks, encoding="utf-8")
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / filename).write_text(solution, encoding="utf-8")
    return prob, sol


def _dev(prob: Path, sol: Path, *extra: str) -> int:
    with pytest.raises(SystemExit) as exc:
        main(["dev", str(prob), "--solution", str(sol), "--no-color", *extra])
    return exc.value.code


# ── time_limit and --timeout ──────────────────────────────────────────


def test_time_limit_is_the_default_timeout_for_run(tmp_path, capsys):
    prob, sol = _problem(tmp_path, "problem:\n  time_limit: 0.5\n", _DEFAULT_TIMEOUT_CHECK, _SLOW)
    assert _dev(prob, sol) == 1
    assert "Too slow" in capsys.readouterr().out


def test_without_time_limit_the_default_is_five_seconds(tmp_path):
    prob, sol = _problem(tmp_path, "problem: {}\n", _DEFAULT_TIMEOUT_CHECK, _SLOW)
    assert _dev(prob, sol) == 0


def test_timeout_flag_overrides_time_limit(tmp_path):
    prob, sol = _problem(tmp_path, "problem:\n  time_limit: 0.5\n", _DEFAULT_TIMEOUT_CHECK, _SLOW)
    assert _dev(prob, sol, "--timeout", "10") == 0


def test_timeout_flag_on_the_legacy_command(tmp_path):
    prob, sol = _problem(tmp_path, "problem: {}\n", _DEFAULT_TIMEOUT_CHECK, _SLOW)
    with pytest.raises(SystemExit) as exc:
        main(["--dev", str(prob), "--solution", str(sol), "--no-color", "--timeout", "0.5"])
    assert exc.value.code == 1


def test_an_explicit_timeout_in_the_check_wins(tmp_path):
    prob, sol = _problem(tmp_path, "problem:\n  time_limit: 0.5\n", _EXPLICIT_TIMEOUT_CHECK, _SLOW)
    assert _dev(prob, sol, "--timeout", "0.5") == 0


@pytest.mark.parametrize("value", ["0", "-1", "fast"])
def test_bad_time_limit_is_a_load_error(tmp_path, value):
    (tmp_path / "suite.yaml").write_text(f"problem:\n  time_limit: {value}\n", encoding="utf-8")
    with pytest.raises(LoadError, match="time_limit"):
        load_suite_config(tmp_path)


def test_bad_timeout_flag_is_refused(tmp_path, capsys):
    prob, sol = _problem(tmp_path, "problem: {}\n", _DEFAULT_TIMEOUT_CHECK, "print('done')\n")
    assert _dev(prob, sol, "--timeout", "0") == 2


# ── languages ─────────────────────────────────────────────────────────


def test_a_language_the_problem_does_not_accept_is_refused(tmp_path, capsys):
    prob, sol = _problem(
        tmp_path, "problem:\n  languages: [c, cpp]\n", _EXPLICIT_TIMEOUT_CHECK, "print('done')\n"
    )
    assert _dev(prob, sol) == 1
    out = capsys.readouterr().out
    assert "accepts C and C++" in out
    assert "Python" in out


def test_an_accepted_language_runs(tmp_path):
    suite = "problem:\n  languages: [python]\n"
    prob, sol = _problem(tmp_path, suite, _EXPLICIT_TIMEOUT_CHECK, "print('done')\n")
    assert _dev(prob, sol) == 0


def test_unknown_language_name_is_a_load_error(tmp_path):
    (tmp_path / "suite.yaml").write_text("problem:\n  languages: [python, rust]\n", encoding="utf-8")
    with pytest.raises(LoadError, match="rust"):
        load_suite_config(tmp_path)


def test_languages_must_be_a_list(tmp_path):
    (tmp_path / "suite.yaml").write_text("problem:\n  languages: python\n", encoding="utf-8")
    with pytest.raises(LoadError, match="languages"):
        load_suite_config(tmp_path)


# ── hints.general ─────────────────────────────────────────────────────


def _suite(status: str, general_hint: str | None) -> SuiteResult:
    return SuiteResult(
        problem="P", topic="T", mode="practice", general_hint=general_hint,
        checks=[CheckResult(name="c", slug="c", status=status, description="c")],  # type: ignore[arg-type]
    )


def test_general_hint_is_shown_when_marks_are_missing():
    buf = io.StringIO()
    render(_suite("fail", "Think about a hash map."), stream=buf, no_color=True)
    assert "Think about a hash map." in buf.getvalue()


def test_general_hint_is_not_shown_on_full_marks():
    buf = io.StringIO()
    render(_suite("pass", "Think about a hash map."), stream=buf, no_color=True)
    assert "hash map" not in buf.getvalue()


def test_general_hint_reaches_the_student_payload():
    assert student_payload(_suite("fail", "Think about a hash map."))["general_hint"] == (
        "Think about a hash map."
    )


def test_general_hint_flows_from_suite_yaml(tmp_path):
    prob, sol = _problem(
        tmp_path, "hints:\n  general: Read the input twice.\n", _EXPLICIT_TIMEOUT_CHECK, "print('no')\n"
    )
    out = tmp_path / "student.json"
    assert _dev(prob, sol, "--student-output", str(out)) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["public"]["general_hint"] == "Read the input twice."


# ── total_points ──────────────────────────────────────────────────────


def test_dev_warns_when_total_points_disagrees_with_the_checks(tmp_path, capsys):
    suite = "scoring:\n  total_points: 5\n"
    prob, sol = _problem(tmp_path, suite, _EXPLICIT_TIMEOUT_CHECK, "print('done')\n")
    assert _dev(prob, sol) == 0
    assert "total_points is 5 but checks.py awards 1" in capsys.readouterr().out


def test_dev_is_quiet_when_total_points_matches(tmp_path, capsys):
    suite = "scoring:\n  total_points: 1\n"
    prob, sol = _problem(tmp_path, suite, _EXPLICIT_TIMEOUT_CHECK, "print('done')\n")
    assert _dev(prob, sol) == 0
    assert "total_points" not in capsys.readouterr().out
