"""--sandbox docker against a real Docker daemon. Skipped where Docker is missing (CI on Linux runs them)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from gradbot.cli import grade_dev
from tests.samples_repo import TWO_SUM_CHECKS, TWO_SUM_SOLUTION, TWO_SUM_SUITE
from tests.test_languages import C_TWO_SUM, JAVA_TWO_SUM
from tests.toolchains import needs_docker, needs_gcc, needs_jdk, with_marks

pytestmark = needs_docker

linux_only = pytest.mark.skipif(sys.platform != "linux", reason="static C binaries run in Linux images only")


def _grade(tmp_path: Path, filename: str, source: str, checks: str = TWO_SUM_CHECKS, capsys=None) -> int:
    suite = tmp_path / "suite"
    suite.mkdir(exist_ok=True)
    (suite / "suite.yaml").write_text(TWO_SUM_SUITE, encoding="utf-8")
    (suite / "checks.py").write_text(checks, encoding="utf-8")
    sol = tmp_path / "sol"
    sol.mkdir(exist_ok=True)
    (sol / filename).write_text(source, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        grade_dev(suite, sol, no_color=True, sandbox="docker")
    return exc.value.code


def test_python_solution_reads_stdin_in_the_container(tmp_path):
    assert _grade(tmp_path, "solution.py", TWO_SUM_SOLUTION) == 0


@needs_gcc
@linux_only
def test_c_solution_runs_in_the_container(tmp_path):
    assert _grade(tmp_path, "solution.c", C_TWO_SUM) == 0


@with_marks(needs_jdk)
def test_java_solution_runs_in_the_container(tmp_path):
    assert _grade(tmp_path, "Solution.java", JAVA_TWO_SUM) == 0


_ECHO_CHECK = """\
import gradbot

@gradbot.check("probe", points=1)
def test_probe():
    gradbot.expect_output(gradbot.run().stdout, "{expected}")
"""


def test_the_container_has_no_network(tmp_path):
    probe = (
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 53), timeout=3)\n"
        "    print('online')\n"
        "except OSError:\n"
        "    print('offline')\n"
    )
    assert _grade(tmp_path, "solution.py", probe, _ECHO_CHECK.format(expected="offline")) == 0


def test_the_container_cannot_see_the_graders_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "faculty-secret")
    probe = "import os\nprint(os.environ.get('GRADBOT_APP_TOKEN', 'absent'))\n"
    assert _grade(tmp_path, "solution.py", probe, _ECHO_CHECK.format(expected="absent")) == 0


def test_a_timed_out_container_is_removed(tmp_path):
    checks = (
        "import gradbot\n\n"
        "@gradbot.check('loops', points=1)\n"
        "def test_loops():\n"
        "    assert gradbot.run(timeout=2).timed_out\n"
    )
    assert _grade(tmp_path, "solution.py", "while True:\n    pass\n", checks) == 0
    left = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "name=gradbot-"], capture_output=True, text=True,
    ).stdout.split()
    assert left == []
