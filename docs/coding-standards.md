# Coding standards

These rules override a reviewer's personal taste. A test that encodes a rule is the check.

## Course files

Join a path under the course directory only after `validate_slug`. A classroom name that is absolute, or that contains `..`, raises `CourseError` and writes nothing outside the course directory.

A roster row is seven columns: GitHub id, username, email, first name, last name, section, role. Write it as plain CSV. Usernames match the GitHub login pattern, so they contain no comma.

## Grade workflows

`grade_workflow_text()` must not contain `github.io` or the word `pages`.

A secret token appears only in the step that checks out the code it is for (`secrets.GRADE_APP_TOKEN` in the course template, `secrets.GRADBOT_APP_TOKEN` in the publish template).

The grade step sets `GRADE_APP_TOKEN`, `GITHUB_TOKEN`, and `GRADBOT_APP_TOKEN` to empty before `python -m gradbot dev`.

Workflow inputs reach the shell only through `env:`. No `${{ inputs.* }}` inside a `run:` block. Checkouts set `persist-credentials: false`.

## Errors and configuration

An error the person at the keyboard can understand or fix is a `UserError` (or a subclass) with a message that says what to do. Never let one reach the "unexpected problem" handler.

Environment variables are read in `gradbot/config.py` only, when a command runs, never at import. A new variable goes in `VARIABLES` and in `.env.example`; `tests/test_config.py` enforces both.

Nothing a student's program prints, and nothing a check raises, may crash GradBot. It becomes a `CheckResult`.

## Tests

Assert a literal a reader can check. Do not rebuild the expected value the way the implementation does.

Test a public function or the `grade` command. One new behavior gets one failing test before the code that makes it pass. A bug gets its regression test first.

The default suite needs no network and no secrets. Real GitHub goes in `tests/test_live.py`. Tests that need a compiler or Docker use the markers in `tests/toolchains.py`, which probe by running the tool, not by `shutil.which`.

## License and dependencies

New Python files include `SPDX-License-Identifier: GPL-3.0-only`. The program stays GPL-3.0-only.

Add a dependency only when a ticket says to.

## Graph

After a code change, run `graphify update .`. `graphify-out/` stays gitignored. The command is the requirement. The graph files are not part of the commit.
