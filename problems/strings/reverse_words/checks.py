"""
Checks for Reverse Words problem.

Reverse the order of words in a sentence.
"""

import gradbot


@gradbot.check("Basic case: hello world", points=1,
               hint="Split the sentence into words, reverse them, and join back together!")
def test_basic():
    result = gradbot.run(input="hello world\n")
    gradbot.expect_output(result.stdout.strip(), "world hello")


@gradbot.check("Multiple words", points=1, depends_on="test_basic",
               hint="Make sure you handle sentences with more than two words!")
def test_multiple():
    result = gradbot.run(input="the quick brown fox\n")
    gradbot.expect_output(result.stdout.strip(), "fox brown quick the")


@gradbot.check("Single word stays the same", points=1, depends_on="test_basic",
               hint="A single word reversed is itself — check your edge cases!")
def test_single_word():
    result = gradbot.run(input="hello\n")
    gradbot.expect_output(result.stdout.strip(), "hello")


@gradbot.check("Handles extra spaces", points=1, depends_on="test_basic",
               hint="Be careful with multiple spaces between words. Use split() without arguments!")
def test_extra_spaces():
    result = gradbot.run(input="  hello   world  \n")
    gradbot.expect_output(result.stdout.strip(), "world hello")
