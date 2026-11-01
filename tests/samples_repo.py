"""Build throwaway samples repos on disk so practice runs need no network."""

from __future__ import annotations

import subprocess
from pathlib import Path

TWO_SUM_SUITE = 'problem:\n  name: "Two Sum"\n  topic: "Arrays"\n'

TWO_SUM_CHECKS = """\
import gradbot

@gradbot.check("basic", points=1, hint="Use a hash map")
def test_basic():
    gradbot.expect_output(gradbot.run(input="4\\n2 7 11 15\\n9\\n").stdout, "0 1")
"""

TWO_SUM_SOLUTION = """\
n = int(input())
nums = list(map(int, input().split()))
target = int(input())
seen = {}
for i, num in enumerate(nums):
    if target - num in seen:
        print(seen[target - num], i)
        break
    seen[num] = i
"""


def git(*args: str, cwd: Path) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, capture_output=True, text=True, check=True,
    )
    return done.stdout.strip()


def write_problem(root: Path, slug: str, checks: str = TWO_SUM_CHECKS, suite: str = TWO_SUM_SUITE) -> None:
    folder = root / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "suite.yaml").write_text(suite, encoding="utf-8")
    (folder / "checks.py").write_text(checks, encoding="utf-8")


class SamplesRepo:
    """A working tree plus a bare clone that plays the role of GitHub."""

    def __init__(self, base: Path):
        self.work = base / "samples-src"
        self.bare = base / "remotes" / "acme" / "samples.git"
        self.work.mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=self.work)

    def commit(self, message: str = "update") -> str:
        git("add", "-A", cwd=self.work)
        git("commit", "-q", "-m", message, cwd=self.work)
        return git("rev-parse", "HEAD", cwd=self.work)

    def publish(self) -> None:
        """Push every branch and tag to the bare 'remote'."""
        if not self.bare.exists():
            self.bare.parent.mkdir(parents=True, exist_ok=True)
            git("init", "-q", "--bare", str(self.bare), cwd=self.work.parent)
        git("push", "-q", "--force", "--tags", str(self.bare), "refs/heads/*:refs/heads/*", cwd=self.work)
