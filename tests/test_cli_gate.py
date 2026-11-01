"""Student runs stay on public checks. Faculty dev runs both sets."""

import json
from pathlib import Path

import pytest

from gradbot.cli import grade_dev, grade_student, main, save_login_token
from gradbot.compiler import compile_solution
from gradbot.loader import CheckFunction, SuiteConfig
from gradbot.runner import run_suite

_SUITE = """\
problem:
  name: "Two Sum"
  topic: "Arrays"
scoring:
  total_points: 1
  pass_threshold: 0.6
"""

_PUBLIC = """\
import gradbot

@gradbot.check("public ok", points=1)
def test_public():
    return
"""

_HIDDEN = """\
import gradbot

@gradbot.check("hidden case", points=1, hint="Try a hash map")
def test_hidden():
    raise gradbot.CheckFailure("Expected SECRET_9998, got 0 1", hint="Try a hash map")
"""


def _problem(tmp_path: Path, hidden: bool = True) -> tuple[Path, Path]:
    suite = tmp_path / "prob"
    suite.mkdir()
    (suite / "suite.yaml").write_text(_SUITE, encoding="utf-8")
    (suite / "checks.py").write_text(_PUBLIC, encoding="utf-8")
    if hidden:
        (suite / "checks_hidden.py").write_text(_HIDDEN, encoding="utf-8")
    solution = tmp_path / "sol"
    solution.mkdir()
    (solution / "solution.py").write_text("print(1)\n", encoding="utf-8")
    return suite, solution


def test_dev_says_which_set_failed_and_strips_student_file(tmp_path: Path, capsys):
    suite, solution = _problem(tmp_path)
    faculty = tmp_path / "faculty.json"
    student = tmp_path / "student.json"
    with pytest.raises(SystemExit) as exc:
        grade_dev(
            suite,
            solution,
            verbose=False,
            no_color=True,
            faculty_output=faculty,
            student_output=student,
        )
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Public checks" in out
    assert "Hidden checks failed" in out
    faculty_text = faculty.read_text(encoding="utf-8")
    student_text = student.read_text(encoding="utf-8")
    assert "SECRET_9998" in faculty_text
    assert "SECRET_9998" not in student_text
    assert "Try a hash map" in student_text
    json.loads(student_text)


def test_student_grade_refuses_hidden_checks(tmp_path: Path, capsys):
    suite, solution = _problem(tmp_path)
    with pytest.raises(SystemExit) as exc:
        grade_student(suite, solution, verbose=False, no_color=True)
    assert exc.value.code == 1
    assert "checks_hidden.py" in capsys.readouterr().out


def test_student_grade_refuses_hidden_file_beside_solution(tmp_path: Path, capsys):
    suite, solution = _problem(tmp_path, hidden=False)
    (solution / "checks_hidden.py").write_text("SECRET\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        grade_student(suite, solution, verbose=False, no_color=True)
    assert exc.value.code == 1
    assert "checks_hidden.py" in capsys.readouterr().out


def test_student_grade_runs_public_checks(tmp_path: Path, capsys):
    suite, solution = _problem(tmp_path, hidden=False)
    with pytest.raises(SystemExit) as exc:
        grade_student(suite, solution, verbose=False, no_color=True)
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "Practice runs on this computer" in out
    assert "submit machine may differ" in out


def test_legacy_submit_does_not_ask_for_a_token(capsys, monkeypatch):
    import gradbot.resolver as resolver
    monkeypatch.setattr(resolver, "GRADBOT_TOKEN", "ghp_leak")
    with pytest.raises(SystemExit) as exc:
        main(["submit/arrays/two_sum", "--no-color"])
    assert exc.value.code == 1
    text = capsys.readouterr().out
    assert "ghp_leak" not in text
    assert "GRADBOT_TOKEN" not in text
    assert "does not download" in text


def test_login_token_stays_out_of_the_solution_dir(tmp_path: Path):
    path = save_login_token("secret-token", tmp_path / "config")
    assert path == tmp_path / "config" / "github_token"
    assert path.read_text(encoding="utf-8") == "secret-token"


def test_run_suite_forwards_docker_sandbox(tmp_path: Path, monkeypatch):
    solution = tmp_path / "sol"
    solution.mkdir()
    (solution / "solution.py").write_text("print(1)\n", encoding="utf-8")
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd

        class Result:
            stdout = "1\n"
            stderr = ""
            returncode = 0

        return Result()

    monkeypatch.setattr("gradbot.api.subprocess.run", fake_run)

    def check():
        import gradbot
        gradbot.run(input="")

    run_suite(
        SuiteConfig(name="T", topic="T"),
        [CheckFunction(func=check, name="c", slug="c")],
        solution,
        compile_solution(solution),
        "practice",
        sandbox="docker",
    )
    assert seen["cmd"][0] == "docker"
    assert "--network" in seen["cmd"]
    assert "none" in seen["cmd"]


def test_broken_checks_file_is_reported_without_blaming_the_student(tmp_path: Path, capsys):
    suite, solution = _problem(tmp_path, hidden=False)
    (suite / "checks.py").write_text("import gradbot\ndef broken(:\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["dev", str(suite), "--solution", str(solution), "--no-color"])
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Error importing checks.py" in out
    assert "bug in Grade" not in out


def test_malformed_suite_yaml_is_reported_cleanly(tmp_path: Path, capsys):
    suite, solution = _problem(tmp_path, hidden=False)
    (suite / "suite.yaml").write_text("problem: [unclosed\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["dev", str(suite), "--solution", str(solution), "--no-color"])
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "suite.yaml" in out
    assert "bug in Grade" not in out
