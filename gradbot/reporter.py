"""
Terminal reporter for GradBot.

This is the result screen for cohort students. Every run shows a clear
verdict. The reporter handles:

- Colored ✓/✗/○ symbols for pass/fail/skip
- Progress bars with Unicode block characters
- A one-line score verdict
- Practice vs submit mode output differences
- Graceful degradation when colors aren't supported

Optional: if ``rich`` is installed, uses it for enhanced formatting.
Falls back to basic ANSI codes otherwise.
"""

from __future__ import annotations

import os
import sys
from typing import TextIO

from gradbot.result import CheckResult, SuiteResult

# ── Color support detection ───────────────────────────────────────────

def _supports_color(stream: TextIO = sys.stdout) -> bool:
    """Detect whether the terminal supports ANSI color codes."""
    # Respect NO_COLOR convention: https://no-color.org/
    if os.environ.get("NO_COLOR"):
        return False
    # Check if stdout is a TTY
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    # Windows terminal support
    if os.name == "nt":
        # Modern Windows 10+ supports ANSI, enable it
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            # Enable ANSI escape code processing
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return True


# ── ANSI color codes ──────────────────────────────────────────────────

class _Colors:
    """ANSI escape codes for terminal colors."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)

    def magenta(self, text: str) -> str:
        return self._wrap("35", text)

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def bold_white(self, text: str) -> str:
        return self._wrap("1;37", text)


# ── Score verdicts ────────────────────────────────────────────────────

_ENCOURAGEMENT = {
    "perfect": [
        "Accepted. All tests passed.",
    ],
    "almost": [
        "Close. A few tests still fail.",
    ],
    "good": [
        "Partial. Review the failing checks.",
    ],
    "early": [
        "Keep debugging. Most checks are still failing.",
    ],
}


def _get_encouragement(score: float) -> str:
    """Pick a one-line score verdict."""
    import random

    if score >= 1.0:
        messages = _ENCOURAGEMENT["perfect"]
    elif score >= 0.8:
        messages = _ENCOURAGEMENT["almost"]
    elif score >= 0.5:
        messages = _ENCOURAGEMENT["good"]
    else:
        messages = _ENCOURAGEMENT["early"]

    return random.choice(messages)


# ── Progress bar ──────────────────────────────────────────────────────

def _progress_bar(score: float, width: int = 10) -> str:
    """Create a Unicode block progress bar."""
    filled = round(score * width)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    pct = round(score * 100)
    return f"{bar}  {pct}%"


# ── Status symbols ────────────────────────────────────────────────────

_STATUS_SYMBOLS = {
    "pass": "✓",
    "fail": "✗",
    "skip": "○",
    "error": "⚠",
}


# ── Main render function ─────────────────────────────────────────────


def render(
    suite_result: SuiteResult,
    verbose: bool = False,
    no_color: bool = False,
    stream: TextIO = sys.stdout,
) -> None:
    """
    Render a SuiteResult to the terminal.

    This is the primary output function. It prints the checks, the score,
    and a one-line verdict.

    Args:
        suite_result: The complete suite result to render
        verbose: Show detailed logs and diffs on failure
        no_color: Force disable colors
        stream: Output stream (default: stdout)
    """
    use_color = not no_color and _supports_color(stream)
    c = _Colors(enabled=use_color)

    lines: list[str] = []

    # ── Header ─────────────────────────────────────────────────────
    lines.append("")
    title = f"Grade — {suite_result.topic}: {suite_result.problem}"
    lines.append(c.bold_white(title))
    lines.append(c.dim("─" * max(45, len(title) + 4)))
    lines.append("")

    # ── Check results ──────────────────────────────────────────────
    for check in suite_result.checks:
        line = _render_check(check, suite_result.mode, c, verbose)
        lines.extend(line)

    # ── Separator ──────────────────────────────────────────────────
    lines.append("")
    lines.append(c.dim("─" * 45))

    # ── Score ──────────────────────────────────────────────────────
    score_text = f"  Score: {suite_result.passed_points} / {suite_result.total_points}"
    bar = _progress_bar(suite_result.score)

    # Color the score line based on result
    if suite_result.score >= 1.0:
        score_line = c.green(f"{score_text}   {bar}")
    elif suite_result.score >= 0.5:
        score_line = c.yellow(f"{score_text}   {bar}")
    else:
        score_line = c.red(f"{score_text}   {bar}")

    lines.append(score_line)

    # ── Encouragement ──────────────────────────────────────────────
    lines.append("")
    encouragement = _get_encouragement(suite_result.score)
    lines.append(f"  {encouragement}")

    # ── Actionable advice ──────────────────────────────────────────
    failed_with_hints = [
        ch for ch in suite_result.checks
        if ch.status == "fail" and ch.hint
    ]
    if failed_with_hints and suite_result.score < 1.0:
        lines.append(c.dim("  Focus on the hints above and try again."))

    lines.append("")

    # Write all lines
    output = "\n".join(lines)
    stream.write(output)
    stream.flush()


def _render_check(
    check: CheckResult,
    mode: str,
    c: _Colors,
    verbose: bool,
) -> list[str]:
    """Render a single check result as a list of lines."""
    lines: list[str] = []

    symbol = _STATUS_SYMBOLS.get(check.status, "?")
    points_str = f"({check.points} pt{'s' if check.points != 1 else ''})"

    if check.status == "pass":
        lines.append(c.green(f"  {symbol}  {check.name:<40} {points_str}"))

    elif check.status == "fail":
        lines.append(c.red(f"  {symbol}  {check.name:<40} {points_str}"))

        # Show hint
        if check.hint:
            lines.append(c.yellow(f"     💡 Hint: {check.hint}"))

        # In practice mode, show expected vs actual
        if mode == "practice" and verbose and check.cause:
            lines.append(c.dim(f"     Cause: {check.cause}"))

        # In practice mode with verbose, show the log
        if mode == "practice" and verbose and check.log:
            for log_line in check.log:
                lines.append(c.dim(f"     │ {log_line}"))

    elif check.status == "skip":
        lines.append(c.yellow(f"  {symbol}  {check.name:<40} skipped"))

    elif check.status == "error":
        lines.append(c.magenta(f"  {symbol}  {check.name:<40} error"))
        if check.hint:
            lines.append(c.yellow(f"     💡 {check.hint}"))
        if verbose and check.cause:
            lines.append(c.dim(f"     Error: {check.cause}"))

    return lines


# ── Compilation error rendering ───────────────────────────────────────


def render_compile_error(
    friendly_error: str,
    raw_error: str = "",
    verbose: bool = False,
    no_color: bool = False,
    stream: TextIO = sys.stdout,
) -> None:
    """
    Render a compilation error to the terminal.

    Shows the friendly message by default. With ``--verbose``, also shows
    the raw compiler output.
    """
    use_color = not no_color and _supports_color(stream)
    c = _Colors(enabled=use_color)

    lines: list[str] = []
    lines.append("")
    lines.append(c.bold_white("Grade — Compilation"))
    lines.append(c.dim("─" * 45))
    lines.append("")
    lines.append(c.red(f"  ✗  {friendly_error}"))

    if verbose and raw_error:
        lines.append("")
        lines.append(c.dim("  Raw compiler output:"))
        for line in raw_error.strip().splitlines()[:20]:
            lines.append(c.dim(f"  │ {line}"))

    lines.append("")
    lines.append("  Keep going — syntax errors happen to everyone! 🌱")
    lines.append("")

    output = "\n".join(lines)
    stream.write(output)
    stream.flush()
