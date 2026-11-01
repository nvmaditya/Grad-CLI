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
import sys
from pathlib import Path

from gradbot import __version__, config
from gradbot.errors import UserError
from gradbot.result import Mode

_COMMANDS_HELP = """\
commands:
  grade run TOPIC/PROBLEM          practise against the public checks
  grade dev PROBLEM_DIR            faculty: public checks, then hidden checks
  grade publish PROBLEM_DIR ...    faculty: split into tests and samples repos
  grade login                      sign in with GitHub (for graded submits)
  grade submit TOPIC/PROBLEM       the one graded submit, sent to the course App
  grade roster add LOGIN           faculty: enrol a student by GitHub id
  grade reset LOGIN TOPIC/PROBLEM  faculty: give a student one more submit
  grade results FILE               print a result without hidden detail
  grade course | assignment ...    classroom files (preview)

Run grade COMMAND --help for the options of each command.
"""


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the GradBot CLI."""
    _make_output_unbreakable()
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] in _HANDLERS:
        try:
            _dispatch(raw)
        except KeyboardInterrupt:
            print("\n\nGradBot cancelled. See you next time! 👋")
            sys.exit(130)
        except SystemExit:
            raise
        except UserError as e:
            print(f"❌ {e}")
            sys.exit(1)
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
        print("\n\nGradBot cancelled. See you next time! 👋")
        sys.exit(130)
    except SystemExit:
        raise
    except UserError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        _handle_fatal_error(e, verbose=args.verbose)
        sys.exit(1)


def _make_output_unbreakable() -> None:
    """Print ? instead of crashing when the terminal can't encode ✓, ✗ or emoji.

    A Windows console redirected to a file, or LANG=C, gives Python an
    ASCII or cp1252 stdout. Without this, the first ✓ raises
    UnicodeEncodeError and the student sees a traceback.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):  # closed or unsupported stream
                pass


def _positive_seconds(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a number of seconds") from None
    if not value > 0 or value != value or value == float("inf"):
        raise argparse.ArgumentTypeError("timeout must be a number of seconds above 0")
    return value


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="grade",
        description=(
            "GradBot — check a solution against a problem's checks.\n\n"
            "Example: grade run arrays/two_sum"
        ),
        epilog=_COMMANDS_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "slug",
        help=(
            "practice/{topic}/{problem}[@ref], or with --dev a problem folder.\n"
            "Same as `grade run` and `grade dev`, kept for older scripts."
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
        type=_positive_seconds,
        default=None,
        metavar="N",
        help="Seconds each run of the program may take (default: suite.yaml time_limit, else 5)",
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
        version=f"GradBot {__version__}",
    )

    return parser


def _run(args: argparse.Namespace) -> None:
    """Execute the GradBot check pipeline."""
    from gradbot.fetcher import FetchError, fetch, fetch_local
    from gradbot.git import GitError, ensure_git_installed
    from gradbot.resolver import SlugError, resolve

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
            timeout=args.timeout,
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
        timeout=args.timeout,
    )


def _handle_fatal_error(error: Exception, verbose: bool = False) -> None:
    """Handle unexpected errors gracefully — never show raw tracebacks to students."""
    print("\n❌ Oops! GradBot ran into an unexpected problem.")
    print("   This isn't your fault — it's a bug in GradBot.")
    print("   Please tell your teacher what happened.\n")

    if verbose:
        import traceback
        print("   Technical details:")
        traceback.print_exc()
    else:
        print(f"   Error: {error}")
        print("   (Run with --verbose for more details)")


