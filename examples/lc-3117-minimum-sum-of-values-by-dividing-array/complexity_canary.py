from __future__ import annotations
from bisect import bisect_left
from functools import lru_cache
from itertools import combinations
from math import inf
MOD = 1000000007

def minimum_value_sum_reference(nums: list[int], targets: list[int]) -> int:
    states = {(0, -1): 0}
    for value in nums:
        nxt: dict[tuple[int, int], int] = {}
        for (done, current), cost in states.items():
            if done == len(targets):
                continue
            merged = value if current == -1 else current & value
            if merged & targets[done] != targets[done]:
                continue
            key = (done, merged)
            nxt[key] = min(nxt.get(key, inf), cost)
            if merged == targets[done]:
                key = (done + 1, -1)
                nxt[key] = min(nxt.get(key, inf), cost + value)
        states = nxt
    answer = states.get((len(targets), -1), inf)
    return -1 if answer == inf else answer

def minimum_value_sum_bruteforce(nums: list[int], targets: list[int]) -> int:
    n, m = (len(nums), len(targets))
    answer = inf
    for cuts in combinations(range(1, n), m - 1):
        starts = (0,) + cuts
        ends = cuts + (n,)
        cost = 0
        valid = True
        for start, end, target in zip(starts, ends, targets):
            value = nums[start]
            for x in nums[start + 1:end]:
                value &= x
            if value != target:
                valid = False
                break
            cost += nums[end - 1]
        if valid:
            answer = min(answer, cost)
    return -1 if answer == inf else answer

def maximum_strength_reference(nums: list[int], k: int) -> int:
    neg = -10 ** 60
    outside = [neg] * (k + 1)
    inside = [neg] * (k + 1)
    outside[0] = 0
    for value in nums:
        old_out, old_in = (outside[:], inside[:])
        for j in range(1, k + 1):
            weight = (k - j + 1) * (1 if j & 1 else -1)
            inside[j] = max(old_in[j], old_out[j - 1], old_in[j - 1]) + weight * value
            outside[j] = max(old_out[j], old_in[j])
    return max(outside[k], inside[k])

def maximum_strength_bruteforce(nums: list[int], k: int) -> int:
    n = len(nums)

    @lru_cache(None)
    def solve(start: int, j: int) -> int:
        if j > k:
            return 0
        best = -10 ** 60
        weight = (k - j + 1) * (1 if j & 1 else -1)
        for left in range(start, n):
            total = 0
            for right in range(left, n):
                total += nums[right]
                remaining = k - j
                if n - right - 1 >= remaining:
                    best = max(best, weight * total + solve(right + 1, j + 1))
        return best
    return solve(0, 1)

def minimum_finish_time_reference(tires: list[list[int]], change: int, laps: int) -> int:
    best = [inf] * (laps + 1)
    for first, ratio in tires:
        total = 0
        current = first
        for length in range(1, laps + 1):
            total += current
            best[length] = min(best[length], total)
            current *= ratio
            if current > first + change:
                break
    dp = [inf] * (laps + 1)
    dp[0] = -change
    for i in range(1, laps + 1):
        for length in range(1, i + 1):
            if best[length] < inf:
                dp[i] = min(dp[i], dp[i - length] + change + best[length])
    return dp[laps]

def minimum_finish_time_bruteforce(tires: list[list[int]], change: int, laps: int) -> int:

    @lru_cache(None)
    def solve(done: int, tire: int, consecutive: int) -> int:
        if done == laps:
            return 0
        best = inf
        if tire >= 0:
            f, r = tires[tire]
            best = f * r ** consecutive + solve(done + 1, tire, consecutive + 1)
        for nxt, (f, _) in enumerate(tires):
            cost = (0 if done == 0 else change) + f + solve(done + 1, nxt, 1)
            best = min(best, cost)
        return best
    return solve(0, -1, 0)

def minimum_time_reference(a: list[int], b: list[int], x: int) -> int:
    n = len(a)
    order = sorted(zip(b, a))
    dp = [0] * (n + 1)
    for growth, initial in order:
        for used in range(n, 0, -1):
            dp[used] = max(dp[used], dp[used - 1] + initial + growth * used)
    initial_sum, growth_sum = (sum(a), sum(b))
    for time in range(n + 1):
        if initial_sum + growth_sum * time - dp[time] <= x:
            return time
    return -1

def minimum_time_bruteforce(a: list[int], b: list[int], x: int) -> int:
    n = len(a)
    for time in range(n + 1):
        best = 0
        for chosen in combinations(range(n), time):
            for order in __import__('itertools').permutations(chosen):
                reduction = sum((a[i] + b[i] * (step + 1) for step, i in enumerate(order)))
                best = max(best, reduction)
        if sum(a) + sum(b) * time - best <= x:
            return time
    return -1

def beautiful_partitions_reference(s: str, k: int, minimum: int) -> int:
    prime = set('2357')
    n = len(s)
    if s[0] not in prime or s[-1] in prime:
        return 0
    start_ok = [False] * (n + 1)
    end_ok = [False] * (n + 1)
    start_ok[0] = True
    end_ok[n] = True
    for i in range(1, n):
        boundary = s[i - 1] not in prime and s[i] in prime
        start_ok[i] = boundary
        end_ok[i] = boundary
    dp = [0] * (n + 1)
    dp[0] = 1
    for _ in range(k):
        nxt = [0] * (n + 1)
        running = 0
        for end in range(1, n + 1):
            start = end - minimum
            if start >= 0 and start_ok[start]:
                running = (running + dp[start]) % MOD
            if end_ok[end]:
                nxt[end] = running
        dp = nxt
    return dp[n]

