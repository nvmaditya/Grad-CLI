# Grade on GitHub for zero rupees

## Recommendation

Keep the public drops repository. Do not put a readable solution in it.

`gradbot submit` encrypts the solution on the student laptop with the course public key, then opens a pull request whose only files are `submit.yml` and `solution.sealed`. Classmates can see the pull request. They cannot decrypt it. Copying the sealed file into their own pull request fails, because the seal is bound to the author's numeric GitHub id and the slug.

The private grader is the only place with the private key. It decrypts, stores plaintext in a private submissions repo the course already owns, and runs the hidden tests. Faculty read code there. Faculty never accept an invite, and faculty are never added to a student repository.

No rented server. No faculty laptop left on. Practice stays `gradbot run` on the public samples repo. Hidden grading spends the 2,000 private Actions minutes. The spending limit is $0.

## Why the other shapes fail

GitHub has no write-only access. Anyone who can read a repo can read every branch, pull request, and file in it. Anyone who can push can read.

| Idea | What happens |
| --- | --- |
| Public pull request with `solution.py` | Simple, and classmates can copy it. |
| Faculty added to each student's private repo | Does not scale. Rejected. |
| One private repo per student, owned by the course | No faculty invite, but the student still accepts one org invite per term. Use this only if sealed files are rejected. |
| A secret in a workflow the student can edit | They print the secret. Rejected. |
| `pull_request_target` that checks out and runs the student's branch | The job that holds the key can be turned into a leak. Rejected. |
| Cron that polls for new work | Burns the 2,000 minutes while idle. Rejected. |
| Write-only deploy key | GitHub does not offer one. |
| `sha` written inside `submit.yml` | A commit cannot contain its own hash. Putting the hash in the file creates a new commit with a different hash. The same is true of a bot that "corrects" the file. Rejected. |
| Faculty PAT pushes a correction onto the student's fork | A fine-grained PAT is limited to named repos. It cannot push to that fork. Rejected. |

Students can still hand a classmate the file on chat. No GitHub setting stops that. This plan stops copying from the course repository.

## Tries

Per student, per problem:

| Kind | Limit | Private minutes | Uses the grade |
| --- | --- | --- | --- |
| Bad structure | 3 | None. Closed on the public repo. | No |
| Seal that will not open | 3, same cap | About 1 minute. Decrypt only, no Docker. | No |
| Hidden grade | 1 | About 3 minutes | Yes |

`STRUCTURE_TRIES = 3`. The grade lock is one ref, `refs/gradbot/slots/<slug>/<user-id>`. Structure refs are `refs/gradbot/structure/<slug>/<user-id>/1` through `/3`. Creating the ref is the lock. Faculty reset deletes the grade ref and the structure refs for that login and slug.

There is no auto-correct push. A bad pull request is closed and commented. The student runs `gradbot submit` again.

## Minute budget

480 first grades at about 3 minutes is about 1,440 minutes. The structure-failure worst case, 60 students and 3 decrypt-only jobs at about 1 minute, is about 180 minutes. Together that is about 1,620 of 2,000.

Resets and second grades spend the same 3 minutes again. The leftover is about 380 minutes, roughly 120 extra grades. A month with many resets does not fit the way a month of only first submits does. The spending limit of $0 stops the jobs rather than charging.

## Repos

| Repo | Who can see it | Contents |
| --- | --- | --- |
| `course-samples` | Public | Statement, `suite.yaml`, `checks.py`, `seal.pub`. No hidden checks. |
| `course-drops` | Public pull requests | `submit.yml` and `solution.sealed` only. Dispatcher workflow. No tests. |
| `course-tests` | Faculty token | Hidden checks, roster, workflows, both ref namespaces, secret `GRADBOT_SEAL_KEY`. |
| `course-submissions` | Faculty token | Plaintext after a successful decrypt, at `<slug>/<user-id>/<sha>/`. |

Students are not collaborators on the private repos. The grader writes the plaintext.

Branch protection on `course-drops`: only faculty push to the default branch. Students contribute through forks.

## Keys

One new runtime dependency, `cryptography`. The stdlib cannot do public-key encryption. No other new dependency.

`gradbot keygen` prints a private key once and writes `seal.pub`. Faculty store the private key as the Actions secret `GRADBOT_SEAL_KEY` on `course-tests` only, and keep a copy in a password manager or on an offline disk. If that copy and the secret are both lost, every sealed file already on GitHub is unreadable. If the key leaks, run `gradbot keygen` again, replace `seal.pub`, and store the new private key. Keep the old key available to the decrypt step until every pull request sealed with it has been graded or closed, then delete the old key.

The sealed file is hybrid encryption: a random content key, AES-GCM for the bytes, and the course public key wrapping the content key. Associated data is `<user-id>:<slug>`. The grader opens the seal with the pull request author's id from the event, not from the file. A copied seal does not open for a different id.

## What the student runs

`gradbot login` stays device-code. Scope is `public_repo` plus `read:user`. That can open a pull request on a public fork. It cannot read a private course repo.

`gradbot submit arrays/two_sum`:

1. Applies today's `safe_source_files` rules. Failure here pushes nothing and counts no try.
2. Reads `seal.pub` from the public samples repo.
3. Seals the source files.
4. Opens a pull request on `course-drops` with exactly two files. `submit.yml` contains `slug` and nothing else. `solution.sealed` is the ciphertext. The commit SHA is not in the file. The CLI will not add a source file.

## Dispatcher, public, free minutes

`pull_request_target` on the default branch of `course-drops`. No `actions/checkout`. It does not download the branch, run student code, decrypt, or print secrets. The user id is `github.event.pull_request.user.id`. The commit to grade is `github.event.pull_request.head.sha`. Both values come from GitHub. The workflow does not read a sha out of `submit.yml`, and it does not write one back.

Valid shape:

- Exactly `submit.yml` and `solution.sealed`
- `submit.yml` has one key, `slug`, and it matches branch `submit/<slug>`
- No source file and no `.github` change
- Author is on the roster, read from `course-tests` with the faculty PAT
- Fewer than 3 structure refs, and no grade slot

If the shape is wrong, close the pull request, comment with the required shape, count one structure try, and stop. Do not push to the fork.

If the shape is valid, dispatch to `course-tests` with slug, user id, repository, `head.sha`, and pull request number.

## Grader, private

`repository_dispatch` and faculty `workflow_dispatch` only. `ubuntu-latest`, `timeout-minutes: 10`, concurrency `grade-<user-id>-<slug>`, `cancel-in-progress: false`.

1. Decrypt. This is the only step whose environment contains `GRADBOT_SEAL_KEY`. Associated data is `<user-id>:<slug>` from the dispatch payload. Failure: structure ref, comment, stop. No Docker and no grade slot.
2. Build the tree with the existing source rules. Junk dropped. `checks.py`, `checks_hidden.py`, and `.github` refused. No solution file: structure ref, comment, stop. This step does not receive the seal key.
3. Create the grade slot. If it exists, comment "already submitted" and stop.
4. Commit the plaintext under `<slug>/<user-id>/<head-sha>/` in `course-submissions`. The sha is the dispatch payload, not a file in the commit. If that commit fails, delete the slot.
5. Grade. The step environment does not include `GRADBOT_SEAL_KEY`, `GITHUB_TOKEN`, or the PAT. The workflow unsets all three before `python -m gradbot dev`. Docker is started with no extra environment, so the container does not receive the seal key either. Run `--sandbox docker`. Student program: `docker run --rm --network none`, solution directory only. `checks_hidden.py` stays outside the container. Image `python:3.12-slim`.
6. Comment on the drops pull request with name, status, points, and hint. No `cause`, no `log`, no plaintext. Full JSON is a private artifact.
7. Leave the slot after the grade starts, including a failing program.

## Faculty, once

- Create the four repos. Protect the drops default branch.
- OAuth app for device login. Callback `http://localhost`.
- Fine-grained PAT as `GRADBOT_APP_TOKEN` on `course-drops` and `course-tests`: contents on the two private repos, pull requests on drops, `repository_dispatch` on tests. It is not granted access to student forks, and it is not on a student machine.
- `gradbot keygen`. Public key in `course-samples`. Private key backed up, then stored only as `GRADBOT_SEAL_KEY` on `course-tests`.
- Spending limit $0.
- `gradbot publish`, then push.

Enroll and reset are `workflow_dispatch` on `course-tests`. Enroll writes the numeric id from `GET /users/{login}`. Reset clears the grade slot and the three structure refs.

`gradbot dev` before publish spends no Actions minutes.

## Tests before a live submit

- Sealing with user A's id does not open with user B's id.
- The dispatcher workflow text has no checkout, no decrypt, no student-code step, and no write of a sha into `submit.yml`.
- The grade workflow sets `GRADBOT_SEAL_KEY` on the decrypt step only. The grade step does not list that secret, and it unsets `GRADBOT_SEAL_KEY`, `GITHUB_TOKEN`, and the PAT. The docker argv passes no seal key.
- A pull request that contains `solution.py` is closed, counts one structure try, and does not dispatch.
- A `submit.yml` that is missing `slug`, or that contains a `sha` key, is closed and counts as a structure try. It is not rewritten.
- The fourth structure try is refused.
- A good seal for an enrolled student with no slot starts one grade. The plaintext is written only under `course-submissions`. The path uses `pull_request.head.sha` from the dispatch payload.
- A second good seal does not start Docker.
- The student token is never sent to `course-tests` or `course-submissions`.

## Live check

Spending limit $0. Enroll `nvmaditya`. Submit Two Sum. The drops pull request file list is `submit.yml` and `solution.sealed`, and `submit.yml` has no sha. The private grade comments. The plaintext is only in `course-submissions`. A copied seal from another account does not grade. A pull request that adds `solution.py` is closed. Reset clears the slot.

## Out of this plan

- Faculty paste-prompt, local spec `923b0bd`, still waiting for review.
- HTML diagram of the codebase, after this flow is the one we build.
- Hosted listeners, databases, polling crons, and GitHub Classroom.