def grade_student(
    suite_dir: Path,
    solution_dir: Path,
    verbose: bool = False,
    no_color: bool = False,
    faculty_output: str | None = None,
    student_output: str | None = None,
    timeout: float | None = None,
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
        timeout=timeout,
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
    timeout: float | None = None,
) -> None:
    """Run public checks, then hidden checks, and say which set failed."""
    public = _grade_one(
        suite_dir, solution_dir, "checks.py", "practice",
        verbose, no_color, sandbox, "Public checks",
        timeout=timeout, faculty=True,
    )
    hidden = None
    hidden_path = Path(suite_dir) / "checks_hidden.py"
    if hidden_path.is_file():
        hidden = _grade_one(
            suite_dir, solution_dir, "checks_hidden.py", "practice",
            verbose, no_color, sandbox, "Hidden checks",
            timeout=timeout,
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
    mode: Mode,
    verbose: bool,
    no_color: bool,
    sandbox: str | None,
    label: str | None,
    timeout: float | None = None,
    faculty: bool = False,
):
    from gradbot.compiler import compile_solution, restrict_languages
    from gradbot.loader import LoadError, load_checks
    from gradbot.reporter import render, render_compile_error
    from gradbot.runner import run_suite
    from gradbot.sandbox import IMAGES, ensure_image
    from gradbot.workspace import staged_solution

    if label:
        print(f"\n{label}")
    try:
        config, checks = load_checks(suite_dir, checks_filename)
    except LoadError as exc:
        # A broken suite is the author's to fix; say what is wrong, no traceback.
        print(f"❌ {exc}")
        sys.exit(1)
    if faculty and config.total_points:
        awarded = sum(check.points for check in checks)
        if awarded != config.total_points:
            print(
                f"⚠️  suite.yaml total_points is {config.total_points} but {checks_filename} "
                f"awards {awarded}. The score uses the checks."
            )
    # Compile and run from a private copy: binaries, .class files and
    # __pycache__ never land in the student's folder.
    with staged_solution(solution_dir) as stage:
        compile_result = restrict_languages(
            compile_solution(stage, static=sandbox == "docker"), config.languages,
        )
        if sandbox == "docker" and compile_result.success:
            ensure_image(IMAGES[compile_result.language])
        if not compile_result.success:
            render_compile_error(
                friendly_error=compile_result.friendly_error,
                raw_error=compile_result.error_output,
                verbose=verbose,
                no_color=no_color,
            )
        result = run_suite(
            config, checks, stage, compile_result, mode, sandbox=sandbox, default_timeout=timeout,
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
    _HANDLERS[argv[0]](argv[1:])


def _cmd_dev(argv: list[str]) -> None:
    from gradbot.fetcher import fetch_local

    args = _local_parser("dev").parse_args(argv)
    _require_solution(Path(args.solution))
    suite_dir = fetch_local(Path(args.path))
    grade_dev(
        suite_dir, Path(args.solution).resolve(),
        verbose=args.verbose, no_color=args.no_color,
        faculty_output=args.output, student_output=args.student_output,
        sandbox=args.sandbox, timeout=args.timeout,
    )


def _cmd_run(argv: list[str]) -> None:
    from gradbot.fetcher import fetch
    from gradbot.git import ensure_git_installed
    from gradbot.resolver import resolve

    args = _local_parser("run").parse_args(argv)
    _require_solution(Path(args.solution))
    slug = args.path
    if slug.startswith("submit/"):
        print("❌ grade run is practice only. Hidden tests are not on this computer.")
        sys.exit(1)
    if not slug.startswith("practice/"):
        slug = f"practice/{slug}"
    ensure_git_installed()
    suite_dir = fetch(resolve(slug), offline=args.offline)
    grade_student(
        suite_dir, Path(args.solution).resolve(),
        verbose=args.verbose, no_color=args.no_color,
        faculty_output=args.output, student_output=args.student_output,
        timeout=args.timeout,
    )


def _local_parser(name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"grade {name}")
    if name == "run":
        parser.add_argument("path", metavar="topic/problem[@ref]", help="Problem in the public samples repo")
        parser.add_argument("--offline", action="store_true", help="Use the copy downloaded earlier")
    else:
        parser.add_argument("path", metavar="PROBLEM_DIR", help="Folder with suite.yaml and checks.py")
        parser.add_argument(
            "--sandbox", choices=["docker"], default=None,
            help="Run the program in Docker with no network (Linux; used by the grader)",
        )
    parser.add_argument("--solution", default=".", metavar="DIR", help="Solution folder (default: .)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show expected output and logs")
    parser.add_argument("--no-color", action="store_true", help="Plain output")
    parser.add_argument("--output", default=None, metavar="FILE", help="Write the full JSON result")
    parser.add_argument(
        "--student-output", default=None, metavar="FILE",
        help="Write the JSON result without expected output",
    )
    parser.add_argument(
        "--timeout", type=_positive_seconds, default=None, metavar="SECONDS",
        help="Time limit per program run (default: suite.yaml time_limit, else 5)",
    )
    return parser


def _require_solution(path: Path) -> None:
    if not path.resolve().is_dir():
        print(f"❌ Solution directory not found: {path.resolve()}")
        sys.exit(1)


def _cmd_submit(argv: list[str]) -> None:
    from gradbot import remote

    parser = argparse.ArgumentParser(prog="grade submit")
    parser.add_argument("slug", help="topic/problem, for example arrays/two_sum")
    parser.add_argument("--solution", default=".")
    args = parser.parse_args(argv)
    solution = Path(args.solution).resolve()
    _require_solution(solution)
    remote.submit(config.load(), args.slug, solution)
    sys.exit(0)


def _cmd_login(argv: list[str]) -> None:
    from gradbot import remote

    argparse.ArgumentParser(prog="grade login").parse_args(argv)
    remote.login(config.load())
    sys.exit(0)


def _cmd_publish(argv: list[str]) -> None:
    from gradbot.fetcher import fetch_local
    from gradbot.policy import hidden_files_in, install_grader_workflow, publish_suite
    from gradbot.remote import problem_slug

    parser = argparse.ArgumentParser(prog="grade publish")
    parser.add_argument("suite")
    parser.add_argument("--tests", required=True, help="Checkout of the private tests repo")
    parser.add_argument("--samples", required=True, help="Checkout of the public samples repo")
    parser.add_argument("--slug", required=True, help="Path inside the repos, such as arrays/two_sum")
    args = parser.parse_args(argv)
    slug = problem_slug(args.slug)
    suite = fetch_local(Path(args.suite))
    tests_root = Path(args.tests).resolve()
    samples_root = Path(args.samples).resolve()
    leaked = hidden_files_in(samples_root)
    if leaked:
        raise UserError(
            "The public samples tree already contains hidden checks: "
            + ", ".join(leaked)
            + ". Remove them (and from that repo's history if it was pushed) before publishing."
        )
    publish_suite(suite, tests_root / slug, samples_root / slug)
    install_grader_workflow(tests_root)
    print(f"Published {slug}. checks_hidden.py stayed in the tests repo.")
    sys.exit(0)


def _cmd_results(argv: list[str]) -> None:
    from gradbot import remote

    parser = argparse.ArgumentParser(prog="grade results")
    parser.add_argument("file")
    args = parser.parse_args(argv)
    remote.results(Path(args.file))
    sys.exit(0)


def _cmd_reset(argv: list[str]) -> None:
    from gradbot import remote

    parser = argparse.ArgumentParser(prog="grade reset")
    parser.add_argument("login")
    parser.add_argument("slug")
    args = parser.parse_args(argv)
    remote.reset(config.load(), args.login, args.slug)
    sys.exit(0)


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
    from gradbot import remote

    parser = argparse.ArgumentParser(prog="grade roster")
    parser.add_argument("action", choices=["add"])
    parser.add_argument("login")
    parser.add_argument("--roster", required=True)
    args = parser.parse_args(argv)
    remote.roster_add(config.load(), args.login, Path(args.roster))
    sys.exit(0)


_HANDLERS = {
    "run": _cmd_run,
    "dev": _cmd_dev,
    "publish": _cmd_publish,
    "login": _cmd_login,
    "submit": _cmd_submit,
    "roster": _cmd_roster,
    "reset": _cmd_reset,
    "results": _cmd_results,
    "course": _cmd_course,
    "assignment": _cmd_assignment,
}
