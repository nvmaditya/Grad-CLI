"""
Two Sum — Sample Solution (O(n) using hash map)

Input:
  Line 1: n (number of elements)
  Line 2: n space-separated integers
  Line 3: target sum

Output:
  Two space-separated indices (0-indexed) of elements that sum to target
"""

n = int(input())
nums = list(map(int, input().split()))
target = int(input())

seen = {}  # value → index
for i, num in enumerate(nums):
    complement = target - num
    if complement in seen:
        print(seen[complement], i)
        break
    seen[num] = i
