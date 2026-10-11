"""
Public API for GradBot check suite authors.

This module provides the functions that check authors use inside ``checks.py``
to run student programs and validate their output. Example::

    import gradbot

    @gradbot.check("Basic case works", points=1)
    def test_basic():
        result = gradbot.run(input="4\\n2 7 11 15\\n9\\n")
        gradbot.expect_output(result.stdout.strip(), "0 1")

Student programs run through ``subprocess.run``. Input is provided all at once
via stdin pipe, which is sufficient for DSA problems.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from gradbot.sandbox import container_argv


class CheckFailure(Exception):
    """
    Raised inside a check to signal failure.

    The ``hint`` is shown to the student. In submit mode, this is the ONLY
    information they get — no diffs, no expected output.
    """

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.hint = hint
        self.expected: str | None = None
        self.actual: str | None = None


class OutputMismatch(CheckFailure):
    """Raised when expected output doesn't match actual output."""

    def __init__(
        self,
        expected: str,
        actual: str,
        hint: str | None = None,
        mode: str = "exact",
    ):
        if hint is None:
            hint = "Your output doesn't match what was expected. Check the format!"
        super().__init__(
            f"Expected {_truncate(expected)}, got {_truncate(actual)}",
            hint=hint,
        )
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True)
class RunResult:
    """Result of running a student's program."""

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


# ── Thread-local state for the current check context ──────────────────
# Set by runner.py before each check executes
_context = threading.local()


def _get_context():
    """Get the current check execution context."""
    return {
        "solution_dir": getattr(_context, "solution_dir", None),
        "run_command": getattr(_context, "run_command", None),
        "work_dir": getattr(_context, "work_dir", None),
        "sandbox": getattr(_context, "sandbox", None),
    }


def set_context(
    solution_dir: Path,
    run_command: list[str],
    work_dir: Path,
    sandbox: str | None = None,
) -> None:
    """Set the context for the current check. Called by runner.py."""
    _context.solution_dir = solution_dir
    _context.run_command = run_command
    _context.work_dir = work_dir
    _context.sandbox = sandbox


def clear_context() -> None:
    """Clear the current check context."""
    _context.solution_dir = None
    _context.run_command = None
    _context.work_dir = None
    _context.sandbox = None


# ── Public API functions ──────────────────────────────────────────────


def run(input: str = "", timeout: float = 5.0, args: list[str] | None = None) -> RunResult:
    """
    Run the student's program with the given stdin input.

    Args:
        input: String to feed to stdin (newlines separate lines)
        timeout: Maximum seconds to wait before killing the process
        args: Additional command-line arguments to pass to the program

    Returns:
        RunResult with stdout, stderr, exit_code, and timed_out flag

    Raises:
        CheckFailure: if there's no program to run (context not set)
    """
    ctx = _get_context()
    cmd = ctx["run_command"]
    work_dir = ctx["work_dir"]

    if not cmd:
        raise CheckFailure(
            "No program to run — check that your code compiled successfully.",
            hint="Make sure your solution file is in the right place!",
        )

    full_cmd = list(cmd)
    if args:
        full_cmd.extend(args)
    if ctx["sandbox"] == "docker":
        full_cmd = container_argv(Path(work_dir), full_cmd)

    timed_out = False
    try:
        result = subprocess.run(
            full_cmd,
            input=input,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(work_dir),
        )
        return RunResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as e:
        return RunResult(
            stdout=e.stdout or "" if isinstance(e.stdout, str) else (e.stdout.decode("utf-8", errors="replace") if e.stdout else ""),
            stderr=e.stderr or "" if isinstance(e.stderr, str) else (e.stderr.decode("utf-8", errors="replace") if e.stderr else ""),
            exit_code=-1,
            timed_out=True,
        )
    except OSError as e:
        raise CheckFailure(
            f"Couldn't run the program: {e}",
            hint="Something went wrong trying to run your code. Ask your teacher for help!",
        )


def expect_output(
    actual: str,
    expected: str,
    mode: Literal["exact", "contains", "regex"] = "exact",
    hint: str | None = None,
) -> None:
    """
    Assert that the actual output matches the expected output.

    Args:
        actual: The actual output from the student's program
        expected: The expected output
        mode: Matching mode:
            - "exact": strings must match exactly (after stripping)
            - "contains": expected must appear somewhere in actual
            - "regex": expected is treated as a regex pattern
        hint: Optional student-facing hint on failure

    Raises:
        OutputMismatch: if the output doesn't match
    """
    if mode == "exact":
        if actual.strip() == expected.strip():
            return
    elif mode == "contains":
        if expected in actual:
            return
    elif mode == "regex":
        if re.search(expected, actual):
            return
    else:
        raise ValueError(f"Unknown match mode: {mode}")

    raise OutputMismatch(expected, actual, hint=hint, mode=mode)


def expect_exit(result: RunResult, code: int = 0, hint: str | None = None) -> None:
    """
    Assert that the program exited with the given exit code.

    Args:
        result: RunResult from a previous ``run()`` call
        code: Expected exit code (default: 0)
        hint: Optional hint on failure

    Raises:
        CheckFailure: if exit code doesn't match or program timed out
    """
    if result.timed_out:
        raise CheckFailure(
            f"Program timed out (expected exit code {code})",
            hint=hint or "Your program took too long! Make sure it exits cleanly.",
        )

    if result.exit_code != code:
        raise CheckFailure(
            f"Expected exit code {code}, got {result.exit_code}",
            hint=hint or (
                f"Your program exited with code {result.exit_code} instead of {code}.\n"
                "An exit code of 0 means success. Check for errors in your code!"
            ),
        )


def file_exists(filename: str, hint: str | None = None) -> None:
    """
    Assert that a file exists in the solution directory.

    Args:
        filename: Name of the file to check for
        hint: Optional hint on failure

    Raises:
        CheckFailure: if the file doesn't exist
    """
    ctx = _get_context()
    work_dir = ctx["work_dir"]

    if work_dir is None:
        raise CheckFailure("Internal error: no working directory set.")

    filepath = Path(work_dir) / filename
    if not filepath.exists():
        raise CheckFailure(
            f"File '{filename}' not found",
            hint=hint or f"Make sure you have a file called '{filename}' in your solution folder.",
        )


def expect_sequence(
    actual: str,
    expected: list,
    hint: str | None = None,
) -> None:
    """
    Assert that the output matches an expected sequence of values.

    Parses the actual output as space/newline-separated tokens and
    compares them to the expected list.

    Args:
        actual: Output string from the student's program
        expected: Expected list of values
        hint: Optional hint on failure

    Raises:
        OutputMismatch: if the sequences don't match
    """
    # Parse actual output into tokens
    actual_tokens = actual.strip().split()
    expected_tokens = [str(v) for v in expected]

    if actual_tokens == expected_tokens:
        return

    raise OutputMismatch(
        " ".join(expected_tokens),
        " ".join(actual_tokens),
        hint=hint or "Your output sequence doesn't match. Check the order and values!",
    )


# ── Internal helpers ──────────────────────────────────────────────────


def _truncate(s: str, max_len: int = 80) -> str:
    """Truncate a string for display in error messages."""
    s = repr(s)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s
