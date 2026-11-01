"""Practice runs fetch the samples repo with real git. No network: the remote is a bare repo on disk."""

from __future__ import annotations

from pathlib import Path

import pytest

from gradbot.config import ConfigError
from gradbot.fetcher import FetchError, fetch
from gradbot.resolver import resolve
from tests.samples_repo import SamplesRepo, write_problem

V1_CHECKS = "import gradbot\n@gradbot.check('version one')\ndef v1(): pass\n"
V2_CHECKS = "import gradbot\n@gradbot.check('version two')\ndef v2(): pass\n"


@pytest.fixture
def samples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SamplesRepo:
    repo = SamplesRepo(tmp_path)
    write_problem(repo.work, "arrays/two_sum", checks=V1_CHECKS)
    repo.commit("v1")
    repo.publish()
    monkeypatch.setenv("GRADBOT_PUBLIC_REPO", str(repo.bare))
    return repo


def _checks_text(slug: str, offline: bool = False) -> str:
    folder = fetch(resolve(slug), offline=offline)
    return (folder / "checks.py").read_text(encoding="utf-8")


# ── config ────────────────────────────────────────────────────────────


def test_default_practice_repo_is_the_public_demo_course():
    assert resolve("practice/arrays/two_sum").repo == "nvmaditya/gradbot-course-samples"
    assert resolve("practice/arrays/two_sum").git_origin == (
        "https://github.com/nvmaditya/gradbot-course-samples.git"
    )


@pytest.mark.parametrize("value", ["just-a-name", "a/b/c", "owner/", "owner repo/x", "-x/y"])
def test_malformed_practice_repo_is_refused_by_name(monkeypatch, value):
    monkeypatch.setenv("GRADBOT_PUBLIC_REPO", value)
    with pytest.raises(ConfigError, match="GRADBOT_PUBLIC_REPO"):
        resolve("practice/arrays/two_sum")


@pytest.mark.parametrize(
    "value",
    ["https://gitlab.com/acme/samples.git", "file:///srv/samples.git", "git@github.com:acme/samples.git"],
)
def test_practice_repo_may_be_a_url(monkeypatch, value):
    monkeypatch.setenv("GRADBOT_PUBLIC_REPO", value)
    assert resolve("practice/arrays/two_sum").git_origin == value


def test_practice_repo_may_be_a_local_path(monkeypatch, tmp_path):
    monkeypatch.setenv("GRADBOT_PUBLIC_REPO", str(tmp_path / "samples.git"))
    assert resolve("practice/arrays/two_sum").git_origin == str(tmp_path / "samples.git")


def test_cache_lives_under_gradbot_local_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("GRADBOT_LOCAL_DIR", str(tmp_path / "cache"))
    path = resolve("practice/arrays/two_sum").local_path
    assert path == tmp_path / "cache" / "nvmaditya" / "gradbot-course-samples"


# ── fetching ──────────────────────────────────────────────────────────


def test_first_fetch_gets_the_problem(samples):
    assert _checks_text("practice/arrays/two_sum") == V1_CHECKS


def test_second_fetch_picks_up_new_commits(samples):
    _checks_text("practice/arrays/two_sum")
    write_problem(samples.work, "arrays/two_sum", checks=V2_CHECKS)
    samples.commit("v2")
    samples.publish()
    assert _checks_text("practice/arrays/two_sum") == V2_CHECKS


def test_tag_ref_gets_the_tagged_content_not_main(samples):
    from tests.samples_repo import git

    git("tag", "v1", cwd=samples.work)
    write_problem(samples.work, "arrays/two_sum", checks=V2_CHECKS)
    samples.commit("v2")
    samples.publish()

    assert _checks_text("practice/arrays/two_sum") == V2_CHECKS
    assert _checks_text("practice/arrays/two_sum@v1") == V1_CHECKS


def test_commit_ref_gets_that_commit(samples):
    from tests.samples_repo import git

    first = git("rev-parse", "HEAD", cwd=samples.work)
    write_problem(samples.work, "arrays/two_sum", checks=V2_CHECKS)
    samples.commit("v2")
    samples.publish()
    git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=samples.bare)

    assert _checks_text("practice/arrays/two_sum") == V2_CHECKS
    assert _checks_text(f"practice/arrays/two_sum@{first}") == V1_CHECKS


