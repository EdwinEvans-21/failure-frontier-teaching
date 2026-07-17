class Solution:

    def isPalindrome(self, x: int) -> bool:
        if x <= 0:
            return False
        digits = str(x)
        return digits == digits[::-1]
