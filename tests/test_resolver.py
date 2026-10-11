"""Tests for gradbot.resolver — slug parsing and git origin URL construction."""

import os
import pytest

from gradbot.resolver import parse_slug, resolve, SlugError, ResolvedSlug


class TestParseSlug:
    """Test slug parsing."""

    def test_practice_basic(self):
        result = parse_slug("practice/arrays/two_sum")
        assert result["mode"] == "practice"
        assert result["topic"] == "arrays"
        assert result["problem"] == "two_sum"
        assert result["ref"] == "main"

    def test_submit_basic(self):
        result = parse_slug("submit/trees/inorder")
        assert result["mode"] == "submit"
        assert result["topic"] == "trees"
        assert result["problem"] == "inorder"

    def test_with_ref(self):
        result = parse_slug("practice/arrays/two_sum@v2")
        assert result["ref"] == "v2"

    def test_with_branch_ref(self):
        result = parse_slug("submit/sorting/merge_sort@feature/new-tests")
        assert result["ref"] == "feature/new-tests"

    def test_with_commit_ref(self):
        result = parse_slug("practice/arrays/two_sum@abc123def")
        assert result["ref"] == "abc123def"

    def test_hyphenated_names(self):
        result = parse_slug("practice/linked-lists/reverse-list")
        assert result["topic"] == "linked-lists"
        assert result["problem"] == "reverse-list"

    def test_invalid_no_mode(self):
        with pytest.raises(SlugError):
            parse_slug("arrays/two_sum")

    def test_invalid_bad_mode(self):
        with pytest.raises(SlugError):
            parse_slug("test/arrays/two_sum")

    def test_invalid_too_few_parts(self):
        with pytest.raises(SlugError):
            parse_slug("practice/arrays")

    def test_invalid_empty(self):
        with pytest.raises(SlugError):
            parse_slug("")

    def test_strips_whitespace(self):
        result = parse_slug("  practice/arrays/two_sum  ")
        assert result["mode"] == "practice"


class TestResolve:
    """Test full slug resolution."""

    def test_practice_repo(self):
        resolved = resolve("practice/arrays/two_sum")
        assert resolved.mode == "practice"
        assert resolved.token is None  # public repo
        assert "github.com/GradBot/gradbot-problems-public" in resolved.git_origin
        assert resolved.git_origin.endswith(".git")

    def test_practice_no_token_in_url(self):
        resolved = resolve("practice/arrays/two_sum")
        assert "@" not in resolved.git_origin  # no token embedded

    def test_submit_does_not_clone_private_tests(self, monkeypatch):
        import gradbot.resolver as r
        monkeypatch.setattr(r, "GRADBOT_TOKEN", "ghp_test123")
        with pytest.raises(SlugError, match="does not download") as raised:
            resolve("submit/arrays/two_sum")
        text = str(raised.value)
        assert "ghp_test123" not in text
        assert "GRADBOT_TOKEN" not in text

    def test_env_var_override(self, monkeypatch):
        import gradbot.resolver as r
        monkeypatch.setattr(r, "GRADBOT_PUBLIC_REPO", "myorg/myrepo")
        resolved = resolve("practice/arrays/two_sum")
        assert "myorg/myrepo" in resolved.git_origin

    def test_cache_key_includes_ref(self):
        resolved = resolve("practice/arrays/two_sum")
        assert "main" in resolved.cache_key

    def test_problem_path(self):
        resolved = resolve("practice/arrays/two_sum")
        assert resolved.problem_path == "arrays/two_sum"

    def test_local_path(self):
        resolved = resolve("practice/arrays/two_sum")
        # local_path should be within GRADBOT_LOCAL_DIR
        assert "gradbot-problems-public" in str(resolved.local_path)
