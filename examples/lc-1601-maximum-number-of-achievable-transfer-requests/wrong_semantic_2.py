from __future__ import annotations

from collections import Counter
from collections import deque
from heapq import heappop, heappush
from functools import lru_cache
from itertools import combinations, permutations, product


MOD = 1_000_000_007


def max_students_reference(seats: list[list[str]]) -> int:
    rows, cols = len(seats), len(seats[0])
    allowed = []
    for row in seats:
        mask = 0
        for column, value in enumerate(row):
            if value == ".":
                mask |= 1 << column
        allowed.append(mask)
    valid = [mask for mask in range(1 << cols) if not mask & (mask << 1)]
    previous = {0: 0}
    for available in allowed:
        current: dict[int, int] = {}
        for mask in valid:
            if mask & ~available:
                continue
            count = mask.bit_count()
            for old, score in previous.items():
                if mask & (old << 1) or mask & (old >> 1):
                    continue
                current[mask] = max(current.get(mask, -1), score + count)
        previous = current
    return max(previous.values())


def max_students_oracle(seats: list[list[str]]) -> int:
    places = [(r, c) for r, row in enumerate(seats) for c, value in enumerate(row)
              if value == "."]
    answer = 0
    for mask in range(1 << len(places)):
        chosen = {places[i] for i in range(len(places)) if mask >> i & 1}
        valid = True
        for r, c in chosen:
            for nr, nc in ((r, c - 1), (r, c + 1), (r - 1, c - 1),
                           (r - 1, c + 1), (r + 1, c - 1), (r + 1, c + 1)):
                if (nr, nc) in chosen:
                    valid = False
                    break
            if not valid:
                break
        if valid:
            answer = max(answer, len(chosen))
    return answer


def max_size_slices_reference(slices: list[int]) -> int:
    picks = len(slices) // 3

    def linear(values: list[int]) -> int:
        previous = [0] + [-10**18] * picks
        before_previous = previous[:]
        for value in values:
            current = previous[:]
            for count in range(1, picks + 1):
                current[count] = max(previous[count], before_previous[count - 1] + value)
            before_previous, previous = previous, current
        return previous[picks]

    return max(linear(slices[:-1]), linear(slices[1:]))


def max_size_slices_oracle(slices: list[int]) -> int:
    size = len(slices)
    picks = size // 3
    answer = 0
    for chosen in combinations(range(size), picks):
        selected = set(chosen)
        if any((index + 1) % size in selected for index in selected):
            continue
        answer = max(answer, sum(slices[index] for index in selected))
    return answer


def number_of_arrays_reference(s: str, k: int) -> int:
    n = len(s)
    dp = [0] * (n + 1)
    dp[n] = 1
    width = len(str(k))
    for i in range(n - 1, -1, -1):
        if s[i] == "0":
            continue
        value = 0
        for j in range(i, min(n, i + width)):
            value = value * 10 + ord(s[j]) - 48
            if value > k:
                break
            dp[i] = (dp[i] + dp[j + 1]) % MOD
    return dp[0]


def number_of_arrays_oracle(s: str, k: int) -> int:
    @lru_cache(None)
    def visit(index: int) -> int:
        if index == len(s):
            return 1
        if s[index] == "0":
            return 0
        total = 0
        for end in range(index + 1, len(s) + 1):
            value = int(s[index:end])
            if value > k:
                break
            total += visit(end)
        return total

    return visit(0) % MOD


def num_of_arrays_reference(n: int, m: int, k: int) -> int:
    if k == 0:
        return 0
    previous = [[0] * (m + 1) for _ in range(k + 1)]
    for maximum in range(1, m + 1):
        previous[1][maximum] = 1
    for _ in range(1, n):
        current = [[0] * (m + 1) for _ in range(k + 1)]
        for cost in range(1, k + 1):
            prefix = 0
            for maximum in range(1, m + 1):
                current[cost][maximum] = (
                    previous[cost][maximum] * maximum + prefix
                ) % MOD
                if cost > 1:
                    prefix = (prefix + previous[cost - 1][maximum]) % MOD
        previous = current
    return sum(previous[k]) % MOD


