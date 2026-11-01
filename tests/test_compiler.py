"""Tests for gradbot.compiler — language detection and compilation."""

import sys

import gradbot
from gradbot.compiler import (
    CompileResult,
    _extract_friendly_error,
    compile_solution,
    detect_language,
    get_run_command,
)
from gradbot.loader import CheckFunction, SuiteConfig
from gradbot.runner import run_suite


class TestDetectLanguage:
    """Test language detection from file extensions."""

    def test_python(self, tmp_path):
        (tmp_path / "solution.py").write_text("print('hello')")
        assert detect_language(tmp_path) == "python"

    def test_c(self, tmp_path):
        (tmp_path / "solution.c").write_text("int main() {}")
        assert detect_language(tmp_path) == "c"

    def test_cpp(self, tmp_path):
        (tmp_path / "solution.cpp").write_text("int main() {}")
        assert detect_language(tmp_path) == "cpp"

    def test_cc_extension(self, tmp_path):
        (tmp_path / "solution.cc").write_text("int main() {}")
        assert detect_language(tmp_path) == "cpp"

    def test_java(self, tmp_path):
        (tmp_path / "Solution.java").write_text("class Solution {}")
        assert detect_language(tmp_path) == "java"

    def test_no_source_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        assert detect_language(tmp_path) is None

    def test_empty_dir(self, tmp_path):
        assert detect_language(tmp_path) is None

    def test_priority_python_over_others(self, tmp_path):
        (tmp_path / "solution.py").write_text("print('hello')")
        (tmp_path / "solution.c").write_text("int main() {}")
        # Python has highest priority
        assert detect_language(tmp_path) == "python"


class TestCompilePython:
    """Test Python syntax checking."""

    def test_valid_python(self, tmp_path):
        (tmp_path / "solution.py").write_text("print('hello world')\n")
        result = compile_solution(tmp_path, "python")
        assert result.success is True
        assert result.language == "python"
        assert result.binary_path is not None

    def test_syntax_error(self, tmp_path):
        (tmp_path / "solution.py").write_text("def foo(\n  # missing close paren\n")
        result = compile_solution(tmp_path, "python")
        assert result.success is False
        assert result.friendly_error  # should have a friendly message

    def test_no_files(self, tmp_path):
        result = compile_solution(tmp_path, "python")
        assert result.success is False


class TestFriendlyErrors:
    """Test student-facing error message extraction."""

    def test_c_error_with_line_number(self):
        raw = "solution.c:12:5: error: expected ';' after expression"
        msg = _extract_friendly_error(raw, "c")
        assert "line 12" in msg
        assert "try again" in msg.lower()

    def test_java_error_with_line_number(self):
        raw = "Solution.java:8: error: ';' expected"
        msg = _extract_friendly_error(raw, "java")
        assert "line 8" in msg

    def test_python_syntax_error(self):
        raw = "  File \"solution.py\", line 5\n    def foo(\n         ^\nSyntaxError: unexpected EOF"
        msg = _extract_friendly_error(raw, "python")
        assert "line 5" in msg

    def test_empty_error(self):
        msg = _extract_friendly_error("", "c")
        assert msg  # should still produce something

    def test_no_line_number(self):
        raw = "some random error message"
        msg = _extract_friendly_error(raw, "c")
        assert msg  # fallback message
        assert "compile" in msg.lower() or "clue" in msg.lower()


class TestGetRunCommand:
    """Test run command generation."""

    def test_c(self):
        cr = CompileResult(success=True, language="c", binary_path="./solution")
        cmd = get_run_command(cr)
        assert cmd == ["./solution"]

    def test_java(self):
        cr = CompileResult(success=True, language="java", binary_path="Solution")
        cmd = get_run_command(cr)
        assert cmd == ["java", "Solution"]

    def test_failed_compilation(self):
        cr = CompileResult(success=False, language="c")
        cmd = get_run_command(cr)
        assert cmd == []


class TestPythonInterpreter:
    """Python solutions run under the interpreter running GradBot, not `python` on PATH."""

    def test_run_command_uses_the_current_interpreter(self):
        cr = CompileResult(success=True, language="python", binary_path="solution.py")
        assert get_run_command(cr) == [sys.executable, "solution.py"]

    def test_solution_passes_when_python_is_not_on_path(self, tmp_path, monkeypatch):
        sol = tmp_path / "sol"
        sol.mkdir()
        (sol / "solution.py").write_text("print(input()[::-1])\n", encoding="utf-8")
        monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

        def check():
            result = gradbot.run(input="abc\n")
            gradbot.expect_output(result.stdout, "cba")

        result = run_suite(
            SuiteConfig(name="Reverse", topic="Strings"),
            [CheckFunction(func=check, name="reverses", slug="reverses")],
            sol,
            compile_solution(sol),
            "practice",
        )
        assert result.checks[0].status == "pass", result.checks[0].cause
