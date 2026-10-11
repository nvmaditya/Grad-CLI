# Problem Authoring Guide

This guide explains how to write problem suites for GradBot. A problem suite
is a directory containing a `suite.yaml` configuration file and a `checks.py`
file with test checks.

---

## Directory Structure

```
your_topic/
  your_problem/
    suite.yaml          # Problem metadata and configuration
    checks.py           # Test checks using the GradBot API
    expected/           # (optional) Expected output files
    sample_solution/    # (optional) Reference solution for testing
      solution.py
```

---

## `suite.yaml` Reference

```yaml
problem:
  name: "Two Sum"                          # Required. Human-readable name
  topic: "Arrays & Strings"               # Required. Topic category
  difficulty: "beginner"                   # Optional. beginner | intermediate | advanced
  description: >                           # Optional. Problem description (shown in docs)
    Given an array of integers and a target sum,
    return the indices of the two numbers that add up to the target.
  languages: [python, c, cpp, java]        # Optional. Supported languages (default: all 4)
  time_limit: 5                            # Optional. Default timeout in seconds (default: 5)
  memory_limit_mb: 64                      # Optional. Memory limit in MB (default: 64)

scoring:
  total_points: 4                          # Optional. Total points (0 = auto-sum from checks)
  pass_threshold: 0.6                      # Optional. Score needed to "pass" (default: 0.6)

hints:
  general: "Think about using a hash map"  # Optional. General hint for the problem
```

### Key Reference

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `problem.name` | string | **Yes** | `"Unnamed Problem"` | Display name |
| `problem.topic` | string | **Yes** | `"General"` | Topic category |
| `problem.difficulty` | string | No | `"beginner"` | `beginner`, `intermediate`, `advanced` |
| `problem.description` | string | No | `""` | Full problem description |
| `problem.languages` | list | No | `[python, c, cpp, java]` | Languages this problem supports |
| `problem.time_limit` | float | No | `5.0` | Default per-check timeout (seconds) |
| `problem.memory_limit_mb` | int | No | `64` | Memory limit |
| `scoring.total_points` | int | No | `0` (auto) | Total points; 0 = sum from checks |
| `scoring.pass_threshold` | float | No | `0.6` | Minimum score to pass |
| `hints.general` | string | No | `""` | General hint for the problem |

---

## `checks.py` API Reference

### The `@gradbot.check()` Decorator

```python
@gradbot.check(name, depends_on=None, points=1, hint=None)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | str | **Yes** | — | Human-readable name shown in results |
| `depends_on` | str | No | `None` | Function name of a check that must pass first |
| `points` | int | No | `1` | Points awarded when this check passes |
| `hint` | str | No | `None` | Default hint shown on failure |

Example:

```python
import gradbot

@gradbot.check("Basic case works", points=1, hint="Check your output format!")
def test_basic():
    result = gradbot.run(input="4\n2 7 11 15\n9\n")
    gradbot.expect_output(result.stdout.strip(), "0 1")

@gradbot.check("Handles negatives", depends_on="test_basic", points=1)
def test_negatives():
    result = gradbot.run(input="3\n-1 -2 -3\n-3\n")
    gradbot.expect_output(result.stdout.strip(), "0 1")
```

---

### `gradbot.run(input, timeout, args)`

Run the student's compiled program with the given stdin input.

```python
result = gradbot.run(input="hello\nworld\n", timeout=5.0)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input` | str | `""` | String to feed to stdin |
| `timeout` | float | `5.0` | Max seconds before killing the process |
| `args` | list[str] | `None` | Additional command-line arguments |

**Returns**: `RunResult` with:
- `.stdout` — captured stdout (string)
- `.stderr` — captured stderr (string)
- `.exit_code` — process exit code (int)
- `.timed_out` — whether the process was killed (bool)

---

### `gradbot.expect_output(actual, expected, mode, hint)`

Assert that actual output matches expected.

```python
gradbot.expect_output(result.stdout.strip(), "0 1")
gradbot.expect_output(result.stdout, "hello", mode="contains")
gradbot.expect_output(result.stdout, r"\d+ \d+", mode="regex")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `actual` | str | — | Actual output from the program |
| `expected` | str | — | Expected output |
| `mode` | str | `"exact"` | `"exact"`, `"contains"`, or `"regex"` |
| `hint` | str | `None` | Custom hint on failure |

**Raises**: `OutputMismatch` on failure.

---

### `gradbot.expect_exit(result, code, hint)`

Assert the program exited with a specific exit code.

