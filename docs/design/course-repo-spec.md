# Grade CLI

## Problem Statement

A teacher needs to run a programming course on GitHub without paying for GitHub Team, GitHub Enterprise, or a hosted autograder. Students need a starter repository, one graded submit, and a score. Hidden checks must stay with the teacher.

## Solution

Grade CLI stores the course in a private GitHub repository on a free organization. The teacher creates classrooms, roster rows, and assignments from the `grade` command. A student gets a private starter repository. One tagged submit is graded inside the course repository. The faculty token never enters the student repository. A later static page can read the same files. The teacher can give the program away under GPL-3.0-only.

## User Stories

1. As a teacher, I want a classroom recorded as files, so that the course has no separate database.
2. As a teacher, I want that classroom marked as a free plan with Pages off, so that setup does not depend on a paid GitHub plan.
3. As a teacher, I want an assignment whose submit mode is one tag, so that grading does not run on every push.
4. As a teacher, I want to add a student to the roster with a GitHub user id and login, so that later invites match a real account.
5. As a teacher, I want a duplicate user id refused, so that one person has one roster row.
6. As a teacher, I want a role of student, teacher, head TA, or TA, so that staff and students stay distinct.
7. As a teacher, I want to attach a named test to an assignment, so that the grader knows what to run.
8. As a teacher, I want two tests with the same name refused, so that the score sheet is unambiguous.
9. As a teacher, I want a test type of input/output, command, or Python, so that simple checks do not need a custom runner.
10. As a teacher, I want the grade job to run in the course repository, so that hidden checks are not copied to the student.
11. As a teacher, I want the faculty token cleared before the student program runs, so that the program cannot read it.
12. As a teacher, I want the workflow to avoid GitHub Pages, so that a free organization can host the course.
13. As a teacher, I want a staged course tree I can inspect before any push, so that I can see the workflow and the classroom files.
14. As a teacher, I want `grade org init` to create a private course repository, so that tests are not public.
15. As a teacher, I want the Actions spending cap set to zero, so that a minute overrun stops instead of billing.
16. As a teacher, I want an advisory when GitHub hides billing, so that setup still finishes on a free organization.
17. As a teacher, I want classroom teams created with the student team secret, so that the roster is not a public team list.
18. As a teacher, I want to invite by GitHub username, so that I do not type a numeric id.
19. As a teacher, I want the invited id to be the id GitHub returns, so that a typed id cannot enroll the wrong person.
20. As a student, I want a starter repository named from the classroom, assignment, and my login, so that the name fits GitHub's limit.
21. As a teacher, I want accept to refuse a starter that contains hidden checks, so that solutions and private tests stay in the course repository.
22. As a student, I want one submit to record a slot for my user id and the commit, so that a second submit does not start a second grade.
23. As a student, I want the submit body to carry the repository and commit without a faculty token, so that my client never sees that secret.
24. As a teacher, I want scores stored as user, commit, points, and total, so that the gradebook has no compiler log.
25. As a teacher, I want a second score for the same student and assignment to replace the first, so that the one-slot rule holds.
26. As a teacher, I want one live grade on a free organization before any website, so that the CLI loop is proven.
27. As a teacher, I want a static page that shows a classroom name from a fixture, so that a browser view can start without a proxy.

## Implementation Decisions

- The course is a private repository named `gradecli` in the teacher's free GitHub organization.
- A classroom file records `plan: free` and `pages: false`.
- An assignment defaults to submission mode `tag` and holds a list of tests.
- A roster row is seven columns: GitHub id, username, email, first name, last name, section, role. Email, names, and section may be empty. Role defaults to student.
- Roles are student, teacher, head_ta, and ta.
- A test stores name, type, and points. Type is io, run, or python. Optional fields are run, expected, input, and timeout.
- Grading is a workflow dispatch in the course repository. It checks out the course and the student's commit. The student repository has no workflow and no hidden checks.
- The faculty token is the Actions secret `GRADE_APP_TOKEN` on the course repository only. The grade step unsets `GRADE_APP_TOKEN`, `GITHUB_TOKEN`, and `GRADBOT_APP_TOKEN` before `python -m gradbot dev`.
- Creating the course repository sends `private: true` and never calls a Pages URL.
- The spending-cap call sends `spending_limit: 0`. A 403 is an advisory, and setup still succeeds.
- Classroom teams are `gradecli-<classroom>` plus `-teacher`, `-hta`, and `-ta`. The student team is secret. Staff teams are closed.
- Invite loads `/users/{username}` and posts that numeric id. The command has no id argument.
- A student repository name is `<classroom>-<assignment>-<username>` lowercased, at most 100 characters.
- Accept copies a starter and refuses `checks_hidden.py` or a workflows directory in that copy.
- One score entry per user id per assignment. The entry is user id, sha, points, and total.
- Practice commands stay as they are.
- The license stays GPL-3.0-only. New code is a rewrite. Classroom 50 source is not copied.
- The Python import name stays `gradbot`. The command is `grade`.
- No new dependency.

## Testing Decisions

- Test behavior at the course functions and the `grade` command, using temporary directories and a fake HTTP transport.
- Expected values are literals: CSV lines, JSON fields, HTTP method, URL, and body fields.
- A good test tells what a teacher or student can do. It does not assert private helpers.
- Prior art is `tests/test_course.py`: temporary directory, public functions, pytest.raises on CourseError.
- GitHub calls are tested with an in-memory transport that records method, URL, and body. Tests fail if any URL contains `/pages`.
- The live free-organization grade is a manual check in the grade-and-scores ticket, not a unit test.

## Out of Scope

- Sealed pull requests and the earlier zero-rupee drops design.
- GitHub Team, Enterprise, and GitHub Pages.
- Email invites, group assignment teams, feedback pull requests, and pause-and-regrade, until a later request.
- A hosted sign-in proxy.
- Renaming the on-disk project folder.
- Copying Classroom 50 source or its branding.

## Further Notes

Session 0 already records a classroom and an assignment. The first ticket to implement is the roster row and the assignment test. The static page waits until one live grade has succeeded.
