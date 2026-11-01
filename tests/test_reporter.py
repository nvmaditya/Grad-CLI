"""Tests for gradbot.reporter — output formatting, colors, encouragement."""

import io

from gradbot.reporter import (
    _Colors,
    _get_encouragement,
    _progress_bar,
    render,
    render_compile_error,
)
from gradbot.result import CheckResult, SuiteResult


def _make_check(status="pass", name="Test check", hint=None, points=1, cause=None):
    return CheckResult(
        name=name,
        slug=name.lower().replace(" ", "_"),
        status=status,
        description=name,
        hint=hint,
        points=points,
        cause=cause,
    )


def _make_suite(checks=None, score_override=None):
    if checks is None:
        checks = [_make_check()]
    return SuiteResult(
        problem="Test Problem",
        topic="Testing",
        mode="practice",
        checks=checks,
    )


class TestProgressBar:
    """Test Unicode progress bar generation."""

    def test_full(self):
        bar = _progress_bar(1.0)
        assert "100%" in bar
        assert "██████████" in bar

    def test_empty(self):
        bar = _progress_bar(0.0)
        assert "0%" in bar
        assert "░░░░░░░░░░" in bar

    def test_half(self):
        bar = _progress_bar(0.5, width=10)
        assert "50%" in bar
        assert "█████░░░░░" in bar


class TestEncouragement:
    """Test score-based encouragement messages."""

    def test_perfect_score(self):
        msg = _get_encouragement(1.0)
        assert "accepted" in msg.lower()

    def test_almost_score(self):
        msg = _get_encouragement(0.85)
        assert "close" in msg.lower()

    def test_good_score(self):
        msg = _get_encouragement(0.6)
        assert "partial" in msg.lower()

    def test_early_score(self):
        msg = _get_encouragement(0.2)
        assert "debugging" in msg.lower()


class TestColors:
    """Test color enable/disable."""

    def test_colors_disabled(self):
        c = _Colors(enabled=False)
        assert c.green("hello") == "hello"
        assert c.red("hello") == "hello"

    def test_colors_enabled(self):
        c = _Colors(enabled=True)
        assert "\033[" in c.green("hello")
        assert "\033[" in c.red("hello")


class TestRender:
    """Test the main render function."""

    def test_renders_without_crash(self):
        suite = _make_suite()
        buf = io.StringIO()
        render(suite, stream=buf, no_color=True)
        output = buf.getvalue()
        assert "Grade" in output
        assert "Test Problem" in output

    def test_shows_pass_symbol(self):
        suite = _make_suite([_make_check(status="pass")])
        buf = io.StringIO()
        render(suite, stream=buf, no_color=True)
        assert "✓" in buf.getvalue()

    def test_shows_fail_symbol_and_hint(self):
        suite = _make_suite([
            _make_check(status="fail", hint="Try harder!")
        ])
        buf = io.StringIO()
        render(suite, stream=buf, no_color=True)
        output = buf.getvalue()
        assert "✗" in output
        assert "Try harder!" in output

    def test_shows_skip_symbol(self):
        suite = _make_suite([_make_check(status="skip")])
        buf = io.StringIO()
        render(suite, stream=buf, no_color=True)
        assert "○" in buf.getvalue()

    def test_shows_encouragement(self):
        suite = _make_suite([_make_check(status="pass")])
        buf = io.StringIO()
        render(suite, stream=buf, no_color=True)
        output = buf.getvalue()
        assert "Accepted. All tests passed." in output

    def test_no_color_mode(self):
        suite = _make_suite()
        buf = io.StringIO()
        render(suite, stream=buf, no_color=True)
        output = buf.getvalue()
        # Should not contain ANSI escape codes
        assert "\033[" not in output

    def test_score_display(self):
        suite = _make_suite([
            _make_check(status="pass", points=2),
            _make_check(status="fail", name="Fail check", points=1),
        ])
        buf = io.StringIO()
        render(suite, stream=buf, no_color=True)
        output = buf.getvalue()
        assert "2 / 3" in output


class TestRenderCompileError:
    """Test compilation error rendering."""

    def test_renders_friendly_error(self):
        buf = io.StringIO()
        render_compile_error(
            "Your code has an error on line 5",
            no_color=True,
            stream=buf,
        )
        output = buf.getvalue()
        assert "line 5" in output
        assert "syntax errors happen" in output.lower()

    def test_verbose_shows_raw(self):
        buf = io.StringIO()
        render_compile_error(
            "Friendly error",
            raw_error="gcc: error: blah blah",
            verbose=True,
            no_color=True,
            stream=buf,
        )
        output = buf.getvalue()
        assert "gcc: error" in output
