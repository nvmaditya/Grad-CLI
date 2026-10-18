"""
CLI entry point for GradBot.

Usage::

    GradBot practice/arrays/two_sum
    GradBot submit/trees/inorder --verbose
    GradBot --dev ./problems/arrays/two_sum --solution ./my_solution

This module handles argument parsing, top-level dispatch, and the
global exception handler that ensures students never see a raw traceback.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from gradbot import __version__

_COMMANDS = {
    "login", "run", "submit", "dev", "publish", "results", "reset", "roster",
    "course", "assignment",
}


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the GradBot CLI."""
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] in _COMMANDS:
        try:
            _dispatch(raw)
        except KeyboardInterrupt:
            print("\n\nGrade cancelled. See you next time! 👋")
            sys.exit(130)
        except SystemExit:
            raise
        except Exception as e:
            _handle_fatal_error(e, verbose="--verbose" in raw or "-v" in raw)
            sys.exit(1)
        return

    parser = _build_parser()
    args = parser.parse_args(argv)

    # ── Version ────────────────────────────────────────────────────
    # (handled by argparse --version action)

    # ── Global exception handler ──────────────────────────────────
    # Wrap everything so students never see a traceback
    try:
        _run(args)
    except KeyboardInterrupt:
        print("\n\nGrade cancelled. See you next time! 👋")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        _handle_fatal_error(e, verbose=args.verbose)
        sys.exit(1)


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="grade",
        description=(
            "Grade CLI — check a solution on a free GitHub organization.\n\n"
            "Example: grade practice/arrays/two_sum"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "slug",
        help=(
            "Problem identifier. Format: {practice|submit}/{topic}/{problem}\n"
            "Examples:\n"
            "  practice/arrays/two_sum    — practice mode with public tests\n"
            "  submit/trees/inorder       — submit mode with hidden tests"
        ),
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full details and logs on failures",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Save JSON results to FILE",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        metavar="N",
        help="Per-check timeout in seconds (default: 5)",
    )

    parser.add_argument(
        "--solution",
        metavar="DIR",
        default=".",
        help="Path to solution directory (default: current directory)",
    )

    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use cached test suite, skip network",
    )

    parser.add_argument(
        "--dev",
        action="store_true",
        help=(
            "Development mode: treat slug as a local path to a problem suite.\n"
            "Runs checks.py and checks_hidden.py.\n"
            "Example: grade --dev ./problems/arrays/two_sum"
        ),
    )

    parser.add_argument(
        "--student-output",
        metavar="FILE",
        help="Save the student-visible JSON (no expected output) to FILE",
    )

    parser.add_argument(
        "--sandbox",
        choices=["docker"],
        default=None,
        help="Run the student program in a container. Used by the grader workflow.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"Grade CLI {__version__}",
    )

    return parser


def _run(args: argparse.Namespace) -> None:
    """Execute the GradBot check pipeline."""
    from gradbot.fetcher import fetch, fetch_local, FetchError
    from gradbot.git import ensure_git_installed, GitError
    from gradbot.resolver import resolve, SlugError

    solution_dir = Path(args.solution).resolve()

    # Validate solution directory
    if not solution_dir.is_dir():
        print(f"❌ Solution directory not found: {solution_dir}")
        print("Make sure you're in the right folder, or use --solution DIR")
        sys.exit(1)

    # ── Step 0: Ensure git is available (needed for fetching) ──────
    if not args.dev:
        try:
            ensure_git_installed()
        except GitError as e:
            print(f"❌ {e}")
            sys.exit(1)

    # ── Step 1: Resolve or locate the problem suite ────────────────
    if args.dev:
        suite_path = Path(args.slug).resolve()
        try:
            suite_dir = fetch_local(suite_path)
        except FetchError as e:
            print(f"❌ {e}")
            sys.exit(1)
        grade_dev(
            suite_dir,
            solution_dir,
            verbose=args.verbose,
            no_color=args.no_color,
            faculty_output=args.output,
            student_output=args.student_output,
            sandbox=args.sandbox,
        )
        return

    try:
        resolved = resolve(args.slug)
    except SlugError as e:
        print(f"❌ {e}")
        sys.exit(1)

    try:
        suite_dir = fetch(resolved, offline=args.offline)
    except FetchError as e:
        print(f"❌ {e}")
        sys.exit(1)

    grade_student(
        suite_dir,
        solution_dir,
        verbose=args.verbose,
        no_color=args.no_color,
        faculty_output=args.output,
        student_output=args.student_output,
    )


