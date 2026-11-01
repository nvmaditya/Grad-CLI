# Coding standards

These rules override a reviewer's personal taste. A test that encodes a rule is the check.

## Course files

Join a path under the course directory only after `validate_slug`. A classroom name that is absolute, or that contains `..`, raises `CourseError` and writes nothing outside the course directory.

A roster row is seven columns: GitHub id, username, email, first name, last name, section, role. Write it as plain CSV. Usernames match the GitHub login pattern, so they contain no comma.

## Grade workflow

`grade_workflow_text()` must not contain `github.io` or the word `pages`.

`${{ secrets.GRADE_APP_TOKEN }}` appears only in the step that checks out the student commit.

The grade step sets `GRADE_APP_TOKEN`, `GITHUB_TOKEN`, and `GRADBOT_APP_TOKEN` to empty before `python -m gradbot dev`.

## Tests

Assert a literal a reader can check. Do not rebuild the expected value the way the implementation does.

Test a public function or the `grade` command. One new behavior gets one failing test before the code that makes it pass.

## License and dependencies

New Python files include `SPDX-License-Identifier: GPL-3.0-only`. The program stays GPL-3.0-only.

Add a dependency only when a ticket says to.

## Graph

After a code change, run `graphify update .`. `graphify-out/` stays gitignored. The command is the requirement. The graph files are not part of the commit.
