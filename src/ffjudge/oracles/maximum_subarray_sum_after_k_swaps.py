"""Trusted solvers for Maximum Subarray Sum After at Most K Swaps."""

from __future__ import annotations

from collections import Counter, deque


def _validate(nums: list[int], k: int) -> None:
    if not isinstance(nums, list) or not 1 <= len(nums) <= 1_500:
        raise ValueError("nums length must be in [1, 1500]")
    if any(type(value) is not int or not -100_000 <= value <= 100_000
           for value in nums):
        raise ValueError("nums values must be integers in [-100000, 100000]")
    if type(k) is not int or not 0 <= k <= len(nums):
        raise ValueError("k must be an integer in [0, len(nums)]")


def kadane_nonempty(nums: list[int] | tuple[int, ...]) -> int:
    """Return the maximum sum of a non-empty contiguous subarray."""

    best_ending = best = nums[0]
    for value in nums[1:]:
        best_ending = max(value, best_ending + value)
        best = max(best, best_ending)
    return best


class _InsideOutsideTree:
    """Dynamic order statistics plus profitable inside/outside matching."""

    def __init__(self, nums: list[int]) -> None:
        self.values = sorted(set(nums))
        self.rank = {value: index for index, value in enumerate(self.values)}
        size = 1
        while size < len(self.values):
            size *= 2
        self.size = size
        length = size * 2

        outside_count = [0] * length
        outside_sum = [0] * length
        for value, count in Counter(nums).items():
            node = size + self.rank[value]
            outside_count[node] = count
            outside_sum[node] = value * count
        for node in range(size - 1, 0, -1):
            outside_count[node] = (
                outside_count[node * 2] + outside_count[node * 2 + 1]
            )
            outside_sum[node] = (
                outside_sum[node * 2] + outside_sum[node * 2 + 1]
            )

        self._outside_count_template = outside_count
        self._outside_sum_template = outside_sum
        self._zero_template = [0] * length
        self.reset()

    def reset(self) -> None:
        self.inside_count = self._zero_template.copy()
        self.inside_sum = self._zero_template.copy()
        self.outside_count = self._outside_count_template.copy()
        self.outside_sum = self._outside_sum_template.copy()
        self.matches = self._zero_template.copy()

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

    @property
    def profitable_pairs(self) -> int:
        return self.matches[1]

    def smallest_inside_sum(self, count: int) -> int:
        return self._extreme_sum(
            count, self.inside_count, self.inside_sum, smallest=True
        )

    def largest_outside_sum(self, count: int) -> int:
        return self._extreme_sum(
            count, self.outside_count, self.outside_sum, smallest=False
        )

    def _extreme_sum(
        self,
        count: int,
        counts: list[int],
        sums: list[int],
        *,
        smallest: bool,
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
        if count:
            total += count * self.values[node - self.size]
        return total


def max_sum_reference(nums: list[int], k: int) -> int:
    """Return the optimum in O(n^2 log n) time and O(n) space."""

    _validate(nums, k)
    if k == 0:
        return kadane_nonempty(nums)
    if k >= len(nums):
        positive_sum = sum(value for value in nums if value > 0)
        return positive_sum if positive_sum else max(nums)

    tree = _InsideOutsideTree(nums)
    answer = nums[0]
    for left in range(len(nums)):
        tree.reset()
        interval_sum = 0
        for right in range(left, len(nums)):
            value = nums[right]
            interval_sum += value
            tree.move_inside(value)
            swaps = min(k, tree.profitable_pairs)
            gain = (
                tree.largest_outside_sum(swaps)
                - tree.smallest_inside_sum(swaps)
                if swaps else 0
            )
            answer = max(answer, interval_sum + gain)
    return answer


def max_sum_bfs(nums: list[int], k: int) -> int:
    """Independent n<=8 oracle using explicit swap-state BFS and Kadane."""

    _validate(nums, k)
    if len(nums) > 8:
        raise ValueError("the BFS oracle is limited to n <= 8")

    start = tuple(nums)
    depths = {start: 0}
    queue = deque([start])
    answer = kadane_nonempty(start)
    while queue:
        state = queue.popleft()
        depth = depths[state]
        answer = max(answer, kadane_nonempty(state))
        if depth == k:
            continue
        for left in range(len(state)):
            for right in range(left + 1, len(state)):
                successor = list(state)
                successor[left], successor[right] = (
                    successor[right], successor[left]
                )
                next_state = tuple(successor)
                if next_state not in depths:
                    depths[next_state] = depth + 1
                    queue.append(next_state)
    return answer


def max_sum_sorting_oracle(nums: list[int], k: int) -> int:
    """Slow interval-sorting oracle used only for tests and wrong fixtures."""

    _validate(nums, k)
    answer = nums[0]
    for left in range(len(nums)):
        for right in range(left, len(nums)):
            inside = sorted(nums[left:right + 1])
            outside = sorted(nums[:left] + nums[right + 1:], reverse=True)
            gains = (
                outside[index] - inside[index]
                for index in range(min(k, len(inside), len(outside)))
            )
            answer = max(
                answer,
                sum(inside) + sum(gain for gain in gains if gain > 0),
            )
    return answer
