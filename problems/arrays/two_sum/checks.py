"""
Checks for Two Sum problem.

Given an array of integers and a target, return the indices of two numbers
that add up to the target.
"""

import gradbot


@gradbot.check("Basic case: [2,7,11,15], target=9", points=1,
               hint="For the simplest case, try every pair of numbers!")
def test_basic():
    # Input: 4 numbers, target 9 → indices 0 and 1 (2+7=9)
    result = gradbot.run(input="4\n2 7 11 15\n9\n")
    gradbot.expect_output(result.stdout.strip(), "0 1")


@gradbot.check("Negative numbers work", points=1, depends_on="test_basic",
               hint="Negative numbers follow the same rules — make sure you handle them!")
def test_negatives():
    # Input: [-1, -2, -3], target -3 → indices 0 and 1 (-1 + -2 = -3)
    result = gradbot.run(input="3\n-1 -2 -3\n-3\n")
    gradbot.expect_output(result.stdout.strip(), "0 1")


@gradbot.check("Duplicate values", points=1, depends_on="test_basic",
               hint="What if the same number appears twice? Make sure you don't use the same index!")
def test_duplicates():
    # Input: [3, 3], target 6 → indices 0 and 1
    result = gradbot.run(input="2\n3 3\n6\n")
    gradbot.expect_output(result.stdout.strip(), "0 1")


@gradbot.check("Large input performance", points=1, depends_on="test_basic",
               hint="Your solution might be too slow for large inputs. Try thinking about a faster approach using a hash map!")
def test_performance():
    # Generate 10000 numbers, target is sum of last two
    nums = list(range(10000))
    target = 19997  # 9998 + 9999
    inp = f"{len(nums)}\n{' '.join(map(str, nums))}\n{target}\n"
    result = gradbot.run(input=inp, timeout=2.0)
    if result.timed_out:
        raise gradbot.CheckFailure(
            "Solution too slow for large input",
            hint="Your solution might be too slow for large inputs. "
                 "Try thinking about a faster approach using a hash map!"
        )
    gradbot.expect_output(result.stdout.strip(), "9998 9999")
