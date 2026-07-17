class Solution:

    def minOperations(self, s1: str, s2: str) -> int:
        decreases = [
            index for index, bits in enumerate(zip(s1, s2))
            if bits == ("1", "0")
        ]
        if any(right != left + 1
               for left, right in zip(decreases[::2], decreases[1::2])):
            return -1
        return len(decreases) // 2 + sum(
            left == "0" and right == "1" for left, right in zip(s1, s2)
        )
