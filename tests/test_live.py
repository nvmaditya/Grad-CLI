"""Live smoke tests against the real GitHub. Off by default.

    GRADBOT_LIVE=1 pytest -m live -v

- Practice needs only the network (the demo samples repo is public).
- The device-code check needs GRADBOT_CLIENT_ID. It starts a login and
  stops before anyone approves it, so it changes nothing.
- The user lookup needs GRADBOT_APP_TOKEN. It is read-only.

Submit and reset are not smoke-tested: each would spend or delete a real
student's one graded attempt. Each part skips with a reason when its
setting is missing.
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

import pytest

from gradbot import net
from gradbot.config import load
from gradbot.policy import device_code_body
from gradbot.remote import github_user
from tests.conftest import REAL_ENV
from tests.samples_repo import TWO_SUM_SOLUTION

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        REAL_ENV.get("GRADBOT_LIVE") != "1", reason="set GRADBOT_LIVE=1 to talk to real GitHub",
    ),
]


def _needs(name: str) -> str:
    value = REAL_ENV.get(name)
    if not value:
        pytest.skip(f"{name} is not set")
    return value


def test_practice_against_the_public_demo_course(tmp_path, gradbot_home):
    sol = tmp_path / "sol"
    sol.mkdir()
    (sol / "solution.py").write_text(TWO_SUM_SOLUTION, encoding="utf-8")
    env = {**os.environ, "NO_COLOR": "1", "GRADBOT_PUBLIC_REPO": REAL_ENV.get("GRADBOT_PUBLIC_REPO", "")}
    done = subprocess.run(
        [sys.executable, "-m", "gradbot", "run", "arrays/two_sum"],
        cwd=sol, env={k: v for k, v in env.items() if v}, capture_output=True, text=True, timeout=180,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Accepted. All tests passed." in done.stdout


def test_github_starts_a_device_login_for_the_course_app():
    client_id = _needs("GRADBOT_CLIENT_ID")
    resp = net.request(
        "https://github.com/login/device/code", "POST",
        data=urllib.parse.urlencode(device_code_body(client_id)).encode(),
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.ok, resp.text
    started = resp.json_object("device_code", "user_code", "verification_uri")
    assert started["verification_uri"].startswith("https://github.com/")


def test_app_token_can_look_up_a_user_id():
    token = _needs("GRADBOT_APP_TOKEN")
    user = github_user(load({}), "octocat", token)
    assert user == {**user, "login": "octocat", "id": 583231}


def test_live_settings_never_reach_this_repo():
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=Path(__file__).parent.parent, capture_output=True, text=True,
    ).stdout.split()
    assert ".env" not in tracked
