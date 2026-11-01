# Writing a problem

A problem is a folder. GradBot reads `suite.yaml` for settings and imports
`checks.py` (and, for faculty, `checks_hidden.py`) to find the checks.

```
arrays/
  two_sum/
    suite.yaml          settings (required)
    checks.py           public checks students can run (required)
    checks_hidden.py    graded checks, faculty and grader only (optional)
    statement.md        the problem as students read it (optional)
    expected/           data files for hidden checks (optional)
    sample_solution/    a reference solution (optional, never published)
      solution.py
```

`grade publish` copies `suite.yaml`, `statement.md` and `checks.py` to the
public samples repo. Everything except `sample_solution/` goes to the private
tests repo, including `checks_hidden.py` and `expected/`.

## `suite.yaml`

```yaml
problem:
  name: "Two Sum"
  topic: "Arrays & Strings"
  languages: [python, c, cpp, java]
  time_limit: 5

scoring:
  total_points: 4

hints:
  general: "Think about what data structure lets you look up values instantly."
```

| Key | Default | What GradBot does with it |
|---|---|---|
| `problem.name` | `Unnamed Problem` | Shown in the result header. |
| `problem.topic` | `General` | Shown in the result header. |
| `problem.languages` | all four | A solution in another language is refused before any check runs: "This problem accepts C and C++. Your folder has Java". Allowed values: `python`, `c`, `cpp`, `java`. |
| `problem.time_limit` | `5` | Seconds each `gradbot.run()` may take when the check does not pass `timeout=`. `grade run --timeout` and `grade dev --timeout` override it. |
| `scoring.total_points` | not set | `grade dev` warns when it differs from the points `checks.py` awards. The score always comes from the checks. |
| `hints.general` | none | Shown under the score whenever a run misses marks, and included in the JSON result. |

Other keys (`difficulty`, `description`, ...) are ignored by GradBot and can
stay for people reading the file. A malformed file (bad YAML, a list where a
mapping belongs, an unknown language, a `time_limit` of 0) stops the run with
a message naming the key.

Memory limits are not enforced yet; they are on the roadmap.

## Checks

```python
import gradbot

@gradbot.check("Basic case", points=1, hint="Try every pair first.")
def test_basic():
    result = gradbot.run(input="4\n2 7 11 15\n9\n")
    gradbot.expect_output(result.stdout, "0 1")

@gradbot.check("Large input", depends_on="test_basic", points=1,
               hint="A hash map makes this one pass.")
def test_large():
    nums = list(range(10_000))
    result = gradbot.run(input=f"{len(nums)}\n{' '.join(map(str, nums))}\n19997\n", timeout=2)
    if result.timed_out:
        raise gradbot.CheckFailure("too slow")
    gradbot.expect_output(result.stdout, "9998 9999")
```

### `@gradbot.check(name, depends_on=None, points=1, hint=None)`

| Argument | Meaning |
|---|---|
| `name` | Shown to the student. |
| `depends_on` | Function name of another check. If that one does not pass, this one is skipped. |
| `points` | Awarded on a pass. A whole number, 0 or more. |
| `hint` | Shown when this check fails, unless the failing call gave its own hint. |

Checks run in declaration order, with every check after the one it depends
on. Two functions with the same name, a `depends_on` that names nothing, and
a dependency cycle are all refused when the file loads.

### Running the program

`gradbot.run(input="", timeout=None, args=None)` runs the student's program
with `input` on stdin and returns a `RunResult`:

| Field | |
|---|---|
| `stdout`, `stderr` | Text, decoded as UTF-8. Bytes that are not UTF-8 become `�` instead of crashing the check. |
| `exit_code` | The process exit code, or `-1` after a timeout. |
| `timed_out` | `True` if the program was stopped at the time limit. Output printed before that is kept. |

Each check gets a fresh copy of the solution folder, so a program that writes
files cannot affect the next check. The program does not see environment
variables whose names contain `TOKEN`, `SECRET`, `PASSWORD`, `CREDENTIAL`,
`API_KEY` or `PRIVATE_KEY`.

### Assertions

| Call | Passes when |
|---|---|
| `expect_output(actual, expected, mode="exact", hint=None)` | `exact`: equal after stripping surrounding whitespace. `contains`: `expected` is a substring. `regex`: `re.search(expected, actual)` matches. |
| `expect_sequence(actual, expected, hint=None)` | The whitespace-separated tokens equal `[str(x) for x in expected]`. |
| `expect_exit(result, code=0, hint=None)` | The program exited with `code` and did not time out. |
| `file_exists(name, hint=None)` | A file called `name` exists in the program's working folder (a fresh copy of the solution folder, plus anything the program wrote). |
| `raise gradbot.CheckFailure(message, hint=None)` | Never; fails the check with your message. |

A plain `assert` also fails a check. Its message goes to the faculty result
only, never to the hint, because it often contains the expected answer.

### Which hint the student sees

1. The `hint=` passed to the call that failed.
2. Otherwise the `hint=` on `@gradbot.check`.
3. Otherwise a generic one ("Your output doesn't match what was expected").

An exception that is not a check failure (a bug in the checks file) marks the
check as an error, not a failure, and tells the student to ask their teacher.

### Data files

A hidden check can read files you keep next to it:

```python
from pathlib import Path

EXPECTED = (Path(__file__).parent / "expected" / "large.txt").read_text()
```

`expected/` is published to the tests repo only, so use it from
`checks_hidden.py`, not from `checks.py`.

## Hints that help

Hints are what a student reads when a check fails. Point at the idea, not the
answer:

| Weak | Better |
|---|---|
| "Wrong answer" | "Indexes are 0-based and separated by one space." |
| "Expected 0 1 but got 1 0" | "Print the smaller index first." |
| "Too slow" | "Two nested loops are O(n²). A hash map gets this to one pass." |

Never put expected output in a hint. Hints are shown in practice and in the
graded result.

## Hidden checks

Put graded cases in `checks_hidden.py`, with the same API. They are never
downloaded to a student's computer:

- `grade run` refuses to run if `checks_hidden.py` is in the suite or next to
  the solution.
- `grade dev` runs `checks.py`, then `checks_hidden.py`, and says which set
  failed. `--output` writes the full result; `--student-output` writes the
  same result without `cause` and `log`, which is where expected output lives.
- `grade publish` copies `checks_hidden.py` to the tests repo only, and stops
  if the samples repo already contains one anywhere.

## Your first problem

```bash
mkdir -p problems/arrays/find_max/sample_solution
cd problems/arrays/find_max
```

`suite.yaml`:

```yaml
problem:
  name: "Find the Maximum"
  topic: "Arrays"
  languages: [python, c, cpp, java]
scoring:
  total_points: 2
hints:
  general: "Walk the array once and remember the largest value."
```

`checks.py`:

```python
import gradbot

@gradbot.check("Basic case", points=1, hint="Try the simplest input first.")
def test_basic():
    gradbot.expect_output(gradbot.run(input="5\n3 1 4 1 5\n").stdout, "5")

@gradbot.check("Negative numbers", depends_on="test_basic", points=1,
               hint="-1 is greater than -10.")
def test_negatives():
    gradbot.expect_output(gradbot.run(input="3\n-5 -2 -8\n").stdout, "-2")
```

`sample_solution/solution.py`:

```python
n = int(input())
print(max(map(int, input().split())))
```

Check it:

```bash
grade dev . --solution sample_solution
```

Then publish it (see the [faculty guide](faculty-guide.md)) and students can
run `grade run arrays/find_max`.
