"""End to end: the installed `grade` command, run as a subprocess, for each main user flow.

No network: the samples repo is a bare repo on disk, and GitHub plus the
course App are a local HTTP server. The App is a thin wrapper around the real
gradbot.policy.accept_zip, so the client and the submit rules are tested
together.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest
import yaml

from gradbot.policy import Identity, PolicyError, accept_zip, parse_roster, slot_ref
from tests.fake_github import FakeServer, Reply, Request
from tests.samples_repo import (
    TWO_SUM_CHECKS,
    TWO_SUM_SOLUTION,
    TWO_SUM_SUITE,
    SamplesRepo,
    git,
    write_problem,
)

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parent.parent
PROBLEMS = ROOT / "problems"
BIN = Path(sys.executable).parent


def _exe(name: str) -> str:
    found = shutil.which(name, path=str(BIN)) or shutil.which(name)
    assert found, f"`{name}` is not installed; run pip install -e ."
    return found


def grade(
    *args: str, cwd: Path, env: dict[str, str], name: str = "grade",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_exe(name), *args], cwd=cwd, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )


@pytest.fixture
def env(gradbot_home: Path) -> dict[str, str]:
    """The test process env (already isolated by conftest), plus no colour."""
    return {**os.environ, "NO_COLOR": "1", "GRADBOT_CONFIG_DIR": str(gradbot_home)}


@pytest.fixture
def student(tmp_path: Path) -> Path:
    folder = tmp_path / "student"
    folder.mkdir()
    (folder / "solution.py").write_text(TWO_SUM_SOLUTION, encoding="utf-8")
    return folder


# ── basics ────────────────────────────────────────────────────────────


def test_version_and_help(tmp_path, env):
    assert grade("--version", cwd=tmp_path, env=env).stdout.strip() == "Grade CLI 1.0.0"
    assert grade("--help", cwd=tmp_path, env=env).returncode == 0


def test_no_arguments_prints_usage(tmp_path, env):
    done = grade(cwd=tmp_path, env=env)
    assert done.returncode == 2
    assert "usage" in done.stderr


def test_python_module_entry_point(tmp_path, env):
    done = subprocess.run(
        [sys.executable, "-m", "gradbot", "--version"], cwd=tmp_path, env=env,
        capture_output=True, text=True,
    )
    assert done.stdout.strip() == "Grade CLI 1.0.0"


# ── student practice ──────────────────────────────────────────────────


@pytest.fixture
def samples(tmp_path: Path, env: dict[str, str]) -> SamplesRepo:
    repo = SamplesRepo(tmp_path)
    write_problem(repo.work, "arrays/two_sum")
    repo.commit()
    repo.publish()
    env["GRADBOT_PUBLIC_REPO"] = str(repo.bare)
    return repo


def test_practice_passes_then_works_offline(samples, student, env):
    first = grade("run", "arrays/two_sum", cwd=student, env=env)
    assert first.returncode == 0, first.stdout + first.stderr
    assert "Score: 1 / 1" in first.stdout

    samples.bare.rename(samples.bare.with_suffix(".moved"))
    offline = grade("run", "arrays/two_sum", "--offline", cwd=student, env=env)
    assert offline.returncode == 0, offline.stdout + offline.stderr


def test_practice_wrong_answer_shows_the_hint_and_exits_1(samples, student, env):
    (student / "solution.py").write_text("print('1 0')\n", encoding="utf-8")
    done = grade("run", "arrays/two_sum", cwd=student, env=env)
    assert done.returncode == 1
    assert "Use a hash map" in done.stdout
    assert "Score: 0 / 1" in done.stdout


def test_practice_with_the_legacy_slug_command(samples, student, env):
    done = grade("practice/arrays/two_sum", cwd=student, env=env, name="GradBot")
    assert done.returncode == 0, done.stdout + done.stderr


def test_practice_json_output(samples, student, env):
    done = grade("run", "arrays/two_sum", "--output", "faculty.json", "--student-output", "student.json",
                 cwd=student, env=env)
    assert done.returncode == 0
    assert json.loads((student / "student.json").read_text(encoding="utf-8"))["public"]["score"] == 1.0


def test_practice_refuses_hidden_checks_next_to_the_solution(samples, student, env):
    (student / "checks_hidden.py").write_text("x = 1\n", encoding="utf-8")
    done = grade("run", "arrays/two_sum", cwd=student, env=env)
    assert done.returncode == 1
    assert "checks_hidden.py" in done.stdout


def test_practice_unknown_problem(samples, student, env):
    done = grade("run", "graphs/dijkstra", cwd=student, env=env)
    assert done.returncode == 1
    assert "Couldn't find the problem 'graphs/dijkstra'" in done.stdout
    assert "Traceback" not in done.stdout + done.stderr


# ── faculty: dev, publish, results ────────────────────────────────────


@pytest.mark.parametrize(
    "problem",
    sorted(str(p.relative_to(PROBLEMS)) for p in PROBLEMS.glob("*/*") if p.is_dir()),
)
def test_every_bundled_problem_passes_its_sample_solution(tmp_path, env, problem):
    done = grade("dev", str(PROBLEMS / problem), "--solution", str(PROBLEMS / problem / "sample_solution"),
                 cwd=tmp_path, env=env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Accepted. All tests passed." in done.stdout


def test_faculty_dev_names_the_failing_hidden_set_and_results_strip_it(tmp_path, env):
    problem = tmp_path / "two_sum"
    problem.mkdir()
    (problem / "suite.yaml").write_text(TWO_SUM_SUITE, encoding="utf-8")
    (problem / "checks.py").write_text(TWO_SUM_CHECKS, encoding="utf-8")
    (problem / "checks_hidden.py").write_text(
        "import gradbot\n\n"
        "@gradbot.check('large', points=2, hint='Think about speed')\n"
        "def test_large():\n"
        "    gradbot.expect_output(gradbot.run(input='2\\n5 5\\n10\\n').stdout, 'SECRET 0 1')\n",
        encoding="utf-8",
    )
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "solution.py").write_text(TWO_SUM_SOLUTION, encoding="utf-8")

    done = grade(
        "dev", str(problem), "--solution", str(sol), "--output", "faculty.json", cwd=tmp_path, env=env,
    )
    assert done.returncode == 1
    assert "Hidden checks failed" in done.stdout
    assert "Public checks failed" not in done.stdout

    shown = grade("results", "faculty.json", cwd=tmp_path, env=env)
    assert shown.returncode == 0
    assert "SECRET" not in shown.stdout
    assert "Think about speed" in shown.stdout
    assert "SECRET" in (tmp_path / "faculty.json").read_text(encoding="utf-8")


def test_publish_then_a_student_practises_the_published_problem(tmp_path, env, student):
    authoring = tmp_path / "authoring" / "two_sum"
    authoring.mkdir(parents=True)
    (authoring / "suite.yaml").write_text(TWO_SUM_SUITE, encoding="utf-8")
    (authoring / "checks.py").write_text(TWO_SUM_CHECKS, encoding="utf-8")
    (authoring / "checks_hidden.py").write_text("SECRET_9998\n", encoding="utf-8")

    samples = SamplesRepo(tmp_path / "course")
    tests_tree = tmp_path / "course-tests"
    done = grade("publish", str(authoring), "--tests", str(tests_tree), "--samples", str(samples.work),
                 "--slug", "arrays/two_sum", cwd=tmp_path, env=env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (tests_tree / ".github" / "workflows" / "grade.yml").is_file()
    hidden = tests_tree / "arrays" / "two_sum" / "checks_hidden.py"
    assert "SECRET_9998" in hidden.read_text(encoding="utf-8")

    samples.commit("publish two_sum")
    samples.publish()
    assert "checks_hidden.py" not in git("ls-tree", "-r", "--name-only", "HEAD", cwd=samples.work)

    env["GRADBOT_PUBLIC_REPO"] = str(samples.bare)
    practice = grade("run", "arrays/two_sum", cwd=student, env=env)
    assert practice.returncode == 0, practice.stdout + practice.stderr


# ── graded submit: login → submit → second submit → reset → submit ───


class CourseApp:
    """The course App's job: identity from the token, roster check, one slot, commit, dispatch."""

    def __init__(self, roster_yaml: str):
        self.roster = parse_roster(roster_yaml)
        self.tokens = {"gho_ada": Identity(583231, "ada"), "gho_eve": Identity(666, "eve")}
        self.refs: set[str] = set()
        self.commits: list[tuple[str, int, list[str]]] = []
        self.dispatches: list[tuple[str, int]] = []
        self._lock = threading.Lock()

    # ops used by gradbot.policy
    def identity(self, token: str) -> Identity:
        if token not in self.tokens:
            raise PolicyError("unknown token")
        return self.tokens[token]

    def create_ref(self, ref: str) -> bool:
        with self._lock:
            if ref in self.refs:
                return False
            self.refs.add(ref)
            return True

    def delete_ref(self, ref: str) -> None:
        with self._lock:
            self.refs.discard(ref)

    def commit(self, slug: str, user_id: int, login: str, files: dict[str, bytes]) -> None:
        self.commits.append((slug, user_id, sorted(files)))

    def dispatch(self, slug: str, user_id: int) -> None:
        self.dispatches.append((slug, user_id))

    # HTTP
    def submit(self, req: Request) -> Reply:
        token = req.headers.get("Authorization", "").removeprefix("Bearer ")
        try:
            result = accept_zip(self, token, req.headers["X-Gradbot-Slug"], req.body, self.roster)
        except PolicyError as exc:
            return Reply(400, {"accepted": False, "reason": str(exc)})
        status = 200 if result.accepted else (401 if result.reason == "unknown token" else 409)
        return Reply(status, {"accepted": result.accepted, "reason": result.reason})

    def delete(self, req: Request) -> Reply:
        ref = "refs/" + req.path.split("/git/refs/", 1)[1]
        if ref not in self.refs:
            return Reply(422, {"message": "Reference does not exist"})
        self.delete_ref(ref)
        return Reply(204, b"", "text/plain")