def beautiful_partitions_bruteforce(s: str, k: int, minimum: int) -> int:
    prime = set('2357')
    answer = 0
    for cuts in combinations(range(1, len(s)), k - 1):
        starts = (0,) + cuts
        ends = cuts + (len(s),)
        if all((end - start >= minimum and s[start] in prime and (s[end - 1] not in prime) for start, end in zip(starts, ends))):
            answer += 1
    return answer % MOD

def count_integers_reference(low: str, high: str, minimum: int, maximum: int) -> int:

    def upto(bound: str) -> int:

        @lru_cache(None)
        def dp(index: int, total: int, tight: bool) -> int:
            if total > maximum:
                return 0
            if index == len(bound):
                return int(minimum <= total <= maximum)
            limit = int(bound[index]) if tight else 9
            return sum((dp(index + 1, total + digit, tight and digit == limit) for digit in range(limit + 1))) % MOD
        return dp(0, 0, True)
    return (upto(high) - upto(str(int(low) - 1))) % MOD

def count_integers_bruteforce(low: str, high: str, minimum: int, maximum: int) -> int:
    return sum((minimum <= sum(map(int, str(x))) <= maximum for x in range(int(low), int(high) + 1))) % MOD

def maximum_nondecreasing_length_reference(nums: list[int]) -> int:
    prefix = [0]
    for value in nums:
        prefix.append(prefix[-1] + value)
    n = len(nums)
    dp = [0] * (n + 1)
    last = [0] * (n + 1)
    for i in range(n + 1):
        if i and dp[i - 1] > dp[i]:
            dp[i] = dp[i - 1]
            last[i] = last[i - 1] + nums[i - 1]
        target = prefix[i] + last[i]
        j = bisect_left(prefix, target, i + 1)
        if j <= n and (dp[i] + 1 > dp[j] or (dp[i] + 1 == dp[j] and prefix[j] - prefix[i] < last[j])):
            dp[j] = dp[i] + 1
            last[j] = prefix[j] - prefix[i]
    return dp[n]

def maximum_nondecreasing_length_bruteforce(nums: list[int]) -> int:
    n = len(nums)
    best = 1
    for mask in range(1 << n - 1):
        sums = []
        current = nums[0]
        for i in range(n - 1):
            if mask >> i & 1:
                sums.append(current)
                current = nums[i + 1]
            else:
                current += nums[i + 1]
        sums.append(current)
        if all((a <= b for a, b in zip(sums, sums[1:]))):
            best = max(best, len(sums))
    return best

def max_balanced_sum_reference(nums: list[int]) -> int:
    keys = sorted(set((value - i for i, value in enumerate(nums))))
    tree = [-10 ** 30] * (len(keys) + 1)

    def query(i: int) -> int:
        answer = -10 ** 30
        while i:
            answer = max(answer, tree[i])
            i -= i & -i
        return answer

    def update(i: int, value: int) -> None:
        while i < len(tree):
            tree[i] = max(tree[i], value)
            i += i & -i
    answer = -10 ** 30
    for i, value in enumerate(nums):
        index = bisect_left(keys, value - i) + 1
        current = value + max(0, query(index))
        update(index, current)
        answer = max(answer, current)
    return answer

def max_balanced_sum_bruteforce(nums: list[int]) -> int:
    answer = -10 ** 30
    n = len(nums)
    for mask in range(1, 1 << n):
        chosen = [i for i in range(n) if mask >> i & 1]
        if all((nums[a] - a <= nums[b] - b for a, b in zip(chosen, chosen[1:]))):
            answer = max(answer, sum((nums[i] for i in chosen)))
    return answer

def minimum_difference_reference(nums: list[int]) -> int:
    half = len(nums) // 2
    left, right = (nums[:half], nums[half:])
    a = [[] for _ in range(half + 1)]
    b = [[] for _ in range(half + 1)]
    for mask in range(1 << half):
        count = mask.bit_count()
        a[count].append(sum((left[i] for i in range(half) if mask >> i & 1)))
        b[count].append(sum((right[i] for i in range(half) if mask >> i & 1)))
    total = sum(nums)
    answer = inf
    for count in range(half + 1):
        values = sorted(b[half - count])
        for x in a[count]:
            target = total / 2 - x
            pos = bisect_left(values, target)
            for j in (pos - 1, pos):
                if 0 <= j < len(values):
                    answer = min(answer, abs(total - 2 * (x + values[j])))
    return int(answer)

def minimum_difference_bruteforce(nums: list[int]) -> int:
    half = len(nums) // 2
    total = sum(nums)
    return min((abs(total - 2 * sum((nums[i] for i in chosen))) for chosen in combinations(range(len(nums)), half)))

def minimum_cut_cost_reference(n: int, cuts: list[int]) -> int:
    points = [0] + sorted(cuts) + [n]
    size = len(points)
    dp = [[0] * size for _ in range(size)]
    for gap in range(2, size):
        for left in range(size - gap):
            right = left + gap
            dp[left][right] = points[right] - points[left] + min((dp[left][mid] + dp[mid][right] for mid in range(left + 1, right)))
    return dp[0][-1]

def minimum_cut_cost_bruteforce(n: int, cuts: list[int]) -> int:

    @lru_cache(None)
    def solve(left: int, right: int, remaining: tuple[int, ...]) -> int:
        if not remaining:
            return 0
        return min((right - left + solve(left, cut, tuple((x for x in remaining if x < cut))) + solve(cut, right, tuple((x for x in remaining if x > cut))) for cut in remaining))
    return solve(0, n, tuple(sorted(cuts)))

class Solution:
    def minimumValueSum(self, *args, **kwargs):
        return minimum_value_sum_bruteforce(*args, **kwargs)
