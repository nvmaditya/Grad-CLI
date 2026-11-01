# Course-repo tickets (sessions 1-8)

The ticket list from the course-repo plan. 01 and 02 are built and tested; 03 to 08 are planned (see the roadmap in the README).

## 01 — Roster rows and assignment tests

**What to build:** A teacher can add a student to a classroom roster and attach a named test to an assignment. A duplicate student or a duplicate test name is refused. The classroom stays on the free plan with Pages off.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] A roster row records the GitHub id, username, and role `student` in the seven-column CSV.
- [x] The same GitHub id cannot be added twice.
- [x] An assignment test stores name, type, and points, and the classroom file still says the free plan and Pages off.
- [x] A second test with the same name is refused.
- [x] `grade course roster-add` and `grade assignment test-add` do the same writes.

## 02 — Grade workflow text

**What to build:** The course grade workflow checks out the course and one student commit, then runs the existing grader. It never mentions GitHub Pages. The faculty token is cleared before the student program starts.

**Blocked by:** 01 — Roster rows and assignment tests

**Status:** done

- [x] The workflow text contains no Pages host.
- [x] The checkout of the student commit is the only step that names the faculty token.
- [x] The grade step clears the faculty token, `GITHUB_TOKEN`, and `GRADBOT_APP_TOKEN` before the grader runs.

## 03 — Stage the course tree

**What to build:** A teacher can stage a course directory that contains the classroom files and the grade workflow, and can read that directory before any push.

**Blocked by:** 02 — Grade workflow text

**Status:** ready-for-agent

- [ ] Staging copies the classroom files into a new directory.
- [ ] Staging writes the grade workflow beside them.
- [ ] The staged tree has no Pages file.

## 04 — Private course repository

**What to build:** A teacher can ask Grade CLI to create a private `gradecli` repository and set the Actions spending cap to zero dollars. If GitHub hides billing, setup says so and still finishes. No Pages site is enabled.

**Blocked by:** 03 — Stage the course tree

**Status:** ready-for-agent

- [ ] The create-repository call is private and named `gradecli`.
- [ ] No request URL contains `/pages`.
- [ ] A spending cap of zero returns set on success and advisory on 403.

## 05 — Teams and invites

**What to build:** A teacher can create the classroom teams and invite a student by GitHub username. The student team is secret. The roster id is the id GitHub returns for that username.

**Blocked by:** 04 — Private course repository

**Status:** ready-for-agent

- [ ] The student team is created as secret.
- [ ] Staff teams are created as closed.
- [ ] Invite posts the id from the username lookup and has no typed-id argument.
- [ ] The roster row uses that same id.

## 06 — Accept a starter repository

**What to build:** A student gets a private repository named from the classroom, assignment, and login. Accept refuses a starter that contains hidden checks or a workflow directory.

**Blocked by:** 05 — Teams and invites

**Status:** ready-for-agent

- [ ] The repository name is lowercase and at most 100 characters.
- [ ] A starter containing hidden checks is refused before a repository is created.
- [ ] The create call is private and does not enable Pages.

## 07 — Submit, grade, and scores

**What to build:** One tagged submit records a slot for that student and commit, without a faculty token in the body. The gradebook stores points and the commit, and a second grade for the same student replaces the first. One live run on a free organization confirms the student repository has no hidden checks.

**Blocked by:** 06 — Accept a starter repository

**Status:** ready-for-agent

- [ ] The submit body has the slot ref, repository, and commit, and no faculty token.
- [ ] A score entry is user id, commit, points, and total.
- [ ] A second score for the same student and assignment replaces the first.
- [ ] The live check on a free organization matches the seven steps in the session plan.

## 08 — Static classroom page

**What to build:** A teacher can open a local page and see a classroom name from a fixture file. The page does not call a sign-in proxy or GitHub Pages.

**Blocked by:** 07 — Submit, grade, and scores

**Status:** ready-for-agent

- [ ] The page shows the fixture classroom name.
- [ ] The test's network log contains no workers.dev host and no github.io host.
