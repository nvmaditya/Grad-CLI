"""`grade publish` splits one problem into a private tests tree and a public samples tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from gradbot.cli import main


def _problem(tmp_path: Path) -> Path:
    prob = tmp_path / "authoring" / "two_sum"
    (prob / "sample_solution").mkdir(parents=True)
    (prob / "expected").mkdir()
    (prob / "suite.yaml").write_text("problem:\n  name: Two Sum\n", encoding="utf-8")
    (prob / "statement.md").write_text("# Two Sum\n", encoding="utf-8")
    (prob / "checks.py").write_text("PUBLIC\n", encoding="utf-8")
    (prob / "checks_hidden.py").write_text("SECRET_9998\n", encoding="utf-8")
    (prob / "expected" / "big.txt").write_text("SECRET_ANSWER\n", encoding="utf-8")
    (prob / "sample_solution" / "solution.py").write_text("print(1)\n", encoding="utf-8")
    return prob


def _publish(prob: Path, tmp_path: Path, slug: str = "arrays/two_sum") -> int:
    with pytest.raises(SystemExit) as exc:
        main([
            "publish", str(prob),
            "--tests", str(tmp_path / "tests"),
            "--samples", str(tmp_path / "samples"),
            "--slug", slug,
        ])
    return exc.value.code


def _files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_publish_splits_the_problem(tmp_path, capsys):
    prob = _problem(tmp_path)
    assert _publish(prob, tmp_path) == 0
    assert _files(tmp_path / "samples") == [
        "arrays/two_sum/checks.py",
        "arrays/two_sum/statement.md",
        "arrays/two_sum/suite.yaml",
    ]
    assert _files(tmp_path / "tests") == [
        ".github/workflows/grade.yml",
        "arrays/two_sum/checks.py",
        "arrays/two_sum/checks_hidden.py",
        "arrays/two_sum/expected/big.txt",
        "arrays/two_sum/statement.md",
        "arrays/two_sum/suite.yaml",
    ]
    assert "checks_hidden.py stayed in the tests repo" in capsys.readouterr().out


@pytest.mark.parametrize("slug", ["../../escape", "/abs/path", "arrays", "arrays/two_sum/extra", "a b/c"])
def test_publish_refuses_a_slug_that_is_not_topic_problem(tmp_path, capsys, slug):
    prob = _problem(tmp_path)
    assert _publish(prob, tmp_path, slug) == 1
    assert "topic/problem" in capsys.readouterr().out
    assert not (tmp_path / "tests").exists()
    assert not (tmp_path / "escape").exists()


def test_publish_refuses_a_folder_that_is_not_a_problem(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _publish(empty, tmp_path) == 1
    assert "suite.yaml" in capsys.readouterr().out
    assert not (tmp_path / "tests").exists()


def test_publish_stops_if_the_samples_tree_already_holds_hidden_checks(tmp_path, capsys):
    prob = _problem(tmp_path)
    stray = tmp_path / "samples" / "graphs" / "dijkstra" / "checks_hidden.py"
    stray.parent.mkdir(parents=True)
    stray.write_text("LEAKED\n", encoding="utf-8")
    assert _publish(prob, tmp_path) == 1
    out = capsys.readouterr().out
    assert "graphs/dijkstra/checks_hidden.py" in out
