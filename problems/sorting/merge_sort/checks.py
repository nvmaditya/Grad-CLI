"""
Checks for Merge Sort problem.

Implement merge sort and print the sorted array.
"""

import gradbot


@gradbot.check("Basic case: 5 3 1 4 2", points=1,
               hint="Start by splitting the array in half, sorting each half, then merging!")
def test_basic():
    result = gradbot.run(input="5\n5 3 1 4 2\n")
    gradbot.expect_output(result.stdout.strip(), "1 2 3 4 5")


@gradbot.check("Already sorted array", points=1, depends_on="test_basic",
               hint="Your sort should handle already-sorted input correctly!")
def test_sorted():
    result = gradbot.run(input="5\n1 2 3 4 5\n")
    gradbot.expect_output(result.stdout.strip(), "1 2 3 4 5")


@gradbot.check("Reverse sorted array", points=1, depends_on="test_basic",
               hint="Try sorting a reversed array — this is the worst case for some algorithms!")
def test_reverse():
    result = gradbot.run(input="5\n5 4 3 2 1\n")
    gradbot.expect_output(result.stdout.strip(), "1 2 3 4 5")


@gradbot.check("Duplicate values", points=1, depends_on="test_basic",
               hint="Make sure your merge step handles equal values correctly!")
def test_duplicates():
    result = gradbot.run(input="6\n3 1 4 1 5 9\n")
    gradbot.expect_output(result.stdout.strip(), "1 1 3 4 5 9")
