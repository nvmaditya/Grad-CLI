"""Hidden checks stay out of the public load and the student bundle."""

from pathlib import Path

import pytest

from gradbot.loader import LoadError, guard_student_suite, load_checks, public_bundle_files


def _suite(directory: Path) -> None:
    (directory / "suite.yaml").write_text(
        "problem:\n  name: Hidden Split\n",
        encoding="utf-8",
    )


def _check(path: Path, name: str, slug: str) -> None:
    path.write_text(
        "import gradbot\n\n"
        f'@gradbot.check("{name}")\n'
        f"def {slug}():\n"
        "    pass\n",
        encoding="utf-8",
    )


def test_public_and_hidden_checks_load_separately(tmp_path):
    _suite(tmp_path)
    _check(tmp_path / "checks.py", "Public addition works", "test_public")
    _check(tmp_path / "checks_hidden.py", "Hidden edge case", "test_hidden_secret")

    _, public = load_checks(tmp_path)
    _, hidden = load_checks(tmp_path, checks_filename="checks_hidden.py")

    public_names = [c.name for c in public]
    hidden_names = [c.name for c in hidden]
    assert public_names == ["Public addition works"]
    assert "Hidden edge case" not in public_names
    assert hidden_names == ["Hidden edge case"]
    assert "Public addition works" not in hidden_names


def test_guard_student_suite_rejects_hidden_checks(tmp_path):
    (tmp_path / "checks_hidden.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(LoadError, match="checks_hidden.py"):
        guard_student_suite(tmp_path)


def test_guard_student_suite_allows_public_only(tmp_path):
    assert guard_student_suite(tmp_path) is None


def test_public_bundle_files_keeps_public_names_only(tmp_path):
    _suite(tmp_path)
    (tmp_path / "statement.md").write_text("# Problem\n", encoding="utf-8")
    (tmp_path / "checks.py").write_text("# public\n", encoding="utf-8")
    (tmp_path / "checks_hidden.py").write_text("# hidden\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("nope\n", encoding="utf-8")
    sample = tmp_path / "sample_solution"
    sample.mkdir()
    (sample / "solution.py").write_text("pass\n", encoding="utf-8")

    names = [path.name for path in public_bundle_files(tmp_path)]

    assert names == ["suite.yaml", "statement.md", "checks.py"]
    assert all(isinstance(path, Path) for path in public_bundle_files(tmp_path))
