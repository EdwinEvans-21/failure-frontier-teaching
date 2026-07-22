class Solution:
    def longestCommonSubsequence(self, text1, text2):
        return sum(left == right for left, right in zip(text1, text2))
