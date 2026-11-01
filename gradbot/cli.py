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

_COMMANDS = {
    "login", "run", "submit", "dev", "publish", "results", "reset", "roster",
    "course", "assignment",
}


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the GradBot CLI."""
    _make_output_unbreakable()
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] in _COMMANDS:
        try:
            _dispatch(raw)
        except KeyboardInterrupt:
            print("\n\nGrade cancelled. See you next time! 👋")
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
        print("\n\nGrade cancelled. See you next time! 👋")
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
        version=f"Grade CLI {__version__}",
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
        compile_result = restrict_languages(compile_solution(stage), config.languages)
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
    cmd = argv[0]
    if cmd == "dev":
        args = _local_parser("dev").parse_args(argv[1:])
        _require_solution(Path(args.solution))
        from gradbot.fetcher import FetchError, fetch_local
        try:
            suite_dir = fetch_local(Path(args.path).resolve())
        except FetchError as exc:
            print(f"❌ {exc}")
            sys.exit(1)
        grade_dev(
            suite_dir, Path(args.solution).resolve(),
            verbose=args.verbose, no_color=args.no_color,
            faculty_output=args.output, student_output=args.student_output,
            sandbox=args.sandbox, timeout=args.timeout,
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
        from gradbot.fetcher import FetchError, fetch
        from gradbot.git import GitError, ensure_git_installed
        from gradbot.resolver import SlugError, resolve
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
            timeout=args.timeout,
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
    parser.add_argument("--timeout", type=_positive_seconds, default=None)
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