def num_of_arrays_oracle(n: int, m: int, k: int) -> int:
    if k == 0:
        return 0
    answer = 0
    for values in product(range(1, m + 1), repeat=n):
        maximum = 0
        cost = 0
        for value in values:
            if value > maximum:
                maximum = value
                cost += 1
        answer += cost == k
    return answer % MOD


def number_ways_hats_reference(hats: list[list[int]]) -> int:
    people = len(hats)
    wearers = [[] for _ in range(41)]
    for person, choices in enumerate(hats):
        for hat in choices:
            wearers[hat].append(person)
    dp = [0] * (1 << people)
    dp[0] = 1
    for hat in range(1, 41):
        next_dp = dp[:]
        for mask, count in enumerate(dp):
            if not count:
                continue
            for person in wearers[hat]:
                if not mask >> person & 1:
                    next_dp[mask | 1 << person] = (next_dp[mask | 1 << person] + count) % MOD
        dp = next_dp
    return dp[-1]


def number_ways_hats_oracle(hats: list[list[int]]) -> int:
    order = sorted(range(len(hats)), key=lambda person: len(hats[person]))

    def visit(position: int, used: set[int]) -> int:
        if position == len(order):
            return 1
        total = 0
        for hat in hats[order[position]]:
            if hat not in used:
                used.add(hat)
                total += visit(position + 1, used)
                used.remove(hat)
        return total

    return visit(0, set()) % MOD


def kth_smallest_sum_reference(mat: list[list[int]], k: int) -> int:
    totals = mat[0][:]
    totals.sort()
    totals = totals[:k]
    for row in mat[1:]:
        row = sorted(row)
        heap: list[tuple[int, int, int]] = []
        visited = {(0, 0)}
        heappush(heap, (totals[0] + row[0], 0, 0))
        merged: list[int] = []
        while heap and len(merged) < k:
            total, i, j = heappop(heap)
            merged.append(total)
            if i + 1 < len(totals) and (i + 1, j) not in visited:
                visited.add((i + 1, j))
                heappush(heap, (totals[i + 1] + row[j], i + 1, j))
            if j + 1 < len(row) and (i, j + 1) not in visited:
                visited.add((i, j + 1))
                heappush(heap, (totals[i] + row[j + 1], i, j + 1))
        totals = merged
    return totals[k - 1]


def kth_smallest_sum_oracle(mat: list[list[int]], k: int) -> int:
    sums = []
    for values in product(*mat):
        sums.append(sum(values))
    sums.sort()
    return sums[k - 1]


def max_pizza_slices_reference(slices: list[int]) -> int:
    picks = len(slices) // 3

    def solve(values: list[int]) -> int:
        previous = [0] + [-10**18] * picks
        before = previous[:]
        for value in values:
            current = previous[:]
            for count in range(1, picks + 1):
                current[count] = max(previous[count], before[count - 1] + value)
            before, previous = previous, current
        return previous[picks]

    return max(solve(slices[:-1]), solve(slices[1:]))


def max_pizza_slices_oracle(slices: list[int]) -> int:
    answer = 0
    picks = len(slices) // 3
    for chosen in combinations(range(len(slices)), picks):
        selected = set(chosen)
        if any((index + 1) % len(slices) in selected for index in selected):
            continue
        answer = max(answer, sum(slices[index] for index in selected))
    return answer


def pizza_ways_reference(pizza: list[str], k: int) -> int:
    rows, cols = len(pizza), len(pizza[0])
    apples = [[0] * (cols + 1) for _ in range(rows + 1)]
    for row in range(rows - 1, -1, -1):
        for col in range(cols - 1, -1, -1):
            apples[row][col] = (
                apples[row + 1][col]
                + apples[row][col + 1]
                - apples[row + 1][col + 1]
                + (pizza[row][col] == "A")
            )

    @lru_cache(None)
    def visit(row: int, col: int, pieces: int) -> int:
        if apples[row][col] == 0:
            return 0
        if pieces == 1:
            return 1
        total = 0
        for next_row in range(row + 1, rows):
            if apples[row][col] - apples[next_row][col] > 0:
                total += visit(next_row, col, pieces - 1)
        for next_col in range(col + 1, cols):
            if apples[row][col] - apples[row][next_col] > 0:
                total += visit(row, next_col, pieces - 1)
        return total % MOD

    return visit(0, 0, k)


