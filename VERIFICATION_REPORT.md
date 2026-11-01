# Verification report

Date: 2026-11-01 · Branch: `harden` (from `main` at `8c5c216`) · Version: 1.0.0

This replaces the Phase 1 verification plan (same file, renamed; the plan is
in git history at `1de8df6`). It records what was verified, how, which test
covers each feature, the bugs found and fixed, and what is still unverified.

## How it was verified

| Item | Detail |
|---|---|
| Machine | macOS 26 (Darwin 25.6, arm64) |
| Python | 3.14.8 (Homebrew). Pins checked for 3.10 with `pip download --python-version 3.10`. |
| Compilers | Apple clang 21 as `gcc`/`g++`; Temurin JDK 21.0.13, unpacked into a scratch folder for the Java runs |
| Not available here | Docker, Windows, Python 3.10–3.13 interpreters, actionlint |
| Fresh clone | `git clone -b harden` into an empty folder with `env -i` and `HOME` set to an empty folder, then the README quickstart typed exactly as written: both commands graded 4/4 and the student folder was left with only `solution.py` |
| Suite in the fresh clone (final `harden` head) | Activated venv: **487 passed, 16 skipped**. Minimal `PATH`, venv not activated, JDK on PATH, `GRADBOT_REQUIRE_TOOLCHAINS=gcc,g++,jdk`, the CI test command: **490 passed, 2 skipped** (11 Docker/live deselected). Working tree clean afterwards. |
| Lint and types | `ruff check gradbot tests` clean; `mypy` (`check_untyped_defs`, `python_version = 3.10`) clean on 22 files |
| Coverage | **96%** line and branch over `gradbot/` (1866 statements, 536 branches) with the CI test command, including the `grade` subprocesses the end-to-end tests start. Uncovered: Windows-only branches, returns after `sys.exit`, a few defensive fallbacks |
| Live | `GRADBOT_LIVE=1 pytest -m live`: practice against the real public demo course **passed**; device-login start and user lookup **skipped** (no `GRADBOT_CLIENT_ID` / `GRADBOT_APP_TOKEN`) |
| CI | `.github/workflows/ci.yml` written; its lint, test and package steps were run locally and pass. **It has not run on GitHub**, because the branch is not pushed |

### Test inventory: 503 tests

| Group | Tests | Where they ran |
|---|---|---|
| Offline suite (`-m "not docker and not live"`) | 492 | Here, every run. 3 Java tests skip without a JDK and ran with one; 2 actionlint tests skip (not installed). |
| Docker (`-m docker`) | 7 | **Not run**: no Docker here. CI's `docker` job runs them. |
| Live (`-m live`) | 4 | 2 ran and passed (practice, `.env` not tracked); 2 skipped for missing keys. |

Largest files: `test_remote_commands.py` 44, `test_course.py` 40,
`test_edges.py` 35, `test_resolver.py` 29, `test_api.py` 27,
`test_practice_fetch.py` 26, `test_compiler_errors.py` 22, `test_loader.py` 21,
`test_policy.py` 21, `test_compiler.py` 21, `test_suite_settings.py` 19,
`test_e2e.py` 18, `test_workflows.py` 18, `test_reporter.py` 18,
`test_docs.py` 18 (every relative link resolves; every test cited here exists).

## Feature table

Status: **verified** = a test I ran passes against real code paths;
**verified (fake)** = verified against the local fake GitHub or fake course
App, not the real service; **unverified** = written, not run; **planned** =
not built, on the roadmap.

