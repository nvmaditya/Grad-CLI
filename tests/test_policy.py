"""Roster, one-submit lock, zip guard, and publish split. No live GitHub."""

import io
import threading
import zipfile
from pathlib import Path

import pytest

from gradbot.policy import (
    WORKFLOW_TEXT,
    Identity,
    PolicyError,
    accept_zip,
    add_roster_entry,
    device_code_body,
    install_grader_workflow,
    parse_roster,
    publish_suite,
    reset_slot,
    safe_source_files,
    slot_ref,
    status_comment,
    submit_once,
)
from gradbot.result import CheckResult, SuiteResult


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buf.getvalue()


class FakeOps:
    """In-memory GitHub App. create_ref is atomic."""

    def __init__(self, users: dict[str, Identity]):
        self.users = users
        self.refs: set[str] = set()
        self.dispatches: list[str] = []
        self.commits: list[tuple] = []
        self.deletes: list[str] = []
        self.fail: str | None = None
        self._lock = threading.Lock()

    def identity(self, token: str) -> Identity:
        try:
            return self.users[token]
        except KeyError:
            raise PolicyError("unknown token") from None

    def create_ref(self, ref: str) -> bool:
        with self._lock:
            if ref in self.refs:
                return False
            self.refs.add(ref)
            return True

    def delete_ref(self, ref: str) -> None:
        with self._lock:
            self.refs.discard(ref)
            self.deletes.append(ref)

    def commit(self, slug: str, user_id: int, login: str, files: dict[str, bytes]) -> None:
        if self.fail == "commit":
            raise PolicyError("commit failed")
        self.commits.append((slug, user_id, login, set(files)))

    def dispatch(self, slug: str, user_id: int) -> None:
        if self.fail == "dispatch":
            raise PolicyError("dispatch failed")
        self.dispatches.append(f"{slug}:{user_id}")


def _suite(cause: str, log: list[str], hint: str) -> SuiteResult:
    return SuiteResult(
        problem="Two Sum",
        topic="Arrays",
        mode="submit",
        checks=[
            CheckResult(
                name="hidden",
                slug="hidden",
                status="fail",
                description="hidden case",
                hint=hint,
                log=log,
                cause=cause,
                points=1,
            )
        ],
    )


def test_status_comment_keeps_hint_and_drops_secret():
    text = status_comment(_suite(
        "Expected SECRET_9998, got 0 1",
        ["Expected: 'SECRET_9998'"],
        "Try a hash map",
    ))
    assert "SECRET_9998" not in text
    assert "Try a hash map" in text


def test_unregistered_id_does_not_create_or_dispatch():
    ops = FakeOps({"tok": Identity(9, "stranger")})
    result = submit_once(ops, "tok", "arrays/two_sum", {"solution.py": b"x"}, {1})
    assert result.accepted is False
    assert result.reason == "not on roster"
    assert ops.refs == set()
    assert ops.dispatches == []
    assert ops.commits == []


def test_unknown_token_stops():
    ops = FakeOps({})
    result = submit_once(ops, "nope", "arrays/two_sum", {"solution.py": b"x"}, {1})
    assert result.accepted is False
    assert result.reason == "unknown token"
    assert ops.refs == set()


def test_body_login_is_ignored():
    ops = FakeOps({"tok": Identity(7, "real")})
    result = submit_once(
        ops, "tok", "arrays/two_sum", {"solution.py": b"x"}, {7}, body_login="ada",
    )
    assert result.accepted is True
    assert result.user_id == 7
    assert result.login == "real"
    assert ops.commits[0][2] == "real"


def test_body_login_on_roster_does_not_enroll_the_token():
    ops = FakeOps({"tok": Identity(9, "stranger")})
    result = submit_once(
        ops, "tok", "arrays/two_sum", {"solution.py": b"x"}, {7}, body_login="ada",
    )
    assert result.accepted is False
    assert ops.dispatches == []


def test_login_case_is_not_the_key():
    ops = FakeOps({"tok": Identity(5, "ada")})
    result = submit_once(ops, "tok", "arrays/two_sum", {"solution.py": b"x"}, {5})
    assert result.accepted is True
    assert result.user_id == 5


def test_second_submit_does_not_dispatch():
    ops = FakeOps({"tok": Identity(5, "ada")})
    files = {"solution.py": b"x"}
    first = submit_once(ops, "tok", "arrays/two_sum", files, {5})
    second = submit_once(ops, "tok", "arrays/two_sum", files, {5})
    assert first.accepted is True
    assert second.accepted is False
    assert second.reason == "already submitted"
    assert ops.dispatches == ["arrays/two_sum:5"]
    assert len(ops.refs) == 1


