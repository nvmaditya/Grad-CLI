"""Loading suite.yaml and checks.py, and ordering checks by dependency."""

from __future__ import annotations

from pathlib import Path

import pytest

from gradbot.loader import LoadError, load_checks, load_suite_config


def _suite(tmp_path: Path, checks: str, suite: str = 'problem:\n  name: "P"\n  topic: "T"\n') -> Path:
    (tmp_path / "suite.yaml").write_text(suite, encoding="utf-8")
    (tmp_path / "checks.py").write_text(checks, encoding="utf-8")
    return tmp_path


def _names(tmp_path: Path, checks: str) -> list[str]:
    _, ordered = load_checks(_suite(tmp_path, checks))
    return [c.slug for c in ordered]


# ── ordering ──────────────────────────────────────────────────────────


def test_independent_checks_keep_declaration_order(tmp_path):
    checks = (
        "import gradbot\n"
        "@gradbot.check('c')\ndef c(): pass\n"
        "@gradbot.check('a')\ndef a(): pass\n"
        "@gradbot.check('b')\ndef b(): pass\n"
    )
    assert _names(tmp_path, checks) == ["c", "a", "b"]


def test_a_dependency_runs_before_its_dependents(tmp_path):
    checks = (
        "import gradbot\n"
        "@gradbot.check('edge', depends_on='basic')\ndef edge(): pass\n"
        "@gradbot.check('perf', depends_on='basic')\ndef perf(): pass\n"
        "@gradbot.check('basic')\ndef basic(): pass\n"
    )
    assert _names(tmp_path, checks) == ["basic", "edge", "perf"]


def test_chain_of_dependencies(tmp_path):
    checks = (
        "import gradbot\n"
        "@gradbot.check('3', depends_on='two')\ndef three(): pass\n"
        "@gradbot.check('2', depends_on='one')\ndef two(): pass\n"
        "@gradbot.check('1')\ndef one(): pass\n"
    )
    assert _names(tmp_path, checks) == ["one", "two", "three"]


# ── refused check files ───────────────────────────────────────────────


def test_cycle_is_refused_with_the_names_involved(tmp_path):
    checks = (
        "import gradbot\n"
        "@gradbot.check('a', depends_on='b')\ndef a(): pass\n"
        "@gradbot.check('b', depends_on='a')\ndef b(): pass\n"
    )
    with pytest.raises(LoadError, match="Circular dependency") as raised:
        load_checks(_suite(tmp_path, checks))
    assert "a" in str(raised.value) and "b" in str(raised.value)


def test_self_dependency_is_a_cycle(tmp_path):
    checks = "import gradbot\n@gradbot.check('a', depends_on='a')\ndef a(): pass\n"
    with pytest.raises(LoadError, match="Circular dependency"):
        load_checks(_suite(tmp_path, checks))


def test_unknown_dependency_is_refused(tmp_path):
    checks = "import gradbot\n@gradbot.check('a', depends_on='nope')\ndef a(): pass\n"
    with pytest.raises(LoadError, match="depends on 'nope'"):
        load_checks(_suite(tmp_path, checks))


def test_two_checks_with_the_same_function_name_are_refused_by_name(tmp_path):
    checks = (
        "import gradbot\n"
        "@gradbot.check('first')\ndef test_basic(): pass\n"
        "@gradbot.check('second')\ndef test_basic(): pass\n"
    )
    with pytest.raises(LoadError, match="test_basic") as raised:
        load_checks(_suite(tmp_path, checks))
    assert "Circular" not in str(raised.value)


def test_negative_points_are_refused(tmp_path):
    checks = "import gradbot\n@gradbot.check('a', points=-1)\ndef a(): pass\n"
    with pytest.raises(LoadError, match="points"):
        load_checks(_suite(tmp_path, checks))


def test_checks_file_with_a_syntax_error(tmp_path):
    with pytest.raises(LoadError, match="Error importing checks.py"):
        load_checks(_suite(tmp_path, "import gradbot\ndef broken(:\n"))


def test_checks_file_that_raises_on_import(tmp_path):
    with pytest.raises(LoadError, match="ZeroDivisionError"):
        load_checks(_suite(tmp_path, "1 / 0\n"))


def test_checks_file_without_checks(tmp_path):
    with pytest.raises(LoadError, match="No checks found"):
        load_checks(_suite(tmp_path, "import gradbot\n"))


def test_missing_checks_file(tmp_path):
    (tmp_path / "suite.yaml").write_text("problem: {}\n", encoding="utf-8")
    with pytest.raises(LoadError, match="Missing checks.py"):
        load_checks(tmp_path)


def test_a_failed_import_does_not_leak_checks_into_the_next_load(tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    good = tmp_path / "good"
    good.mkdir()
    _suite(bad, "import gradbot\n@gradbot.check('leak')\ndef leak(): pass\nraise RuntimeError('x')\n")
    _suite(good, "import gradbot\n@gradbot.check('ok')\ndef ok(): pass\n")

    with pytest.raises(LoadError):
        load_checks(bad)
    _, ordered = load_checks(good)

    assert [c.slug for c in ordered] == ["ok"]


# ── suite.yaml ────────────────────────────────────────────────────────


def test_missing_suite_yaml_is_a_load_error(tmp_path):
    with pytest.raises(LoadError, match="Missing suite.yaml"):
        load_suite_config(tmp_path)


def test_empty_suite_yaml_uses_defaults(tmp_path):
    (tmp_path / "suite.yaml").write_text("", encoding="utf-8")
    config = load_suite_config(tmp_path)
    assert (config.name, config.topic) == ("Unnamed Problem", "General")


def test_null_sections_use_defaults(tmp_path):
    (tmp_path / "suite.yaml").write_text("problem:\nscoring:\nhints:\n", encoding="utf-8")
    assert load_suite_config(tmp_path).name == "Unnamed Problem"


def test_malformed_yaml_is_a_load_error(tmp_path):
    (tmp_path / "suite.yaml").write_text("problem: [unclosed\n", encoding="utf-8")
    with pytest.raises(LoadError, match="suite.yaml"):
        load_suite_config(tmp_path)


def test_suite_yaml_that_is_a_list_is_a_load_error(tmp_path):
    (tmp_path / "suite.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(LoadError, match="mapping"):
        load_suite_config(tmp_path)


def test_problem_section_that_is_a_string_is_a_load_error(tmp_path):
    (tmp_path / "suite.yaml").write_text("problem: Two Sum\n", encoding="utf-8")
    with pytest.raises(LoadError, match="problem"):
        load_suite_config(tmp_path)


def test_unicode_problem_name(tmp_path):
    (tmp_path / "suite.yaml").write_text('problem:\n  name: "Somme à deux — 两数之和"\n', encoding="utf-8")
    assert load_suite_config(tmp_path).name == "Somme à deux — 两数之和"


def test_checks_can_read_data_files_next_to_them(tmp_path):
    (tmp_path / "expected").mkdir()
    (tmp_path / "expected" / "large.txt").write_text("42\n", encoding="utf-8")
    checks = (
        "from pathlib import Path\n"
        "import gradbot\n"
        "EXPECTED = (Path(__file__).parent / 'expected' / 'large.txt').read_text().strip()\n"
        "@gradbot.check('reads data')\n"
        "def reads():\n"
        "    assert EXPECTED == '42'\n"
    )
    _, ordered = load_checks(_suite(tmp_path, checks))
    ordered[0].func()