| # | Feature | Code | Status | Tests |
|---|---|---|---|---|
| 1 | Practice from the public samples repo (`grade run`, `GradBot practice/...`) | `cli._cmd_run`, `resolver`, `fetcher`, `git` | verified, and live against GitHub | `test_practice_fetch.py`; `test_e2e.py::test_practice_*`; `test_live.py::test_practice_against_the_public_demo_course` |
| 2 | Pinned refs: branch, tag, full commit | `git.clone_or_update` | verified | `test_practice_fetch.py::test_tag_ref_gets_the_tagged_content_not_main`, `::test_commit_ref_gets_that_commit`, `::test_branch_ref_with_a_slash`, `::test_unknown_ref_is_an_error_and_never_falls_back_to_main` |
| 3 | `--offline` and network fallback to the same ref | `fetcher.fetch`, `git.checkout_cached` | verified | `test_practice_fetch.py::test_offline_*`, `::test_network_failure_*`, `::test_failed_first_fetch_leaves_no_cache_behind`; `test_git.py::TestCloneOrUpdate` |
| 4 | Faculty `grade dev`: public then hidden, names the failing set | `cli.grade_dev` | verified | `test_e2e.py::test_every_bundled_problem_passes_its_sample_solution` (all 5), `::test_faculty_dev_names_the_failing_hidden_set_and_results_strip_it`; `test_cli_gate.py::test_dev_says_which_set_failed_and_strips_student_file` |
| 5 | Student runs refuse `checks_hidden.py` | `loader.guard_student_suite` | verified | `test_cli_gate.py::test_student_grade_refuses_*`; `test_hidden_load.py`; `test_e2e.py::test_practice_refuses_hidden_checks_next_to_the_solution` |
| 6 | Python solutions | `compiler._compile_python` | verified | `test_languages.py::*[python]`; `test_compiler.py::TestPythonInterpreter`; `test_student_folder.py` |
| 7 | C solutions | `compiler._compile_c` | verified (Apple clang) | `test_languages.py::*[c]`; `test_student_folder.py::test_c_grade_leaves_no_binary_in_the_student_folder` |
| 8 | C++ solutions | `compiler._compile_cpp` | verified (Apple clang) | `test_languages.py::*[cpp]` |
| 9 | Java solutions | `compiler._compile_java` | verified (Temurin 21) | `test_languages.py::*[java]`; `test_compiler_errors.py::test_java_main_class_is_the_file_with_main` |
| 10 | Compile errors as "error on line N" | `compiler._extract_friendly_error` | verified | `test_languages.py::test_compile_error_names_the_line_and_skips_checks` (4 languages); `test_compiler_errors.py::test_friendly_errors` |
| 11 | Check API: `run`, `expect_*`, `file_exists`, `CheckFailure`, hint order | `api.py`, `runner` | verified | `test_api.py`; `test_runner.py::TestHintPrecedence`, `::TestAssertionMessages` |
| 12 | Dependency order, skip on failed dependency, load errors | `loader._topological_sort`, `runner.run_suite` | verified | `test_loader.py`; `test_runner.py::TestRunSuiteDependencies` |
| 13 | Isolation: fresh copy per check, no tokens in the program's environment | `runner`, `workspace`, `api._child_env` | verified | `test_api.py::test_run_hides_tokens_from_the_student_program`; `test_student_folder.py`; `test_edges.py::test_a_failure_while_preparing_a_check_is_a_grader_error` |
| 14 | Terminal report, colours, `NO_COLOR`, ASCII terminals | `reporter.py`, `cli._make_output_unbreakable` | verified | `test_reporter.py`; `test_edges.py` (reporter section); `test_cli_output.py` |
| 15 | JSON results (`--output`, `--student-output`) and `grade results` | `cli._write_views`, `visibility`, `remote.results` | verified | `test_e2e.py::test_practice_json_output`, `::test_faculty_dev_names_the_failing_hidden_set_and_results_strip_it`; `test_remote_commands.py::test_results_*`; `test_visibility.py` |
| 16 | Exit code 0 only on full marks | `cli` | verified | every test in `test_e2e.py` asserts the exit code |
| 17 | `--timeout` | `cli._positive_seconds`, `api.run` | verified | `test_suite_settings.py::test_timeout_flag_*`, `::test_an_explicit_timeout_in_the_check_wins`, `::test_bad_timeout_flag_is_refused` |
| 18 | `suite.yaml`: `time_limit`, `languages`, `hints.general`, `total_points` | `loader.load_suite_config`, `compiler.restrict_languages`, `reporter` | verified | `test_suite_settings.py`; `test_loader.py` (suite.yaml section) |
| 19 | Docker sandbox (`--sandbox docker`) | `sandbox.py`, `api.run`, `runner` | **argv verified; execution unverified** | `test_sandbox.py` (argv, stdin flag, container paths, limits, kill on timeout, image pull) ran. `test_docker_sandbox.py` (6 real-daemon tests) did not run: no Docker here |
| 20 | `grade publish` | `policy.publish_suite`, `cli._cmd_publish` | verified | `test_publish.py`; `test_policy.py::test_publish_hides_checks_and_workflow_from_samples`; `test_e2e.py::test_publish_then_a_student_practises_the_published_problem` |
| 21 | Grader workflow `grade.yml` | `policy.WORKFLOW_TEXT` | **structure verified; never dispatched** | `test_workflows.py` (YAML parsed: triggers, install before grade, no inputs in shell, credentials, cleared tokens, grading-finished check). `::test_publish_grade_step_runs_for_real` needs Docker and did not run |
| 22 | `grade login` (device flow) | `remote.login` | verified (fake) | `test_remote_commands.py::test_login_*`; `test_e2e.py::test_graded_submit_round_trip`. Live device start skipped (no client id) |
| 23 | `grade submit` | `remote.submit` | verified (fake App) | `test_remote_commands.py::test_submit_*`; `test_e2e.py::test_graded_submit_round_trip` |
| 24 | Submit rules: roster by id, one slot, zip checks, rollback | `policy.accept_zip`, `submit_once`, `safe_source_files` | verified (in-memory ops) | `test_policy.py`; `test_edges.py` (zip and roster sections); `test_e2e.py::CourseApp` |
| 25 | `grade roster add` | `remote.roster_add` | verified (fake) | `test_remote_commands.py::test_roster_add_*`; `test_e2e.py::test_graded_submit_round_trip`. Live lookup skipped (no token) |
| 26 | `grade reset` | `remote.reset` | verified (fake) | `test_remote_commands.py::test_reset_*`; `test_e2e.py::test_graded_submit_round_trip` |
| 27 | Course files: classroom, roster, assignment, tests | `course.py`, `cli._cmd_course`, `_cmd_assignment` | verified (local files) | `test_course.py`; `test_e2e.py::test_course_files_from_the_command_line` |
| 28 | Course-repo grade workflow text | `grade_workflow.py` | structure verified; not reachable from the CLI | `test_grade_workflow.py`; `test_workflows.py` (`course` cases) |
| 29 | Old `GradBot submit/...` refused without touching a token | `resolver.resolve` | verified | `test_cli_gate.py::test_legacy_submit_does_not_ask_for_a_token`; `test_resolver.py::TestResolve::test_submit_does_not_clone_private_tests` |
| 30 | `--version`, `--help`, `python -m gradbot` | `cli` | verified | `test_e2e.py::test_version_and_help`, `::test_python_module_entry_point` |
| 31 | Config in one place, loud errors, `.env.example` in sync | `config.py` | verified | `test_config.py`; `test_practice_fetch.py::test_malformed_practice_repo_is_refused_by_name`; `test_cli_gate.py::test_malformed_practice_repo_setting_names_the_variable` |
| 32 | GitHub Enterprise URLs | `config`, `remote` | verified (fake) | every `test_remote_commands.py` test points `GRADBOT_GITHUB_URL` / `GRADBOT_GITHUB_API_URL` at the fake |
| 33 | Wheel builds and installs | `pyproject.toml` | verified | Run by hand: `python -m build --wheel`, installed into a clean venv, graded a bundled problem (the CI `package` job does the same) |
| 34 | `rich` output | — | removed | it was never imported |
| 35 | Reference course App | — | planned | roadmap |
| 36 | Course repo, teams, invites, starter repos, tag submits, scores, page | — | planned | roadmap; `docs/design/course-repo-tickets.md` 03–08 |
| 37 | Memory limits in local runs | — | planned | roadmap (Docker runs are capped at 512 MB) |
| 38 | Faculty authoring prompt | — | planned | roadmap; `docs/design/faculty-authoring-prompt.md` |
| 39 | Sealed pull-request grading | — | not planned | superseded by the course-repo design; `docs/design/sealed-pr-grading.md` |