def _handle_fatal_error(error: Exception, verbose: bool = False) -> None:
    """Handle unexpected errors gracefully — never show raw tracebacks to students."""
    print("\n❌ Oops! Grade ran into an unexpected problem.")
    print("   This isn't your fault — it's a bug in Grade.")
    print("   Please tell your teacher what happened.\n")

    if verbose:
        import traceback
        print("   Technical details:")
        traceback.print_exc()
    else:
        print(f"   Error: {error}")
        print("   (Run with --verbose for more details)")


def save_login_token(token: str, config_dir: Path) -> Path:
    """Store the device token outside the solution directory."""
    path = Path(config_dir) / "github_token"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    return path


def grade_student(
    suite_dir: Path,
    solution_dir: Path,
    verbose: bool = False,
    no_color: bool = False,
    faculty_output: str | None = None,
    student_output: str | None = None,
) -> None:
    """Public checks only. Refuse a hidden file in the suite or the solution."""
    from gradbot.loader import LoadError, guard_student_suite

    try:
        guard_student_suite(suite_dir)
        guard_student_suite(solution_dir)
    except LoadError as exc:
        print(f"❌ {exc}")
        sys.exit(1)

    print("Practice runs on this computer. The submit machine may differ.")
    result = _grade_one(
        suite_dir, solution_dir, "checks.py", "practice", verbose, no_color, None, None,
    )
    _write_views(result, None, faculty_output, student_output)
    sys.exit(0 if result.score >= 1.0 else 1)


def grade_dev(
    suite_dir: Path,
    solution_dir: Path,
    verbose: bool = False,
    no_color: bool = False,
    faculty_output: str | None = None,
    student_output: str | None = None,
    sandbox: str | None = None,
) -> None:
    """Run public checks, then hidden checks, and say which set failed."""
    public = _grade_one(
        suite_dir, solution_dir, "checks.py", "practice",
        verbose, no_color, sandbox, "Public checks",
    )
    hidden = None
    hidden_path = Path(suite_dir) / "checks_hidden.py"
    if hidden_path.is_file():
        hidden = _grade_one(
            suite_dir, solution_dir, "checks_hidden.py", "practice",
            verbose, no_color, sandbox, "Hidden checks",
        )
    else:
        print("No hidden checks in this problem.")

    if public.score < 1.0:
        print("Public checks failed")
    if hidden is not None and hidden.score < 1.0:
        print("Hidden checks failed")

    _write_views(public, hidden, faculty_output, student_output)
    failed = public.score < 1.0 or (hidden is not None and hidden.score < 1.0)
    sys.exit(1 if failed else 0)


def _grade_one(
    suite_dir: Path,
    solution_dir: Path,
    checks_filename: str,
    mode: str,
    verbose: bool,
    no_color: bool,
    sandbox: str | None,
    label: str | None,
):
    from gradbot.compiler import compile_solution
    from gradbot.loader import load_checks
    from gradbot.reporter import render, render_compile_error
    from gradbot.runner import run_suite

    if label:
        print(f"\n{label}")
    config, checks = load_checks(suite_dir, checks_filename)
    compile_result = compile_solution(solution_dir)
    if not compile_result.success:
        render_compile_error(
            friendly_error=compile_result.friendly_error,
            raw_error=compile_result.error_output,
            verbose=verbose,
            no_color=no_color,
        )
    result = run_suite(
        config, checks, solution_dir, compile_result, mode, sandbox=sandbox,
    )
    render(result, verbose=verbose, no_color=no_color)
    return result


def _write_views(public, hidden, faculty_output, student_output) -> None:
    from gradbot.visibility import faculty_payload, student_payload

    if not faculty_output and not student_output:
        return
    faculty = {"public": faculty_payload(public)}
    student = {"public": student_payload(public)}
    if hidden is not None:
        faculty["hidden"] = faculty_payload(hidden)
        student["hidden"] = student_payload(hidden)
    if faculty_output:
        Path(faculty_output).write_text(json.dumps(faculty, indent=2), encoding="utf-8")
    if student_output:
        Path(student_output).write_text(json.dumps(student, indent=2), encoding="utf-8")


