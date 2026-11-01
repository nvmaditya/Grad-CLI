"""
Check runner for GradBot.

Executes checks in dependency order, handles isolation (temp dir per check),
catches all exceptions, and produces a SuiteResult.
"""

from __future__ import annotations

import shutil
import tempfile
import time
import traceback
from pathlib import Path

from gradbot import api
from gradbot.compiler import CompileResult, get_run_command
from gradbot.loader import CheckFunction, SuiteConfig
from gradbot.result import CheckResult, Mode, SuiteResult


def run_suite(
    config: SuiteConfig,
    checks: list[CheckFunction],
    solution_dir: Path,
    compile_result: CompileResult,
    mode: Mode,
    sandbox: str | None = None,
) -> SuiteResult:
    """
    Execute all checks in dependency order and return a SuiteResult.

    Rules:
    - If compilation failed, ALL checks are skipped
    - Checks run in topological order (from loader)
    - If a check's dependency failed/skipped/errored, the check is SKIPPED
    - Each check runs with a fresh copy of the student files in a temp dir
    - ALL exceptions are caught — the CLI never crashes from a bad check

    Args:
        config: The parsed suite.yaml configuration
        checks: Checks in topological (execution) order
        solution_dir: Path to the student's solution directory
        compile_result: Result of compiling the student's code
        mode: "practice" or "submit"

    Returns:
        SuiteResult with all check outcomes
    """
    results: list[CheckResult] = []
    # Track status by slug for dependency resolution
    status_map: dict[str, str] = {}

    # ── If compilation failed, skip everything ─────────────────────
    if not compile_result.success:
        for check in checks:
            results.append(CheckResult(
                name=check.name,
                slug=check.slug,
                status="skip",
                description="Skipped — your code needs to compile first",
                hint=compile_result.friendly_error or None,
                points=check.points,
            ))
            status_map[check.slug] = "skip"

        return SuiteResult(
            problem=config.name,
            topic=config.topic,
            mode=mode,
            checks=results,
        )

    # ── Build the run command ──────────────────────────────────────
    run_command = get_run_command(compile_result)

    # ── Execute each check ─────────────────────────────────────────
    for check in checks:
        # Check if dependency passed
        if check.depends_on is not None:
            dep_status = status_map.get(check.depends_on)
            if dep_status != "pass":
                result = CheckResult(
                    name=check.name,
                    slug=check.slug,
                    status="skip",
                    description=f"Skipped — depends on '{check.depends_on}' which didn't pass",
                    hint="Fix the earlier check first, then this one will run!",
                    points=check.points,
                )
                results.append(result)
                status_map[check.slug] = "skip"
                continue

        # Run the check in isolation
        result = _run_single_check(
            check, solution_dir, run_command, compile_result, sandbox=sandbox,
        )
        results.append(result)
        status_map[check.slug] = result.status

    return SuiteResult(
        problem=config.name,
        topic=config.topic,
        mode=mode,
        checks=results,
    )