```python
gradbot.expect_exit(result, 0)  # Expect successful exit
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `result` | RunResult | — | Result from `gradbot.run()` |
| `code` | int | `0` | Expected exit code |
| `hint` | str | `None` | Custom hint on failure |

---

### `gradbot.expect_sequence(actual, expected, hint)`

Assert that output matches a sequence of values (space/newline separated).

```python
gradbot.expect_sequence(result.stdout, [1, 2, 3, 4, 5])
```

---

### `gradbot.file_exists(filename, hint)`

Assert that a file exists in the solution directory.

```python
gradbot.file_exists("output.txt")
```

---

### `gradbot.CheckFailure(message, hint)`

Raise a check failure manually with a custom message and hint.

```python
if elapsed > 2.0:
    raise gradbot.CheckFailure(
        "Solution too slow",
        hint="Try a more efficient algorithm!"
    )
```

---

## How to Write Good Hints

Hints are what students see when a check fails. Write them for a cohort working on DSA and competitive programming:

### Bad Hints ❌

```
"Wrong answer"
"Output mismatch"
"Test failed"
"Expected 0 1 but got 1 0"  # Never reveal the answer in submit mode!
```

### Good Hints ✅

```
"Check your output format — the indices should be space-separated!"
"Your solution might be too slow for large inputs. Try a hash map!"
"Remember to handle negative numbers — they follow the same rules."
"A single-element list is already sorted. Make sure you handle that case!"
```

### Guidelines

1. **Be specific** — Name the case or constraint that failed
2. **Give direction** — Point at the approach (hash map, edge case, complexity) without giving the code
3. **No spoilers** — Never include expected output in hints, especially in submit mode
4. **Efficiency is fair game** — A slow solution can fail with a hint about complexity

---

## How Hidden Tests Work

Hidden checks live in `checks_hidden.py` next to `checks.py`. They are not a second copy of the problem that gets cloned onto a student laptop.

- `gradbot dev` (and `GradBot --dev`) runs `checks.py`, then `checks_hidden.py`, and says which set failed. Faculty see the full result.
- `gradbot run` and `GradBot practice/...` run `checks.py` only. If `checks_hidden.py` is in the suite or beside the solution, the run stops.
- `gradbot publish` copies `checks_hidden.py` into the private tests repo only. The public samples repo gets `suite.yaml`, `statement.md`, and `checks.py`.
- `gradbot submit` zips the solution and sends it to the course App. The App checks `roster.yml` by GitHub user id, creates one slot ref, and dispatches the workflow in the tests repo. The student program runs with no network and no mount of the tests. The comment posted back has pass/fail, points, and hints.

Keep expected answers out of hint text. A hint is shown to the student on purpose.

### Setting Up

1. Private repo `org/<course>-tests` for faculty and the GitHub App. Disable student access.
2. Public repo `org/<course>-samples` for practice.
3. Private repo `org/<course>-submissions` for solution files. Do not enable a workflow that runs on push.
4. Faculty machine: `GRADBOT_APP_TOKEN` and `GRADBOT_SUBMISSIONS_REPO`.
5. Student machine: `GRADBOT_CLIENT_ID` and `GRADBOT_SUBMIT_URL`. No personal access token.

---

## Step-by-Step: Write Your First Problem

### 1. Create the directory

```bash
mkdir -p problems/arrays/find_max
cd problems/arrays/find_max
```

### 2. Write `suite.yaml`

```yaml
problem:
  name: "Find the Maximum"
  topic: "Arrays & Strings"
  difficulty: "beginner"
  description: >
    Given an array of integers, find and print the maximum value.

scoring:
  total_points: 3

hints:
  general: "Walk through the array and keep track of the biggest number you've seen!"
```

### 3. Write `checks.py`

```python
import gradbot

@gradbot.check("Basic case", points=1,
               hint="Try the simplest case first!")
def test_basic():
    result = gradbot.run(input="5\n3 1 4 1 5\n")
    gradbot.expect_output(result.stdout.strip(), "5")

@gradbot.check("Single element", points=1, depends_on="test_basic",
               hint="An array with one element — the max is that element!")
def test_single():
    result = gradbot.run(input="1\n42\n")
    gradbot.expect_output(result.stdout.strip(), "42")

@gradbot.check("Negative numbers", points=1, depends_on="test_basic",
               hint="Don't forget: -1 is greater than -10!")
def test_negatives():
    result = gradbot.run(input="3\n-5 -2 -8\n")
    gradbot.expect_output(result.stdout.strip(), "-2")
```

### 4. Write a sample solution

```bash
mkdir sample_solution
```

```python
# sample_solution/solution.py
n = int(input())
nums = list(map(int, input().split()))
print(max(nums))
```

### 5. Test it

```bash
GradBot --dev ./problems/arrays/find_max --solution ./problems/arrays/find_max/sample_solution
```

### 6. Push to your problem repo

Commit and push to your GitHub repository. Students can now run:

```bash
GradBot practice/arrays/find_max
```