def _dispatch(argv: list[str]) -> None:
    cmd = argv[0]
    if cmd == "dev":
        args = _local_parser("dev").parse_args(argv[1:])
        _require_solution(Path(args.solution))
        from gradbot.fetcher import fetch_local, FetchError
        try:
            suite_dir = fetch_local(Path(args.path).resolve())
        except FetchError as exc:
            print(f"❌ {exc}")
            sys.exit(1)
        grade_dev(
            suite_dir, Path(args.solution).resolve(),
            verbose=args.verbose, no_color=args.no_color,
            faculty_output=args.output, student_output=args.student_output,
            sandbox=args.sandbox,
        )
        return
    if cmd == "run":
        args = _local_parser("run").parse_args(argv[1:])
        _require_solution(Path(args.solution))
        slug = args.path
        if slug.startswith("submit/"):
            print("❌ gradbot run is practice only. Hidden tests are not on this computer.")
            sys.exit(1)
        if not slug.startswith("practice/"):
            slug = f"practice/{slug}"
        from gradbot.fetcher import fetch, FetchError
        from gradbot.git import ensure_git_installed, GitError
        from gradbot.resolver import resolve, SlugError
        try:
            ensure_git_installed()
            resolved = resolve(slug)
            suite_dir = fetch(resolved, offline=args.offline)
        except (GitError, SlugError, FetchError) as exc:
            print(f"❌ {exc}")
            sys.exit(1)
        grade_student(
            suite_dir, Path(args.solution).resolve(),
            verbose=args.verbose, no_color=args.no_color,
            faculty_output=args.output, student_output=args.student_output,
        )
        return
    if cmd == "submit":
        _cmd_submit(argv[1:])
        return
    if cmd == "login":
        _cmd_login(argv[1:])
        return
    if cmd == "publish":
        _cmd_publish(argv[1:])
        return
    if cmd == "results":
        _cmd_results(argv[1:])
        return
    if cmd == "reset":
        _cmd_reset(argv[1:])
        return
    if cmd == "roster":
        _cmd_roster(argv[1:])
        return
    if cmd == "course":
        _cmd_course(argv[1:])
        return
    if cmd == "assignment":
        _cmd_assignment(argv[1:])
        return
    print(f"❌ Unknown command {cmd}")
    sys.exit(2)


def _local_parser(name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"gradbot {name}")
    parser.add_argument("path" if name != "run" else "path", help="Problem directory or slug")
    parser.add_argument("--solution", default=".")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", default=None)
    parser.add_argument("--student-output", default=None)
    parser.add_argument("--sandbox", choices=["docker"], default=None)
    return parser


def _require_solution(path: Path) -> None:
    if not path.resolve().is_dir():
        print(f"❌ Solution directory not found: {path.resolve()}")
        sys.exit(1)


def _cmd_submit(argv: list[str]) -> None:
    import io
    import zipfile

    from gradbot.policy import PolicyError, safe_source_files

    parser = argparse.ArgumentParser(prog="gradbot submit")
    parser.add_argument("slug")
    parser.add_argument("--solution", default=".")
    args = parser.parse_args(argv)
    solution = Path(args.solution).resolve()
    _require_solution(solution)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for path in solution.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(solution).as_posix())
    try:
        safe_source_files(buf.getvalue())
    except PolicyError as exc:
        print(f"❌ {exc}")
        sys.exit(1)

    url = os.environ.get("GRADBOT_SUBMIT_URL")
    if not url:
        print("Hidden tests are not on this computer.")
        print("Set GRADBOT_SUBMIT_URL to your course App, then run: gradbot submit " + args.slug)
        print("Practice with: gradbot run " + args.slug)
        sys.exit(1)
    token_file = Path(os.environ.get("GRADBOT_CONFIG_DIR", Path.home() / ".gradbot")) / "github_token"
    if not token_file.is_file():
        print("❌ Run gradbot login first.")
        sys.exit(1)
    token = token_file.read_text(encoding="utf-8").strip()
    status, response = _http(
        url,
        method="POST",
        data=buf.getvalue(),
        headers={
            "Authorization": f"Bearer {token}",
            "X-Gradbot-Slug": args.slug,
            "Content-Type": "application/zip",
        },
    )
    print(response)
    sys.exit(0 if status == 200 else 1)


