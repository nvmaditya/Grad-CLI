"""login, submit, roster add, reset and results, against a fake GitHub on localhost."""

from __future__ import annotations

import io
import json
import os
import stat
import zipfile

import pytest
import yaml

from gradbot.cli import main
from tests.fake_github import FakeServer, Reply, dead_url


@pytest.fixture
def github(monkeypatch):
    with FakeServer() as server:
        monkeypatch.setenv("GRADBOT_GITHUB_URL", server.url)
        monkeypatch.setenv("GRADBOT_GITHUB_API_URL", server.url)
        yield server


def _run(*argv: str) -> int:
    with pytest.raises(SystemExit) as exc:
        main(list(argv))
    return exc.value.code


def _no_crash(out: str) -> None:
    assert "bug in Grade" not in out
    assert "Traceback" not in out


# ── login ─────────────────────────────────────────────────────────────

_DEVICE = {
    "device_code": "dev-123",
    "user_code": "ABCD-1234",
    "verification_uri": "https://github.com/login/device",
    "expires_in": 900,
    "interval": 0,
}


def test_login_device_flow_saves_a_private_token(github, monkeypatch, capsys, gradbot_home):
    monkeypatch.setenv("GRADBOT_CLIENT_ID", "client-1")
    github.route("POST", "/login/device/code", Reply(body=_DEVICE))
    github.route("POST", "/login/oauth/access_token", [
        Reply(body={"error": "authorization_pending"}),
        Reply(body={"error": "slow_down", "interval": 0}),
        Reply(body={"access_token": "gho_student", "token_type": "bearer", "scope": "read:user"}),
    ])

    assert _run("login") == 0

    out = capsys.readouterr().out
    assert "ABCD-1234" in out and "https://github.com/login/device" in out
    token_file = gradbot_home / "github_token"
    assert token_file.read_text(encoding="utf-8") == "gho_student"
    if os.name == "posix":
        assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
    start = github.requests[0]
    assert start.body.decode() == "client_id=client-1&scope=read%3Auser"
    assert len([r for r in github.requests if r.path == "/login/oauth/access_token"]) == 3


def test_login_without_client_id_names_the_variable(github, capsys):
    assert _run("login") == 1
    out = capsys.readouterr().out
    assert "GRADBOT_CLIENT_ID is not set" in out
    assert github.requests == []


@pytest.mark.parametrize(
    ("error", "message"),
    [("access_denied", "cancelled"), ("expired_token", "expired"), ("unsupported_grant_type", "unsupported")],
)
def test_login_refusals_are_explained(github, monkeypatch, capsys, error, message):
    monkeypatch.setenv("GRADBOT_CLIENT_ID", "client-1")
    github.route("POST", "/login/device/code", Reply(body=_DEVICE))
    github.route("POST", "/login/oauth/access_token", Reply(body={"error": error}))
    assert _run("login") == 1
    out = capsys.readouterr().out
    assert message in out.lower()
    _no_crash(out)


def test_login_with_a_bad_client_id(github, monkeypatch, capsys):
    monkeypatch.setenv("GRADBOT_CLIENT_ID", "wrong")
    github.route("POST", "/login/device/code", Reply(401, {"error": "Not Found"}))
    assert _run("login") == 1
    out = capsys.readouterr().out
    assert "GRADBOT_CLIENT_ID" in out
    _no_crash(out)


@pytest.mark.parametrize("body", ["<html>oops</html>", {"user_code": "X"}, [1, 2]])
def test_login_with_a_malformed_github_reply(github, monkeypatch, capsys, body):
    monkeypatch.setenv("GRADBOT_CLIENT_ID", "client-1")
    github.route("POST", "/login/device/code", Reply(body=body))
    assert _run("login") == 1
    out = capsys.readouterr().out
    assert "unexpected" in out.lower()
    _no_crash(out)


def test_login_when_github_is_unreachable(monkeypatch, capsys):
    monkeypatch.setenv("GRADBOT_CLIENT_ID", "client-1")
    monkeypatch.setenv("GRADBOT_GITHUB_URL", dead_url())
    assert _run("login") == 1
    out = capsys.readouterr().out
    assert "Couldn't reach" in out
    _no_crash(out)


