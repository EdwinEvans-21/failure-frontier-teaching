class Solution:
    def countPrefixSuffixPairs(self, words):
        seen = {}
        answer = 0
        for word in words:
            n = len(word)
            z = [0] * n
            left = right = 0
            for i in range(1, n):
                if i < right:
                    z[i] = min(right - i, z[i-left])
                while i + z[i] < n and word[z[i]] == word[i+z[i]]:
                    z[i] += 1
                if i + z[i] > right:
                    left, right = i, i + z[i]
            for length in range(1, n + 1):
                if length == n or z[n-length] >= length:
                    answer += seen.get(word[:length], 0)
            seen[word] = seen.get(word, 0) + 1
        return answer
