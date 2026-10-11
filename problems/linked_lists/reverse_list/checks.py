"""
Checks for Reverse Linked List problem.

Reverse a singly linked list and print nodes in order.
"""

import gradbot


@gradbot.check("Basic case: 1 2 3 4 5", points=1,
               hint="Walk through the list with three pointers: prev, current, and next!")
def test_basic():
    result = gradbot.run(input="5\n1 2 3 4 5\n")
    gradbot.expect_output(result.stdout.strip(), "5 4 3 2 1")


@gradbot.check("Single node list", points=1, depends_on="test_basic",
               hint="A single node reversed is still just that node!")
def test_single():
    result = gradbot.run(input="1\n42\n")
    gradbot.expect_output(result.stdout.strip(), "42")


@gradbot.check("Two nodes", points=1, depends_on="test_basic",
               hint="Try the simplest case with just two nodes — swap them!")
def test_two():
    result = gradbot.run(input="2\n10 20\n")
    gradbot.expect_output(result.stdout.strip(), "20 10")


@gradbot.check("Large list performance", points=1, depends_on="test_basic",
               hint="Make sure your solution runs in O(n) — one pass through the list!")
def test_large():
    n = 1000
    nums = list(range(1, n + 1))
    inp = f"{n}\n{' '.join(map(str, nums))}\n"
    result = gradbot.run(input=inp, timeout=2.0)
    if result.timed_out:
        raise gradbot.CheckFailure(
            "Solution too slow for large list",
            hint="Your solution should run in O(n) time — one pass through the list!"
        )
    expected = " ".join(map(str, reversed(nums)))
    gradbot.expect_output(result.stdout.strip(), expected)
