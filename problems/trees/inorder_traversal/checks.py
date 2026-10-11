"""
Checks for BST Inorder Traversal problem.

Insert values into a BST, then print the inorder traversal.
"""

import gradbot


@gradbot.check("Basic BST: 4 2 6 1 3", points=1,
               hint="Remember: inorder means Left, Root, Right. For a BST, this gives sorted order!")
def test_basic():
    result = gradbot.run(input="5\n4 2 6 1 3\n")
    gradbot.expect_output(result.stdout.strip(), "1 2 3 4 6")


@gradbot.check("Single node", points=1, depends_on="test_basic",
               hint="A tree with one node — the traversal is just that node!")
def test_single():
    result = gradbot.run(input="1\n42\n")
    gradbot.expect_output(result.stdout.strip(), "42")


@gradbot.check("Right-skewed tree (already sorted input)", points=1, depends_on="test_basic",
               hint="When you insert sorted values, the tree becomes a straight line to the right. Inorder should still work!")
def test_skewed():
    result = gradbot.run(input="5\n1 2 3 4 5\n")
    gradbot.expect_output(result.stdout.strip(), "1 2 3 4 5")


@gradbot.check("Balanced tree with many nodes", points=1, depends_on="test_basic",
               hint="Make sure your recursion works correctly for deeper trees!")
def test_balanced():
    # Insert in an order that creates a somewhat balanced tree
    # 8, 4, 12, 2, 6, 10, 14
    result = gradbot.run(input="7\n8 4 12 2 6 10 14\n")
    gradbot.expect_output(result.stdout.strip(), "2 4 6 8 10 12 14")
