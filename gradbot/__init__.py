"""
GradBot — A CLI grading tool for coding-cohort students, mainly DSA and competitive programming.

This package provides the core grading engine and a public API
for check suite authors to write problem checks.
"""

__version__ = "1.0.0"

# ── Public API re-exports for check suite authors ──────────────────────
# These are used inside checks.py files:
#   import gradbot
#   @gradbot.check(...)
#   def test_basic():
#       result = gradbot.run(input="...")
#       gradbot.expect_output(result.stdout, "expected")

from gradbot.api import (
    CheckFailure,
    RunResult,
    expect_exit,
    expect_output,
    expect_sequence,
    file_exists,
    run,
)
from gradbot.loader import check

__all__ = [
    "__version__",
    "check",
    "run",
    "expect_output",
    "expect_exit",
    "expect_sequence",
    "file_exists",
    "CheckFailure",
    "RunResult",
]
