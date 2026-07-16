class Solution:

    def isPalindrome(self, x: int) -> bool:
        allocations = []
        while True:
            allocations.append(bytearray(32 * 1024 * 1024))
