"""Course files stay on the free-plan layout."""

import json
from pathlib import Path

import pytest

from gradbot.course import (
    CourseError,
    add_assignment,
    add_classroom,
    add_roster_row,
    add_test,
)


def test_add_classroom_writes_free_plan_files(tmp_path: Path):
    folder = add_classroom(tmp_path, "cs-fall", "CS Fall")
    meta = json.loads((folder / "classroom.json").read_text(encoding="utf-8"))
    assignments = json.loads((folder / "assignments.json").read_text(encoding="utf-8"))
    assert meta == {
        "schema": "gradecli/classroom/v1",
        "name": "CS Fall",
        "slug": "cs-fall",
        "plan": "free",
        "pages": False,
    }
    assert assignments["assignments"] == []
    assert (folder / "roster.csv").read_text(encoding="utf-8").startswith("github_id,")


def test_duplicate_classroom_is_refused(tmp_path: Path):
    add_classroom(tmp_path, "cs-fall", "CS Fall")
    with pytest.raises(CourseError, match="already exists"):
        add_classroom(tmp_path, "cs-fall", "Again")


def test_slug_must_be_a_repo_name(tmp_path: Path):
    with pytest.raises(CourseError):
        add_classroom(tmp_path, "CS Fall", "CS Fall")


def test_assignment_slug_fits_the_repo_name_budget(tmp_path: Path):
    add_classroom(tmp_path, "a" * 40, "Long")
    with pytest.raises(CourseError):
        add_assignment(tmp_path, "a" * 40, "b" * 20, "Too long")
    add_assignment(tmp_path, "a" * 40, "b" * 18, "Fits")


def test_course_add_from_the_cli(tmp_path: Path, capsys):
    from gradbot.cli import main

    main(["course", "add", "cs-fall", "--name", "CS Fall", "--root", str(tmp_path)])
    main([
        "assignment", "add", "cs-fall", "hello",
        "--name", "Hello", "--root", str(tmp_path),
    ])
    data = json.loads((tmp_path / "cs-fall" / "assignments.json").read_text(encoding="utf-8"))
    assert data["assignments"][0]["slug"] == "hello"
    assert data["assignments"][0]["submission"] == "tag"
    assert "Created" in capsys.readouterr().out


def test_roster_refuses_a_classroom_outside_the_course(tmp_path: Path):
    outside = tmp_path / "outside"
    add_classroom(outside, "cs-fall", "CS Fall")
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(CourseError):
        add_roster_row(root, str(outside / "cs-fall"), 42, "ada")
    text = (outside / "cs-fall" / "roster.csv").read_text(encoding="utf-8")
    assert text.splitlines() == ["github_id,username,email,first_name,last_name,section,role"]


def test_roster_row_records_the_student(tmp_path: Path):
    add_classroom(tmp_path, "cs-fall", "CS Fall")
    add_roster_row(tmp_path, "cs-fall", 42, "ada", "student")
    text = (tmp_path / "cs-fall" / "roster.csv").read_text(encoding="utf-8")
    assert text.splitlines()[1] == "42,ada,,,,,student"


def test_roster_rejects_a_duplicate_student(tmp_path: Path):
    add_classroom(tmp_path, "cs-fall", "CS Fall")
    add_roster_row(tmp_path, "cs-fall", 42, "ada")
    with pytest.raises(CourseError, match="already"):
        add_roster_row(tmp_path, "cs-fall", 42, "ada")


def test_assignment_test_records_name_and_points(tmp_path: Path):
    add_classroom(tmp_path, "cs-fall", "CS Fall")
    add_assignment(tmp_path, "cs-fall", "hello", "Hello")
    add_test(tmp_path, "cs-fall", "hello", {
        "name": "prints hello",
        "type": "io",
        "run": "./hello",
        "expected": "Hello",
        "points": 2,
    })
    data = json.loads((tmp_path / "cs-fall" / "assignments.json").read_text(encoding="utf-8"))
    meta = json.loads((tmp_path / "cs-fall" / "classroom.json").read_text(encoding="utf-8"))
    assert data["assignments"][0]["tests"] == [{
        "name": "prints hello",
        "type": "io",
        "points": 2,
        "run": "./hello",
        "expected": "Hello",
    }]
    assert meta["pages"] is False
    assert meta["plan"] == "free"


def test_assignment_test_name_is_unique(tmp_path: Path):
    add_classroom(tmp_path, "cs-fall", "CS Fall")
    add_assignment(tmp_path, "cs-fall", "hello", "Hello")
    body = {"name": "prints hello", "type": "run", "run": "gcc hello.c", "points": 1}
    add_test(tmp_path, "cs-fall", "hello", body)
    with pytest.raises(CourseError, match="already"):
        add_test(tmp_path, "cs-fall", "hello", body)


def test_cli_adds_a_roster_row_and_a_test(tmp_path: Path, capsys):
    from gradbot.cli import main

    root = str(tmp_path)
    main(["course", "add", "cs-fall", "--name", "CS Fall", "--root", root])
    main(["course", "roster-add", "cs-fall", "--id", "42", "--username", "ada", "--root", root])
    main(["assignment", "add", "cs-fall", "hello", "--name", "Hello", "--root", root])
    main([
        "assignment", "test-add", "cs-fall", "hello",
        "--name", "prints hello", "--type", "io", "--points", "2",
        "--run", "./hello", "--expected", "Hello", "--root", root,
    ])
    text = (tmp_path / "cs-fall" / "roster.csv").read_text(encoding="utf-8")
    data = json.loads((tmp_path / "cs-fall" / "assignments.json").read_text(encoding="utf-8"))
    assert "42,ada,,,,,student" in text.splitlines()
    assert data["assignments"][0]["tests"][0]["name"] == "prints hello"
    assert "Added ada" in capsys.readouterr().out