def test_graded_submit_round_trip(tmp_path, env, student):
    with FakeServer() as server:
        env.update({
            "GRADBOT_GITHUB_URL": server.url,
            "GRADBOT_GITHUB_API_URL": server.url,
            "GRADBOT_CLIENT_ID": "course-app",
            "GRADBOT_SUBMIT_URL": server.url + "/submit",
            "GRADBOT_APP_TOKEN": "faculty-token",
            "GRADBOT_SUBMISSIONS_REPO": "acme/course-submissions",
        })
        server.route("GET", "/users/ada", Reply(body={"login": "ada", "id": 583231}))

        # Faculty enrolls ada by the id GitHub reports.
        roster = tmp_path / "roster.yml"
        enrolled = grade("roster", "add", "ada", "--roster", str(roster), cwd=tmp_path, env=env)
        assert enrolled.returncode == 0, enrolled.stdout + enrolled.stderr
        written = yaml.safe_load(roster.read_text(encoding="utf-8"))
        assert written == {"students": [{"id": 583231, "login": "ada"}]}

        app = CourseApp(roster.read_text(encoding="utf-8"))
        server.route("POST", "/submit", app.submit)
        server.route("DELETE", "/repos/acme/course-submissions/git/refs/gradbot/slots/arrays/two_sum/583231",
                     app.delete)

        # Student logs in with the device flow.
        server.route("POST", "/login/device/code", Reply(body={
            "device_code": "d", "user_code": "WXYZ-0000", "verification_uri": "https://github.com/login/device",
            "expires_in": 60, "interval": 0,
        }))
        server.route("POST", "/login/oauth/access_token", Reply(body={"access_token": "gho_ada"}))
        login = grade("login", cwd=student, env=env)
        assert login.returncode == 0, login.stdout + login.stderr
        assert "WXYZ-0000" in login.stdout

        # First submit is accepted, the second is refused.
        first = grade("submit", "arrays/two_sum", cwd=student, env=env)
        assert first.returncode == 0, first.stdout + first.stderr
        second = grade("submit", "arrays/two_sum", cwd=student, env=env)
        assert second.returncode == 1
        assert "already submitted" in second.stdout
        assert app.dispatches == [("arrays/two_sum", 583231)]
        assert app.commits == [("arrays/two_sum", 583231, ["solution.py"])]
        assert app.refs == {slot_ref("arrays/two_sum", 583231)}

        # Faculty reset gives exactly one more submit.
        reset = grade("reset", "ada", "arrays/two_sum", cwd=tmp_path, env=env)
        assert reset.returncode == 0, reset.stdout + reset.stderr
        again = grade("submit", "arrays/two_sum", cwd=student, env=env)
        assert again.returncode == 0, again.stdout + again.stderr
        assert len(app.dispatches) == 2

        # Someone who is not on the roster cannot submit.
        (Path(env["GRADBOT_CONFIG_DIR"]) / "github_token").write_text("gho_eve", encoding="utf-8")
        stranger = grade("submit", "arrays/two_sum", cwd=student, env=env)
        assert stranger.returncode == 1
        assert "not on roster" in stranger.stdout
        assert len(app.dispatches) == 2


# ── course files ──────────────────────────────────────────────────────


def test_course_files_from_the_command_line(tmp_path, env):
    root = str(tmp_path / "gradecli")
    steps = [
        ("course", "add", "cs-fall", "--name", "CS Fall", "--root", root),
        ("course", "roster-add", "cs-fall", "--id", "42", "--username", "ada", "--root", root),
        ("assignment", "add", "cs-fall", "hello", "--name", "Hello", "--root", root),
        ("assignment", "test-add", "cs-fall", "hello", "--name", "prints hello", "--type", "io",
         "--points", "2", "--root", root),
    ]
    for step in steps:
        done = grade(*step, cwd=tmp_path, env=env)
        assert done.returncode == 0, (step, done.stdout, done.stderr)
    again = grade(*steps[1], cwd=tmp_path, env=env)
    assert again.returncode == 1
    assert "already on the roster" in again.stdout
