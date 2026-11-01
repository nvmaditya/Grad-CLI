# GradBot for faculty

You write two check files per problem. Students run the public one
(`checks.py`) on their own computers. The hidden one (`checks_hidden.py`)
runs on your computer and, for graded submits, on a grader that students
cannot read. Students never receive a copy of it.

Install GradBot the same way students do (see the
[student guide](student-guide.md#install)). Docker is needed only if you run
the grader's sandbox yourself; for Java submissions that also needs JDK 21 or
newer, because Java is compiled for the sandbox image's Java 21 runtime
(`javac --release 21`).

## Author and check a problem

A problem folder has `suite.yaml`, `checks.py`, optionally
`checks_hidden.py`, `statement.md` and `sample_solution/`. The
[authoring guide](problem-authoring.md) covers every key and function.

```bash
grade dev problems/arrays/two_sum --solution problems/arrays/two_sum/sample_solution
```

`grade dev` prints a **Public checks** section, then a **Hidden checks**
section, then which set failed, if any. It exits 0 only when both pass. It
also warns when `scoring.total_points` disagrees with the points the public
checks award.

| Option | |
|---|---|
| `--output FILE` | Full JSON result, including each failure's `cause` and `log` (the expected output). |
| `--student-output FILE` | The same result with `cause` and `log` removed: what a student may see. |
| `--verbose` | Expected output and logs in the terminal. |
| `--timeout SECONDS` | Overrides the problem's `time_limit`. |
| `--sandbox docker` | Run the program in Docker with no network (Linux only; this is what the grader uses). |

`grade results faculty.json` prints a result with every `cause` and `log`
removed, for pasting where students can see it.

Keep expected answers out of hint text. Hints are shown to students on
purpose.

## Publish

Publishing splits one folder into two trees:

```bash
grade publish problems/arrays/two_sum \
  --tests ../course-tests --samples ../course-samples --slug arrays/two_sum
```

| Tree | Gets | Who can read it |
|---|---|---|
| `--tests` | everything except `sample_solution/`, and `.github/workflows/grade.yml` | faculty and the grader (make the repo private) |
| `--samples` | `suite.yaml`, `statement.md`, `checks.py` | students (make the repo public; practice sends no token) |

`publish` refuses a slug that is not `topic/problem`, and stops without
writing anything if the samples tree already contains a `checks_hidden.py`
anywhere. Commit and push both trees with the tool you already use, then tell
students the samples repo name (`GRADBOT_PUBLIC_REPO`).

## Graded submits: what exists and what you deploy

One graded submit per student per problem works like this:

```
student                   course App (you deploy)            GitHub
grade login  ───────────────────────────────────────────▶  device flow, scope read:user
grade submit ──zip + token──▶ accept_zip()
                              ├ identity: GET /user with the student token
                              ├ roster check by numeric id
                              ├ create refs/gradbot/slots/<slug>/<id>  (the lock)
                              ├ commit the files to the submissions repo
                              └ dispatch grade.yml in the tests repo ──▶ hidden checks in Docker
```

**In this repository and tested:** the `login` and `submit` client, the
submit rules in `gradbot.policy.accept_zip`, `grade roster add`,
`grade reset`, and the `grade.yml` template.

**Not in this repository:** the course App, the service at
`GRADBOT_SUBMIT_URL`. Nothing here listens on that URL. Until you deploy one,
`grade submit` tells students graded submits are not on yet.

The App receives a `POST` with the zip as the body,
`Authorization: Bearer <student token>` and `X-Gradbot-Slug: topic/problem`,
and calls:

```python
from gradbot.policy import accept_zip, parse_roster

result = accept_zip(ops, token, slug, zip_bytes, parse_roster(roster_yml_text))
# result.accepted, result.reason ("accepted", "not on roster", "already submitted", "retry", ...)
```

`ops` is your GitHub client with five methods: `identity(token)` returning
`Identity(user_id, login)` (raise `PolicyError` for a bad token),
`create_ref(ref)` returning `False` if it exists (this must be atomic; GitHub's
create-ref call is), `delete_ref(ref)`, `commit(slug, user_id, login, files)`
and `dispatch(slug, user_id)`. `accept_zip` checks the zip before any ref
exists: no path escapes, no `checks.py`, `checks_hidden.py` or `.github`, at
most 1 MB. If `commit` or `dispatch` raises, it deletes the ref so the student
can retry. Once dispatched, the slot stays used even if the program fails.
Reply with HTTP 200 for accepted, 409 for refused and 401 for a bad token,
and a JSON body `{"accepted": ..., "reason": ...}`. `grade submit` shows the
reason to the student.

`tests/test_e2e.py` contains a working in-memory App (`CourseApp`) that does
exactly this, driven by the real `grade` command. Use it as the reference.

### Roster and second chances

```bash
export GRADBOT_APP_TOKEN=...                       # faculty token, never on a student machine
grade roster add octocat --roster roster.yml       # looks up the numeric id on GitHub

export GRADBOT_SUBMISSIONS_REPO=your-org/course-submissions
grade reset octocat arrays/two_sum                 # deletes the slot ref: one more submit
```

The roster stores GitHub's numeric id, not the login, so a renamed account
keeps its place and a typed id can never enroll the wrong person.

### The grader workflow

`grade publish` writes `.github/workflows/grade.yml` into the tests tree. It
runs only on `workflow_dispatch` with `slug`, `user_id` and
`submission_path`, and:

1. checks out the tests repo and the submission (with `GRADBOT_APP_TOKEN`,
   only in that step, and without leaving credentials in `.git/config`),
2. installs Python 3.12, JDK 21 (Java is compiled on the runner with
   `--release 21` for the sandbox image's Java 21 runtime) and GradBot,
3. runs `grade dev --sandbox docker` with every token cleared: the student
   program runs in a container with no network, 512 MB, 256 processes, as a
   non-root user, with only the solution folder mounted,
4. fails the run if grading itself broke (no `student.json`), but not when
   the student's program fails,
5. keeps `faculty.json` and `student.json` as a run artifact.

Set on the tests repo: the secret `GRADBOT_APP_TOKEN`, and the variable
`GRADBOT_SUBMISSIONS_REPO`. The workflow installs
`gradbot @ git+https://github.com/nvmaditya/gradbot@v1.0.0`. That tag must
exist, or set the repository variable `GRADBOT_PIP_SPEC` to another pip
requirement (a fork, a commit).

The template's structure is tested, and a Docker-only test runs its Grade
step's script against a published tree (CI's Docker job runs it). The
workflow itself has not yet been dispatched on GitHub; see
[VERIFICATION_REPORT.md](../VERIFICATION_REPORT.md).

## Classroom files (preview)

```bash
grade course add cs-fall --name "CS Fall"
grade course roster-add cs-fall --id 583231 --username octocat
grade assignment add cs-fall hello --name "Hello"
grade assignment test-add cs-fall hello --name "prints hello" --type io --points 2
```

These write `classroom.json`, `roster.csv` and `assignments.json` under
`gradecli/`. They are the first step of running a course from one private
repo on a free GitHub organization. The later steps (creating the repo, team
invites, starter repos, tag-based submits, a score book) are on the roadmap;
see [design/course-repo-spec.md](design/course-repo-spec.md).
