class Solution:

    def isPalindrome(self, x: int) -> bool:
        digits = str(x)
        return 1 if digits == digits[::-1] else 0
