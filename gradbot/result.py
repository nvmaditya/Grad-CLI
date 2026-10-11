"""
Result dataclasses for GradBot.

Every check produces a CheckResult; every suite run produces a SuiteResult.
These are the core data types that flow through the entire system:
    runner.py → result.py → reporter.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


@dataclass(slots=True)
class CheckResult:
    """Result of a single check execution."""

    name: str                                          # human-readable check name
    slug: str                                          # machine identifier (function name)
    status: Literal["pass", "fail", "skip", "error"]   # outcome
    description: str                                   # what was being tested
    hint: str | None = None                            # student-facing hint on failure
    log: list[str] = field(default_factory=list)        # internal detail (--verbose only)
    cause: str | None = None                           # underlying exception or mismatch
    duration_ms: int = 0                               # execution time in milliseconds
    points: int = 1                                    # how many points this check is worth

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass(slots=True)
class SuiteResult:
    """Aggregate result for an entire problem suite."""

    problem: str                                       # e.g. "Two Sum"
    topic: str                                         # e.g. "Arrays & Strings"
    mode: Literal["practice", "submit"]                # practice shows details, submit hides
    checks: list[CheckResult] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── Computed properties ────────────────────────────────────────────

    @property
    def total_points(self) -> int:
        """Total possible points across all checks."""
        return sum(c.points for c in self.checks)

    @property
    def passed_points(self) -> int:
        """Points earned (only from passed checks)."""
        return sum(c.points for c in self.checks if c.passed)

    @property
    def total(self) -> int:
        """Total number of checks."""
        return len(self.checks)

    @property
    def passed(self) -> int:
        """Number of passed checks."""
        return sum(1 for c in self.checks if c.passed)

    @property
    def score(self) -> float:
        """Score as a fraction from 0.0 to 1.0."""
        if self.total_points == 0:
            return 0.0
        return self.passed_points / self.total_points

    # ── Serialization ──────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        return {
            "problem": self.problem,
            "topic": self.topic,
            "mode": self.mode,
            "score": round(self.score, 4),
            "total_points": self.total_points,
            "passed_points": self.passed_points,
            "total_checks": self.total,
            "passed_checks": self.passed,
            "timestamp": self.timestamp,
            "checks": [asdict(c) for c in self.checks],
        }

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_file(self, path: Path) -> None:
        """Save JSON results to a file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