def pizza_ways_oracle(pizza: list[str], k: int) -> int:
    rows, cols = len(pizza), len(pizza[0])
    apples = [[0] * (cols + 1) for _ in range(rows + 1)]
    for row in range(rows - 1, -1, -1):
        for col in range(cols - 1, -1, -1):
            apples[row][col] = (
                apples[row + 1][col]
                + apples[row][col + 1]
                - apples[row + 1][col + 1]
                + (pizza[row][col] == "A")
            )

    @lru_cache(None)
    def search(row: int, col: int, pieces: int) -> int:
        if apples[row][col] == 0:
            return 0
        if pieces == 1:
            return 1
        total = 0
        for next_row in range(row + 1, rows):
            if apples[row][col] - apples[next_row][col] > 0:
                total += search(next_row, col, pieces - 1)
        for next_col in range(col + 1, cols):
            if apples[row][col] - apples[row][next_col] > 0:
                total += search(row, next_col, pieces - 1)
        return total

    return search(0, 0, k) % MOD


def max_dot_product_reference(nums1: list[int], nums2: list[int]) -> int:
    neg_inf = -10**18
    dp = [[neg_inf] * (len(nums2) + 1) for _ in range(len(nums1) + 1)]
    for i, a in enumerate(nums1, 1):
        for j, b in enumerate(nums2, 1):
            product_value = a * b
            dp[i][j] = max(
                product_value,
                dp[i - 1][j],
                dp[i][j - 1],
                dp[i - 1][j - 1] + product_value,
            )
    return dp[-1][-1]


def max_dot_product_oracle(nums1: list[int], nums2: list[int]) -> int:
    answer = -10**18
    left_subsequences = [[]]
    for value in nums1:
        left_subsequences += [seq + [value] for seq in left_subsequences]
    right_subsequences = [[]]
    for value in nums2:
        right_subsequences += [seq + [value] for seq in right_subsequences]
    for left in left_subsequences:
        if not left:
            continue
        for right in right_subsequences:
            if not right:
                continue
            if len(left) != len(right):
                continue
            answer = max(answer, sum(a * b for a, b in zip(left, right)))
    return answer


def cherry_pickup_reference(grid: list[list[int]]) -> int:
    rows, cols = len(grid), len(grid[0])
    dp = [[-10**18] * cols for _ in range(cols)]
    dp[0][cols - 1] = grid[0][0] + (grid[0][cols - 1] if cols - 1 else 0)
    for row in range(1, rows):
        current = [[-10**18] * cols for _ in range(cols)]
        for left in range(cols):
            for right in range(cols):
                best = -10**18
                for delta_left in (-1, 0, 1):
                    for delta_right in (-1, 0, 1):
                        prev_left = left - delta_left
                        prev_right = right - delta_right
                        if 0 <= prev_left < cols and 0 <= prev_right < cols:
                            best = max(best, dp[prev_left][prev_right])
                if best == -10**18:
                    continue
                cherries = grid[row][left]
                if left != right:
                    cherries += grid[row][right]
                current[left][right] = best + cherries
        dp = current
    return max(max(row) for row in dp)


def cherry_pickup_oracle(grid: list[list[int]]) -> int:
    rows, cols = len(grid), len(grid[0])
    paths = []

    def walk(row: int, left: int, right: int, total: int) -> None:
        if row == rows:
            paths.append(total)
            return
        cherries = grid[row][left]
        if left != right:
            cherries += grid[row][right]
        if row + 1 == rows:
            paths.append(total + cherries)
            return
        for delta_left in (-1, 0, 1):
            for delta_right in (-1, 0, 1):
                nl, nr = left + delta_left, right + delta_right
                if 0 <= nl < cols and 0 <= nr < cols:
                    walk(row + 1, nl, nr, total + cherries)

    walk(0, 0, cols - 1, 0)
    return max(paths)


