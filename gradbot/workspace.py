"""
Workspace utilities for GradBot.

Context managers for temporary working directories and directory changes.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def working_area(files: list[str | Path], name: str = ""):
    """
    Context manager that copies files to a temporary directory.

    Creates a temp dir, copies all specified files into it (preserving
    relative directory structure), and yields the path. The temp dir
    is cleaned up on exit.

    Args:
        files: files to copy into the working area (relative paths)
        name: optional subdirectory name within the temp dir

    Yields:
        Path to the working area directory

    Example::

        with working_area(["solution.py", "data/input.txt"], name="check") as area:
            # area is a Path to a temp dir containing the copied files
            subprocess.run(["python", str(area / "solution.py")])
    """
    with tempfile.TemporaryDirectory(prefix="gradbot_") as tmpdir:
        work_dir = Path(tmpdir) / name if name else Path(tmpdir)
        work_dir.mkdir(exist_ok=True)

        for f in files:
            f = Path(f)
            dest = (work_dir / f).absolute()
            dest.parent.mkdir(parents=True, exist_ok=True)
            if f.is_dir():
                shutil.copytree(f, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(f, dest)

        yield work_dir


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


@contextmanager
def cd(dest: str | Path):
    """
    Context manager for temporarily changing the working directory.

    Args:
        dest: the directory to change to

    Yields:
        The destination path (unchanged)

    Example::

        with cd("/tmp/workdir") as cwd:
            print(os.getcwd())  # /tmp/workdir
        # original directory is restored here
    """
    origin = os.getcwd()
    try:
        os.chdir(dest)
        yield Path(dest)
    finally:
        os.chdir(origin)
