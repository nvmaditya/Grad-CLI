"""The grader workflows are valid YAML, install GradBot, and keep tokens away from student code."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from gradbot.grade_workflow import grade_workflow_text
from gradbot.policy import INSTALL_SPEC, WORKFLOW_TEXT, publish_suite
from tests.samples_repo import TWO_SUM_CHECKS, TWO_SUM_SOLUTION, TWO_SUM_SUITE
from tests.toolchains import needs_docker, with_marks

TEMPLATES = {"publish": WORKFLOW_TEXT, "course": grade_workflow_text()}


def _steps(text: str) -> dict[str, dict]:
    data = yaml.safe_load(text)
    return {step["name"]: step for step in data["jobs"]["grade"]["steps"]}


def _trigger(text: str) -> dict:
    data = yaml.safe_load(text)
    return data.get("on") or data[True]  # PyYAML reads the key `on` as True


# The first major of each action that runs on Node 24. GitHub deprecated the
# Node 20 runtime; CI run #1 on harden warned about every older major below.
_NODE24_MAJOR = {
    "actions/checkout": 5,
    "actions/setup-python": 6,
    "actions/setup-java": 5,
    "actions/upload-artifact": 6,
}
_CI = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"


@pytest.mark.parametrize("name", [*TEMPLATES, "ci"])
def test_every_action_is_a_node24_major(name):
    text = _CI.read_text(encoding="utf-8") if name == "ci" else TEMPLATES[name]
    uses = re.findall(r"uses:\s*(\S+)@v(\d+)", text)
    assert uses
    old = [f"{action}@v{major}" for action, major in uses if int(major) < _NODE24_MAJOR[action]]
    assert old == []


@pytest.mark.parametrize("name", TEMPLATES)
def test_workflow_is_dispatch_only(name):
    assert set(_trigger(TEMPLATES[name])) == {"workflow_dispatch"}
    assert "pull_request_target" not in TEMPLATES[name]


@pytest.mark.parametrize("name", TEMPLATES)
def test_python_and_gradbot_are_installed_before_grading(name):
    order = list(_steps(TEMPLATES[name]))
    assert order.index("Set up Python") < order.index("Install GradBot") < order.index("Grade")
    install = _steps(TEMPLATES[name])["Install GradBot"]
    assert install["run"] == 'python -m pip install "$GRADBOT_PIP_SPEC"'
    assert INSTALL_SPEC in install["env"]["GRADBOT_PIP_SPEC"]


@pytest.mark.parametrize("name", TEMPLATES)
def test_inputs_never_reach_the_shell_directly(name):
    for step in _steps(TEMPLATES[name]).values():
        assert "${{" not in step.get("run", ""), step["name"]


@pytest.mark.parametrize("name", TEMPLATES)
def test_checkouts_do_not_keep_credentials(name):
    for step in _steps(TEMPLATES[name]).values():
        if step.get("uses", "").startswith("actions/checkout"):
            assert step["with"]["persist-credentials"] is False, step["name"]


@pytest.mark.parametrize("name", TEMPLATES)
def test_grade_step_clears_tokens_and_uses_the_sandbox(name):
    grade = _steps(TEMPLATES[name])["Grade"]
    assert grade["env"]["GITHUB_TOKEN"] == ""
    assert grade["env"]["GRADBOT_APP_TOKEN"] == ""
    assert "--sandbox docker" in grade["run"]
    assert "--student-output student.json" in grade["run"]


def test_publish_workflow_token_is_only_in_the_submission_checkout():
    users = [
        step["name"] for step in _steps(WORKFLOW_TEXT).values()
        if "secrets.GRADBOT_APP_TOKEN" in json.dumps(step)
    ]
    assert users == ["Check out the submission"]


def test_publish_workflow_keeps_results_even_when_grading_fails():
    steps = _steps(WORKFLOW_TEXT)
    assert steps["Grade"]["continue-on-error"] is True
    assert steps["Keep the results"]["if"] == "always()"


@pytest.mark.parametrize("name", TEMPLATES)
def test_a_broken_grader_still_fails_the_job(name):
    """A failing student is a finished grade; a grader that never wrote student.json is not."""
    steps = _steps(TEMPLATES[name])
    order = list(steps)
    check = steps["Check that grading finished"]
    assert order.index("Grade") + 1 == order.index("Check that grading finished")
    assert "continue-on-error" not in check
    assert check["run"].startswith("test -f student.json")


def test_install_spec_pins_this_version():
    import gradbot

    assert INSTALL_SPEC.endswith(f"@v{gradbot.__version__}")


@pytest.mark.skipif(shutil.which("actionlint") is None, reason="actionlint is not installed")
@pytest.mark.parametrize("name", TEMPLATES)
def test_actionlint_accepts_the_template(tmp_path, name):
    path = tmp_path / ".github" / "workflows" / "grade.yml"
    path.parent.mkdir(parents=True)
    path.write_text(TEMPLATES[name], encoding="utf-8")
    done = subprocess.run(["actionlint", str(path)], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


@with_marks(needs_docker)
def test_publish_grade_step_runs_for_real(tmp_path):
    """Run the Grade step's own script, in the layout the checkouts create."""
    problem = tmp_path / "authoring"
    problem.mkdir()
    (problem / "suite.yaml").write_text(TWO_SUM_SUITE, encoding="utf-8")
    (problem / "checks.py").write_text(TWO_SUM_CHECKS, encoding="utf-8")
    (problem / "checks_hidden.py").write_text(
        TWO_SUM_CHECKS.replace("test_basic", "test_hidden").replace('"basic"', '"hidden basic"'),
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    publish_suite(problem, workspace / "tests" / "arrays" / "two_sum", tmp_path / "samples")
    submission = workspace / "submission" / "arrays" / "two_sum" / "42" / "1"
    submission.mkdir(parents=True)
    (submission / "solution.py").write_text(TWO_SUM_SOLUTION, encoding="utf-8")

    script = _steps(WORKFLOW_TEXT)["Grade"]["run"]
    env = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_TOKEN": "",
        "GRADBOT_APP_TOKEN": "",
        "SLUG": "arrays/two_sum",
        "SUBMISSION_PATH": "arrays/two_sum/42/1",
    }
    done = subprocess.run(
        ["bash", "-e", "-c", script], cwd=workspace, env=env, capture_output=True, text=True,
    )

    assert done.returncode == 0, done.stdout + done.stderr
    finished = _steps(WORKFLOW_TEXT)["Check that grading finished"]["run"]
    assert subprocess.run(["bash", "-c", finished], cwd=workspace).returncode == 0
    student = json.loads((workspace / "student.json").read_text(encoding="utf-8"))
    assert student["public"]["passed_points"] == 1
    assert student["hidden"]["passed_points"] == 1
    assert not re.search(r'"(cause|log)"', (workspace / "student.json").read_text(encoding="utf-8"))