LLM-specific checks from the brief (prompt construction, malformed model
output, rate limits) do not apply: GradBot calls no model. The same risks for
its real dependencies are covered: malformed, empty and non-JSON replies from
GitHub and the course App, HTTP errors, refused credentials, timeouts and a
dead network (`test_remote_commands.py`), and git failures (`test_practice_fetch.py`).

## Bugs found and fixed

Each one had a regression test that failed before the fix.

| Bug | Fixed in |
|---|---|
| Python solutions ran `python` from PATH; scored 0 where there is none (8 tests failed outside a venv) | `a2e1fe9` |
| Helper file run instead of `solution.py`; binaries, `.class`, `__pycache__` written into the student's folder and the suite | `66bb25b` |
| Invalid UTF-8 output reported as a grader error; non-ASCII output crashed under an ASCII locale | `dd296c7` |
| **Security:** the student program inherited `GRADBOT_APP_TOKEN` and other secrets from the environment | `dd296c7` |
| **Leak:** a plain `assert` message became the student-visible hint | `ac7bbcd` |
| Duplicate check names reported as a cycle; malformed `suite.yaml` reported as a crash; `render()` bound a stale `sys.stdout` | `ac7bbcd` |
| CLI crashed with a traceback on an ASCII/cp1252 terminal, inside its own error handler | `adcfed0` |
| Default practice repo did not exist; tag and commit refs silently graded the cached `main`; failed first fetch left a fake cache; git could block on a password prompt | `d6e0a62` |
| `--timeout`, `time_limit`, `languages`, `hints.general` parsed and ignored | `cbf3ea3` |
| Network commands printed "bug in Grade" for every failure; token file world-readable; submit zipped `.git` and binaries; token sendable over plain HTTP; login ignored `expires_in`/`slow_down` interval | `3734922` |
| The check author's hint never shown for an output mismatch | `7cd4c11` |
| Docker sandbox used host paths inside the container, never forwarded stdin, left containers running after a timeout, had no Java image | `052e935` |
| Grader workflow could not import GradBot (no install step), interpolated inputs into shell, kept checkout credentials | `55c0e6a` |
| `coverage==7.17.0` could not install on Python 3.10 | `72d44dc` |
| `publish --slug ../../x` wrote outside the repos; `expected/` folders never published; no check for leaked hidden checks in the samples tree | `c093c6a` |
| A broken grader passed the workflow because of `continue-on-error` | `ad4bdfc` |
| `.cxx` files compiled in practice but were left out of submit | `318ff58` |

