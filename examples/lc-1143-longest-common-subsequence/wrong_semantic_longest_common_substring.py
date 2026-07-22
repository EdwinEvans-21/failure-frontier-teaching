class Solution:
    def longestCommonSubsequence(self, text1, text2):
        answer = 0
        for left in range(len(text1)):
            for right in range(len(text2)):
                length = 0
                while left + length < len(text1) and right + length < len(text2) and text1[left + length] == text2[right + length]:
                    length += 1
                answer = max(answer, length)
        return answer
