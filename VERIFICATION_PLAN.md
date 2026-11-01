# Verification plan

Date: 2026-11-01 · Branch: `harden` · Base commit: `8c5c216`

This is the Phase 1 record. Nothing in the code was changed to produce it. Every
"broken" entry below was reproduced on this machine; the command or probe is
named next to it.

## 1. What GradBot is

GradBot (the README calls it "Grade CLI"; the command is `grade`) is a Python
command-line autograder for programming courses that live on a free GitHub
organization. A problem is a folder with `suite.yaml`, a public `checks.py`,
and an optional faculty-only `checks_hidden.py`. Checks are plain Python
functions decorated with `@gradbot.check(...)` that run the student's program
on stdin and compare its output.

Three audiences, from the docs and code:

- **Students** practise on their own machine against public checks fetched
  from a public "samples" Git repo (`grade run arrays/two_sum`). Later they
  make one graded submit, which zips the solution and POSTs it to a course
  service.
- **Faculty** run public and hidden checks locally (`grade dev <dir>`), split a
  problem into a private tests tree and a public samples tree
  (`grade publish`), manage a roster by numeric GitHub user id, and reset a
  student's single submit slot.
- **A grader** (GitHub Actions workflow in the private tests repo) runs the
  hidden checks on the submitted code in a no-network Docker container.

The commit history (6 commits, 2026-10-11 → 2026-10-18) shows three layers
added in sequence: the local grading engine, the "hidden checks never reach
the student" submit policy, and the first two sessions of an 8-session "Grade
CLI" plan for classroom files in a private `gradecli` course repo.

## 2. Stack, entry points, external dependencies

| Item | Detail |
|---|---|
| Language | Python ≥ 3.10 (setup.py). Only Python 3.14.8 exists on this machine. |
| Runtime deps | `pyyaml>=6.0` (unpinned upper bound) |
| Dev deps | `pytest`, `pytest-mock`, `responses`, `rich` — the last three are never imported |
| Packaging | `setup.py` (setuptools). No `pyproject.toml`. |
| Console scripts | `grade`, `GradBot` → `gradbot.cli:main`; also `python -m gradbot` |
| Tests | pytest, 145 tests in `tests/` |
| CI | none |
| Lint / types | none configured |

### External programs and services

| Dependency | Used by | Notes |
|---|---|---|
| `git` CLI | practice fetch (`git.py`) | shallow fetch of the samples repo over HTTPS |
| GitHub (HTTPS git) | `grade run` | public samples repo, no token |
| `python` on PATH | running every Python solution | hard-coded `["python", file]` |
| `gcc`, `g++` | C / C++ solutions | |
| `javac`, `java` | Java solutions | not runnable here (macOS stub, no JRE) |
| `docker` | `--sandbox docker` (grader only) | not installed here |
| GitHub OAuth device flow | `grade login` | `github.com/login/device/code`, `/login/oauth/access_token` |
| GitHub REST API | `grade roster add`, `grade reset` | `GET /users/{login}`, `DELETE /repos/{repo}/git/refs/...` |
| Course App at `GRADBOT_SUBMIT_URL` | `grade submit` | **not in this repo**; FACULTY.md says nothing listens there |
| GitHub Actions | `grade.yml` written by `grade publish` | never dispatched |

No database, no LLM provider, no chat-platform integration. "Bot" is in the
name only. The faculty "authoring prompt" is a design for a prompt to paste
into any chat; nothing in the code calls a model.

### Environment variables (all read in `cli.py` / `resolver.py`)

| Variable | Read by | Default | Notes |
|---|---|---|---|
| `GRADBOT_PUBLIC_REPO` | resolver (at import time) | `GradBot/gradbot-problems-public` | **default repo does not exist** |
| `GRADBOT_LOCAL_DIR` | resolver (at import time) | `~/.gradbot/local` | |
| `GRADBOT_CONFIG_DIR` | login, submit | `~/.gradbot` | token stored here |
| `GRADBOT_CLIENT_ID` | login | none | required for login |
| `GRADBOT_SUBMIT_URL` | submit | none | required for submit |
| `GRADBOT_APP_TOKEN` | roster add, reset | none | faculty secret |
| `GRADBOT_SUBMISSIONS_REPO` | reset | none | `owner/repo` |
| `NO_COLOR` | reporter | none | |
| `GRADBOT_PRIVATE_REPO`, `GRADBOT_TOKEN` | resolver | — | read, never used ("older installs") |

