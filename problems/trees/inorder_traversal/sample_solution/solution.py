"""
BST Inorder Traversal — Sample Solution

Inserts values into a BST, then performs inorder traversal.

Input: n, then n integers
Output: space-separated inorder traversal
"""

class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

def insert(root, val):
    if root is None:
        return Node(val)
    if val < root.val:
        root.left = insert(root.left, val)
    else:
        root.right = insert(root.right, val)
    return root

def inorder(root, result):
    if root is None:
        return
    inorder(root.left, result)
    result.append(str(root.val))
    inorder(root.right, result)

n = int(input())
values = list(map(int, input().split()))

root = None
for v in values:
    root = insert(root, v)

result = []
inorder(root, result)
print(" ".join(result))