def paint_house_reference(houses: list[int], cost: list[list[int]], m: int, n: int, target: int) -> int:
    inf = 10**18
    dp = [[[inf] * (n + 1) for _ in range(target + 1)] for _ in range(m + 1)]
    dp[0][0][0] = 0
    for i in range(1, m + 1):
        for neighborhoods in range(1, target + 1):
            for color in range(1, n + 1):
                if houses[i - 1] not in (0, color):
                    continue
                paint_cost = 0 if houses[i - 1] == color else cost[i - 1][color - 1]
                if i == 1:
                    if neighborhoods == 1:
                        dp[i][neighborhoods][color] = min(dp[i][neighborhoods][color], paint_cost)
                    continue
                for previous_color in range(1, n + 1):
                    previous_neighborhoods = neighborhoods - (previous_color != color)
                    if previous_neighborhoods < 0:
                        continue
                    value = dp[i - 1][previous_neighborhoods][previous_color]
                    dp[i][neighborhoods][color] = min(dp[i][neighborhoods][color], value + paint_cost)
    answer = min(dp[m][target][color] for color in range(1, n + 1))
    return -1 if answer == inf else answer


def paint_house_oracle(houses: list[int], cost: list[list[int]], m: int, n: int, target: int) -> int:
    inf = 10**18
    blanks = [index for index, color in enumerate(houses) if color == 0]
    answer = inf
    for colors in product(range(1, n + 1), repeat=len(blanks)):
        painted = houses[:]
        for index, color in zip(blanks, colors):
            painted[index] = color
        neighborhoods = 1
        total = 0
        for index, color in enumerate(painted):
            if index and painted[index - 1] != color:
                neighborhoods += 1
            if houses[index] == 0:
                total += cost[index][color - 1]
        if neighborhoods == target:
            answer = min(answer, total)
    return -1 if answer == inf else answer


def parallel_courses_reference(n: int, relations: list[list[int]], k: int) -> int:
    prerequisites = [0] * n
    for prev, course in relations:
        prerequisites[course - 1] |= 1 << (prev - 1)

    @lru_cache(None)
    def solve(mask: int) -> int:
        if mask == (1 << n) - 1:
            return 0
        available = [
            course for course in range(n)
            if not mask >> course & 1 and prerequisites[course] & mask == prerequisites[course]
        ]
        best = 10**9
        if len(available) <= k:
            next_mask = mask
            for course in available:
                next_mask |= 1 << course
            best = min(best, 1 + solve(next_mask))
        else:
            for chosen in combinations(available, k):
                next_mask = mask
                for course in chosen:
                    next_mask |= 1 << course
                best = min(best, 1 + solve(next_mask))
        return best

    return solve(0)


def parallel_courses_oracle(n: int, relations: list[list[int]], k: int) -> int:
    prerequisites = [set() for _ in range(n)]
    for prev, course in relations:
        prerequisites[course - 1].add(prev - 1)
    full = (1 << n) - 1
    queue = deque([(0, 0)])
    seen = {0}
    while queue:
        mask, dist = queue.popleft()
        if mask == full:
            return dist
        available = [
            course for course in range(n)
            if not mask >> course & 1 and prerequisites[course] <= {node for node in range(n) if mask >> node & 1}
        ]
        for count in range(1, min(k, len(available)) + 1):
            for chosen in combinations(available, count):
                next_mask = mask
                for course in chosen:
                    next_mask |= 1 << course
                if next_mask not in seen:
                    seen.add(next_mask)
                    queue.append((next_mask, dist + 1))
    raise AssertionError("unreachable")


def string_compression_reference(s: str, k: int) -> int:
    @lru_cache(None)
    def solve(index: int, last: str, run: int, deleted: int) -> int:
        if deleted > k:
            return 10**9
        if index == len(s):
            return 0
        keep_cost = 0
        if s[index] == last:
            keep_cost = 1 if run in {1, 9, 99} else 0
            keep = keep_cost + solve(index + 1, last, run + 1, deleted)
        else:
            keep = 1 + solve(index + 1, s[index], 1, deleted)
        drop = solve(index + 1, last, run, deleted + 1)
        return min(keep, drop)

    return solve(0, "", 0, 0)


def string_compression_oracle(s: str, k: int) -> int:
    best = 10**9
    for deleted in combinations(range(len(s)), k):
        removed = set(deleted)
        compressed: list[list[str | int]] = []
        for index, ch in enumerate(s):
            if index in removed:
                continue
            if compressed and compressed[-1][0] == ch:
                compressed[-1][1] += 1
            else:
                compressed.append([ch, 1])
        length = 0
        for _, count in compressed:
            length += 1 + (len(str(count)) if count > 1 else 0)
        best = min(best, length)
    return best if best < 10**9 else 0


