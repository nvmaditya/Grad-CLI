# Contributing to GradBot

Thanks for helping. This page is how to get a working checkout, what the
tests expect, and what a change needs before it is merged.

## Set up

```bash
git clone https://github.com/nvmaditya/gradbot && cd gradbot
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The dev tools are pinned in `pyproject.toml`, so your results match CI's.

For the language tests you also want `gcc`, `g++` and a JDK (`javac -version`
must work; on macOS the `/usr/bin/javac` stub doesn't count). Without them,
those tests skip with a reason.

## Before you open a pull request

```bash
ruff check gradbot tests
mypy
pytest --cov
```

All three must pass. CI runs the same commands on Python 3.10–3.14.

## Tests

- **A bug gets its regression test first.** Write the test, watch it fail,
  then fix the code. Say in the commit that it failed before.
- **Assert literals a reader can check**, not values rebuilt the way the
  implementation builds them. More rules are in
  [docs/coding-standards.md](docs/coding-standards.md).
- **The default suite is offline and free.** Use `tests/fake_github.py` (a
  local HTTP server) for GitHub and course-App calls, and
  `tests/samples_repo.py` (bare git repos on disk) for practice fetches.
  Anything that talks to the real GitHub goes in `tests/test_live.py`.
- **Toolchain tests** use the markers in `tests/toolchains.py`: `needs_gcc`,
  `needs_gxx`, `needs_jdk`, `needs_docker`. They probe by running the tool.

| Run | Command |
|---|---|
| Everything offline | `pytest` |
| One area | `pytest tests/test_practice_fetch.py -v` |
| End to end only | `pytest -m e2e` |
| Docker sandbox | `pytest -m docker` (needs a Docker daemon) |
| Live smoke tests | `GRADBOT_LIVE=1 pytest -m live` (add `GRADBOT_CLIENT_ID` / `GRADBOT_APP_TOKEN` for the parts that need them) |
| Fail instead of skip on a missing toolchain | `GRADBOT_REQUIRE_TOOLCHAINS=gcc,g++,jdk,docker pytest` |

## Code

- Environment variables are read only in `gradbot/config.py`. A new one also
  goes in `VARIABLES` and `.env.example`.
- An error the user can fix is a `UserError` with a message that says what
  to do. The CLI prints it without a traceback.
- New Python files start with `# SPDX-License-Identifier: GPL-3.0-only`.
- Add a runtime dependency only with a good reason. GradBot needs only PyYAML.

## Commits

Small commits with [Conventional Commit](https://www.conventionalcommits.org/)
subjects (`fix(fetch): ...`, `test: ...`, `docs: ...`), and a body that says
what was wrong and how you know it is fixed.

## License

GradBot is GPL-3.0-only. By contributing you agree your contribution is
under the same license.
