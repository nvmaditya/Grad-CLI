"""Tests for gradbot.git — Git CLI wrapper."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from gradbot.git import (
    GitError,
    clone_or_update,
    ensure_git_installed,
    has_cached,
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
    """clone_or_update() against a real bare repo on disk."""

    @pytest.fixture
    def remote(self, tmp_path):
        from tests.samples_repo import SamplesRepo, write_problem

        repo = SamplesRepo(tmp_path)
        write_problem(repo.work, "arrays/two_sum")
        repo.commit()
        repo.publish()
        return repo

    def test_fresh_clone(self, remote, tmp_path):
        local = tmp_path / "clone"
        assert clone_or_update(str(remote.bare), local, "main") == local
        assert (local / "arrays" / "two_sum" / "checks.py").is_file()
        assert has_cached(local, "main")

    def test_update_existing_removes_stray_files(self, remote, tmp_path):
        local = tmp_path / "clone"
        clone_or_update(str(remote.bare), local, "main")
        (local / "arrays" / "two_sum" / "__pycache__").mkdir()
        clone_or_update(str(remote.bare), local, "main")
        assert not (local / "arrays" / "two_sum" / "__pycache__").exists()

    def test_offline_existing(self, remote, tmp_path):
        local = tmp_path / "clone"
        clone_or_update(str(remote.bare), local, "main")
        remote.bare.rename(tmp_path / "gone.git")
        assert clone_or_update(str(remote.bare), local, "main", offline=True) == local

    def test_offline_no_existing_raises(self, tmp_path):
        with pytest.raises(GitError, match="offline"):
            clone_or_update("https://github.com/test/repo.git", tmp_path / "none", "main", offline=True)

    def test_failed_first_fetch_removes_the_folder(self, tmp_path):
        local = tmp_path / "clone"
        with pytest.raises(GitError):
            clone_or_update(str(tmp_path / "missing.git"), local, "main")
        assert not local.exists()

    def test_failed_update_keeps_the_existing_cache(self, remote, tmp_path):
        local = tmp_path / "clone"
        clone_or_update(str(remote.bare), local, "main")
        with pytest.raises(GitError):
            clone_or_update(str(remote.bare), local, "no-such-branch")
        assert has_cached(local, "main")