def test_login_gives_up_when_the_code_expires(github, monkeypatch, capsys):
    monkeypatch.setenv("GRADBOT_CLIENT_ID", "client-1")
    github.route("POST", "/login/device/code", Reply(body={**_DEVICE, "expires_in": 0}))
    github.route("POST", "/login/oauth/access_token", Reply(body={"error": "authorization_pending"}))
    assert _run("login") == 1
    assert "expired" in capsys.readouterr().out


# ── submit ────────────────────────────────────────────────────────────


@pytest.fixture
def logged_in(gradbot_home):
    (gradbot_home / "github_token").write_text("gho_student\n", encoding="utf-8")
    return gradbot_home


@pytest.fixture
def solution(tmp_path):
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "solution.py").write_text("print('0 1')\n", encoding="utf-8")
    return sol


def _zip_names(body: bytes) -> list[str]:
    return sorted(zipfile.ZipFile(io.BytesIO(body)).namelist())


def test_submit_posts_only_source_files(github, monkeypatch, logged_in, solution, capsys):
    monkeypatch.setenv("GRADBOT_SUBMIT_URL", github.url + "/submit")
    github.route("POST", "/submit", Reply(body={"accepted": True, "reason": "accepted"}))
    git = solution / ".git" / "objects"
    git.mkdir(parents=True)
    (git / "pack").write_bytes(os.urandom(2_000_000))  # would blow the 1 MB cap
    (solution / "solution").write_bytes(os.urandom(500_000))  # compiled binary
    (solution / "notes.txt").write_text("todo", encoding="utf-8")
    (solution / "checks.py").write_text("# practice checks\n", encoding="utf-8")
    (solution / "lib").mkdir()
    (solution / "lib" / "helper.py").write_text("X = 1\n", encoding="utf-8")

    assert _run("submit", "arrays/two_sum", "--solution", str(solution)) == 0

    sent = github.requests[-1]
    assert sent.headers["Authorization"] == "Bearer gho_student"
    assert sent.headers["X-Gradbot-Slug"] == "arrays/two_sum"
    assert _zip_names(sent.body) == ["lib/helper.py", "solution.py"]
    assert "accepted" in capsys.readouterr().out


def test_submit_without_a_url_does_not_send_anything(github, logged_in, solution, capsys):
    assert _run("submit", "arrays/two_sum", "--solution", str(solution)) == 1
    out = capsys.readouterr().out
    assert "GRADBOT_SUBMIT_URL is not set" in out
    assert github.requests == []


def test_submit_before_login(github, monkeypatch, solution, capsys):
    monkeypatch.setenv("GRADBOT_SUBMIT_URL", github.url + "/submit")
    assert _run("submit", "arrays/two_sum", "--solution", str(solution)) == 1
    assert "grade login" in capsys.readouterr().out
    assert github.requests == []


def test_submit_refuses_to_send_the_token_over_plain_http(monkeypatch, logged_in, solution, capsys):
    monkeypatch.setenv("GRADBOT_SUBMIT_URL", "http://grader.example.com/submit")
    assert _run("submit", "arrays/two_sum", "--solution", str(solution)) == 1
    assert "https://" in capsys.readouterr().out


def test_submit_refuses_hidden_checks_in_the_folder(github, monkeypatch, logged_in, solution, capsys):
    monkeypatch.setenv("GRADBOT_SUBMIT_URL", github.url + "/submit")
    (solution / "checks_hidden.py").write_text("SECRET\n", encoding="utf-8")
    assert _run("submit", "arrays/two_sum", "--solution", str(solution)) == 1
    assert "checks_hidden.py" in capsys.readouterr().out
    assert github.requests == []


def test_submit_with_no_source_files(github, monkeypatch, logged_in, tmp_path, capsys):
    monkeypatch.setenv("GRADBOT_SUBMIT_URL", github.url + "/submit")
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "README.md").write_text("hi", encoding="utf-8")
    assert _run("submit", "arrays/two_sum", "--solution", str(empty)) == 1
    out = capsys.readouterr().out
    assert "no source file" in out.lower()
    _no_crash(out)


@pytest.mark.parametrize("slug", ["two_sum", "arrays/two sum", "../x/y", "a/b/c/d"])
def test_submit_refuses_a_malformed_slug(github, monkeypatch, logged_in, solution, capsys, slug):
    monkeypatch.setenv("GRADBOT_SUBMIT_URL", github.url + "/submit")
    assert _run("submit", slug, "--solution", str(solution)) == 1
    assert "topic/problem" in capsys.readouterr().out
    assert github.requests == []


