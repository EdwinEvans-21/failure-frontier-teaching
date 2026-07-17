class Solution:

    def isPalindrome(self, x: int) -> bool:
        digits = str(x)
        return digits[0] == digits[-1]
