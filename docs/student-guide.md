# GradBot for students

GradBot checks a program you wrote. Practice runs on your computer, as many times as you want. The graded checks stay with your teacher.

## Install

You need Python 3.10 or newer, and Git.

```bash
pip install -e .
```

Use the project folder your teacher gave you for that command. Check the install:

```bash
python -m gradbot --version
```

## Practice

Put `solution.py` in a folder. From that folder:

```bash
set GRADBOT_PUBLIC_REPO=nvmaditya/gradbot-course-samples
python -m gradbot run arrays/two_sum
```

On macOS or Linux, use `export` instead of `set`.

You can practice the same problem again. A practice run shows the sample checks and, when a check fails, a hint. Add `--verbose` to see the expected output for those sample checks.

A full score exits with code 0. Anything short of full marks exits with code 1.

## What you are writing

Read the problem statement in the practice repo. For Two Sum, the program reads three lines and prints two indexes:

```text
4
2 7 11 15
9
```

prints `0 1`.

## Graded submit

Your teacher turns grading on by giving you two values: `GRADBOT_CLIENT_ID` and `GRADBOT_SUBMIT_URL`. Until you have both, `python -m gradbot submit` stops and does not grade you.

When they are set:

```bash
python -m gradbot login
python -m gradbot submit arrays/two_sum
```

Login opens GitHub in the browser and asks you to enter a device code. GradBot stores that login under your user folder (`~/.gradbot`), not in the solution folder. You can log in with any GitHub account. Only an account your teacher added to the roster can submit.

You get one graded submit per problem. A second submit is refused. If the upload fails before grading starts, you can try again. After the grader has accepted the job, that attempt is used even if your program fails the checks. A second chance is a teacher action (`gradbot reset`), not another submit from your side.

The result you get back is pass or fail, the points, and the hint. It does not include the hidden expected output.

## If practice says it cannot find the problem

Check `GRADBOT_PUBLIC_REPO`. For this course it is `nvmaditya/gradbot-course-samples`. You need a network connection the first time. Later you can add `--offline` to reuse the copy already on your machine.
