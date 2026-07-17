class Solution:

    def isPalindrome(self, x: int) -> bool:
        digits = str(abs(x))
        return digits == digits[::-1]
