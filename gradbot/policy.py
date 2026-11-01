"""Submit rules: roster by GitHub user id, one slot ref, no hidden files in samples.

No network. Callers pass an object with identity, create_ref, delete_ref, commit,
and dispatch. The slot ref is created only after the roster check. A failed
commit or dispatch deletes it. A finished grade does not.
"""

from __future__ import annotations

import io
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from gradbot import __version__
from gradbot.errors import UserError
from gradbot.loader import public_bundle_files
from gradbot.result import SuiteResult
from gradbot.visibility import student_payload

MAX_ZIP_BYTES = 1_048_576
_ALLOWED_EXTENSIONS = {".py", ".c", ".h", ".cpp", ".cc", ".hpp", ".java"}

# Where the grader installs GradBot from. Override per course with the
# repository variable GRADBOT_PIP_SPEC (for example a fork or a commit).
INSTALL_SPEC = f"grade-cli @ git+https://github.com/nvmaditya/gradbot@v{__version__}"

# Inputs reach the shell only through env, never as ${{ inputs.* }} inside
# run:, so a crafted slug cannot inject commands. Checkouts do not persist
# credentials, and the grade step clears every token before the student
# program starts.
WORKFLOW_TEXT = """\
name: grade

on:
  workflow_dispatch:
    inputs:
      slug:
        description: Problem slug, such as arrays/two_sum
        required: true
        type: string
      user_id:
        description: GitHub numeric user id
        required: true
        type: string
      submission_path:
        description: Path of the submission in the submissions repo
        required: true
        type: string

permissions:
  contents: read

concurrency:
  group: grade-${{ inputs.user_id }}-${{ inputs.slug }}
  cancel-in-progress: false

jobs:
  grade:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Check out hidden tests
        uses: actions/checkout@v4
        with:
          path: tests
          persist-credentials: false

      - name: Check out the submission
        uses: actions/checkout@v4
        with:
          repository: ${{ vars.GRADBOT_SUBMISSIONS_REPO }}
          token: ${{ secrets.GRADBOT_APP_TOKEN }}
          path: submission
          persist-credentials: false

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install GradBot
        env:
          GRADBOT_PIP_SPEC: ${{ vars.GRADBOT_PIP_SPEC || '@INSTALL_SPEC@' }}
        run: python -m pip install "$GRADBOT_PIP_SPEC"

      - name: Grade
        continue-on-error: true
        env:
          GITHUB_TOKEN: ""
          GRADBOT_APP_TOKEN: ""
          SLUG: ${{ inputs.slug }}
          SUBMISSION_PATH: ${{ inputs.submission_path }}
        run: |
          case "$SLUG/$SUBMISSION_PATH" in *..*) echo "refusing a path with .."; exit 1;; esac
          # docker run --rm --network none mounts only the solution directory.
          # checks_hidden.py stays in this process and is not mounted into the container.
          python -m gradbot dev "tests/$SLUG" --solution "submission/$SUBMISSION_PATH" --sandbox docker --output faculty.json --student-output student.json

      - name: Keep the results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: grade-${{ inputs.user_id }}-${{ github.run_id }}
          path: |
            faculty.json
            student.json
          if-no-files-found: warn
""".replace("@INSTALL_SPEC@", INSTALL_SPEC)


class PolicyError(UserError):
    """A submit or publish rule refused the request."""


@dataclass(frozen=True, slots=True)
class Identity:
    user_id: int
    login: str


@dataclass(frozen=True, slots=True)
class SubmitResult:
    accepted: bool
    reason: str
    user_id: int | None = None
    login: str | None = None
    ref: str | None = None
    dispatched: bool = False


def slot_ref(slug: str, user_id: int) -> str:
    """Atomic lock key. The login string is not part of it."""
    clean = slug.strip().strip("/")
    return f"refs/gradbot/slots/{clean}/{user_id}"


def status_comment(result: SuiteResult) -> str:
    """Short student-visible grade. Hint stays. Cause and log do not."""
    payload = student_payload(result)
    lines = [
        f"{payload['problem']}: {payload['passed_points']}/{payload['total_points']}"
    ]
    for check in payload["checks"]:
        hint = check.get("hint") or ""
        lines.append(f"{check['status']} {check['name']} {hint}".rstrip())
    return "\n".join(lines)


def device_code_body(client_id: str) -> dict:
    """Device-flow body. read:user proves identity and cannot read private repos."""
    return {"client_id": client_id, "scope": "read:user"}


