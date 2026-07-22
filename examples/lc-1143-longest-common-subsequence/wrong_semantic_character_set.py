class Solution:
    def longestCommonSubsequence(self, text1, text2):
        return len(set(text1) & set(text2))
