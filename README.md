# GradBot

**A CLI grading tool for coding-cohort students, mainly for DSA and competitive programming.**

Students write a solution, then run `GradBot` in the terminal. Practice mode shows the tests. Submit mode shows pass or fail plus a hint, and keeps the hidden cases hidden. Compiler errors name the line. Raw compiler output stays behind `--verbose`.

---

## Quick Start

### Install

```bash
pip install -e .
```

### Write Your Solution

Create a file (e.g., `solution.py`) that solves the problem:

```python
# solution.py — Two Sum
n = int(input())
nums = list(map(int, input().split()))
target = int(input())

seen = {}
for i, num in enumerate(nums):
    complement = target - num
    if complement in seen:
        print(seen[complement], i)
        break
    seen[num] = i
```

### Run GradBot

```bash
GradBot practice/arrays/two_sum
```

You'll see output like:

```
GradBot — Arrays & Strings: Two Sum
─────────────────────────────────────────────

  ✓  Basic case: [2,7,11,15], target=9        (1 pt)
  ✓  Negative numbers work                    (1 pt)
  ✓  Duplicate values                         (1 pt)
  ✓  Large input performance                  (1 pt)

─────────────────────────────────────────────
  Score: 4 / 4   ██████████  100%

  Accepted. All tests passed.
```

---

## Slug Format

```
{mode}/{topic}/{problem}[@ref]
```

| Part | Description | Example |
|------|-------------|---------|
| `mode` | `practice` (public tests) or `submit` (hidden tests) | `practice` |
| `topic` | Topic folder name | `arrays`, `graphs`, `dp` |
| `problem` | Problem folder name | `two_sum`, `merge_sort` |
| `@ref` | Optional git ref (branch/tag/commit) | `@v2`, `@main` |

**Practice** (`gradbot run` or `GradBot practice/...`) runs the public sample checks on this computer. It can show expected output. The submit machine may differ.

**Submit** (`gradbot submit`) sends the solution to the course App. Hidden checks never download to the student machine. The student sees pass or fail, points, and hints.

---

## Commands

```bash
gradbot login                         # GitHub device code, scope read:user
gradbot run arrays/two_sum            # public checks, as many times as you want
gradbot submit arrays/two_sum         # one graded attempt, hidden checks stay on the grader
gradbot dev ./problems/arrays/two_sum # faculty: public checks, then hidden checks
gradbot publish ./problems/arrays/two_sum --tests ../course-tests --samples ../course-samples --slug arrays/two_sum
gradbot results faculty.json          # print a result with cause and log removed
gradbot reset <login> <slug>          # faculty second chance
gradbot roster add <login> --roster roster.yml
```

`GradBot practice/arrays/two_sum` and `GradBot --dev ./problems/arrays/two_sum` still work. `GradBot submit/...` does not clone hidden tests.

Share [STUDENT.md](STUDENT.md) with students and [FACULTY.md](FACULTY.md) with faculty. The private course used to try both flows is [nvmaditya/gradbot-e2e](https://github.com/nvmaditya/gradbot-e2e). Practice problems for that course are in the public repo [nvmaditya/gradbot-course-samples](https://github.com/nvmaditya/gradbot-course-samples).

One submit per student per problem. The lock is a git ref `refs/gradbot/slots/<slug>/<github-user-id>`. The id comes from GitHub's response to the login token. A login typed in the request is ignored. An account that is not on `roster.yml` is refused. Faculty `reset` is the only second chance.

---

## CLI Options

```
GradBot <slug> [options]

positional:
  slug                  e.g. practice/arrays/two_sum

options:
  --verbose, -v         Show full diff and log on failures
  --no-color            Disable colored output
  --output FILE         Save JSON results to FILE
  --timeout N           Per-check timeout in seconds (default: 5)
  --solution DIR        Path to solution directory (default: current dir)
  --offline             Use cached test suite, skip network
  --dev                 Dev mode: treat slug as local path to problem suite
  --version             Print GradBot version
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GRADBOT_PUBLIC_REPO` | Public samples repo for `gradbot run` | `GradBot/gradbot-problems-public` |
| `GRADBOT_CLIENT_ID` | GitHub OAuth app id for `gradbot login` | _(none)_ |
| `GRADBOT_SUBMIT_URL` | Course App that receives a submission zip | _(none)_ |
| `GRADBOT_APP_TOKEN` | Faculty/App token for roster, reset, and the tests repo | _(none)_ |
| `GRADBOT_SUBMISSIONS_REPO` | `owner/repo` whose slot refs `gradbot reset` deletes | _(none)_ |
| `GRADBOT_CONFIG_DIR` | Where the device token is stored | `~/.gradbot` |
| `GRADBOT_LOCAL_DIR` | Clone of the public samples repo | `~/.gradbot/local` |
| `NO_COLOR` | Disable colored output (any value) | _(none)_ |

Students do not get a personal access token. `GRADBOT_TOKEN` is not read.

### Three repos

| Repo | Who can read | Contents |
|---|---|---|
| `org/<course>-tests` | Faculty and the GitHub App | `checks.py`, `checks_hidden.py`, `suite.yaml`, `roster.yml`, the grader workflow |
| `org/<course>-samples` | Public | Statement, `suite.yaml`, `checks.py` only |
| `org/<course>-submissions` | Faculty and the App | Solution files under `<slug>/<github-user-id>/<timestamp>/` |

---

## Supported Languages

| Language | Extension | Compiler | Run Command |
|----------|-----------|----------|-------------|
| Python | `.py` | Syntax check (`py_compile`) | `python solution.py` |
| C | `.c` | `gcc` | `./solution` |
| C++ | `.cpp`, `.cc` | `g++ -std=c++17` | `./solution` |
| Java | `.java` | `javac` | `java ClassName` |

---

## Setting Up Your Own Problem Repository

1. Create a GitHub repository (public for practice, private for submit)
2. Organize problems by topic:
   ```
   arrays/
     two_sum/
       suite.yaml
       checks.py
   trees/
     inorder_traversal/
       suite.yaml
       checks.py
   ```
3. Set the environment variables to point to your repo:
   ```bash
   export GRADBOT_PUBLIC_REPO="your-org/your-problems"
   ```
4. See [PROBLEM_AUTHORING.md](PROBLEM_AUTHORING.md) for the complete guide to writing problems.

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Test with a local problem suite
GradBot --dev ./problems/arrays/two_sum --solution ./problems/arrays/two_sum/sample_solution
```

---

## License

MIT
