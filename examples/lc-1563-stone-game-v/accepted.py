from __future__ import annotations
from bisect import bisect_left, bisect_right
from typing import List

class Solution:
    def stoneGameV(self, stoneValue: List[int]) -> int:
        n = len(stoneValue)
        prefix = [0]
        for value in stoneValue:
            prefix.append(prefix[-1] + value)

        dp = [[0] * n for _ in range(n)]
        left_best = [[0] * n for _ in range(n)]
        right_best = [[0] * n for _ in range(n)]
        for index in range(n):
            left_best[index][index] = prefix[index + 1]
            right_best[index][index] = -prefix[index]

        for length in range(2, n + 1):
            for left in range(n - length + 1):
                right = left + length - 1
                total = prefix[right + 1] - prefix[left]
                answer = 0

                split_prefix = bisect_right(
                    prefix, prefix[left] + total // 2, left + 1, right + 1
                )
                if split_prefix > left + 1:
                    answer = left_best[left][split_prefix - 2] - prefix[left]

                split_prefix = bisect_left(
                    prefix, prefix[left] + (total + 1) // 2, left + 1, right + 1
                )
                if split_prefix <= right:
                    answer = max(answer, prefix[right + 1] + right_best[split_prefix][right])

                dp[left][right] = answer
                left_best[left][right] = max(
                    left_best[left][right - 1], prefix[right + 1] + answer
                )
                right_best[left][right] = max(
                    -prefix[left] + answer, right_best[left + 1][right]
                )
        return dp[0][n - 1]
