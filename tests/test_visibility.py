"""Tests for gradbot.visibility — student vs faculty payloads."""

import json

from gradbot.result import CheckResult, SuiteResult
from gradbot.visibility import faculty_payload, student_payload

SECRET = "SECRET_9998"


def _failed_suite() -> SuiteResult:
    check = CheckResult(
        name="Hidden case",
        slug="hidden_case",
        status="fail",
        description="large input",
        hint="Try a hash map",
        log=[f"Expected: '{SECRET}'"],
        cause=f"Expected {SECRET}, got 0 1",
    )
    return SuiteResult(
        problem="Two Sum",
        topic="Arrays",
        mode="submit",
        checks=[check],
    )


def test_student_payload_hides_secret_keeps_hint():
    result = _failed_suite()
    payload = student_payload(result)
    dumped = json.dumps(payload)

    assert SECRET not in dumped
    assert payload["checks"][0]["hint"] == "Try a hash map"
    assert set(payload["checks"][0]) == {
        "name",
        "slug",
        "status",
        "description",
        "hint",
        "points",
        "duration_ms",
    }


def test_faculty_payload_keeps_secret():
    result = _failed_suite()
    payload = faculty_payload(result)

    assert payload == result.to_dict()
    assert SECRET in json.dumps(payload)