def test_parallel_submits_create_one_ref():
    ops = FakeOps({"tok": Identity(5, "ada")})
    files = {"solution.py": b"x"}
    results: list = []

    def go():
        results.append(submit_once(ops, "tok", "arrays/two_sum", files, {5}))

    threads = [threading.Thread(target=go) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(item.accepted for item in results) == 1
    assert len(ops.dispatches) == 1
    assert len(ops.refs) == 1


def test_failed_dispatch_deletes_the_ref():
    ops = FakeOps({"tok": Identity(5, "ada")})
    ops.fail = "dispatch"
    result = submit_once(ops, "tok", "arrays/two_sum", {"solution.py": b"x"}, {5})
    assert result.accepted is False
    assert result.reason == "retry"
    assert ops.refs == set()
    assert ops.deletes


def test_failed_commit_deletes_the_ref():
    ops = FakeOps({"tok": Identity(5, "ada")})
    ops.fail = "commit"
    result = submit_once(ops, "tok", "arrays/two_sum", {"solution.py": b"x"}, {5})
    assert result.accepted is False
    assert ops.refs == set()
    assert ops.dispatches == []


def test_accepted_submit_keeps_the_slot():
    ops = FakeOps({"tok": Identity(5, "ada")})
    result = submit_once(ops, "tok", "arrays/two_sum", {"solution.py": b"x"}, {5})
    assert result.accepted is True
    assert result.dispatched is True
    assert ops.deletes == []
    assert slot_ref("arrays/two_sum", 5) in ops.refs


def test_empty_files_do_not_create_a_ref():
    ops = FakeOps({"tok": Identity(5, "ada")})
    result = submit_once(ops, "tok", "arrays/two_sum", {}, {5})
    assert result.reason == "empty submission"
    assert ops.refs == set()


def test_reset_deletes_the_ref_and_does_not_dispatch():
    ops = FakeOps({"tok": Identity(5, "ada")})
    submit_once(ops, "tok", "arrays/two_sum", {"solution.py": b"x"}, {5})
    reset_slot(ops, "arrays/two_sum", 5)
    assert ops.refs == set()
    assert ops.dispatches == ["arrays/two_sum:5"]


def test_bad_zip_does_not_create_a_ref():
    ops = FakeOps({"tok": Identity(5, "ada")})
    with pytest.raises(PolicyError):
        accept_zip(ops, "tok", "arrays/two_sum", _zip({"../secret.py": b"x"}), {5})
    assert ops.refs == set()
    assert ops.dispatches == []


def test_zip_rejects_hidden_checks_and_workflows():
    good = {"solution.py": b"print(1)\n"}
    with pytest.raises(PolicyError):
        safe_source_files(_zip({**good, "checks_hidden.py": b"SECRET"}))
    with pytest.raises(PolicyError):
        safe_source_files(_zip({**good, ".github/workflows/grade.yml": b"on: push"}))


def test_zip_rejects_empty_and_oversized():
    with pytest.raises(PolicyError):
        safe_source_files(b"")
    with pytest.raises(PolicyError):
        safe_source_files(_zip({"README.md": b"hi"}))
    with pytest.raises(PolicyError):
        safe_source_files(_zip({"solution.py": b"print(1)\n"}), max_bytes=4)


def test_zip_keeps_source_only():
    files = safe_source_files(_zip({
        "solution.py": b"print(1)\n",
        "notes.txt": b"ignore",
    }))
    assert files == {"solution.py": b"print(1)\n"}


def test_student_login_asks_only_for_read_user():
    # read:user proves who the student is and cannot read a private repo.
    assert device_code_body("course-client") == {"client_id": "course-client", "scope": "read:user"}


def test_publish_hides_checks_and_workflow_from_samples(tmp_path: Path):
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "suite.yaml").write_text("name: Two Sum\n", encoding="utf-8")
    (suite / "checks.py").write_text("PUBLIC\n", encoding="utf-8")
    (suite / "checks_hidden.py").write_text("SECRET_9998\n", encoding="utf-8")
    (suite / "statement.md").write_text("statement\n", encoding="utf-8")
    sample = suite / "sample_solution"
    sample.mkdir()
    (sample / "solution.py").write_text("print(1)\n", encoding="utf-8")

    tests = tmp_path / "tests-repo"
    samples = tmp_path / "samples-repo"
    publish_suite(suite, tests / "arrays" / "two_sum", samples / "arrays" / "two_sum")
    install_grader_workflow(tests)

    hidden = (tests / "arrays" / "two_sum" / "checks_hidden.py").read_text(encoding="utf-8")
    assert "SECRET_9998" in hidden
    assert not (samples / "arrays" / "two_sum" / "checks_hidden.py").exists()
    assert (samples / "arrays" / "two_sum" / "checks.py").read_text(encoding="utf-8") == "PUBLIC\n"
    assert not (samples / "sample_solution").exists()
    workflow = tests / ".github" / "workflows" / "grade.yml"
    assert workflow.is_file()
    assert not (samples / ".github" / "workflows" / "grade.yml").exists()
    text = workflow.read_text(encoding="utf-8")
    assert text == WORKFLOW_TEXT
    assert "pull_request_target" not in text
    assert "timeout-minutes: 10" in text
    assert "cancel-in-progress: false" in text
    assert "--network none" in text
    assert "workflow_dispatch" in text


def test_roster_tracks_id_not_login_case():
    text = "students:\n  - id: 5\n    login: Ada\n"
    assert parse_roster(text) == {5}
    updated = add_roster_entry(text, "ada", 5)
    assert parse_roster(updated) == {5}
    assert updated.count("id: 5") == 1