def _run_single_check(
    check: CheckFunction,
    solution_dir: Path,
    run_command: list[str],
    compile_result: CompileResult,
    sandbox: str | None = None,
) -> CheckResult:
    """
    Run a single check function in an isolated temp directory.

    Catches ALL exceptions and converts them to CheckResult.
    Never raises — always returns a result.
    """
    start_time = time.perf_counter_ns()
    log_lines: list[str] = []

    try:
        # Create isolated working directory
        with tempfile.TemporaryDirectory(prefix="gradbot_") as temp_dir:
            work_dir = Path(temp_dir)

            # Copy student's files into the temp dir
            _copy_solution_files(solution_dir, work_dir, compile_result)

            # Adjust run command for the temp directory
            adjusted_cmd = _adjust_command_for_workdir(
                run_command, solution_dir, work_dir, compile_result
            )

            # Set up the API context so run(), expect_output(), etc. work
            api.set_context(
                solution_dir=solution_dir,
                run_command=adjusted_cmd,
                work_dir=work_dir,
                sandbox=sandbox,
            )

            try:
                # Execute the check function
                check.func()

                # If we get here, the check passed
                elapsed_ms = (time.perf_counter_ns() - start_time) // 1_000_000
                return CheckResult(
                    name=check.name,
                    slug=check.slug,
                    status="pass",
                    description=check.name,
                    duration_ms=elapsed_ms,
                    points=check.points,
                    log=log_lines,
                )

            except api.CheckFailure as e:
                elapsed_ms = (time.perf_counter_ns() - start_time) // 1_000_000
                hint = e.hint or check.hint or "Try reviewing your approach!"

                log_lines.append(f"CheckFailure: {e}")
                if hasattr(e, "expected") and e.expected is not None:
                    log_lines.append(f"  Expected: {e.expected!r}")
                if hasattr(e, "actual") and e.actual is not None:
                    log_lines.append(f"  Actual:   {e.actual!r}")

                return CheckResult(
                    name=check.name,
                    slug=check.slug,
                    status="fail",
                    description=check.name,
                    hint=hint,
                    cause=str(e),
                    duration_ms=elapsed_ms,
                    points=check.points,
                    log=log_lines,
                )

            except AssertionError as e:
                # Support plain assert statements in checks
                elapsed_ms = (time.perf_counter_ns() - start_time) // 1_000_000
                hint = check.hint or str(e) or "One of the assertions in this check failed."
                log_lines.append(f"AssertionError: {e}")

                return CheckResult(
                    name=check.name,
                    slug=check.slug,
                    status="fail",
                    description=check.name,
                    hint=hint,
                    cause=str(e) or "Assertion failed",
                    duration_ms=elapsed_ms,
                    points=check.points,
                    log=log_lines,
                )

            except Exception as e:
                # Unexpected error in the check itself
                elapsed_ms = (time.perf_counter_ns() - start_time) // 1_000_000
                tb = traceback.format_exc()
                log_lines.append(f"Unexpected error: {type(e).__name__}: {e}")
                log_lines.append(tb)

                return CheckResult(
                    name=check.name,
                    slug=check.slug,
                    status="error",
                    description=check.name,
                    hint="Something unexpected went wrong with this check. Ask your teacher for help!",
                    cause=f"{type(e).__name__}: {e}",
                    duration_ms=elapsed_ms,
                    points=check.points,
                    log=log_lines,
                )
            finally:
                api.clear_context()

    except Exception as e:
        # Even the temp dir setup failed
        elapsed_ms = (time.perf_counter_ns() - start_time) // 1_000_000
        return CheckResult(
            name=check.name,
            slug=check.slug,
            status="error",
            description=check.name,
            hint="GradBot had trouble setting up this check. Ask your teacher for help!",
            cause=f"Setup error: {type(e).__name__}: {e}",
            duration_ms=elapsed_ms,
            points=check.points,
        )


def _copy_solution_files(
    solution_dir: Path, work_dir: Path, compile_result: CompileResult
) -> None:
    """Copy the student's files into the isolated working directory."""
    for item in solution_dir.iterdir():
        if item.name.startswith("."):
            continue  # skip hidden files
        if item.name == "__pycache__":
            continue

        dest = work_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


def _adjust_command_for_workdir(
    run_command: list[str],
    original_dir: Path,
    work_dir: Path,
    compile_result: CompileResult,
) -> list[str]:
    """
    Adjust the run command to work in the new temp directory.

    For compiled languages, the binary path needs to point to the copy
    in the work dir. For interpreted languages, the script path changes.
    """
    if not run_command:
        return []

    adjusted = list(run_command)
    lang = compile_result.language

    if lang == "python":
        # Replace the script path to point to the work dir
        if len(adjusted) >= 2:
            original_script = Path(adjusted[1])
            adjusted[1] = str(work_dir / original_script.name)
    elif lang in ("c", "cpp"):
        # The binary was copied to work_dir
        if adjusted:
            original_binary = Path(adjusted[0])
            adjusted[0] = str(work_dir / original_binary.name)
    elif lang == "java":
        # Java runs by class name, but needs the work_dir as classpath
        if len(adjusted) >= 2:
            # java -cp work_dir ClassName
            adjusted = ["java", "-cp", str(work_dir), adjusted[-1]]

    return adjusted