def _roster_rows(text: str) -> list[dict]:
    """The students list of roster.yml. Every row needs a numeric id."""
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise PolicyError(f"roster is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyError("roster must be a mapping with a 'students' list")
    rows = data.get("students") or []
    if not isinstance(rows, list):
        raise PolicyError("roster 'students' must be a list")
    for row in rows:
        user_id = row.get("id") if isinstance(row, dict) else None
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
            raise PolicyError(f"roster row {row!r} has no numeric GitHub id")
    return rows


def parse_roster(text: str) -> set[int]:
    return {row["id"] for row in _roster_rows(text)}


def add_roster_entry(text: str, login: str, user_id: int) -> str:
    """Insert or replace one student. The numeric id is the key."""
    students = [row for row in _roster_rows(text) if row["id"] != int(user_id)]
    students.append({"id": int(user_id), "login": login})
    return yaml.safe_dump({"students": students}, sort_keys=False)


def safe_source_files(data: bytes, max_bytes: int = MAX_ZIP_BYTES) -> dict[str, bytes]:
    """Source files from a zip. Rejects path escape, hidden checks, and workflows."""
    if not data:
        raise PolicyError("empty zip")
    if len(data) > max_bytes:
        raise PolicyError("zip too large")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PolicyError("bad zip") from exc

    files: dict[str, bytes] = {}
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        if name.endswith("/"):
            continue
        parts = [part for part in name.split("/") if part != ""]
        if (
            not parts
            or name.startswith("/")
            or ".." in name.split("/")
            or info.filename.startswith("/")
        ):
            raise PolicyError(f"unsafe path {info.filename}")
        if ".." in parts or ".github" in parts or parts[-1] in {"checks_hidden.py", "checks.py"}:
            raise PolicyError(f"refused {info.filename}")
        if Path(parts[-1]).suffix.lower() not in _ALLOWED_EXTENSIONS:
            continue
        files["/".join(parts)] = archive.read(info)
    if not files:
        raise PolicyError("no source file")
    return files


def submit_once(
    ops,
    token: str,
    slug: str,
    files: dict[str, bytes],
    roster: set[int],
    body_login: str | None = None,
) -> SubmitResult:
    """One submit for (slug, user id). body_login is never read."""
    del body_login
    try:
        ident = ops.identity(token)
    except PolicyError:
        return SubmitResult(False, "unknown token")
    if ident.user_id not in roster:
        return SubmitResult(False, "not on roster", ident.user_id, ident.login)
    if not files:
        return SubmitResult(False, "empty submission", ident.user_id, ident.login)

    ref = slot_ref(slug, ident.user_id)
    if not ops.create_ref(ref):
        return SubmitResult(False, "already submitted", ident.user_id, ident.login, ref, False)
    try:
        ops.commit(slug, ident.user_id, ident.login, files)
        ops.dispatch(slug, ident.user_id)
    except Exception:
        ops.delete_ref(ref)
        return SubmitResult(False, "retry", ident.user_id, ident.login, ref, False)
    return SubmitResult(True, "accepted", ident.user_id, ident.login, ref, True)


def accept_zip(
    ops,
    token: str,
    slug: str,
    zip_bytes: bytes,
    roster: set[int],
    body_login: str | None = None,
) -> SubmitResult:
    """Validate the zip before the slot ref exists."""
    files = safe_source_files(zip_bytes)
    return submit_once(ops, token, slug, files, roster, body_login)


def reset_slot(ops, slug: str, user_id: int) -> None:
    """Faculty second chance. Does not grade."""
    ops.delete_ref(slot_ref(slug, user_id))


def publish_suite(suite_dir: Path, tests_dir: Path, samples_dir: Path) -> None:
    """Copy a problem. Hidden checks stay in the tests tree only.

    The tests tree gets every file and folder (such as ``expected/``) except
    ``sample_solution``. The samples tree gets suite.yaml, statement.md and
    checks.py, nothing else.
    """
    suite_dir = Path(suite_dir)
    tests_dir = Path(tests_dir)
    samples_dir = Path(samples_dir)
    tests_dir.mkdir(parents=True, exist_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)
    for path in suite_dir.iterdir():
        if path.name == "sample_solution" or path.name.startswith(".") or path.name == "__pycache__":
            continue
        if path.is_dir():
            shutil.copytree(
                path, tests_dir / path.name, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".*", "__pycache__"),
            )
        else:
            shutil.copy2(path, tests_dir / path.name)
    for path in public_bundle_files(suite_dir):
        shutil.copy2(path, samples_dir / path.name)


def hidden_files_in(samples_root: Path) -> list[str]:
    """Any checks_hidden.py under a public samples tree, as paths relative to it."""
    root = Path(samples_root)
    if not root.is_dir():
        return []
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("checks_hidden.py"))


def install_grader_workflow(tests_repo: Path) -> Path:
    """Write the grader workflow into the private tests repo only."""
    dest = Path(tests_repo) / ".github" / "workflows" / "grade.yml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(WORKFLOW_TEXT, encoding="utf-8")
    return dest