## 3. Feature inventory

Status key: **works** = I ran it and it did what the docs say; **broken** =
reproduced failure; **untested** = no test and not exercised; **stub** =
documented or parsed but does nothing; **planned** = design doc only.

| # | Feature | Where it lives | Status |
|---|---|---|---|
| 1 | Practice run from the public samples repo (`grade run t/p`, `GradBot practice/t/p`) | `cli._dispatch`, `cli._run`, `resolver.py`, `fetcher.py`, `git.py` | **broken** by default (repo missing, `python` on PATH); works with `GRADBOT_PUBLIC_REPO=nvmaditya/gradbot-course-samples` in an activated venv |
| 2 | Pinned ref `slug@ref` (branch / tag / commit) | `resolver.parse_slug`, `git.clone_or_update` | branch **works**; tag and commit **broken** — checkout of `origin/<ref>` fails and the run silently grades the previously cached `main` |
| 3 | Offline mode and stale-cache fallback | `fetcher.fetch`, `git.clone_or_update` | **broken**: a failed first fetch leaves an empty `git init` folder that is then treated as a cache ("Couldn't reach GitHub… using cached tests") |
| 4 | Faculty dev run: public then hidden checks, names the failing set | `cli.grade_dev` (`grade dev`, `GradBot --dev`) | **works** (needs `python` on PATH) |
| 5 | Refuse `checks_hidden.py` in a student run | `loader.guard_student_suite`, `cli.grade_student` | **works**, tested |
| 6 | Python solutions | `compiler._compile_python`, `get_run_command` | **broken**: runs `python` from PATH; picks the alphabetically first `.py` as the entry point; writes `__pycache__` into the student folder |
| 7 | C solutions (`gcc`) | `compiler._compile_c` | **works** (manual probe); no test compiles real C; binary written into the student folder |
| 8 | C++ solutions (`g++ -std=c++17`) | `compiler._compile_cpp` | **works** (manual probe); no test |
| 9 | Java solutions (`javac` / `java -cp`) | `compiler._compile_java`, `runner._adjust_command_for_workdir` | **untested** (no JRE here) |
| 10 | Friendly compiler errors, raw output behind `--verbose` | `compiler._extract_friendly_error`, `reporter.render_compile_error` | **works**, parser unit-tested |
| 11 | Check-author API: `@check`, `run`, `expect_output` (exact/contains/regex), `expect_exit`, `expect_sequence`, `file_exists`, `CheckFailure` | `loader.check`, `api.py` | partly tested; `expect_*` and `file_exists` have no tests. Invalid UTF-8 from the program becomes a check **error** blamed on the teacher |
| 12 | Dependency DAG: topological order, skip dependents, cycle and unknown-dependency errors | `loader._topological_sort`, `runner.run_suite` | skipping tested; ordering, cycles, unknown deps **untested**; duplicate function names produce a false "circular dependency" error |
| 13 | Per-check isolation in a fresh temp dir | `runner._run_single_check` | **works**, tested indirectly |
| 14 | Terminal report (✓ ✗ ○, colours, `NO_COLOR`, progress bar, verdict) | `reporter.py` | **works**, tested; **crashes with a raw traceback** when stdout can't encode the glyphs (`PYTHONIOENCODING=ascii`) |
| 15 | JSON results: `--output` (faculty) and `--student-output` (cause/log stripped) | `cli._write_views`, `visibility.py` | **works**, tested |
| 16 | Exit code 0 on full score, 1 otherwise | `cli.grade_student`, `cli.grade_dev` | **works**, partly tested |
| 17 | `--timeout N` | `cli._build_parser` | **stub**: parsed, never used; absent from `run`/`dev` |
| 18 | `suite.yaml` settings: `time_limit`, `memory_limit_mb`, `languages`, `pass_threshold`, `total_points`, `hints.general`, `difficulty`, `description` | `loader.load_suite_config` | **stub**: parsed, never read. PROBLEM_AUTHORING.md documents them as enforced |
| 19 | Docker sandbox (`--sandbox docker`) | `sandbox.py`, `api.run` | **broken** by inspection: passes host paths into the container, no `-i` so stdin never reaches the program, a timeout kills the client but not the container. Docker is not installed here |
| 20 | Publish: split into private tests tree and public samples tree | `policy.publish_suite`, `cli._cmd_publish` | **works**, tested |
| 21 | Grader workflow `grade.yml` written by publish | `policy.WORKFLOW_TEXT`, `install_grader_workflow` | **broken** by inspection: no setup-python or install step, so `python -m gradbot` cannot import; `GRADBOT_APP_TOKEN` not cleared; never dispatched |
| 22 | Login via GitHub device flow | `cli._cmd_login`, `policy.device_code_body` | **untested**; token file written with default (world-readable) mode; network or non-JSON errors print "it's a bug in Grade" |
| 23 | Submit: zip the solution and POST it to the course App | `cli._cmd_submit` | **untested**; zips the whole folder (including `.git`, binaries), so the 1 MB cap can refuse a tiny solution; network errors print "bug in Grade" |
| 24 | Submit policy: roster by numeric id, one slot ref, zip guard, rollback on failure | `policy.accept_zip`, `submit_once`, `safe_source_files`, `reset_slot`, `status_comment` | **works** against an in-memory fake, tested. The service that would call it is **not in the repo** |
| 25 | `grade roster add <login>` (GitHub lookup → `roster.yml`) | `cli._cmd_roster`, `policy.add_roster_entry` | library tested; command **untested** |
| 26 | `grade reset <login> <slug>` (delete the slot ref) | `cli._cmd_reset` | **untested** |
| 27 | `grade results <file>` (print with cause/log removed) | `cli._cmd_results` | **untested** |
| 28 | Course files: classroom, roster CSV, assignment, assignment tests | `course.py`, `cli._cmd_course`, `cli._cmd_assignment` | **works** (local files only), tested |
| 29 | Course-repo grade workflow text | `grade_workflow.py` | text tested; not reachable from the CLI (session 3 of the plan) |
| 30 | Old `GradBot submit/…` slug refused without touching a token | `resolver.resolve` | **works**, tested |
| 31 | `--version` | `cli._build_parser` | **works** |
| 32 | `rich` enhanced output | `setup.py` extra, reporter docstring | **stub**: never imported |
| 33 | Faculty authoring prompt section in FACULTY.md | `docs/superpowers/specs/2026-10-11-…` | **planned** (spec only; FACULTY.md has no such section) |
| 34 | Sealed pull-request grading | `docs/plans/2026-10-12-zero-rupee-grading.md` | **planned** (the newer plan says not to build it) |
| 35 | Course repo creation, teams, invites, starter repos, tag submit, scores, static page | `.scratch/grade-cli/issues/03–08`, `docs/superpowers/plans/2026-10-18-grade-cli.md` | **planned** |