def test_branch_ref_with_a_slash(samples):
    from tests.samples_repo import git

    git("checkout", "-q", "-b", "feature/new-tests", cwd=samples.work)
    write_problem(samples.work, "arrays/two_sum", checks=V2_CHECKS)
    samples.commit("branch")
    samples.publish()

    assert _checks_text("practice/arrays/two_sum@feature/new-tests") == V2_CHECKS
    assert _checks_text("practice/arrays/two_sum") == V1_CHECKS


def test_unknown_ref_is_an_error_and_never_falls_back_to_main(samples):
    _checks_text("practice/arrays/two_sum")  # main is now cached
    with pytest.raises(FetchError, match="v9"):
        _checks_text("practice/arrays/two_sum@v9")


def test_missing_repo_is_not_reported_as_a_network_problem(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADBOT_PUBLIC_REPO", str(tmp_path / "no-such-repo.git"))
    with pytest.raises(FetchError) as raised:
        _checks_text("practice/arrays/two_sum")
    text = str(raised.value)
    assert "Couldn't find" in text
    assert "internet" not in text


def test_failed_first_fetch_leaves_no_cache_behind(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADBOT_PUBLIC_REPO", str(tmp_path / "no-such-repo.git"))
    resolved = resolve("practice/arrays/two_sum")
    with pytest.raises(FetchError):
        fetch(resolved)
    assert not resolved.local_path.exists()


def test_missing_problem_names_the_repo(samples):
    with pytest.raises(FetchError) as raised:
        _checks_text("practice/graphs/dijkstra")
    assert "graphs/dijkstra" in str(raised.value)
    assert str(samples.bare) in str(raised.value)


def test_offline_uses_the_cached_copy(samples):
    _checks_text("practice/arrays/two_sum")
    write_problem(samples.work, "arrays/two_sum", checks=V2_CHECKS)
    samples.commit("v2")
    samples.publish()
    assert _checks_text("practice/arrays/two_sum", offline=True) == V1_CHECKS


def test_offline_without_a_cache_says_so(samples):
    with pytest.raises(FetchError, match="offline"):
        _checks_text("practice/arrays/two_sum", offline=True)


def test_offline_with_a_different_ref_cached_does_not_substitute_it(samples):
    _checks_text("practice/arrays/two_sum")  # caches main only
    with pytest.raises(FetchError, match="offline"):
        _checks_text("practice/arrays/two_sum@v1", offline=True)


def test_network_failure_falls_back_to_the_cache_with_a_warning(tmp_path, monkeypatch, capsys):
    repo = SamplesRepo(tmp_path)
    write_problem(repo.work, "arrays/two_sum", checks=V1_CHECKS)
    repo.commit()
    repo.publish()
    monkeypatch.setenv("GRADBOT_PUBLIC_REPO", "acme/samples")
    # git rewrites the GitHub URL: first to the bare repo, then to a dead port.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{repo.bare.parent.parent.as_uri()}/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/")
    assert _checks_text("practice/arrays/two_sum") == V1_CHECKS

    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.http://127.0.0.1:9/.insteadOf")
    assert _checks_text("practice/arrays/two_sum") == V1_CHECKS
    assert "Using the copy downloaded earlier" in capsys.readouterr().err


def test_network_failure_without_a_cache_says_to_check_the_connection(monkeypatch):
    monkeypatch.setenv("GRADBOT_PUBLIC_REPO", "acme/samples")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.http://127.0.0.1:9/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/")
    with pytest.raises(FetchError, match="internet connection"):
        _checks_text("practice/arrays/two_sum")


def test_git_never_waits_for_a_password(monkeypatch):
    from gradbot.git import _git_env

    monkeypatch.delenv("GIT_TERMINAL_PROMPT", raising=False)
    assert _git_env()["GIT_TERMINAL_PROMPT"] == "0"
