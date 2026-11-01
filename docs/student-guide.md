# GradBot for students

GradBot checks a program you wrote. Practice runs on your computer against
the sample checks, as often as you like. The graded checks stay with your
teacher.

## Install

You need Python 3.10 or newer and Git.

```bash
git clone https://github.com/nvmaditya/gradbot
cd gradbot
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install .
grade --version                   # GradBot 1.0.0
```

A virtual environment avoids the "externally managed environment" error
newer macOS and Linux systems give for a plain `pip install`. Activate it
again in each new terminal (`source path/to/gradbot/.venv/bin/activate`), or
run `path/to/gradbot/.venv/bin/grade` directly.

## Practice

Put your solution in a folder, then run GradBot from that folder:

```bash
cd ~/work/two_sum
grade run arrays/two_sum
```

GradBot downloads the problem's public checks from your course's samples
repo, compiles your code, and runs each check:

```
Grade — Arrays & Strings: Two Sum
─────────────────────────────────────────────

  ✓  Basic case: [2,7,11,15], target=9        (1 pt)
  ✗  Negative numbers work                    (1 pt)
     💡 Hint: Negative numbers follow the same rules — make sure you handle them!
  ○  Duplicate values                         skipped
  ...
  Score: 1 / 4   ██░░░░░░░░  25%
```

`✓` passed, `✗` failed (with a hint), `○` skipped because a check it depends
on failed, `⚠` a problem with the check itself (tell your teacher).

The exit code is 0 only for full marks, so scripts can tell.

### Which course?

`grade run` uses the public demo course until you point it at yours. Your
teacher gives you the repo name:

```bash
export GRADBOT_PUBLIC_REPO=your-org/your-course-samples   # Windows: set GRADBOT_PUBLIC_REPO=...
```

### Useful options

| Option | |
|---|---|
| `--solution DIR` | Grade a folder other than the current one. |
| `--verbose` | Show the expected output and logs for failed sample checks. |
| `--offline` | Use the copy downloaded earlier, no network. |
| `--timeout SECONDS` | Give each run of your program longer than the problem's limit. |
| `topic/problem@REF` | A tag, branch or full commit of the samples repo, for example `arrays/two_sum@v2`. |
| `--no-color` | Plain output. `NO_COLOR=1` does the same. |

## What you are writing

Your program reads the input from stdin and prints the answer to stdout. For
Two Sum it reads three lines and prints two indexes:

```text
4
2 7 11 15
9
```

prints `0 1`. The problem's `statement.md` gives the exact format.

GradBot works out the language from the file extension:

| Language | Files | Runs |
|---|---|---|
| Python | `.py` | `solution.py`, else `main.py`, else the only `.py` file |
| C | `.c` | `gcc` (all `.c` files together) |
| C++ | `.cpp`, `.cc`, `.cxx` | `g++ -std=c++17` |
| Java | `.java` | `javac`, then the class with `public static void main` |

A compile error is reported with the line number. Add `--verbose` to see the
compiler's full message. GradBot compiles in a private copy, so nothing
(binaries, `.class` files, `__pycache__`) is added to your folder.

## Graded submit

Your teacher turns graded submits on by giving you two values,
`GRADBOT_CLIENT_ID` and `GRADBOT_SUBMIT_URL`. Until both are set, `grade
submit` stops and tells you so.

```bash
grade login
grade submit arrays/two_sum
```

`grade login` prints a code and a GitHub address. Open it, enter the code,
and approve. GradBot asks only for `read:user`, which proves who you are and
cannot read your repositories. The token is saved in `~/.gradbot`, readable
only by you.

`grade submit` sends your source files (`.py`, `.c`, `.h`, `.cpp`, `.cc`, `.cxx`,
`.hpp`, `.java`) and nothing else: no `.git`, no binaries, no `checks.py`.

You get **one** graded submit per problem. A second one is refused. If the
upload fails before grading starts, you can try again. A second chance is a
teacher action (`grade reset`), not another submit.

The result you get back is pass or fail per check, the points, and the
hints. It never includes the hidden expected output.

## When something goes wrong

| Message | What to do |
|---|---|
| `Couldn't find the problem 'x/y' in ...` | Check the slug, and that `GRADBOT_PUBLIC_REPO` is your course. |
| `Couldn't find the problem repo ...` | `GRADBOT_PUBLIC_REPO` names a repo that does not exist or is private. |
| `Couldn't connect to download the problem` | Check your connection, or add `--offline` if you ran this problem before. |
| `This problem accepts ...` | Your folder has a language this problem doesn't take. |
| `GradBot found several Python files ...` | Name the file to run `solution.py`. |
| `checks_hidden.py must not be shipped ...` | Delete that file from your folder and tell your teacher where it came from. |
