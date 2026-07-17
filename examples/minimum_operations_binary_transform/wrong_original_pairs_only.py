class Solution:

    def minOperations(self, s1: str, s2: str) -> int:
        operations = 0
        index = 0
        while index < len(s1):
            if (index + 1 < len(s1)
                    and s1[index:index + 2] == "11"
                    and s2[index:index + 2] == "00"):
                operations += 1
                index += 2
            elif s1[index] == "0" and s2[index] == "1":
                operations += 1
                index += 1
            elif s1[index] != s2[index]:
                return -1
            else:
                index += 1
        return operations