## 4. Fresh clone, README followed literally

Clone into a temp directory, then the README's commands in order.

| Step | Command | Result |
|---|---|---|
| 1 | `git clone https://github.com/nvmaditya/gradbot` | ok |
| 2 | `pip install -e .` | **fails**: `pip: command not found` (macOS ships `pip3`) |
| 2a | `pip3 install -e .` | **fails**: PEP 668 `externally-managed-environment`. The README has no virtualenv step |
| 2b | `python3 -m venv .venv && . .venv/bin/activate && pip install -e .` | ok (not in README) |
| 3 | write `solution.py` from the README | ok |
| 4 | `GradBot practice/arrays/two_sum` | **fails**, exit 1: `⚠️ Couldn't reach GitHub … Using cached tests` then `Couldn't find the problem`. The default repo `GradBot/gradbot-problems-public` does not exist; the network was fine. Side effect: an empty `~/.gradbot/local/GradBot/gradbot-problems-public` is left behind |
| 4a | `GRADBOT_PUBLIC_REPO=nvmaditya/gradbot-course-samples python -m gradbot run arrays/two_sum` (STUDENT.md) | ok, 4/4, exit 0 — **inside the activated venv** |
| 4b | same engine via `.venv/bin/grade dev …` without the venv on PATH | **fails**: sample solution scores 0/4, hint "Something went wrong trying to run your code" (`python` not found) |
| 5 | `gradbot login` / `gradbot run …` (README "Commands") | there is no `gradbot` script; it only resolves on macOS because the file system is case-insensitive and finds `GradBot` |
| 6 | `pip install -e ".[dev]"`, `pytest tests/ -v` | 145 passed in the venv; **8 failed** with the venv not on PATH (same `python` bug) |
| 7 | `GradBot --dev ./problems/arrays/two_sum --solution ./problems/arrays/two_sum/sample_solution` | ok, 4/4 in the venv |