def test_submit_reports_an_app_refusal(github, monkeypatch, logged_in, solution, capsys):
    monkeypatch.setenv("GRADBOT_SUBMIT_URL", github.url + "/submit")
    github.route("POST", "/submit", Reply(409, {"accepted": False, "reason": "already submitted"}))
    assert _run("submit", "arrays/two_sum", "--solution", str(solution)) == 1
    out = capsys.readouterr().out
    assert "already submitted" in out
    _no_crash(out)


def test_submit_with_an_expired_login(github, monkeypatch, logged_in, solution, capsys):
    monkeypatch.setenv("GRADBOT_SUBMIT_URL", github.url + "/submit")
    github.route("POST", "/submit", Reply(401, {"reason": "unknown token"}))
    assert _run("submit", "arrays/two_sum", "--solution", str(solution)) == 1
    assert "grade login" in capsys.readouterr().out


def test_submit_when_the_app_is_down(monkeypatch, logged_in, solution, capsys):
    monkeypatch.setenv("GRADBOT_SUBMIT_URL", dead_url() + "/submit")
    assert _run("submit", "arrays/two_sum", "--solution", str(solution)) == 1
    out = capsys.readouterr().out
    assert "Couldn't reach" in out
    _no_crash(out)


def test_submit_shows_a_long_html_error_page_briefly(github, monkeypatch, logged_in, solution, capsys):
    monkeypatch.setenv("GRADBOT_SUBMIT_URL", github.url + "/submit")
    github.route("POST", "/submit", Reply(502, "<html>" + "x" * 50_000 + "</html>", "text/html"))
    assert _run("submit", "arrays/two_sum", "--solution", str(solution)) == 1
    out = capsys.readouterr().out
    assert "502" in out
    assert len(out) < 2_000


# ── roster add ────────────────────────────────────────────────────────


def test_roster_add_writes_the_id_github_returns(github, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "faculty-token")
    github.route("GET", "/users/ada", Reply(body={"login": "Ada", "id": 583231}))
    roster = tmp_path / "roster.yml"

    assert _run("roster", "add", "ada", "--roster", str(roster)) == 0

    written = yaml.safe_load(roster.read_text(encoding="utf-8"))
    assert written == {"students": [{"id": 583231, "login": "Ada"}]}
    assert github.requests[0].headers["Authorization"] == "Bearer faculty-token"
    assert "583231" in capsys.readouterr().out


def test_roster_add_without_token(github, tmp_path, capsys):
    assert _run("roster", "add", "ada", "--roster", str(tmp_path / "r.yml")) == 1
    assert "GRADBOT_APP_TOKEN is not set" in capsys.readouterr().out
    assert github.requests == []


def test_roster_add_unknown_user(github, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "faculty-token")
    roster = tmp_path / "roster.yml"
    assert _run("roster", "add", "ghost", "--roster", str(roster)) == 1
    out = capsys.readouterr().out
    assert "No GitHub user named ghost" in out
    assert not roster.exists()


def test_roster_add_with_a_rejected_token(github, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "bad")
    github.route("GET", "/users/ada", Reply(401, {"message": "Bad credentials"}))
    assert _run("roster", "add", "ada", "--roster", str(tmp_path / "r.yml")) == 1
    out = capsys.readouterr().out
    assert "GRADBOT_APP_TOKEN" in out and "rejected" in out
    _no_crash(out)


@pytest.mark.parametrize("login", ["../repos/x", "a b", "-ada", "x" * 40])
def test_roster_add_refuses_a_malformed_login(github, monkeypatch, tmp_path, capsys, login):
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "faculty-token")
    assert _run("roster", "add", "--roster", str(tmp_path / "r.yml"), "--", login) == 1
    assert "GitHub login" in capsys.readouterr().out
    assert github.requests == []


def test_roster_add_with_a_malformed_roster_file(github, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "faculty-token")
    github.route("GET", "/users/ada", Reply(body={"login": "ada", "id": 5}))
    roster = tmp_path / "roster.yml"
    roster.write_text("students: [{login: nobody}]\n", encoding="utf-8")
    assert _run("roster", "add", "ada", "--roster", str(roster)) == 1
    out = capsys.readouterr().out
    assert "roster" in out.lower()
    _no_crash(out)
    assert roster.read_text(encoding="utf-8") == "students: [{login: nobody}]\n"


