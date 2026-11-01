"""Tests for gradbot.runner — check execution, DAG traversal, error handling."""



from gradbot.compiler import CompileResult
from gradbot.loader import CheckFunction, SuiteConfig
from gradbot.runner import run_suite


def _make_config(**kwargs) -> SuiteConfig:
    """Create a test SuiteConfig with defaults."""
    defaults = {
        "name": "Test Problem",
        "topic": "Test",
    }
    defaults.update(kwargs)
    return SuiteConfig(**defaults)


def _make_compile_result(success=True, language="python", binary_path="solution.py", friendly_error=""):
    return CompileResult(
        success=success,
        language=language,
        binary_path=binary_path,
        friendly_error=friendly_error,
    )


class TestRunSuiteCompilationFailure:
    """Test that compilation failure skips all checks."""

    def test_all_skipped_on_compile_fail(self, tmp_path):
        config = _make_config()
        checks = [
            CheckFunction(func=lambda: None, name="check1", slug="check1"),
            CheckFunction(func=lambda: None, name="check2", slug="check2"),
        ]
        compile_result = _make_compile_result(
            success=False,
            friendly_error="Syntax error on line 5",
        )

        result = run_suite(config, checks, tmp_path, compile_result, "practice")

        assert result.total == 2
        assert result.passed == 0
        assert all(c.status == "skip" for c in result.checks)


class TestRunSuiteDependencies:
    """Test dependency-based skipping."""

    def test_dependent_skipped_when_parent_fails(self, tmp_path):
        # Create a solution file
        (tmp_path / "solution.py").write_text("print('hello')\n")

        def failing_check():
            from gradbot.api import CheckFailure
            raise CheckFailure("intentional failure", hint="test hint")

        def dependent_check():
            pass  # would pass if run

        config = _make_config()
        checks = [
            CheckFunction(func=failing_check, name="parent", slug="parent"),
            CheckFunction(
                func=dependent_check,
                name="child",
                slug="child",
                depends_on="parent",
            ),
        ]
        compile_result = _make_compile_result(binary_path=str(tmp_path / "solution.py"))

        result = run_suite(config, checks, tmp_path, compile_result, "practice")

        assert result.checks[0].status == "fail"
        assert result.checks[1].status == "skip"


class TestRunSuitePassFail:
    """Test basic pass/fail scenarios."""

    def test_passing_check(self, tmp_path):
        (tmp_path / "solution.py").write_text("print('hello')\n")

        def passing_check():
            pass  # no exception = pass

        config = _make_config()
        checks = [
            CheckFunction(func=passing_check, name="passes", slug="passes"),
        ]
        compile_result = _make_compile_result(binary_path=str(tmp_path / "solution.py"))

        result = run_suite(config, checks, tmp_path, compile_result, "practice")

        assert result.checks[0].status == "pass"
        assert result.score == 1.0

    def test_failing_check_with_hint(self, tmp_path):
        (tmp_path / "solution.py").write_text("print('hello')\n")

        def failing_check():
            from gradbot.api import CheckFailure
            raise CheckFailure("wrong output", hint="Try again!")

        config = _make_config()
        checks = [
            CheckFunction(func=failing_check, name="fails", slug="fails"),
        ]
        compile_result = _make_compile_result(binary_path=str(tmp_path / "solution.py"))

        result = run_suite(config, checks, tmp_path, compile_result, "practice")

        assert result.checks[0].status == "fail"
        assert result.checks[0].hint == "Try again!"

    def test_error_in_check(self, tmp_path):
        (tmp_path / "solution.py").write_text("print('hello')\n")

        def buggy_check():
            raise RuntimeError("unexpected error in check code")

        config = _make_config()
        checks = [
            CheckFunction(func=buggy_check, name="buggy", slug="buggy"),
        ]
        compile_result = _make_compile_result(binary_path=str(tmp_path / "solution.py"))

        result = run_suite(config, checks, tmp_path, compile_result, "practice")

        # Should be "error", not crash
        assert result.checks[0].status == "error"
        assert "unexpected" in (result.checks[0].cause or "").lower()