## 5. Other probes

| Probe | Result |
|---|---|
| C O(n²) and C++ hash-map Two Sum via `grade dev` | 4/4 each; `solution` binary left in the student folder |
| `solution.py` plus `aaa_helper.py` | 0/4: the helper is run as the program |
| Program writes bytes `\xff\xfe` to stdout | status **error**, hint "Ask your teacher" |
| Unicode round trip (`héllo wörld — 你好 🙂`) | passes |
| Same with `PYTHONIOENCODING=ascii` | raw `UnicodeEncodeError` traceback from `_handle_fatal_error` |
| `grade practice/arrays/two_sum@v2` and `@<sha>` against a local bare repo | "Couldn't reach GitHub" then 4/4 graded against `main` |
| Secret scan of all history (`ghp_`, `github_pat_`, `sk-`, `AKIA`, private keys, generic `token=` / `password=`) | **clean**. Only test fixtures (`ghp_test123`, `ghp_leak`, `secret-token`) |

## 6. How each phase will be verified

- **Run.** Fix the `python` lookup, the fetch and ref handling, the missing default
  repo, install docs, and loud config errors. Add `.env.example`.
- **Test.** pytest with `pytest-cov`. Unit tests for every module, including
  empty, very long, malformed and unicode input. Integration tests for each
  inventory row, with GitHub HTTP replaced by a local fake server and the
  samples repo replaced by a local bare repo (git's `url.<base>.insteadOf`), so
  the suite runs offline. End-to-end tests drive the installed `grade` script
  as a subprocess. Every bug above gets a failing test before the fix.
- **Toolchain-gated tests.** C/C++ run here. Java and Docker are skipped here
  (checked by running `javac -version`, not `shutil.which`, because macOS ships
  a stub) and run in CI on `ubuntu-latest`.
- **Live smoke.** Separate `live` marker: practice against the real samples repo
  when `GRADBOT_LIVE=1`; GitHub API calls only when their tokens are set.
  Skipped otherwise.
- **CI.** GitHub Actions: ruff, mypy, the offline suite on a Python version
  matrix. I will not push; confirming CI on GitHub is on the owner's checklist.
- **No LLM.** The LLM-specific checks in the brief (prompt construction,
  malformed model output, rate limits) do not apply: the code calls no model.
  The equivalent risk is a malformed response from GitHub or the course App,
  and those paths get the same treatment.

## 7. Needs secrets (deferred to the owner)

| What | Why |
|---|---|
| `GRADBOT_CLIENT_ID` (GitHub OAuth app) | live device-code login |
| `GRADBOT_APP_TOKEN` + `GRADBOT_SUBMISSIONS_REPO` | live roster lookup and slot reset |
| A deployed course App at `GRADBOT_SUBMIT_URL` | live submit; the App is not in this repo |
| A course org with the tests repo and Actions enabled | dispatching `grade.yml` |

Everything else runs without secrets.