def _cmd_login(argv: list[str]) -> None:
    import time
    import urllib.parse

    from gradbot.policy import device_code_body

    argparse.ArgumentParser(prog="gradbot login").parse_args(argv)
    client_id = os.environ.get("GRADBOT_CLIENT_ID")
    if not client_id:
        print("Set GRADBOT_CLIENT_ID to the course GitHub OAuth app id, then run gradbot login.")
        print("The requested scope is read:user. That proves who you are. It does not enroll you.")
        sys.exit(1)
    body = urllib.parse.urlencode(device_code_body(client_id)).encode()
    status, payload = _http(
        "https://github.com/login/device/code",
        method="POST",
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )
    if status != 200:
        print(f"❌ GitHub login failed: {payload}")
        sys.exit(1)
    started = json.loads(payload)
    print(f"Open {started['verification_uri']} and enter {started['user_code']}")
    interval = int(started.get("interval", 5))
    deadline = time.time() + 15 * 60
    while time.time() < deadline:
        time.sleep(interval)
        poll = urllib.parse.urlencode({
            "client_id": client_id,
            "device_code": started["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }).encode()
        status, raw = _http(
            "https://github.com/login/oauth/access_token",
            method="POST",
            data=poll,
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        )
        token_payload = json.loads(raw) if raw else {}
        if "access_token" in token_payload:
            config = Path(os.environ.get("GRADBOT_CONFIG_DIR", Path.home() / ".gradbot"))
            path = save_login_token(token_payload["access_token"], config)
            print(f"Logged in. Token saved to {path}")
            sys.exit(0)
        error = token_payload.get("error")
        if error == "slow_down":
            interval += 5
            continue
        if error == "authorization_pending":
            continue
        print(f"❌ GitHub login failed: {error or raw}")
        sys.exit(1)
    print("❌ The device code expired. Run gradbot login again.")
    sys.exit(1)


def _cmd_publish(argv: list[str]) -> None:
    from gradbot.policy import install_grader_workflow, publish_suite

    parser = argparse.ArgumentParser(prog="gradbot publish")
    parser.add_argument("suite")
    parser.add_argument("--tests", required=True, help="Checkout of the private tests repo")
    parser.add_argument("--samples", required=True, help="Checkout of the public samples repo")
    parser.add_argument("--slug", required=True, help="Path inside the repos, such as arrays/two_sum")
    args = parser.parse_args(argv)
    suite = Path(args.suite).resolve()
    tests_root = Path(args.tests).resolve()
    samples_root = Path(args.samples).resolve()
    publish_suite(suite, tests_root / args.slug, samples_root / args.slug)
    install_grader_workflow(tests_root)
    print(f"Published {args.slug}. checks_hidden.py stayed in the tests repo.")
    sys.exit(0)


def _cmd_results(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="gradbot results")
    parser.add_argument("file")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    print(json.dumps(_strip_secrets(payload), indent=2))
    sys.exit(0)


def _strip_secrets(value):
    if isinstance(value, dict):
        return {
            key: _strip_secrets(item)
            for key, item in value.items()
            if key not in {"cause", "log"}
        }
    if isinstance(value, list):
        return [_strip_secrets(item) for item in value]
    return value


def _cmd_reset(argv: list[str]) -> None:
    from gradbot.policy import slot_ref

    parser = argparse.ArgumentParser(prog="gradbot reset")
    parser.add_argument("login")
    parser.add_argument("slug")
    args = parser.parse_args(argv)
    token = os.environ.get("GRADBOT_APP_TOKEN")
    repo = os.environ.get("GRADBOT_SUBMISSIONS_REPO")
    if not token or not repo:
        print("Faculty only. Set GRADBOT_APP_TOKEN and GRADBOT_SUBMISSIONS_REPO.")
        print("A student token cannot delete a slot.")
        sys.exit(1)
    user = _github_user(args.login, token)
    ref = slot_ref(args.slug, int(user["id"]))
    print(f"Reset {user['login']} id {user['id']} by deleting {ref}")
    api_ref = ref.removeprefix("refs/")
    status, response = _http(
        f"https://api.github.com/repos/{repo}/git/refs/{api_ref}",
        method="DELETE",
        token=token,
    )
    print(response or "deleted")
    sys.exit(0 if status in (200, 204) else 1)


def _cmd_course(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="grade course")
    sub = parser.add_subparsers(dest="action", required=True)
    add = sub.add_parser("add")
    add.add_argument("slug")
    add.add_argument("--name", required=True)
    add.add_argument("--root", default="gradecli")
    roster = sub.add_parser("roster-add")
    roster.add_argument("slug")
    roster.add_argument("--id", required=True, type=int)
    roster.add_argument("--username", required=True)
    roster.add_argument("--role", default="student")
    roster.add_argument("--root", default="gradecli")
    args = parser.parse_args(argv)
    from gradbot.course import CourseError, add_classroom, add_roster_row
    try:
        if args.action == "add":
            path = add_classroom(Path(args.root), args.slug, args.name)
            print(f"Created {path}")
        else:
            add_roster_row(Path(args.root), args.slug, args.id, args.username, args.role)
            print(f"Added {args.username} to {args.slug}")
    except CourseError as exc:
        print(f"❌ {exc}")
        sys.exit(1)


def _cmd_assignment(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="grade assignment")
    sub = parser.add_subparsers(dest="action", required=True)
    add = sub.add_parser("add")
    add.add_argument("classroom")
    add.add_argument("slug")
    add.add_argument("--name", required=True)
    add.add_argument("--root", default="gradecli")
    test_add = sub.add_parser("test-add")
    test_add.add_argument("classroom")
    test_add.add_argument("slug")
    test_add.add_argument("--name", required=True)
    test_add.add_argument("--type", required=True, dest="test_type")
    test_add.add_argument("--points", required=True, type=int)
    test_add.add_argument("--run", default=None)
    test_add.add_argument("--expected", default=None)
    test_add.add_argument("--root", default="gradecli")
    args = parser.parse_args(argv)
    from gradbot.course import CourseError, add_assignment, add_test
    try:
        if args.action == "add":
            add_assignment(Path(args.root), args.classroom, args.slug, args.name)
            print(f"Added {args.classroom}/{args.slug}")
        else:
            body = {"name": args.name, "type": args.test_type, "points": args.points}
            if args.run is not None:
                body["run"] = args.run
            if args.expected is not None:
                body["expected"] = args.expected
            add_test(Path(args.root), args.classroom, args.slug, body)
            print(f"Added test {args.name}")
    except CourseError as exc:
        print(f"❌ {exc}")
        sys.exit(1)


def _cmd_roster(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="grade roster")
    parser.add_argument("action", choices=["add"])
    parser.add_argument("login")
    parser.add_argument("--roster", required=True)
    args = parser.parse_args(argv)
    from gradbot.policy import add_roster_entry

    token = os.environ.get("GRADBOT_APP_TOKEN")
    if not token:
        print("Set GRADBOT_APP_TOKEN. The id has to come from GitHub, not from a number you type.")
        sys.exit(1)
    user = _github_user(args.login, token)
    print(f"GitHub says login {user['login']} id {user['id']}. Writing that id.")
    path = Path(args.roster)
    current = path.read_text(encoding="utf-8") if path.is_file() else "students: []\n"
    path.write_text(add_roster_entry(current, user["login"], int(user["id"])), encoding="utf-8")
    print(f"Wrote {path}")
    sys.exit(0)


def _github_user(login: str, token: str) -> dict:
    status, raw = _http(f"https://api.github.com/users/{login}", token=token)
    if status != 200:
        print(f"❌ GitHub did not resolve {login}: {raw}")
        sys.exit(1)
    return json.loads(raw)


def _http(url: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None, token: str | None = None) -> tuple[int, str]:
    import urllib.error
    import urllib.request

    req_headers = {"User-Agent": "gradbot", "Accept": "application/vnd.github+json"}
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    if headers:
        req_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
