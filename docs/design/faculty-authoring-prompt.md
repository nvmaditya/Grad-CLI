# Faculty authoring prompt

Date: 2026-10-11
Status: approved design, waiting for spec review

## Problem

Faculty need to turn a question into GradBot problem files they can commit to a course's problem repos. The minimum input is the question text. The instructions must work when pasted into Claude, ChatGPT, or any other chat. This is not a Codex, Claude Code, or Grok Build skill.

## Decision

Add one prompt section to the end of `FACULTY.md`. Faculty paste that section into a chat, then send a question. The chat returns the problem files, each labeled with the repo that may receive it. Faculty review the files and commit with whatever method they already use.

These alternatives were set aside:

- A separate `AUTHORING_PROMPT.md`. The prompt lives inside `FACULTY.md`.
- A new GradBot command that checks the folder or renders the files.
- A case list that only GradBot can turn into `checks.py`.

## Where the prompt sits

The new section goes after the grader-workflow section in `FACULTY.md`.

One sentence for the human reader sits above the prompt: copy from the heading "You are writing a GradBot problem" through the end of the file into Claude, ChatGPT, or any other chat, then send the question.

The prompt starts at that heading. Its first rule tells the model to follow only that section when guide text from higher in the file was pasted as well.

## Faculty flow

A question alone is enough. When the same message also includes examples, a language, or a solution, the chat uses them.

One question produces one problem folder. Several questions in one message produce one folder each, in that same reply.

The chat does not commit. Faculty commit the reviewed files however they already do. That includes the GitHub website, a chat that is connected to GitHub, or git on their machine.

## Files the chat returns

The folder name is `topic/slug`: lowercase, a single slash, no spaces. Use the existing slug shape, as in `arrays/two_sum`.

Each file is its own fenced block, with the repo path on the fence.

| File | Where it may go |
| --- | --- |
| `statement.md` | Public samples repo. The problem a student can read: input format, output format, and the public examples. |
| `suite.yaml` | Public samples repo. |
| `checks.py` | Public samples repo. |
| `checks_hidden.py` | Private tests repo only. |
| `sample_solution/` | Faculty authoring tree only. The public samples repo does not receive it. The file inside is `solution.py` unless the language section below names another one. |

`suite.yaml` contains `problem.name`, `problem.topic`, a short `problem.description`, `problem.languages`, and `scoring.total_points`. `scoring.total_points` is the sum of the public check points. Hidden check points stay out of that total. `scoring.pass_threshold` is omitted. A full score is the only passing exit, and the prompt does not describe a lower threshold as a pass.

`gradbot publish` already copies `statement.md`, `suite.yaml`, and `checks.py` into the samples tree, copies `checks_hidden.py` into the tests tree, and does not copy the `sample_solution` directory. The labels match that split.

`sample_solution/` may be stored in the private course repo faculty use for authoring. `checks_hidden.py` may be stored only in a private tests repo. Neither file is committed to the public samples repo. Faculty who commit without `gradbot publish` copy files according to these labels.

## Check files

Both check files are Python. They import `gradbot`. Each check uses `@gradbot.check(name, depends_on=..., points=..., hint=...)`, `gradbot.run(input=...)`, and `gradbot.expect_output(result.stdout.strip(), expected)`.

`checks.py` has three or four checks: a basic case, an edge case, and a larger case. Later checks set `depends_on` to the basic check's function name. A case that is about speed passes `timeout=` to `gradbot.run`.

`checks_hidden.py` has one to three checks. Those inputs do not appear in `checks.py`, `statement.md`, `suite.yaml`, or in comments in the public files. The expected output of a hidden check does not appear in those public files either.

A hint describes a strategy. A hint does not contain the expected output.

## Language and extra material

The sample is `sample_solution/solution.py` unless the question names C, C++, or Java.

- C writes `sample_solution/solution.c`.
- C++ writes `sample_solution/solution.cpp`.
- Java writes one `.java` file in `sample_solution/`. The public class name matches the filename.

Checks stay Python for every language.

Examples included with the question become the public checks. The chat still writes hidden cases, and those cases use different inputs.

A solution included with the question becomes the sample. Its behavior agrees with the examples the question states. The expected lines in the checks agree with that solution.

When the question already states an input layout, every check uses that layout. When it does not, and the ordinary competitive-programming stdin layout is the obvious reading, the chat uses that layout, states it in `statement.md`, and uses it in every check.

## When the chat writes no files

Questions are handled in order. A question with a clear format gets a folder. At the first question that needs an answer before files can be written, the chat asks that one question and writes no folder for it or for any question after it.

A question gets no folder in these cases:

- The input and output format cannot be read from the question.
- The question names a language other than Python, C, C++, or Java. The chat names those four and asks which one to use.
- A supplied solution disagrees with an example stated in the question.

The reply does not claim the chat ran the sample. A reply that contains files ends with a paragraph that tells faculty to read the files, to keep `checks_hidden.py` and `sample_solution/` out of the public repo, to run `gradbot dev` on the folder when GradBot is installed, and to commit with whatever they already use. The prompt does not include git commands, remotes, tokens, or a `gradbot publish` invocation. Publish stays in the earlier part of `FACULTY.md`, outside the pasted prompt.

## Out of scope

- Graded login, roster, submit, reset, and the course App. That is the next design.
- The HTML flow diagram of the codebase. That design comes after the graded path.
- A rewrite of `PROBLEM_AUTHORING.md`.
- Installing a Grok, Claude Code, or Codex skill, and any change to the skills guide.
- New Python, a new dependency, or a new test.

## Verification

Read the new `FACULTY.md` section against this spec. Then paste that section into a chat with the Two Sum statement and no solution. In the reply, the public files do not contain the hidden input, and the sample solution agrees with the public examples in the question. That trial does not commit to a repository.
