"""Grading reads the student's folder and leaves it exactly as it was."""

from __future__ import annotations

from pathlib import Path

import pytest

from gradbot.cli import grade_dev
from gradbot.compiler import compile_solution
from tests.toolchains import needs_gcc

_SUITE = 'problem:\n  name: "Reverse"\n  topic: "Strings"\n'

_CHECKS = """\
import gradbot

@gradbot.check("reverses abc", points=1)
def test_reverse():
    result = gradbot.run(input="abc\\n")
    gradbot.expect_output(result.stdout, "cba")
"""


def _suite(tmp_path: Path) -> Path:
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "suite.yaml").write_text(_SUITE, encoding="utf-8")
    (suite / "checks.py").write_text(_CHECKS, encoding="utf-8")
    return suite


def _listing(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*"))


def _grade(suite: Path, solution: Path) -> int:
    with pytest.raises(SystemExit) as exc:
        grade_dev(suite, solution, no_color=True)
    return exc.value.code


def test_python_entry_point_is_solution_py_not_the_first_file(tmp_path: Path):
    suite = _suite(tmp_path)
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "aaa_helper.py").write_text("def rev(s):\n    return s[::-1]\n", encoding="utf-8")
    (sol / "solution.py").write_text("from aaa_helper import rev\nprint(rev(input()))\n", encoding="utf-8")

    assert _grade(suite, sol) == 0


def test_python_main_py_is_an_entry_point(tmp_path: Path):
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "helpers.py").write_text("X = 1\n", encoding="utf-8")
    (sol / "main.py").write_text("print(input())\n", encoding="utf-8")

    result = compile_solution(sol)

    assert result.success
    assert Path(result.binary_path).name == "main.py"


def test_python_two_files_and_no_entry_point_names_the_expected_file(tmp_path: Path):
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "a.py").write_text("print(1)\n", encoding="utf-8")
    (sol / "b.py").write_text("print(2)\n", encoding="utf-8")

    result = compile_solution(sol)

    assert result.success is False
    assert "solution.py" in result.friendly_error
    assert "a.py" in result.friendly_error and "b.py" in result.friendly_error


def test_python_grade_leaves_no_pycache_in_the_student_folder(tmp_path: Path):
    suite = _suite(tmp_path)
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "solution.py").write_text("print(input()[::-1])\n", encoding="utf-8")
    before = _listing(sol)

    assert _grade(suite, sol) == 0
    assert _listing(sol) == before


def test_loading_checks_leaves_no_pycache_in_the_suite(tmp_path: Path):
    suite = _suite(tmp_path)
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "solution.py").write_text("print(input()[::-1])\n", encoding="utf-8")

    _grade(suite, sol)

    assert _listing(suite) == ["checks.py", "suite.yaml"]


@needs_gcc
def test_c_grade_leaves_no_binary_in_the_student_folder(tmp_path: Path):
    suite = _suite(tmp_path)
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "solution.c").write_text(
        "#include <stdio.h>\n#include <string.h>\n"
        "int main(void){char s[64];scanf(\"%63s\",s);"
        "for(int i=(int)strlen(s)-1;i>=0;i--)putchar(s[i]);putchar('\\n');return 0;}\n",
        encoding="utf-8",
    )

    assert _grade(suite, sol) == 0
    assert _listing(sol) == ["solution.c"]
