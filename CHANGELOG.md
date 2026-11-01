# Changelog

All notable changes to GradBot. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-01

The first release that is tested end to end. Every bug below has a
regression test that failed before its fix. [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md)
lists the test that covers each feature.

### Fixed

- Python solutions ran `python` from PATH. Where there is none (pipx,
  Homebrew, stock Ubuntu) every Python solution scored zero. They now run
  under the interpreter running GradBot.
- The default practice repo did not exist, so the README quickstart failed.
  It is now the public demo course `nvmaditya/gradbot-course-samples`.
- `@tag` and `@commit` refs failed to check out and the run then graded the
  cached `main` while printing "Couldn't reach GitHub". Each ref now has its
  own cache entry and is never substituted.
- A failed first fetch left an empty folder that later runs treated as a
  cache. Missing repo, missing ref and network failure now get separate
  messages; only a network failure falls back to the cache.
- The author's `hint=` on `@gradbot.check` was never shown for an output
  mismatch, the most common failure. Order is now: the failing call's hint,
  then the check's hint, then a generic one.
- A plain `assert` message became the student-visible hint, which could
  leak the expected answer. It now goes to the faculty result only.
- A folder with `solution.py` and a helper ran whichever file sorted first.
- Compiling wrote binaries, `.class` files and `__pycache__` into the
  student's folder, and loading checks wrote `__pycache__` into the suite.
- Program output that was not valid UTF-8 was reported as a grader error,
  and a correct solution printing non-ASCII text failed under an ASCII
  locale.
- The CLI crashed with a traceback on a terminal that could not print ✓.
- `--timeout`, `time_limit`, `languages` and `hints.general` were parsed
  and ignored. They now work as documented.
- The Docker sandbox passed host paths into the container and never
  forwarded stdin, and a timed-out container kept running.
- The grader workflow written by `grade publish` had no Python setup or
  install step, interpolated inputs into the shell, and left checkout
  credentials on disk.
- `login`, `submit`, `roster add`, `reset` and `results` reported every
  network failure or odd reply as "a bug in Grade".
- `submit` zipped `.git` and binaries, so the 1 MB cap could refuse a tiny
  solution. It also skipped `.cxx` files that practice compiles.
- `publish --slug ../../x` wrote outside both repos, and `expected/` folders
  never reached the tests repo.
- Duplicate check names produced a false "circular dependency" error, and a
  malformed `suite.yaml` was reported as a crash.

### Security

- The student's program no longer inherits environment variables whose names
  contain TOKEN, SECRET, PASSWORD, CREDENTIAL, API_KEY or PRIVATE_KEY.
  Before, `grade dev` on a submission handed it `GRADBOT_APP_TOKEN`.
- The login token is stored with mode 0600, and `submit` refuses to send it
  over plain HTTP.
- git runs with `GIT_TERMINAL_PROMPT=0`. Refs starting with `-` or containing
  `..` are refused before git sees them.
- Docker runs get memory, process and CPU limits, `no-new-privileges`, and
  the caller's uid instead of root.
- The grader workflow fails when grading itself breaks, instead of passing
  silently.

### Added

- `gradbot/config.py`: every environment variable in one place, read at
  call time, with `.env.example` kept in step by a test.
- `GRADBOT_PUBLIC_REPO` accepts a git URL or a local path.
  `GRADBOT_GITHUB_URL` and `GRADBOT_GITHUB_API_URL` support GitHub Enterprise
  Server.
- `grade dev` warns when `scoring.total_points` disagrees with the checks.
- `grade --help` lists every subcommand.
- Test suite: unit, integration against a local fake GitHub and bare git
  repos, end-to-end runs of the installed `grade` command, real C, C++ and
  Java compilation, Docker sandbox tests, and opt-in live smoke tests.
- GitHub Actions CI: ruff, mypy, tests on Python 3.10–3.14 and macOS, the
  Docker sandbox, and a clean wheel install.

### Changed

- Packaging moved to `pyproject.toml` with pinned dev tools. The
  distribution is `gradbot`, and `--version` prints `GradBot 1.0.0`.
- `scoring.pass_threshold` and `problem.memory_limit_mb` are no longer read
  (the first contradicted the full-marks exit code; the second is on the
  roadmap).
- Docs live in `docs/`; design history is in `docs/design/`.

### Removed

- The `rich`, `responses` and `pytest-mock` dependencies, which nothing
  imported, and helpers nothing called (`working_area`, `cd`, `cache_key`,
  `credential_for`, `student_can_read_private_repo`).

## Before 1.0.0 (2026-10-11 to 2026-10-18)

Initial development, recorded in the git history:

- The local grading engine: check API, dependency ordering, Python, C, C++
  and Java, the terminal report, JSON output.
- Hidden checks kept off student machines: `checks_hidden.py`, `grade dev`,
  `grade publish`, student-safe JSON.
- The submit rules (`gradbot.policy`): roster by GitHub id, one slot ref,
  zip checks, rollback on failure; device login, roster and reset commands.
- The first two steps of the course-repo design: classroom files and the
  grade workflow text.

[1.0.0]: https://github.com/nvmaditya/gradbot/releases/tag/v1.0.0
