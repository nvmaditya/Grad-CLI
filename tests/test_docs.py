"""The docs point at files and tests that exist."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted([*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md")])
_LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(doc: Path):
    text = doc.read_text(encoding="utf-8")
    # Links inside HTML comments (the demo TODO), code fences and inline code are not links.
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    broken = [
        target for target in _LINK.findall(text)
        if "://" not in target and not target.startswith("mailto:")
        and not (doc.parent / target).exists()
    ]
    assert broken == [], f"{doc.name} links to missing files: {broken}"


def _test_names() -> dict[str, set[str]]:
    """file name -> every test function and test class defined in it."""
    names: dict[str, set[str]] = {}
    for path in (ROOT / "tests").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names[path.name] = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }
    return names


def test_verification_report_cites_real_tests():
    text = (ROOT / "VERIFICATION_REPORT.md").read_text(encoding="utf-8")
    names = _test_names()
    missing = []
    for file, name in re.findall(r"(test_\w+\.py)::(\w+\*?)", text):
        assert file in names, f"VERIFICATION_REPORT cites {file}, which does not exist"
        if name.endswith("*"):
            if not any(n.startswith(name[:-1]) for n in names[file]):
                missing.append(f"{file}::{name}")
        elif name not in names[file]:
            missing.append(f"{file}::{name}")
    assert missing == []
    for file in set(re.findall(r"`(?:tests/)?(test_\w+\.py)`", text)):
        assert file in names, f"VERIFICATION_REPORT cites {file}, which does not exist"