class TestRunSuiteScoring:
    """Test score computation."""

    def test_mixed_results_score(self, tmp_path):
        (tmp_path / "solution.py").write_text("print('hello')\n")

        def pass_check():
            pass

        def fail_check():
            from gradbot.api import CheckFailure
            raise CheckFailure("nope", hint="hint")

        config = _make_config()
        checks = [
            CheckFunction(func=pass_check, name="c1", slug="c1", points=2),
            CheckFunction(func=fail_check, name="c2", slug="c2", points=1),
            CheckFunction(func=pass_check, name="c3", slug="c3", points=1),
        ]
        compile_result = _make_compile_result(binary_path=str(tmp_path / "solution.py"))

        result = run_suite(config, checks, tmp_path, compile_result, "practice")

        assert result.passed_points == 3  # c1(2) + c3(1)
        assert result.total_points == 4
        assert result.score == 0.75


class TestAssertionMessages:
    """A plain assert message can hold the expected answer; it is not a hint."""

    def test_assert_message_stays_out_of_the_student_hint(self, tmp_path):
        from gradbot.visibility import student_payload

        def check():
            raise AssertionError("expected SECRET_9998")

        result = run_suite(
            _make_config(),
            [CheckFunction(func=check, name="hidden", slug="hidden")],
            tmp_path,
            _make_compile_result(binary_path=str(tmp_path / "solution.py")),
            "submit",
        )

        assert result.checks[0].status == "fail"
        assert result.checks[0].cause == "expected SECRET_9998"
        assert "SECRET_9998" not in str(student_payload(result))

    def test_assert_uses_the_author_hint(self, tmp_path):
        def check():
            raise AssertionError("detail")

        result = run_suite(
            _make_config(),
            [CheckFunction(func=check, name="c", slug="c", hint="Check the order")],
            tmp_path,
            _make_compile_result(binary_path=str(tmp_path / "solution.py")),
            "practice",
        )

        assert result.checks[0].hint == "Check the order"


class TestHintPrecedence:
    """A hint passed to the failing call beats the check's hint, which beats the generic one."""

    def _hint(self, tmp_path, func, check_hint=None):
        result = run_suite(
            _make_config(),
            [CheckFunction(func=func, name="c", slug="c", hint=check_hint)],
            tmp_path,
            _make_compile_result(binary_path=str(tmp_path / "solution.py")),
            "practice",
        )
        return result.checks[0].hint

    def test_check_hint_is_shown_for_an_output_mismatch(self, tmp_path):
        import gradbot

        def check():
            gradbot.expect_output("1 0", "0 1")

        assert self._hint(tmp_path, check, "Try every pair") == "Try every pair"

    def test_hint_given_to_expect_output_wins(self, tmp_path):
        import gradbot

        def check():
            gradbot.expect_output("1 0", "0 1", hint="Indexes are 0-based")

        assert self._hint(tmp_path, check, "Try every pair") == "Indexes are 0-based"

    def test_generic_hint_when_nobody_wrote_one(self, tmp_path):
        import gradbot

        def check():
            gradbot.expect_output("1 0", "0 1")

        assert self._hint(tmp_path, check) == "Your output doesn't match what was expected. Check the format!"

    def test_check_hint_is_shown_for_sequence_exit_and_file_failures(self, tmp_path):
        import gradbot
        from gradbot.api import RunResult

        def seq():
            gradbot.expect_sequence("3 2 1", [1, 2, 3])

        def exit_code():
            gradbot.expect_exit(RunResult("", "", 1, False))

        def missing():
            gradbot.file_exists("out.txt")

        for func in (seq, exit_code, missing):
            assert self._hint(tmp_path, func, "Author hint") == "Author hint"
