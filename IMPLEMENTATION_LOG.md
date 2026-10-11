# Implementation log

Date: 2026-10-11

Students no longer receive hidden tests. Practice stays on this computer. A graded submit is one slot per GitHub user id, and the grade runs where the student cannot read the checks.

## What landed

- `gradbot run` and `GradBot practice/...` load `checks.py` only. A `checks_hidden.py` in the suite or next to the solution stops the run.
- `gradbot dev` and `GradBot --dev` run public checks, then hidden checks, and print which set failed.
- `student_payload` drops `cause` and `log` before anything a student can read. The hint stays. Faculty JSON keeps the full result.
- The grader can run the student program with `docker run --rm --network none` and a single mount. Local practice does not use that container.
- `gradbot.policy` decides a submit with no network of its own:
  - The user id comes from the token. A login in the request body is ignored.
  - An id that is not on the roster does not create a ref and does not dispatch.
  - The second submit, including two at the same time, creates one ref and dispatches once.
  - A failed commit or dispatch deletes the ref. A finished submit keeps it.
  - Zip paths that escape, `checks_hidden.py`, and workflow files are refused before the ref exists.
- `gradbot publish` copies hidden checks into the tests tree only and writes `.github/workflows/grade.yml` there. The samples tree does not get that file.
- `GradBot submit/...` no longer clones a private repo and no longer puts `GRADBOT_TOKEN` in a git URL.
- `gradbot login` uses the GitHub device-code flow with scope `read:user` and stores the token under the config directory.
- `gradbot submit` checks the zip, then POSTs it to `GRADBOT_SUBMIT_URL` with that token. It does not grade hidden checks locally.
- `gradbot roster add` asks GitHub for the numeric id and writes `roster.yml`.
- `gradbot reset` deletes `refs/gradbot/slots/<slug>/<id>` with the App token.

The workflow template lives in `gradbot/policy.py` as `WORKFLOW_TEXT`. It is `workflow_dispatch` only, times out after 10 minutes, and does not use `pull_request_target`. The student program's container is not given `GITHUB_TOKEN` and is not given a tests mount.

## Checks

Command: `C:\Users\chhav\AppData\Local\Temp\gradbot-e2e\.venv\Scripts\python.exe -m pytest tests -q`

Result: 133 passed.

Local `--dev` runs of `problems/arrays/two_sum`:

- Sample solution: 4/4, exit 0.
- `print("0 1")`: checks 1–3 pass, large input fails, 3/4, exit 1.
- `print(`: line-1 syntax error, all four checks skipped, 0/4, exit 1.
- `gradbot submit` with no App URL exits 1 and does not download tests.

## Not run against a live course

No course org, App private key, or `GRADBOT_SUBMIT_URL` was available. These were not executed against GitHub:

- Device-code approval in a browser.
- Creating or deleting a real slot ref.
- `workflow_dispatch` of `grade.yml`.
- A student token being rejected by the private tests repo's ACLs. The code refuses to use that token as the tests credential. GitHub's own permissions are still what blocks a stolen token from reading the repo.

The course App that receives the zip has to call `accept_zip` in `gradbot.policy`. This repository does not start that process. Until that App is deployed, `gradbot submit` stops after telling the student the URL is unset, or it POSTs and waits for whatever is at that URL.

## Agents

Check loading, result stripping, and the container argv were written as three separate slices because they do not share files. The submit rules and the CLI were written together after that, because both edit the command path.