## Still unverified, and why

| What | Why | How to close it |
|---|---|---|
| Docker sandbox execution (7 tests) | No Docker on this machine | Push and check CI's `docker` job |
| CI itself, Python 3.10–3.13, Ubuntu gcc, macOS runner | Branch not pushed; only 3.14 installed here | Push `harden`; the matrix runs them |
| Grader workflow on GitHub | Needs a course org, tests repo, secret and a dispatch | Publish a problem to a test org, dispatch `grade.yml` once |
| Workflow install step | It installs `gradbot @ git+...@v1.0.0`; **that tag does not exist yet** | Tag `v1.0.0` after merging, or set `GRADBOT_PIP_SPEC` |
| Live device login and roster lookup | No `GRADBOT_CLIENT_ID` / `GRADBOT_APP_TOKEN` supplied | `GRADBOT_LIVE=1 GRADBOT_CLIENT_ID=... GRADBOT_APP_TOKEN=... pytest -m live` |
| Live submit and reset | No course App exists, and each would spend or delete a real attempt | Deploy an App, then submit and reset once with a test account |
| Windows | Not available; not in the CI matrix | Add `windows-latest` to CI |
| actionlint on the workflow templates | Not installed; download was not allowed here | Install actionlint; `test_workflows.py::test_actionlint_accepts_the_template` runs automatically |
| `graphify update .` (required by `docs/coding-standards.md`) | graphify is not installed here | Run it after pulling |

## Removed

| What | Why |
|---|---|
| `setup.py`, `requirements*.txt` | Replaced by `pyproject.toml` with pinned dev tools |
| `rich`, `responses`, `pytest-mock` dependencies | Never imported |
| `workspace.working_area`, `workspace.cd`, `ResolvedSlug.cache_key`, `policy.credential_for`, `policy.student_can_read_private_repo` | No caller outside their own tests |
| `GRADBOT_PRIVATE_REPO`, `GRADBOT_TOKEN` reads | Read at import, never used |
| `scoring.pass_threshold`, `problem.memory_limit_mb` | First contradicted the exit code; second moved to the roadmap |
| `IMPLEMENTATION_LOG.md`, `.scratch/` | Folded into CHANGELOG and `docs/design/` |

## Other findings

- **Secrets in git history:** none. All of history was scanned for GitHub,
  OpenAI, AWS, Slack and Google key formats, private-key headers, and generic
  `token=` / `password=` assignments. The only matches are test fixtures
  (`ghp_test123`, `ghp_leak`, `secret-token`, `SECRET_9998`).
- **Local paths:** the research and plan notes contained another user's
  Windows temp paths; they are replaced with placeholders.
- **Corrections to my own commit messages:** `ac7bbcd` says
  `tests/test_loader.py` had 22 tests; it had 20. `cbf3ea3` says
  `tests/test_suite_settings.py` had 23; it had 19. The code and tests in
  those commits are as described; only the counts were wrong.
- **Side effect on this machine:** the very first README run created an
  empty `~/.gradbot/local/GradBot/gradbot-problems-public`. Deleting it was
  not permitted from here; it is safe to remove.
