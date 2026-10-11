"""Student vs faculty views of a suite result.

Faculty gets the full dict. Students get the same summary, but each check
keeps only the fields safe to post: expected output lives in cause and log.
"""

from __future__ import annotations

from gradbot.result import SuiteResult

_STUDENT_CHECK_KEYS = (
    "name",
    "slug",
    "status",
    "description",
    "hint",
    "points",
    "duration_ms",
)


def faculty_payload(result: SuiteResult) -> dict:
    """Full suite dict, including cause and log."""
    return result.to_dict()


def student_payload(result: SuiteResult) -> dict:
    """Suite dict with cause and log stripped from every check."""
    payload = result.to_dict()
    payload["checks"] = [
        {key: check[key] for key in _STUDENT_CHECK_KEYS}
        for check in payload["checks"]
    ]
    return payload