@lru_cache(None)
def _minimum_days_cached(n: int) -> int:
    if n <= 1:
        return n
    return 1 + min(n % 2 + _minimum_days_cached(n // 2), n % 3 + _minimum_days_cached(n // 3))


def minimum_days_reference(n: int) -> int:
    return _minimum_days_cached(n)


def minimum_days_oracle(n: int) -> int:
    queue = deque([(n, 0)])
    seen = {n}
    while queue:
        value, dist = queue.popleft()
        if value == 0:
            return dist
        for nxt in (value - 1, value // 2 if value % 2 == 0 else None, value // 3 if value % 3 == 0 else None):
            if nxt is None or nxt < 0 or nxt in seen:
                continue
            seen.add(nxt)
            queue.append((nxt, dist + 1))
    raise AssertionError("unreachable")


def stone_game_v_reference(stone_value: list[int]) -> int:
    n = len(stone_value)
    prefix = [0]
    for value in stone_value:
        prefix.append(prefix[-1] + value)
    dp = [[0] * n for _ in range(n)]
    for length in range(2, n + 1):
        for left in range(0, n - length + 1):
            right = left + length - 1
            best = 0
            for split in range(left, right):
                left_sum = prefix[split + 1] - prefix[left]
                right_sum = prefix[right + 1] - prefix[split + 1]
                if left_sum < right_sum:
                    best = max(best, left_sum + dp[left][split])
                elif left_sum > right_sum:
                    best = max(best, right_sum + dp[split + 1][right])
                else:
                    best = max(best, left_sum + max(dp[left][split], dp[split + 1][right]))
            dp[left][right] = best
    return dp[0][n - 1]


def stone_game_v_oracle(stone_value: list[int]) -> int:
    @lru_cache(None)
    def solve(left: int, right: int) -> int:
        if left == right:
            return 0
        best = 0
        total = sum(stone_value[left:right + 1])
        for split in range(left, right):
            left_sum = sum(stone_value[left:split + 1])
            right_sum = total - left_sum
            if left_sum < right_sum:
                best = max(best, left_sum + solve(left, split))
            elif left_sum > right_sum:
                best = max(best, right_sum + solve(split + 1, right))
            else:
                best = max(best, left_sum + max(solve(left, split), solve(split + 1, right)))
        return best
    return solve(0, len(stone_value) - 1)


def count_routes_reference(locations: list[int], start: int, finish: int, fuel: int) -> int:
    @lru_cache(None)
    def solve(city: int, remaining: int) -> int:
        total = 1 if city == finish else 0
        for nxt, loc in enumerate(locations):
            if nxt == city:
                continue
            cost = abs(locations[city] - loc)
            if cost <= remaining:
                total = (total + solve(nxt, remaining - cost)) % MOD
        return total
    return solve(start, fuel)


def count_routes_oracle(locations: list[int], start: int, finish: int, fuel: int) -> int:
    return count_routes_reference(locations, start, finish, fuel)


def remove_edges_reference(n: int, edges: list[list[int]]) -> int:
    alice = _Dsu(n)
    bob = _Dsu(n)
    used = 0
    for edge_type, u, v in edges:
        if edge_type == 3:
            merged_a = alice.union(u - 1, v - 1)
            merged_b = bob.union(u - 1, v - 1)
            if merged_a or merged_b:
                used += 1
    for edge_type, u, v in edges:
        if edge_type == 1 and alice.union(u - 1, v - 1):
            used += 1
        elif edge_type == 2 and bob.union(u - 1, v - 1):
            used += 1
    if alice.components != 1 or bob.components != 1:
        return -1
    return len(edges) - used


def remove_edges_oracle(n: int, edges: list[list[int]]) -> int:
    answer = -1
    for mask in range(1 << len(edges)):
        alice = _Dsu(n)
        bob = _Dsu(n)
        kept = 0
        for index, (edge_type, u, v) in enumerate(edges):
            if not mask >> index & 1:
                continue
            kept += 1
            u -= 1
            v -= 1
            if edge_type == 1:
                alice.union(u, v)
            elif edge_type == 2:
                bob.union(u, v)
            else:
                alice.union(u, v)
                bob.union(u, v)
        if alice.components == 1 and bob.components == 1:
            answer = max(answer, len(edges) - kept)
    return answer


def strange_printer_ii_reference(target_grid: list[list[int]]) -> bool:
    colors = sorted({value for row in target_grid for value in row})
    bounds: dict[int, list[int]] = {
        color: [10**9, -1, 10**9, -1] for color in colors
    }
    for r, row in enumerate(target_grid):
        for c, color in enumerate(row):
            top, bottom, left, right = bounds[color]
            bounds[color] = [min(top, r), max(bottom, r), min(left, c), max(right, c)]
    graph = {color: set() for color in colors}
    indegree = {color: 0 for color in colors}
    for color, (top, bottom, left, right) in bounds.items():
        for r in range(top, bottom + 1):
            for c in range(left, right + 1):
                other = target_grid[r][c]
                if other != color and other not in graph[color]:
                    graph[color].add(other)
                    indegree[other] += 1
    queue = deque([color for color in colors if indegree[color] == 0])
    seen = 0
    while queue:
        color = queue.popleft()
        seen += 1
        for other in graph[color]:
            indegree[other] -= 1
            if indegree[other] == 0:
                queue.append(other)
    return seen == len(colors)


def strange_printer_ii_oracle(target_grid: list[list[int]]) -> bool:
    colors = sorted({value for row in target_grid for value in row})
    for order in permutations(colors):
        drawn = [[0] * len(target_grid[0]) for _ in target_grid]
        ok = True
        for color in order:
            cells = [(r, c) for r, row in enumerate(target_grid) for c, value in enumerate(row) if value == color]
            rows = {r for r, _ in cells}
            cols = {c for _, c in cells}
            for r in range(min(rows), max(rows) + 1):
                for c in range(min(cols), max(cols) + 1):
                    drawn[r][c] = color
        if drawn == target_grid:
            return True
    return False


def maximum_requests_reference(n: int, requests: list[list[int]]) -> int:
    answer = 0
    for mask in range(1 << len(requests)):
        delta = [0] * n
        count = 0
        for index, (src, dst) in enumerate(requests):
            if mask >> index & 1:
                delta[src] -= 1
                delta[dst] += 1
                count += 1
        if all(value == 0 for value in delta):
            answer = max(answer, count)
    return answer


def maximum_requests_oracle(n: int, requests: list[list[int]]) -> int:
    return maximum_requests_reference(n, requests)


class _Dsu:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.size = [1] * n
        self.components = n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        if self.size[a] < self.size[b]:
            a, b = b, a
        self.parent[b] = a
        self.size[a] += self.size[b]
        self.components -= 1
        return True


def critical_edges_reference(n: int, edges: list[list[int]]) -> list[list[int]]:
    indexed = sorted((weight, a, b, index) for index, (a, b, weight) in enumerate(edges))

    def mst(skip: int = -1, force: int = -1) -> int | None:
        dsu = _Dsu(n)
        cost = 0
        if force >= 0:
            weight, a, b, _ = indexed[force]
            if dsu.union(a, b):
                cost += weight
        for position, (weight, a, b, _) in enumerate(indexed):
            if position == skip or position == force:
                continue
            if dsu.union(a, b):
                cost += weight
        return cost if dsu.components == 1 else None

    base = mst()
    critical: list[int] = []
    pseudo: list[int] = []
    for position, (_, _, _, original) in enumerate(indexed):
        if mst(skip=position) != base:
            critical.append(original)
        elif mst(force=position) == base:
            pseudo.append(original)
    return [critical, pseudo]


def critical_edges_oracle(n: int, edges: list[list[int]]) -> list[list[int]]:
    best: int | None = None
    trees: list[set[int]] = []
    for chosen in combinations(range(len(edges)), n - 1):
        dsu = _Dsu(n)
        cost = 0
        valid = True
        for index in chosen:
            a, b, weight = edges[index]
            if not dsu.union(a, b):
                valid = False
                break
            cost += weight
        if not valid or dsu.components != 1:
            continue
        if best is None or cost < best:
            best, trees = cost, [set(chosen)]
        elif cost == best:
            trees.append(set(chosen))
    common = set.intersection(*trees)
    any_tree = set.union(*trees)
    return [sorted(common), sorted(any_tree - common)]


def maximize_xor_reference(nums: list[int], queries: list[list[int]]) -> list[int]:
    values = sorted(nums)
    ordered = sorted((limit, value, index) for index, (value, limit) in enumerate(queries))
    root: dict[int, dict] = {}
    answer = [-1] * len(queries)
    cursor = 0
    for limit, value, index in ordered:
        while cursor < len(values) and values[cursor] <= limit:
            node = root
            for bit in range(30, -1, -1):
                digit = values[cursor] >> bit & 1
                node = node.setdefault(digit, {})
            cursor += 1
        if not root:
            continue
        node = root
        result = 0
        for bit in range(30, -1, -1):
            digit = value >> bit & 1
            wanted = digit ^ 1
            if wanted in node:
                result |= 1 << bit
                node = node[wanted]
            else:
                node = node[digit]
        answer[index] = result
    return answer


def maximize_xor_oracle(nums: list[int], queries: list[list[int]]) -> list[int]:
    result = []
    for value, limit in queries:
        eligible = [value ^ item for item in nums if item <= limit]
        result.append(max(eligible, default=-1))
    return result


def recover_array_reference(n: int, sums: list[int]) -> list[int]:
    def recover(current: list[int], remaining: int) -> list[int] | None:
        if remaining == 0:
            return []
        current.sort()
        difference = current[1] - current[0]
        unused = Counter(current)
        lower: list[int] = []
        upper: list[int] = []
        for value in current:
            if unused[value] == 0:
                continue
            unused[value] -= 1
            if unused[value + difference] == 0:
                return None
            unused[value + difference] -= 1
            lower.append(value)
            upper.append(value + difference)
        if 0 in lower:
            tail = recover(lower, remaining - 1)
            if tail is not None:
                return [difference] + tail
        if 0 in upper:
            tail = recover(upper, remaining - 1)
            if tail is not None:
                return [-difference] + tail
        return None

    answer = recover(list(sums), n)
    if answer is None:
        raise ValueError("valid subset sums could not be reconstructed")
    return answer


def subset_sums(values: list[int]) -> list[int]:
    sums = [0]
    for value in values:
        sums += [old + value for old in sums]
    return sorted(sums)


def recover_array_oracle(n: int, sums: list[int]) -> list[int]:
    # This intentionally uses bounded exhaustive search, not the partitioning
    # recurrence used by the efficient reference.
    bound = max(abs(min(sums)), abs(max(sums))) if sums else 0
    for candidate in combinations(range(-bound, bound + 1), n):
        if subset_sums(list(candidate)) == sorted(sums):
            return list(candidate)
    # Repeated values require combinations with replacement.
    def search(prefix: list[int], start: int) -> list[int] | None:
        if len(prefix) == n:
            return prefix if subset_sums(prefix) == sorted(sums) else None
        for value in range(start, bound + 1):
            found = search(prefix + [value], value)
            if found is not None:
                return found
        return None
    answer = search([], -bound)
    if answer is None:
        raise ValueError("oracle bounds contain no valid reconstruction")
    return answer


__all__ = [
    "critical_edges_oracle", "critical_edges_reference", "max_students_oracle",
    "max_students_reference", "maximize_xor_oracle", "maximize_xor_reference",
    "cherry_pickup_oracle", "cherry_pickup_reference",
    "kth_smallest_sum_oracle", "kth_smallest_sum_reference",
    "max_dot_product_oracle", "max_dot_product_reference",
    "max_size_slices_oracle", "max_size_slices_reference",
    "max_pizza_slices_oracle", "max_pizza_slices_reference",
    "pizza_ways_oracle", "pizza_ways_reference",
    "paint_house_oracle", "paint_house_reference",
    "parallel_courses_oracle", "parallel_courses_reference",
    "string_compression_oracle", "string_compression_reference",
    "minimum_days_oracle", "minimum_days_reference",
    "stone_game_v_oracle", "stone_game_v_reference",
    "count_routes_oracle", "count_routes_reference",
    "remove_edges_oracle", "remove_edges_reference",
    "strange_printer_ii_oracle", "strange_printer_ii_reference",
    "maximum_requests_oracle", "maximum_requests_reference",
    "num_of_arrays_oracle", "num_of_arrays_reference",
    "number_of_arrays_oracle", "number_of_arrays_reference",
    "number_ways_hats_oracle", "number_ways_hats_reference",
    "recover_array_oracle", "recover_array_reference", "subset_sums",
]


class Solution:
    def maximumRequests(self, n, requests):
        return len(requests)
