class Solution:
    def longestCommonSubsequence(self, text1, text2):
        position = 0
        matches = 0
        for character in text1:
            while position < len(text2) and text2[position] != character:
                position += 1
            if position < len(text2):
                matches += 1
                position += 1
        return matches
