"""
Reverse Words — Sample Solution

Input: a single line with a sentence
Output: the sentence with words reversed
"""

sentence = input()
words = sentence.split()
print(" ".join(reversed(words)))
