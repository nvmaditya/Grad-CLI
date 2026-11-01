"""Compiler edge cases: missing toolchains, timeouts, odd files. No real compiler needed."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gradbot.compiler import (
    CompileResult,
    _extract_friendly_error,
    _find_java_main_class,
    compile_solution,
    detect_language,
    get_run_command,
    restrict_languages,
)


@pytest.mark.parametrize(
    ("filename", "language", "tool"),
    [("solution.c", "c", "gcc"), ("solution.cpp", "cpp", "g++"), ("Solution.java", "java", "javac")],
)
def test_missing_compiler_is_named(tmp_path, monkeypatch, filename, language, tool):
    (tmp_path / filename).write_text("x", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "no-bin"))
    result = compile_solution(tmp_path)
    assert result.success is False
    assert result.language == language
    assert f"({tool})" in result.friendly_error


@pytest.mark.parametrize("filename", ["solution.c", "solution.cpp", "Solution.java"])
def test_compiler_timeout_is_reported(tmp_path, monkeypatch, filename):
    (tmp_path / filename).write_text("x", encoding="utf-8")

    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 30)

    monkeypatch.setattr("gradbot.compiler.subprocess.run", slow)
    result = compile_solution(tmp_path)
    assert result.success is False
    assert "took too long" in result.friendly_error


def test_java_compile_error_from_javac_output(tmp_path, monkeypatch):
    (tmp_path / "Solution.java").write_text("class Solution {", encoding="utf-8")

    def javac(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "Solution.java:1: error: reached end of file\n")

    monkeypatch.setattr("gradbot.compiler.subprocess.run", javac)
    result = compile_solution(tmp_path)
    assert result.friendly_error.startswith("Hmm, your code has an error on line 1.")
    assert "reached end of file" in result.friendly_error


def test_forced_language_without_matching_files(tmp_path):
    (tmp_path / "solution.py").write_text("print(1)\n", encoding="utf-8")
    result = compile_solution(tmp_path, "c")
    assert result.success is False
    assert "no c source files" in result.friendly_error


def test_unsupported_forced_language(tmp_path):
    (tmp_path / "main.rs").write_text("fn main() {}\n", encoding="utf-8")
    result = compile_solution(tmp_path, "rust")
    assert result.success is False


def test_empty_folder_says_which_files_are_supported(tmp_path):
    result = compile_solution(tmp_path)
    assert result.success is False
    assert ".py, .c, .cpp, .java" in result.friendly_error


def test_uppercase_and_cxx_extensions_are_detected(tmp_path):
    (tmp_path / "SOLUTION.PY").write_text("print(1)\n", encoding="utf-8")
    assert detect_language(tmp_path) == "python"
    other = tmp_path / "cxx"
    other.mkdir()
    (other / "solution.cxx").write_text("int main(){}\n", encoding="utf-8")
    assert detect_language(other) == "cpp"


def test_python_source_with_a_null_byte_is_a_syntax_error(tmp_path):
    (tmp_path / "solution.py").write_bytes(b"print(1)\x00\n")
    result = compile_solution(tmp_path)
    assert result.success is False
    assert result.friendly_error


def test_python_unicode_source_and_encoding_cookie(tmp_path):
    (tmp_path / "solution.py").write_bytes(
        "# -*- coding: latin-1 -*-\nprint('caf\xe9')\n".encode("latin-1")
    )
    assert compile_solution(tmp_path).success


def test_python_huge_source_file(tmp_path):
    (tmp_path / "solution.py").write_text("x = 1\n" * 200_000, encoding="utf-8")
    assert compile_solution(tmp_path).success


def test_python_entry_point_is_the_only_file_with_a_main_guard(tmp_path):
    (tmp_path / "lib.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "run.py").write_text("if __name__ == '__main__':\n    print(1)\n", encoding="utf-8")
    result = compile_solution(tmp_path)
    assert Path(result.binary_path).name == "run.py"


def test_java_main_class_is_the_file_with_main(tmp_path):
    helper = tmp_path / "Helper.java"
    main = tmp_path / "Main.java"
    helper.write_text("class Helper {}\n", encoding="utf-8")
    main.write_text("public class Main { public static void main(String[] a) {} }\n", encoding="utf-8")
    assert _find_java_main_class(tmp_path, [helper, main]) == "Main"
    assert _find_java_main_class(tmp_path, [helper]) == "Helper"
    assert _find_java_main_class(tmp_path, []) is None


@pytest.mark.parametrize(
    ("raw", "language", "expected"),
    [
        ("solution.cpp:7:3: error: expected ';'", "cpp", "line 7"),
        ("  File \"s.py\", line 3\nIndentationError", "python", "line 3"),
        ("linker failed", "cpp", "Here's a clue: linker failed"),
        ("weird python failure", "python", "Here's a clue"),
    ],
)
def test_friendly_errors(raw, language, expected):
    assert expected in _extract_friendly_error(raw, language)


def test_run_command_for_an_unknown_language_is_empty():
    assert get_run_command(CompileResult(success=True, language="rust", binary_path="x")) == []


def test_restrict_languages_keeps_failures_and_accepted_languages():
    failed = CompileResult(success=False, language="c", friendly_error="boom")
    assert restrict_languages(failed, ["python"]) is failed
    ok = CompileResult(success=True, language="python", binary_path="s.py")
    assert restrict_languages(ok, ["python", "c"]) is ok
    refused = restrict_languages(
        CompileResult(success=True, language="java", binary_path="S", source_files=["S.java"]), ["python"]
    )
    assert refused.success is False
    assert refused.friendly_error == "This problem accepts Python. Your folder has Java (S.java)."
