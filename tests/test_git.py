"""Tests for gradbot.git — Git CLI wrapper."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from gradbot.git import (
    GitError,
    clone_or_update,
    ensure_git_installed,
    run_git,
)


class TestRunGit:
    """Tests for the run_git() function."""

    @patch("gradbot.git.subprocess.run")
    def test_success(self, mock_run):
        """run_git returns stripped stdout on success."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="  git version 2.42.0  \n",
            stderr="",
        )
        result = run_git("--version")
        assert result == "git version 2.42.0"
        mock_run.assert_called_once()

    @patch("gradbot.git.subprocess.run")
    def test_failure_raises_git_error(self, mock_run):
        """run_git raises GitError when git returns non-zero."""
        mock_run.return_value = MagicMock(
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )
        with pytest.raises(GitError) as exc_info:
            run_git("status")
        assert exc_info.value.stderr == "fatal: not a git repository"

    @patch("gradbot.git.subprocess.run", side_effect=FileNotFoundError)
    def test_git_not_found(self, mock_run):
        """run_git raises GitError when git is not installed."""
        with pytest.raises(GitError, match="Git is not installed"):
            run_git("--version")

    @patch("gradbot.git.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30))
    def test_timeout(self, mock_run):
        """run_git raises GitError on timeout."""
        with pytest.raises(GitError, match="timed out"):
            run_git("fetch", timeout=30)

    @patch("gradbot.git.subprocess.run")
    def test_cwd_passed(self, mock_run):
        """run_git passes cwd to subprocess."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_git("status", cwd="/tmp/repo")
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("cwd") == "/tmp/repo" or call_kwargs[1].get("cwd") == "/tmp/repo"


class TestEnsureGitInstalled:
    """Tests for ensure_git_installed()."""

    @patch("gradbot.git.run_git")
    def test_git_available(self, mock_run_git):
        """No error when git is available."""
        mock_run_git.return_value = "git version 2.42.0"
        ensure_git_installed()  # should not raise

    @patch("gradbot.git.run_git", side_effect=GitError("Git is not installed"))
    def test_git_not_available(self, mock_run_git):
        """Raises GitError with install instructions when git is missing."""
        with pytest.raises(GitError, match="needs Git"):
            ensure_git_installed()


class TestCloneOrUpdate:
    """Tests for clone_or_update()."""

    @patch("gradbot.git.run_git")
    def test_fresh_clone(self, mock_run_git, tmp_path):
        """Creates a new repo when local_path doesn't exist."""
        local = tmp_path / "new_repo"
        # local doesn't exist yet

        result = clone_or_update(
            origin="https://github.com/test/repo.git",
            local_path=local,
            branch="main",
        )

        assert result == local
        assert local.exists()

        # Verify the git commands were called
        calls = [c.args for c in mock_run_git.call_args_list]
        # Should have: init, remote add, set-url, fetch, checkout, reset
        cmd_strs = [" ".join(c) for c in calls]
        assert any("init" in s for s in cmd_strs)
        assert any("remote" in s and "add" in s for s in cmd_strs)
        assert any("fetch" in s for s in cmd_strs)
        assert any("checkout" in s for s in cmd_strs)
        assert any("reset" in s for s in cmd_strs)

    @patch("gradbot.git.run_git")
    def test_update_existing(self, mock_run_git, tmp_path):
        """Fetches and checks out when repo already exists."""
        local = tmp_path / "existing_repo"
        local.mkdir()

        clone_or_update(
            origin="https://github.com/test/repo.git",
            local_path=local,
            branch="main",
        )

        calls = [c.args for c in mock_run_git.call_args_list]
        cmd_strs = [" ".join(c) for c in calls]
        # Should NOT have init or remote add (repo exists)
        assert not any("init" in s for s in cmd_strs)
        # Should have set-url, fetch, checkout, reset
        assert any("set-url" in s for s in cmd_strs)
        assert any("fetch" in s for s in cmd_strs)

    @patch("gradbot.git.run_git")
    def test_offline_existing(self, mock_run_git, tmp_path):
        """In offline mode with existing repo, skips fetch."""
        local = tmp_path / "cached_repo"
        local.mkdir()

        clone_or_update(
            origin="https://github.com/test/repo.git",
            local_path=local,
            branch="main",
            offline=True,
        )

        calls = [c.args for c in mock_run_git.call_args_list]
        cmd_strs = [" ".join(c) for c in calls]
        # Should NOT have fetch
        assert not any("fetch" in s for s in cmd_strs)
        # Should still have checkout and reset
        assert any("checkout" in s for s in cmd_strs)
        assert any("reset" in s for s in cmd_strs)

    def test_offline_no_existing_raises(self, tmp_path):
        """In offline mode with no existing repo, raises GitError."""
        local = tmp_path / "nonexistent"

        with pytest.raises(GitError, match="offline"):
            clone_or_update(
                origin="https://github.com/test/repo.git",
                local_path=local,
                branch="main",
                offline=True,
            )

    @patch("gradbot.git.run_git")
    def test_custom_branch(self, mock_run_git, tmp_path):
        """Uses the specified branch for fetch and checkout."""
        local = tmp_path / "repo"
        local.mkdir()

        clone_or_update(
            origin="https://github.com/test/repo.git",
            local_path=local,
            branch="v2",
        )

        calls = [c.args for c in mock_run_git.call_args_list]
        cmd_strs = [" ".join(c) for c in calls]
        assert any("v2" in s and "fetch" in s for s in cmd_strs)
        assert any("origin/v2" in s and "checkout" in s for s in cmd_strs)
