"""The CLI never shows a student a traceback, even on a terminal that can't print ✓."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gradbot import cli

_SUITE = 'problem:\n  name: "Écho — 回声"\n  topic: "Strings"\n'
_CHECKS = """\
import gradbot

@gradbot.check("echoes ✓ text", points=1, hint="Print the line 🙂")
def test_echo():
    gradbot.expect_output(gradbot.run(input="héllo\\n").stdout, "héllo")
"""


def _problem(tmp_path: Path, solution: str) -> tuple[Path, Path]:
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "suite.yaml").write_text(_SUITE, encoding="utf-8")
    (suite / "checks.py").write_text(_CHECKS, encoding="utf-8")
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "solution.py").write_text(solution, encoding="utf-8")
    return suite, sol


def _grade_ascii(suite: Path, sol: Path) -> subprocess.CompletedProcess[bytes]:
    env = {**os.environ, "PYTHONIOENCODING": "ascii"}
    return subprocess.run(
        [sys.executable, "-m", "gradbot", "dev", str(suite), "--solution", str(sol), "--no-color"],
        capture_output=True,
        env=env,
        timeout=60,
    )


def test_passing_run_on_an_ascii_terminal(tmp_path):
    suite, sol = _problem(tmp_path, "print(input())\n")
    proc = _grade_ascii(suite, sol)
    output = proc.stdout + proc.stderr
    assert b"Traceback" not in output
    assert b"Score: 1 / 1" in proc.stdout
    assert proc.returncode == 0


def test_failing_run_with_unicode_hint_on_an_ascii_terminal(tmp_path):
    suite, sol = _problem(tmp_path, "print('nope')\n")
    proc = _grade_ascii(suite, sol)
    assert b"Traceback" not in proc.stdout + proc.stderr
    assert b"Score: 0 / 1" in proc.stdout
    assert proc.returncode == 1


def test_fatal_error_message_survives_an_ascii_stdout(monkeypatch):
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="ascii"))

    def boom(argv):
        raise RuntimeError("unexpected ✗")

    monkeypatch.setattr(cli, "_dispatch", boom)
    with pytest.raises(SystemExit) as exc:
        cli.main(["results", "x.json"])
    sys.stdout.flush()

    assert exc.value.code == 1
    assert b"GradBot ran into an unexpected problem" in raw.getvalue()
