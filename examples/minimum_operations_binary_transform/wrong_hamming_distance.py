class Solution:

    def minOperations(self, s1: str, s2: str) -> int:
        return sum(left != right for left, right in zip(s1, s2))
