# Grade CLI — course files on a free GitHub organization.
# Copyright (C) 2026 Grade CLI contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Classroom files for Grade CLI.

GitHub Free is the target. These files do not ask for a Team or Enterprise
plan, and they do not use GitHub Pages. A later grader reads them from the
course repository with a reusable workflow.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
_ROLES = {"student", "teacher", "head_ta", "ta"}
_TEST_TYPES = {"io", "run", "python"}
MAX_CLASSROOM_SLUG = 40
MAX_REPO_PREFIX = 59

_ROSTER_HEADER = "github_id,username,email,first_name,last_name,section,role\n"


class CourseError(ValueError):
    """A classroom or assignment file cannot be written."""


def validate_slug(slug: str, *, limit: int = MAX_CLASSROOM_SLUG) -> str:
    if not SLUG_RE.match(slug) or len(slug) > limit:
        raise CourseError(
            "use lowercase words separated by hyphens, "
            f"at most {limit} characters"
        )
    return slug


def add_classroom(root: Path, slug: str, name: str) -> Path:
    slug = validate_slug(slug)
    title = name.strip()
    if not title:
        raise CourseError("name is required")
    folder = root / slug
    if folder.exists():
        raise CourseError(f"{slug} already exists")
    folder.mkdir(parents=True)
    _write_json(folder / "classroom.json", {
        "schema": "gradecli/classroom/v1",
        "name": title,
        "slug": slug,
        "plan": "free",
        "pages": False,
    })
    _write_json(folder / "assignments.json", {
        "schema": "gradecli/assignments/v1",
        "assignments": [],
    })
    (folder / "roster.csv").write_text(_ROSTER_HEADER, encoding="utf-8")
    return folder


def add_roster_row(
    root: Path,
    classroom: str,
    github_id: int,
    username: str,
    role: str = "student",
) -> None:
    path = _classroom_dir(root, classroom) / "roster.csv"
    if role not in _ROLES:
        raise CourseError("role must be student, teacher, head_ta, or ta")
    if not isinstance(github_id, int) or isinstance(github_id, bool) or github_id < 1:
        raise CourseError("github_id must be a positive integer")
    if not _USERNAME_RE.match(username):
        raise CourseError("username is not a GitHub login")
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines[1:]:
        if line.split(",")[0] == str(github_id):
            raise CourseError(f"{github_id} already on the roster")
    lines.append(f"{github_id},{username},,,,,{role}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_assignment(root: Path, classroom: str, slug: str, name: str) -> None:
    folder = _classroom_dir(root, classroom)
    path = folder / "assignments.json"
    if not path.is_file():
        raise CourseError(f"no classroom {classroom}")
    try:
        classroom_slug = json.loads((folder / "classroom.json").read_text(encoding="utf-8"))["slug"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise CourseError(f"no classroom {classroom}") from exc
    if not isinstance(classroom_slug, str):
        raise CourseError(f"no classroom {classroom}")
    prefix = len(classroom_slug) + 1
    validate_slug(slug, limit=MAX_REPO_PREFIX - prefix)
    title = name.strip()
    if not title:
        raise CourseError("name is required")
    data = json.loads(path.read_text(encoding="utf-8"))
    if any(item["slug"] == slug for item in data["assignments"]):
        raise CourseError(f"{slug} already exists")
    data["assignments"].append({
        "slug": slug,
        "name": title,
        "submission": "tag",
        "autograder": True,
        "tests": [],
    })
    _write_json(path, data)


def add_test(root: Path, classroom: str, assignment: str, test: dict) -> None:
    path = _classroom_dir(root, classroom) / "assignments.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    item = next((row for row in data["assignments"] if row["slug"] == assignment), None)
    if item is None:
        raise CourseError(f"no assignment {assignment}")
    name = str(test.get("name", "")).strip()
    kind = test.get("type")
    points = test.get("points")
    if not name:
        raise CourseError("test name is required")
    if kind not in _TEST_TYPES:
        raise CourseError("test type must be io, run, or python")
    if not isinstance(points, int) or isinstance(points, bool) or points < 0:
        raise CourseError("points must be a non-negative integer")
    if any(existing["name"] == name for existing in item["tests"]):
        raise CourseError(f"{name} already exists")
    stored = {"name": name, "type": kind, "points": points}
    for key in ("run", "expected", "input", "timeout"):
        if key in test and test[key] is not None:
            stored[key] = test[key]
    item["tests"].append(stored)
    _write_json(path, data)


def _classroom_dir(root: Path, classroom: str) -> Path:
    validate_slug(classroom)
    folder = root / classroom
    if not (folder / "classroom.json").is_file():
        raise CourseError(f"no classroom {classroom}")
    return folder


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
