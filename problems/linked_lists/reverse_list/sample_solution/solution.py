"""
Reverse Linked List — Sample Solution

Uses a simple iterative approach with three pointers.

Input: n, then n space-separated values
Output: space-separated values in reverse order
"""

class Node:
    def __init__(self, val):
        self.val = val
        self.next = None

n = int(input())
values = list(map(int, input().split()))

# Build the linked list
head = None
tail = None
for v in values:
    node = Node(v)
    if head is None:
        head = node
        tail = node
    else:
        tail.next = node
        tail = node

# Reverse the linked list
prev = None
current = head
while current:
    next_node = current.next
    current.next = prev
    prev = current
    current = next_node
head = prev

# Print the reversed list
result = []
current = head
while current:
    result.append(str(current.val))
    current = current.next
print(" ".join(result))