def test_roster_add_when_github_is_unreachable(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "faculty-token")
    monkeypatch.setenv("GRADBOT_GITHUB_API_URL", dead_url())
    assert _run("roster", "add", "ada", "--roster", str(tmp_path / "r.yml")) == 1
    out = capsys.readouterr().out
    assert "Couldn't reach" in out
    _no_crash(out)


# ── reset ─────────────────────────────────────────────────────────────


def _faculty(monkeypatch):
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "faculty-token")
    monkeypatch.setenv("GRADBOT_SUBMISSIONS_REPO", "acme/course-submissions")


def test_reset_deletes_the_slot_ref_by_user_id(github, monkeypatch, capsys):
    _faculty(monkeypatch)
    github.route("GET", "/users/ada", Reply(body={"login": "ada", "id": 42}))
    ref = "/repos/acme/course-submissions/git/refs/gradbot/slots/arrays/two_sum/42"
    github.route("DELETE", ref, Reply(204, b"", "text/plain"))

    assert _run("reset", "ada", "arrays/two_sum") == 0

    assert [(r.method, r.path) for r in github.requests] == [("GET", "/users/ada"), ("DELETE", ref)]
    assert "refs/gradbot/slots/arrays/two_sum/42" in capsys.readouterr().out


def test_reset_when_there_is_no_slot(github, monkeypatch, capsys):
    _faculty(monkeypatch)
    github.route("GET", "/users/ada", Reply(body={"login": "ada", "id": 42}))
    github.route(
        "DELETE",
        "/repos/acme/course-submissions/git/refs/gradbot/slots/arrays/two_sum/42",
        Reply(422, {"message": "Reference does not exist"}),
    )
    assert _run("reset", "ada", "arrays/two_sum") == 1
    out = capsys.readouterr().out
    assert "no submit slot" in out.lower()
    _no_crash(out)


def test_reset_needs_both_faculty_settings(github, monkeypatch, capsys):
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "faculty-token")
    assert _run("reset", "ada", "arrays/two_sum") == 1
    assert "GRADBOT_SUBMISSIONS_REPO is not set" in capsys.readouterr().out
    assert github.requests == []


def test_reset_refuses_a_malformed_slug(github, monkeypatch, capsys):
    _faculty(monkeypatch)
    assert _run("reset", "ada", "arrays/../../x") == 1
    assert "topic/problem" in capsys.readouterr().out
    assert github.requests == []


def test_reset_refuses_a_malformed_submissions_repo(github, monkeypatch, capsys):
    _faculty(monkeypatch)
    monkeypatch.setenv("GRADBOT_SUBMISSIONS_REPO", "not a repo")
    assert _run("reset", "ada", "arrays/two_sum") == 1
    assert "GRADBOT_SUBMISSIONS_REPO" in capsys.readouterr().out
    assert github.requests == []


# ── results ───────────────────────────────────────────────────────────


def test_results_strips_cause_and_log(tmp_path, capsys):
    faculty = tmp_path / "faculty.json"
    faculty.write_text(json.dumps({"public": {"checks": [
        {"name": "c", "hint": "h", "cause": "Expected SECRET", "log": ["SECRET"]},
    ]}}), encoding="utf-8")
    assert _run("results", str(faculty)) == 0
    out = capsys.readouterr().out
    assert "SECRET" not in out
    assert json.loads(out) == {"public": {"checks": [{"name": "c", "hint": "h"}]}}


def test_results_missing_file(tmp_path, capsys):
    assert _run("results", str(tmp_path / "nope.json")) == 1
    out = capsys.readouterr().out
    assert "not found" in out.lower()
    _no_crash(out)


def test_results_invalid_json(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert _run("results", str(bad)) == 1
    out = capsys.readouterr().out
    assert "JSON" in out
    _no_crash(out)


def test_requests_identify_gradbot(github, monkeypatch, tmp_path):
    monkeypatch.setenv("GRADBOT_APP_TOKEN", "faculty-token")
    github.route("GET", "/users/ada", Reply(body={"login": "ada", "id": 1}))
    _run("roster", "add", "ada", "--roster", str(tmp_path / "r.yml"))
    assert github.requests[0].headers["User-Agent"].startswith("gradbot/")

