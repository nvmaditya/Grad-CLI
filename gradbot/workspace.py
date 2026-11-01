"""
Workspace utilities for GradBot.

Copy a student's folder without dotfiles or bytecode, and stage a private
copy that compilers may write into.
"""

from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


def copy_solution(source: Path, dest: Path) -> None:
    """Copy a student's folder into ``dest``, leaving out dotfiles and ``__pycache__``.

    ``.git`` and editor folders are skipped so a large repository history is
    never copied once per check.
    """
    dest.mkdir(parents=True, exist_ok=True)
    for item in Path(source).iterdir():
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(
                item, target, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".*", "__pycache__"),
            )
        else:
            shutil.copy2(item, target)


@contextmanager
def staged_solution(source: Path):
    """Yield a private copy of the student's folder that compilers may write into."""
    with tempfile.TemporaryDirectory(prefix="gradbot_stage_") as tmpdir:
        stage = Path(tmpdir) / "solution"
        copy_solution(Path(source), stage)
        yield stage
