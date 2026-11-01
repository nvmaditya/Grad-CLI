# GradBot for faculty

You write two check files. Students run the public one on their own computers. The hidden one runs only for you, and later on the grader. Students are not given a copy of the hidden file.

## Install

Python 3.10 or newer, Git, and this repository:

```bash
pip install -e .
python -m gradbot --version
```

## Author a problem

A problem folder contains:

- `suite.yaml` — name, topic, points
- `checks.py` — sample checks students can run
- `checks_hidden.py` — graded checks, faculty only
- `sample_solution/solution.py` — a solution that should pass both

The private course repo for trying this is https://github.com/nvmaditya/gradbot-e2e. Clone it and, from that clone:

```bash
python -m gradbot dev problems/arrays/two_sum --solution problems/arrays/two_sum/sample_solution --no-color
```

You should see a "Public checks" section and a "Hidden checks" section. The command says which set failed. The sample solution passes both.

`python -m gradbot --dev problems/arrays/two_sum --solution problems/arrays/two_sum/sample_solution` is the same loop.

Keep expected answers out of hint text. Hints are shown to the student on purpose.

## Publish

Publishing splits one folder into two trees. Hidden checks go to the tests tree. The samples tree receives `suite.yaml`, `statement.md`, and `checks.py` only.

```bash
python -m gradbot publish problems/arrays/two_sum --tests ./course-tests --samples ./course-samples --slug arrays/two_sum
```

Push `course-tests` to a private repo that students cannot read. Push `course-samples` to a repo they can read. For this course the public practice repo is https://github.com/nvmaditya/gradbot-course-samples. Practice has to be readable without a token. `gradbot run` does not send one.

Confirm `checks_hidden.py` is absent from the samples tree before you push.

## What students do

Share [STUDENT.md](STUDENT.md). Their practice command is:

```bash
set GRADBOT_PUBLIC_REPO=nvmaditya/gradbot-course-samples
python -m gradbot run arrays/two_sum
```

## Roster, login, and the one graded submit

These commands exist. They are not a live course yet.

- `gradbot login` needs a GitHub OAuth app id in `GRADBOT_CLIENT_ID`. Scope is `read:user`. Login proves who someone is. It does not enroll them.
- `gradbot roster add <login> --roster roster.yml` needs `GRADBOT_APP_TOKEN`. It asks GitHub for the numeric user id and writes that id. Check the printed id before you rely on the file.
- `gradbot submit` sends a zip to `GRADBOT_SUBMIT_URL`. Nothing in this repository is listening on that URL. The service at that URL has to call `accept_zip` in `gradbot/policy.py`. Until that service is deployed, submit tells the student to keep practicing.
- `gradbot reset <login> <slug>` deletes the slot ref with `GRADBOT_APP_TOKEN` and `GRADBOT_SUBMISSIONS_REPO`. That is the second chance.

The rules already covered by tests, with a stand-in for GitHub:

- The user id comes from GitHub's response to the token. A login typed into the request is ignored.
- An id that is not on the roster does not store a solution and does not start grading.
- One slot per student per problem. Two submits at the same time create one slot.
- A failed upload deletes the slot so they can retry. A grade that finished, including a failing grade, keeps the slot.

## Grader workflow

`gradbot publish` writes `.github/workflows/grade.yml` into the tests tree only. It runs when the App sends `workflow_dispatch`. The student program is started with no network and with only the solution directory mounted. That workflow has not been dispatched against GitHub from this project yet.
