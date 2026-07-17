from collections import Counter


class OrderStatisticsTree:

    def __init__(self, nums: list[int]) -> None:
        self.values = sorted(set(nums))
        self.rank = {value: index for index, value in enumerate(self.values)}
        self.size = 1
        while self.size < len(self.values):
            self.size *= 2
        length = self.size * 2
        outside_count = [0] * length
        outside_sum = [0] * length
        for value, count in Counter(nums).items():
            node = self.size + self.rank[value]
            outside_count[node] = count
            outside_sum[node] = value * count
        for node in range(self.size - 1, 0, -1):
            outside_count[node] = (
                outside_count[node * 2] + outside_count[node * 2 + 1]
            )
            outside_sum[node] = (
                outside_sum[node * 2] + outside_sum[node * 2 + 1]
            )
        self.outside_count_template = outside_count
        self.outside_sum_template = outside_sum
        self.zeros = [0] * length

    def reset(self) -> None:
        self.inside_count = self.zeros.copy()
        self.inside_sum = self.zeros.copy()
        self.outside_count = self.outside_count_template.copy()
        self.outside_sum = self.outside_sum_template.copy()
        self.matches = self.zeros.copy()

    def move_inside(self, value: int) -> None:
        node = self.size + self.rank[value]
        self.inside_count[node] += 1
        self.inside_sum[node] += value
        self.outside_count[node] -= 1
        self.outside_sum[node] -= value
        node //= 2
        while node:
            left = node * 2
            right = left + 1
            left_matches = self.matches[left]
            right_matches = self.matches[right]
            cross = min(
                self.inside_count[left] - left_matches,
                self.outside_count[right] - right_matches,
            )
            self.inside_count[node] = (
                self.inside_count[left] + self.inside_count[right]
            )
            self.inside_sum[node] = (
                self.inside_sum[left] + self.inside_sum[right]
            )
            self.outside_count[node] = (
                self.outside_count[left] + self.outside_count[right]
            )
            self.outside_sum[node] = (
                self.outside_sum[left] + self.outside_sum[right]
            )
            self.matches[node] = left_matches + right_matches + cross
            node //= 2

    def extreme_sum(
        self, count: int, counts: list[int], sums: list[int], smallest: bool
    ) -> int:
        node = 1
        total = 0
        while node < self.size:
            preferred = node * 2 if smallest else node * 2 + 1
            other = preferred + 1 if smallest else preferred - 1
            if counts[preferred] >= count:
                node = preferred
            else:
                total += sums[preferred]
                count -= counts[preferred]
                node = other
        return total + count * self.values[node - self.size]


class Solution:

    def maxSum(self, nums: list[int], k: int) -> int:
        if k == 0:
            best_ending = answer = nums[0]
            for value in nums[1:]:
                best_ending = max(value, best_ending + value)
                answer = max(answer, best_ending)
            return answer
        if k >= len(nums):
            positive_sum = sum(value for value in nums if value > 0)
            return positive_sum if positive_sum else max(nums)

        tree = OrderStatisticsTree(nums)
        answer = nums[0]
        for left in range(len(nums)):
            tree.reset()
            interval_sum = 0
            for right in range(left, len(nums)):
                value = nums[right]
                interval_sum += value
                tree.move_inside(value)
                swaps = min(k, tree.matches[1])
                gain = 0
                if swaps:
                    gain = tree.extreme_sum(
                        swaps,
                        tree.outside_count,
                        tree.outside_sum,
                        False,
                    ) - tree.extreme_sum(
                        swaps,
                        tree.inside_count,
                        tree.inside_sum,
                        True,
                    )
                answer = max(answer, interval_sum + gain)
        return answer
