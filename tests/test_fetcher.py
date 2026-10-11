"""Tests for gradbot.fetcher — git-based test suite fetching."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from gradbot.fetcher import fetch, fetch_local, FetchError
from gradbot.git import GitError
from gradbot.resolver import ResolvedSlug


def _make_slug(
    mode="practice",
    topic="arrays",
    problem="two_sum",
    ref="main",
    repo="GradBot/gradbot-problems-public",
    token=None,
) -> ResolvedSlug:
    """Helper to create a ResolvedSlug for tests."""
    return ResolvedSlug(
        mode=mode,
        topic=topic,
        problem=problem,
        ref=ref,
        repo=repo,
        token=token,
        raw_slug=f"{mode}/{topic}/{problem}",
    )


@pytest.fixture(autouse=True)
def _use_tmp_local_dir(tmp_path, monkeypatch):
    """Redirect GRADBOT_LOCAL_DIR to a temp path for all tests."""
    import gradbot.resolver as resolver_mod
    monkeypatch.setattr(resolver_mod, "GRADBOT_LOCAL_DIR", tmp_path / "local")


class TestFetch:
    """Tests for the fetch() function."""

    @patch("gradbot.fetcher.clone_or_update")
    def test_success(self, mock_clone):
        """Successful fetch returns the problem directory path."""
        resolved = _make_slug()

        # Set up the local path with the problem directory
        local_path = resolved.local_path
        problem_dir = local_path / "arrays" / "two_sum"
        problem_dir.mkdir(parents=True, exist_ok=True)

        mock_clone.return_value = local_path

        result = fetch(resolved)
        assert result == problem_dir

        mock_clone.assert_called_once_with(
            origin=resolved.git_origin,
            local_path=resolved.local_path,
            branch="main",
            offline=False,
        )

    @patch("gradbot.fetcher.clone_or_update")
    def test_problem_not_found(self, mock_clone):
        """Raises FetchError when problem dir doesn't exist in repo."""
        resolved = _make_slug()

        # Create the local path but NOT the problem directory
        local_path = resolved.local_path
        local_path.mkdir(parents=True, exist_ok=True)

        mock_clone.return_value = local_path

        with pytest.raises(FetchError, match="Couldn't find the problem"):
            fetch(resolved)

    @patch("gradbot.fetcher.clone_or_update")
    def test_offline_mode(self, mock_clone):
        """Offline mode passes offline=True to clone_or_update."""
        resolved = _make_slug()

        local_path = resolved.local_path
        problem_dir = local_path / "arrays" / "two_sum"
        problem_dir.mkdir(parents=True, exist_ok=True)

        mock_clone.return_value = local_path

        fetch(resolved, offline=True)

        mock_clone.assert_called_once_with(
            origin=resolved.git_origin,
            local_path=resolved.local_path,
            branch="main",
            offline=True,
        )

    @patch("gradbot.fetcher.clone_or_update")
    def test_network_failure_with_stale_cache(self, mock_clone, capsys):
        """Falls back to stale cache on network failure."""
        resolved = _make_slug()

        # Create a stale local repo with the problem dir
        local_path = resolved.local_path
        problem_dir = local_path / "arrays" / "two_sum"
        problem_dir.mkdir(parents=True, exist_ok=True)

        mock_clone.side_effect = GitError("Could not resolve host")

        result = fetch(resolved, offline=False)
        assert result == problem_dir

        # Should print a warning
        captured = capsys.readouterr()
        assert "Couldn't reach GitHub" in captured.err

    @patch("gradbot.fetcher.clone_or_update")
    def test_offline_no_cache(self, mock_clone):
        """Raises FetchError in offline mode with no cached repo."""
        resolved = _make_slug()

        mock_clone.side_effect = GitError("offline and no cache")

        # local_path doesn't exist (fresh tmp_path)
        with pytest.raises(FetchError, match="offline mode"):
            fetch(resolved, offline=True)

    @patch("gradbot.fetcher.clone_or_update")
    def test_auth_failure(self, mock_clone):
        """Raises FetchError with auth message on authentication errors."""
        resolved = _make_slug(mode="submit", token="bad_token",
                              repo="GradBot/gradbot-problems-private")

        mock_clone.side_effect = GitError(
            "Git command failed",
            stderr="fatal: Authentication failed for 'https://github.com/...'"
        )

        # local_path doesn't exist (fresh tmp_path)
        with pytest.raises(FetchError, match="authentication"):
            fetch(resolved, offline=False)


class TestFetchLocal:
    """Tests for the fetch_local() function."""

    def test_valid_suite(self, tmp_path):
        """Returns the path when suite.yaml and checks.py exist."""
        suite = tmp_path / "my_problem"
        suite.mkdir()
        (suite / "suite.yaml").write_text("problem:\n  name: Test\n")
        (suite / "checks.py").write_text("# checks\n")

        result = fetch_local(suite)
        assert result == suite.resolve()

    def test_missing_directory(self, tmp_path):
        """Raises FetchError for nonexistent directory."""
        with pytest.raises(FetchError, match="Directory not found"):
            fetch_local(tmp_path / "nope")

    def test_missing_suite_yaml(self, tmp_path):
        """Raises FetchError when suite.yaml is missing."""
        suite = tmp_path / "incomplete"
        suite.mkdir()
        (suite / "checks.py").write_text("# checks\n")

        with pytest.raises(FetchError, match="Missing suite.yaml"):
            fetch_local(suite)

    def test_missing_checks_py(self, tmp_path):
        """Raises FetchError when checks.py is missing."""
        suite = tmp_path / "incomplete"
        suite.mkdir()
        (suite / "suite.yaml").write_text("problem:\n  name: Test\n")

        with pytest.raises(FetchError, match="Missing checks.py"):
            fetch_local(suite)
