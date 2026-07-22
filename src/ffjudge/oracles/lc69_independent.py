"""Independent small-input oracles for the LC69 import.

These functions intentionally use different state spaces or recurrences from the
candidate implementations.  They are used only on bounded differential cases by
the v4 quality gate; production expected values remain host-only test data.
"""

from __future__ import annotations

from collections import deque
from functools import lru_cache
from itertools import combinations, product


MOD = 1_000_000_007
ORACLES: dict[int, object] = {}


def _metadata(algorithm: str, bounds: str, limitations: str) -> dict[str, str]:
    return {
        "oracle_version": "lc69-small-oracle-v1",
        "oracle_algorithm": algorithm,
        "safe_input_bounds": bounds,
        "exhaustive_bounds": bounds,
        "random_bounds": bounds,
        "known_limitations": limitations,
    }


# These are deliberately conservative bounds.  The audit harness must not call
# a small oracle outside its stated domain merely to increase case counts.
ORACLE_METADATA: dict[int, dict[str, str]] = {
    1143: _metadata("all subsequences of shorter input", "min(len(text1), len(text2)) <= 12", "exponential"),
    1155: _metadata("cartesian enumeration of die faces", "n <= 8 and faces <= 8", "exponential"),
    1187: _metadata("explicit value-state expansion", "len(arr1), len(arr2) <= 10", "state growth"),
    1220: _metadata("forward transition simulation", "n <= 500", "not an exhaustive oracle"),
    1235: _metadata("all job subsets", "job count <= 16", "exponential"),
    1240: _metadata("exact cell-cover recursion", "rows, columns <= 5", "exponential"),
    1269: _metadata("memoized path enumeration", "steps <= 20 and arrLen <= 10", "state growth"),
    1278: _metadata("all partition endpoints", "len(s) <= 14", "exponential partitions"),
    1284: _metadata("state-space BFS", "rows * columns <= 12", "2^(rows*columns) states"),
    1293: _metadata("unpruned BFS over position and remaining eliminations", "rows, columns <= 8 and k <= 8", "state growth"),
    1301: _metadata("memoized path enumeration", "board side <= 8", "exponential paths without memoization"),
    1312: _metadata("LCS against reversed string using exhaustive LCS oracle", "len(s) <= 12", "inherits LCS exponential bound"),
    1335: _metadata("all schedule split positions", "job count <= 14", "exponential partitions"),
    1349: _metadata("all available-seat subsets", "available seats <= 16", "exponential"),
    1354: _metadata("forward state-space BFS", "length <= 5 and max(target) <= 40", "state space grows rapidly"),
    1388: _metadata("all non-adjacent index subsets", "len(slices) <= 18", "exponential"),
    1402: _metadata("all value subsets and direct scoring", "len(satisfaction) <= 18", "exponential"),
    1416: _metadata("all valid string partitions", "len(s) <= 20", "partition count growth"),
    1420: _metadata("all arrays", "n <= 7 and m <= 6", "m^n enumeration"),
    1434: _metadata("all person-to-hat assignments", "people <= 7 and hats per person <= 8", "cartesian product"),
    1439: _metadata("all row-choice sums", "rows <= 6 and columns <= 6", "columns^rows"),
    1444: _metadata("all valid cut recursion", "rows, columns <= 8", "recursive branching"),
    1458: _metadata("all equal-length subsequence pairs", "both lengths <= 10", "combinatorial"),
    1463: _metadata("all paired robot paths", "rows <= 8 and columns <= 6", "branching state search"),
    1473: _metadata("all color assignments", "houses <= 9 and colors <= 5", "colors^houses"),
    1494: _metadata("BFS over completed-course subsets", "course count <= 12", "2^n states"),
    1510: _metadata("memoized direct game recurrence", "n <= 500", "not suitable for max n"),
    1526: _metadata("BFS over target-height vectors", "length <= 7 and values <= 5", "state-space growth"),
    1531: _metadata("all deletion subsets plus RLE simulation", "len(s) <= 16", "exponential"),
    1553: _metadata("BFS over remaining oranges", "n <= 5000", "linear state space"),
    1563: _metadata("all split recursion", "length <= 14", "cubic-like memoized state"),
}


def oracle(number: int):
    def register(function):
        ORACLES[number] = function
        return function
    return register


@oracle(1143)
def lcs(text1: str, text2: str) -> int:
    """Enumerate subsequences of the shorter string, rather than reuse DP."""
    if len(text1) > len(text2):
        text1, text2 = text2, text1
    answer = 0
    for mask in range(1 << len(text1)):
        if mask.bit_count() <= answer:
            continue
        wanted = ''.join(text1[i] for i in range(len(text1)) if mask >> i & 1)
        position = 0
        for character in text2:
            if position < len(wanted) and character == wanted[position]:
                position += 1
        if position == len(wanted):
            answer = len(wanted)
    return answer


@oracle(1155)
def dice_rolls(n: int, faces: int, target: int) -> int:
    return sum(1 for values in product(range(1, faces + 1), repeat=n)
               if sum(values) == target) % MOD


@oracle(1187)
def make_array_increasing(arr1: list[int], arr2: list[int]) -> int:
    choices = sorted(set(arr2))
    states = {-(10 ** 30): 0}
    for value in arr1:
        next_states: dict[int, int] = {}
        for previous, changes in states.items():
            for candidate, cost in ((value, changes), *[(x, changes + 1) for x in choices]):
                if candidate > previous:
                    next_states[candidate] = min(next_states.get(candidate, 10 ** 9), cost)
        states = next_states
    return min(states.values(), default=-1)


@oracle(1220)
def vowel_permutations(n: int) -> int:
    allowed = {
        'a': 'e', 'e': 'ai', 'i': 'aeou', 'o': 'iu', 'u': 'a',
    }
    current = {letter: 1 for letter in allowed}
    for _ in range(1, n):
        following = {letter: 0 for letter in allowed}
        for before, count in current.items():
            for after in allowed[before]:
                following[after] += count
        current = following
    return sum(current.values()) % MOD


@oracle(1235)
def job_scheduling(start: list[int], end: list[int], profit: list[int]) -> int:
    jobs = list(zip(start, end, profit))
    answer = 0
    for mask in range(1 << len(jobs)):
        selected = [jobs[index] for index in range(len(jobs)) if mask >> index & 1]
        selected.sort()
        if all(selected[index][1] <= selected[index + 1][0]
               for index in range(len(selected) - 1)):
            answer = max(answer, sum(job[2] for job in selected))
    return answer


@oracle(1240)
def tiling_rectangle(rows: int, columns: int) -> int:
    """Exact cell-cover search; deliberately restricted to small differential inputs."""
    board = 0
    total = rows * columns
    whole = (1 << total) - 1

    @lru_cache(None)
    def solve(covered: int) -> int:
        if covered == whole:
            return 0
        cell = next(index for index in range(total) if not (covered >> index & 1))
        row, column = divmod(cell, columns)
        result = total
        for size in range(1, min(rows - row, columns - column) + 1):
            bits = 0
            for y in range(row, row + size):
                for x in range(column, column + size):
                    bits |= 1 << (y * columns + x)
            if not covered & bits:
                result = min(result, 1 + solve(covered | bits))
        return result

    return solve(board)


@oracle(1269)
def ways_to_stay(steps: int, length: int) -> int:
    @lru_cache(None)
    def visit(position: int, remaining: int) -> int:
        if remaining == 0:
            return int(position == 0)
        return sum(visit(next_position, remaining - 1)
                   for next_position in (position - 1, position, position + 1)
                   if 0 <= next_position < length)
    return visit(0, steps) % MOD


@oracle(1278)
def palindrome_partition(s: str, parts: int) -> int:
    @lru_cache(None)
    def cost(left: int, right: int) -> int:
        return sum(s[left + offset] != s[right - offset]
                   for offset in range((right - left + 1) // 2))

    @lru_cache(None)
    def split(start: int, count: int) -> int:
        if count == 1:
            return cost(start, len(s) - 1)
        return min(cost(start, end) + split(end + 1, count - 1)
                   for end in range(start, len(s) - count + 1))
    return split(0, parts)


@oracle(1284)
def minimum_flips(matrix: list[list[int]]) -> int:
    rows, columns = len(matrix), len(matrix[0])
    start = sum(value << (row * columns + column)
                for row, values in enumerate(matrix)
                for column, value in enumerate(values))
    masks = []
    for row in range(rows):
        for column in range(columns):
            mask = 0
            for y, x in ((row, column), (row - 1, column), (row + 1, column),
                         (row, column - 1), (row, column + 1)):
                if 0 <= y < rows and 0 <= x < columns:
                    mask ^= 1 << (y * columns + x)
            masks.append(mask)
    queue = deque([(start, 0)])
    seen = {start}
    while queue:
        state, distance = queue.popleft()
        if state == 0:
            return distance
        for mask in masks:
            next_state = state ^ mask
            if next_state not in seen:
                seen.add(next_state)
                queue.append((next_state, distance + 1))
    return -1


@oracle(1293)
def shortest_path(grid: list[list[int]], eliminations: int) -> int:
    rows, columns = len(grid), len(grid[0])
    queue = deque([(0, 0, eliminations, 0)])
    seen = {(0, 0, eliminations)}
    while queue:
        row, column, remaining, distance = queue.popleft()
        if (row, column) == (rows - 1, columns - 1):
            return distance
        for next_row, next_column in ((row - 1, column), (row + 1, column),
                                      (row, column - 1), (row, column + 1)):
            if 0 <= next_row < rows and 0 <= next_column < columns:
                next_remaining = remaining - grid[next_row][next_column]
                state = (next_row, next_column, next_remaining)
                if next_remaining >= 0 and state not in seen:
                    seen.add(state)
                    queue.append((*state, distance + 1))
    return -1


@oracle(1301)
def paths_with_max_score(board: list[str]) -> list[int]:
    size = len(board)

    @lru_cache(None)
    def visit(row: int, column: int) -> tuple[int, int]:
        if not (0 <= row < size and 0 <= column < size) or board[row][column] == 'X':
            return (-10 ** 9, 0)
        if (row, column) == (size - 1, size - 1):
            return (0, 1)
        branches = [visit(row + 1, column), visit(row, column + 1),
                    visit(row + 1, column + 1)]
        best = max(value for value, _ in branches)
        if best < 0:
            return (-10 ** 9, 0)
        ways = sum(count for value, count in branches if value == best) % MOD
        return (best + (0 if board[row][column] == 'E' else int(board[row][column])), ways)

    score, count = visit(0, 0)
    return [score if count else 0, count]


@oracle(1312)
def min_insertions(s: str) -> int:
    return len(s) - lcs(s, s[::-1])


@oracle(1335)
def min_difficulty(jobs: list[int], days: int) -> int:
    @lru_cache(None)
    def schedule(start: int, remaining_days: int) -> int:
        if len(jobs) - start < remaining_days:
            return 10 ** 12
        if remaining_days == 1:
            return max(jobs[start:])
        difficulty = 0
        best = 10 ** 12
        for stop in range(start, len(jobs) - remaining_days + 1):
            difficulty = max(difficulty, jobs[stop])
            best = min(best, difficulty + schedule(stop + 1, remaining_days - 1))
        return best
    answer = schedule(0, days)
    return -1 if answer >= 10 ** 12 else answer


@oracle(1349)
def max_students(seats: list[list[str]]) -> int:
    available = [(row, column) for row, values in enumerate(seats)
                 for column, value in enumerate(values) if value == '.']
    answer = 0
    for mask in range(1 << len(available)):
        if mask.bit_count() <= answer:
            continue
        chosen = {available[index] for index in range(len(available)) if mask >> index & 1}
        if all((row, column + 1) not in chosen and (row + 1, column - 1) not in chosen
               and (row + 1, column + 1) not in chosen
               for row, column in chosen):
            answer = mask.bit_count()
    return answer


@oracle(1354)
def construct_target(target: list[int]) -> bool:
    """Forward BFS from [1, ..., 1], retained for genuinely small targets only."""
    wanted = tuple(target)
    start = (1,) * len(target)
    if wanted == start:
        return True
    queue = deque([start])
    seen = {start}
    cap = max(target)
    while queue:
        state = queue.popleft()
        total = sum(state)
        for index in range(len(state)):
            next_state = list(state)
            next_state[index] = total
            frozen = tuple(next_state)
            if frozen == wanted:
                return True
            if max(frozen) <= cap and frozen not in seen:
                seen.add(frozen)
                queue.append(frozen)
    return False


@oracle(1388)
def pizza_slices(slices: list[int]) -> int:
    size = len(slices)
    picks = size // 3
    answer = 0
    for chosen in combinations(range(size), picks):
        selected = set(chosen)
        if all((index + 1) % size not in selected for index in selected):
            answer = max(answer, sum(slices[index] for index in selected))
    return answer


@oracle(1402)
def reducing_dishes(values: list[int]) -> int:
    answer = 0
    for count in range(len(values) + 1):
        for chosen in combinations(values, count):
            answer = max(answer, sum(index * value for index, value in enumerate(sorted(chosen), 1)))
    return answer


@oracle(1416)
def restore_array(s: str, bound: int) -> int:
    @lru_cache(None)
    def count(index: int) -> int:
        if index == len(s):
            return 1
        if s[index] == '0':
            return 0
        total = 0
        for end in range(index + 1, len(s) + 1):
            if int(s[index:end]) > bound:
                break
            total += count(end)
        return total
    return count(0) % MOD


@oracle(1420)
def arrays_with_cost(length: int, maximum: int, comparisons: int) -> int:
    return sum(1 for values in product(range(1, maximum + 1), repeat=length)
               if sum(value > max(values[:index], default=0)
                      for index, value in enumerate(values)) == comparisons) % MOD


@oracle(1434)
def hat_assignments(hats: list[list[int]]) -> int:
    return sum(1 for assignment in product(*hats) if len(set(assignment)) == len(assignment)) % MOD


@oracle(1439)
def kth_matrix_sum(matrix: list[list[int]], k: int) -> int:
    return sorted(map(sum, product(*matrix)))[k - 1]


@oracle(1444)
def cut_pizza(pizza: list[str], cuts: int) -> int:
    rows, columns = len(pizza), len(pizza[0])

    @lru_cache(None)
    def apples(top: int, left: int) -> int:
        return sum(pizza[row][column] == 'A' for row in range(top, rows)
                   for column in range(left, columns))

    @lru_cache(None)
    def divide(top: int, left: int, pieces: int) -> int:
        if not apples(top, left):
            return 0
        if pieces == 1:
            return 1
        total = 0
        for row in range(top + 1, rows):
            if apples(top, left) > apples(row, left):
                total += divide(row, left, pieces - 1)
        for column in range(left + 1, columns):
            if apples(top, left) > apples(top, column):
                total += divide(top, column, pieces - 1)
        return total % MOD
    return divide(0, 0, cuts)


@oracle(1458)
def max_dot_product(first: list[int], second: list[int]) -> int:
    answer = -10 ** 18
    for count in range(1, min(len(first), len(second)) + 1):
        for left in combinations(range(len(first)), count):
            for right in combinations(range(len(second)), count):
                answer = max(answer, sum(first[a] * second[b] for a, b in zip(left, right)))
    return answer


@oracle(1463)
def cherry_pickup(grid: list[list[int]]) -> int:
    rows, columns = len(grid), len(grid[0])

    @lru_cache(None)
    def collect(row: int, first: int, second: int) -> int:
        gained = grid[row][first] + (grid[row][second] if first != second else 0)
        if row == rows - 1:
            return gained
        return gained + max(collect(row + 1, next_first, next_second)
                            for next_first in range(max(0, first - 1), min(columns, first + 2))
                            for next_second in range(max(0, second - 1), min(columns, second + 2)))
    return collect(0, 0, columns - 1)


@oracle(1473)
def paint_houses(houses: list[int], costs: list[list[int]], rows: int, colors: int,
                target: int) -> int:
    choices = [([house] if house else list(range(1, colors + 1))) for house in houses]
    answer = 10 ** 15
    for assignment in product(*choices):
        neighborhoods = 1 + sum(assignment[index] != assignment[index - 1]
                                for index in range(1, rows))
        if neighborhoods == target:
            answer = min(answer, sum(0 if houses[index] else costs[index][color - 1]
                                     for index, color in enumerate(assignment)))
    return -1 if answer == 10 ** 15 else answer


@oracle(1494)
def parallel_courses(course_count: int, relations: list[list[int]], limit: int) -> int:
    prerequisite = [0] * course_count
    for before, after in relations:
        prerequisite[after - 1] |= 1 << (before - 1)
    complete = (1 << course_count) - 1
    queue = deque([(0, 0)])
    seen = {0}
    while queue:
        taken, semesters = queue.popleft()
        if taken == complete:
            return semesters
        available = [index for index in range(course_count)
                     if not (taken >> index & 1)
                     and prerequisite[index] & taken == prerequisite[index]]
        count = min(limit, len(available))
        for selected in combinations(available, count):
            next_taken = taken | sum(1 << index for index in selected)
            if next_taken not in seen:
                seen.add(next_taken)
                queue.append((next_taken, semesters + 1))
    return -1


@oracle(1510)
def stone_game_four(n: int) -> bool:
    @lru_cache(None)
    def winning(remaining: int) -> bool:
        return any(not winning(remaining - square * square)
                   for square in range(1, int(remaining ** .5) + 1))
    return winning(n)


@oracle(1526)
def minimum_subarray_increments(target: list[int]) -> int:
    """BFS on height vectors; bounded only to tiny differential inputs."""
    wanted = tuple(target)
    queue = deque([((0,) * len(target), 0)])
    seen = {(0,) * len(target)}
    while queue:
        state, steps = queue.popleft()
        if state == wanted:
            return steps
        for left in range(len(target)):
            for right in range(left, len(target)):
                next_state = list(state)
                for index in range(left, right + 1):
                    next_state[index] += 1
                frozen = tuple(next_state)
                if all(frozen[index] <= wanted[index] for index in range(len(target))) and frozen not in seen:
                    seen.add(frozen)
                    queue.append((frozen, steps + 1))
    raise AssertionError("target is always reachable")


@oracle(1531)
def string_compression(s: str, deletions: int) -> int:
    def encoded_length(value: str) -> int:
        length = 0
        index = 0
        while index < len(value):
            end = index
            while end < len(value) and value[end] == value[index]:
                end += 1
            count = end - index
            length += 1 + (len(str(count)) if count > 1 else 0)
            index = end
        return length
    return min(encoded_length(''.join(s[index] for index in range(len(s)) if index not in removed))
               for count in range(deletions + 1)
               for removed in combinations(range(len(s)), count))


@oracle(1553)
def eat_oranges(n: int) -> int:
    queue = deque([(n, 0)])
    seen = {n}
    while queue:
        remaining, days = queue.popleft()
        if remaining == 0:
            return days
        for next_remaining in ({remaining - 1}
                               | ({remaining // 2} if remaining % 2 == 0 else set())
                               | ({remaining // 3} if remaining % 3 == 0 else set())):
            if next_remaining not in seen:
                seen.add(next_remaining)
                queue.append((next_remaining, days + 1))
    raise AssertionError("unreachable")


@oracle(1563)
def stone_game_five(values: list[int]) -> int:
    prefix = [0]
    for value in values:
        prefix.append(prefix[-1] + value)

    @lru_cache(None)
    def play(left: int, right: int) -> int:
        if left == right:
            return 0
        answer = 0
        for middle in range(left, right):
            first = prefix[middle + 1] - prefix[left]
            second = prefix[right + 1] - prefix[middle + 1]
            if first <= second:
                answer = max(answer, first + play(left, middle))
            if second <= first:
                answer = max(answer, second + play(middle + 1, right))
        return answer
    return play(0, len(values) - 1)


@oracle(1575)
def count_routes(locations: list[int], start: int, finish: int, fuel: int) -> int:
    @lru_cache(None)
    def walk(place: int, remaining: int) -> int:
        return (int(place == finish) + sum(walk(next_place, remaining - abs(locations[place] - locations[next_place]))
                                            for next_place in range(len(locations)) if next_place != place
                                            and abs(locations[place] - locations[next_place]) <= remaining)) % MOD
    return walk(start, fuel)


@oracle(1579)
def removable_edges(nodes: int, edges: list[list[int]]) -> int:
    def connected(selected: list[list[int]], allowed: set[int]) -> bool:
        graph = [[] for _ in range(nodes)]
        for kind, left, right in selected:
            if kind in allowed:
                graph[left - 1].append(right - 1)
                graph[right - 1].append(left - 1)
        seen = {0}
        queue = deque([0])
        while queue:
            vertex = queue.popleft()
            for neighbour in graph[vertex]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
        return len(seen) == nodes
    best = -1
    for mask in range(1 << len(edges)):
        kept = [edge for index, edge in enumerate(edges) if mask >> index & 1]
        if len(kept) > best and connected(kept, {1, 3}) and connected(kept, {2, 3}):
            best = len(kept)
    return -1 if best < 0 else len(edges) - best


@oracle(1591)
def strange_printer(grid: list[list[int]]) -> bool:
    colors = sorted({color for row in grid for color in row})
    rows, columns = len(grid), len(grid[0])
    boxes = {}
    for color in colors:
        positions = [(row, column) for row in range(rows) for column in range(columns)
                     if grid[row][column] == color]
        boxes[color] = (min(row for row, _ in positions), max(row for row, _ in positions),
                        min(column for _, column in positions), max(column for _, column in positions))
    for order in __import__('itertools').permutations(colors):
        canvas = [[0] * columns for _ in range(rows)]
        for color in order:
            top, bottom, left, right = boxes[color]
            for row in range(top, bottom + 1):
                for column in range(left, right + 1):
                    canvas[row][column] = color
        if canvas == grid:
            return True
    return False


@oracle(1601)
def transfer_requests(nodes: int, requests: list[list[int]]) -> int:
    answer = 0
    for mask in range(1 << len(requests)):
        if mask.bit_count() <= answer:
            continue
        balance = [0] * nodes
        for index, (source, destination) in enumerate(requests):
            if mask >> index & 1:
                balance[source] -= 1
                balance[destination] += 1
        if not any(balance):
            answer = mask.bit_count()
    return answer


@oracle(1632)
def matrix_rank(matrix: list[list[int]]) -> list[list[int]]:
    rows, columns = len(matrix), len(matrix[0])
    answer = [[0] * columns for _ in range(rows)]
    # Relax the defining strict-order constraints until ranks stabilize.
    changed = True
    while changed:
        changed = False
        for row in range(rows):
            for column in range(columns):
                lower = [answer[row][other] for other in range(columns) if matrix[row][other] < matrix[row][column]]
                lower += [answer[other][column] for other in range(rows) if matrix[other][column] < matrix[row][column]]
                needed = 1 + max(lower, default=0)
                if needed > answer[row][column]:
                    answer[row][column] = needed
                    changed = True
        for row in range(rows):
            for column in range(columns):
                for other in range(columns):
                    if matrix[row][other] == matrix[row][column] and answer[row][other] != answer[row][column]:
                        value = max(answer[row][other], answer[row][column])
                        answer[row][other] = answer[row][column] = value
                        changed = True
                for other in range(rows):
                    if matrix[other][column] == matrix[row][column] and answer[other][column] != answer[row][column]:
                        value = max(answer[other][column], answer[row][column])
                        answer[other][column] = answer[row][column] = value
                        changed = True
    return answer


@oracle(1639)
def form_target(words: list[str], target: str) -> int:
    answer = 0
    for columns in combinations(range(len(words[0])), len(target)):
        ways = 1
        for character, column in zip(target, columns):
            ways *= sum(word[column] == character for word in words)
        answer += ways
    return answer % MOD


@oracle(1659)
def grid_happiness(rows: int, columns: int, introverts: int, extroverts: int) -> int:
    def pair(left: int, right: int) -> int:
        if not left or not right:
            return 0
        return -60 if left == right == 1 else 40 if left == right == 2 else -10
    answer = 0
    for layout in product(range(3), repeat=rows * columns):
        if layout.count(1) > introverts or layout.count(2) > extroverts:
            continue
        value = 120 * layout.count(1) + 40 * layout.count(2)
        for row in range(rows):
            for column in range(columns):
                index = row * columns + column
                if row:
                    value += pair(layout[index], layout[index - columns])
                if column:
                    value += pair(layout[index], layout[index - 1])
        answer = max(answer, value)
    return answer


@oracle(1671)
def mountain_removals(nums: list[int]) -> int:
    best = 0
    for mask in range(1 << len(nums)):
        values = [nums[index] for index in range(len(nums)) if mask >> index & 1]
        for peak in range(1, len(values) - 1):
            if all(values[index] < values[index + 1] for index in range(peak)) and all(values[index] > values[index + 1] for index in range(peak, len(values) - 1)):
                best = max(best, len(values))
                break
    return len(nums) - best


@oracle(1675)
def minimum_deviation(nums: list[int]) -> int:
    choices = []
    for value in nums:
        values = {value * 2} if value % 2 else {value}
        while max(values) % 2 == 0:
            values.add(max(values) // 2)
        choices.append(sorted(values))
    return min(max(values) - min(values) for values in product(*choices))


@oracle(1681)
def incompatibility(nums: list[int], groups: int) -> int:
    size = len(nums) // groups
    if max(nums.count(value) for value in nums) > groups:
        return -1
    @lru_cache(None)
    def split(remaining: tuple[int, ...]) -> int:
        if not remaining:
            return 0
        first = remaining[0]
        answer = 10 ** 9
        for rest in combinations(remaining[1:], size - 1):
            subset = (first,) + rest
            values = [nums[index] for index in subset]
            if len(set(values)) != size:
                continue
            next_remaining = tuple(index for index in remaining if index not in subset)
            answer = min(answer, max(values) - min(values) + split(next_remaining))
        return answer
    answer = split(tuple(range(len(nums))))
    return -1 if answer >= 10 ** 9 else answer


@oracle(1691)
def stack_cuboids(cuboids: list[list[int]]) -> int:
    blocks = [tuple(sorted(block)) for block in cuboids]
    @lru_cache(None)
    def stack(last: tuple[int, int, int], remaining: tuple[int, ...]) -> int:
        best = 0
        for index in remaining:
            block = blocks[index]
            if all(block[axis] <= last[axis] for axis in range(3)):
                best = max(best, block[2] + stack(block, tuple(other for other in remaining if other != index)))
        return best
    return stack((10 ** 9, 10 ** 9, 10 ** 9), tuple(range(len(blocks))))


@oracle(1707)
def maximum_xor(nums: list[int], queries: list[list[int]]) -> list[int]:
    return [max((value ^ query for value in nums if value <= bound), default=-1)
            for query, bound in queries]


ORACLE_METADATA.update({
    1575: _metadata("direct path recursion", "locations <= 8 and fuel <= 18", "route count growth"),
    1579: _metadata("all retained-edge subsets plus connectivity", "edges <= 14", "exponential"),
    1591: _metadata("all print-color orders and canvas simulation", "colors <= 7 and grid <= 5x5", "factorial colors"),
    1601: _metadata("all request subsets", "requests <= 16", "exponential"),
    1632: _metadata("constraint-relaxation simulation", "matrix <= 5x5", "slow fixed-point iteration"),
    1639: _metadata("all increasing column choices", "column count <= 12", "combinatorial"),
    1659: _metadata("all ternary cell layouts", "cells <= 10", "3^cells"),
    1671: _metadata("all subsequences and direct mountain check", "length <= 16", "exponential"),
    1675: _metadata("all per-value legal halving choices", "length <= 10 and values <= 1000", "cartesian product"),
    1681: _metadata("all canonical partitions", "length <= 10", "exponential"),
    1691: _metadata("all stack orders", "cuboid count <= 9", "exponential"),
    1707: _metadata("direct eligible-value scan per query", "nums, queries <= 100", "quadratic"),
})


@oracle(1959)
def resize_waste(nums: list[int], changes: int) -> int:
    @lru_cache(None)
    def partition(start: int, groups_left: int) -> int:
        if start == len(nums):
            return 0
        if groups_left == 0:
            return 10 ** 12
        maximum = 0
        total = 0
        answer = 10 ** 12
        for end in range(start, len(nums)):
            maximum = max(maximum, nums[end])
            total += nums[end]
            answer = min(answer, maximum * (end - start + 1) - total + partition(end + 1, groups_left - 1))
        return answer
    return partition(0, changes + 1)


@oracle(1977)
def split_non_decreasing(num: str) -> int:
    if num.startswith('0'):
        return 0
    @lru_cache(None)
    def split(start: int, previous: str) -> int:
        if start == len(num):
            return 1
        total = 0
        for end in range(start + 1, len(num) + 1):
            current = num[start:end]
            if current.startswith('0'):
                break
            if len(current) > len(previous) or len(current) == len(previous) and current >= previous:
                total += split(end, current)
        return total
    return split(0, '') % MOD


@oracle(1987)
def unique_good_subsequences(binary: str) -> int:
    values = {''.join(binary[index] for index in range(len(binary)) if mask >> index & 1)
              for mask in range(1, 1 << len(binary))}
    return sum(value == '0' or value.startswith('1') for value in values) % MOD


@oracle(1994)
def good_subsets(nums: list[int]) -> int:
    primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)
    answer = 0
    for mask in range(1, 1 << len(nums)):
        product_value = 1
        for index, value in enumerate(nums):
            if mask >> index & 1:
                product_value *= value
        valid = product_value > 1
        for prime in primes:
            if product_value % (prime * prime) == 0:
                valid = False
                break
        answer += valid
    return answer % MOD


@oracle(2009)
def continuous_operations(nums: list[int]) -> int:
    size = len(nums)
    unique = sorted(set(nums))
    keep = 0
    for left, value in enumerate(unique):
        keep = max(keep, sum(candidate <= value + size - 1 for candidate in unique[left:]))
    return size - keep


@oracle(2045)
def second_minimum_time(nodes: int, edges: list[list[int]], travel: int, change: int) -> int:
    graph = [[] for _ in range(nodes + 1)]
    for left, right in edges:
        graph[left].append(right)
        graph[right].append(left)
    arrivals = [[] for _ in range(nodes + 1)]
    queue = [(0, 1)]
    from heapq import heappop, heappush
    while queue:
        time, node = heappop(queue)
        if arrivals[node] and arrivals[node][-1] == time:
            continue
        if len(arrivals[node]) == 2:
            continue
        arrivals[node].append(time)
        if node == nodes and len(arrivals[node]) == 2:
            return time
        depart = time if (time // change) % 2 == 0 else (time // change + 1) * change
        for neighbour in graph[node]:
            heappush(queue, (depart + travel, neighbour))
    raise AssertionError("connected graph has a second route")


@oracle(2060)
def encoded_strings_equal(first: str, second: str) -> bool:
    """Breadth-first search over literal positions and unmatched wildcard length."""
    queue = deque([(0, 0, 0)])
    seen = {(0, 0, 0)}
    while queue:
        left, right, difference = queue.popleft()
        if left == len(first) and right == len(second) and difference == 0:
            return True
        transitions = []
        if left < len(first) and first[left].isdigit():
            value = 0
            for end in range(left, min(len(first), left + 3)):
                if not first[end].isdigit():
                    break
                value = value * 10 + int(first[end])
                transitions.append((end + 1, right, difference + value))
        if right < len(second) and second[right].isdigit():
            value = 0
            for end in range(right, min(len(second), right + 3)):
                if not second[end].isdigit():
                    break
                value = value * 10 + int(second[end])
                transitions.append((left, end + 1, difference - value))
        if difference > 0 and right < len(second) and second[right].isalpha():
            transitions.append((left, right + 1, difference - 1))
        if difference < 0 and left < len(first) and first[left].isalpha():
            transitions.append((left + 1, right, difference + 1))
        if difference == 0 and left < len(first) and right < len(second) and first[left].isalpha() and first[left] == second[right]:
            transitions.append((left + 1, right + 1, 0))
        for state in transitions:
            if state not in seen:
                seen.add(state)
                queue.append(state)
    return False


@oracle(2092)
def people_with_secret(nodes: int, meetings: list[list[int]], first_person: int) -> list[int]:
    known = {0, first_person}
    for time in sorted({meeting[2] for meeting in meetings}):
        same_time = [(left, right) for left, right, meeting_time in meetings if meeting_time == time]
        changed = True
        while changed:
            changed = False
            for left, right in same_time:
                if left in known and right not in known:
                    known.add(right); changed = True
                if right in known and left not in known:
                    known.add(left); changed = True
    return sorted(known)


@oracle(2106)
def harvest_fruits(fruits: list[list[int]], start: int, steps: int) -> int:
    answer = 0
    for left in range(len(fruits)):
        total = 0
        for right in range(left, len(fruits)):
            total += fruits[right][1]
            low, high = fruits[left][0], fruits[right][0]
            distance = min(abs(start - low) + high - low, abs(start - high) + high - low)
            if distance <= steps:
                answer = max(answer, total)
    return answer


@oracle(2127)
def invitations(favorite: list[int]) -> int:
    people = range(len(favorite))
    for count in range(len(favorite), 1, -1):
        for selected in combinations(people, count):
            for arrangement in __import__('itertools').permutations(selected):
                positions = {person: index for index, person in enumerate(arrangement)}
                if all(favorite[person] in (arrangement[(index - 1) % count], arrangement[(index + 1) % count])
                       for index, person in enumerate(arrangement)):
                    return count
    return 0


@oracle(2147)
def divide_corridor(corridor: str) -> int:
    seats = [index for index, value in enumerate(corridor) if value == 'S']
    if not seats or len(seats) % 2:
        return 0
    answer = 1
    for index in range(2, len(seats), 2):
        answer *= seats[index] - seats[index - 1]
    return answer % MOD


@oracle(2163)
def three_part_difference(nums: list[int]) -> int:
    size = len(nums) // 3
    answer = 10 ** 18
    for retained in combinations(range(len(nums)), 2 * size):
        answer = min(answer, sum(nums[index] for index in retained[:size]) - sum(nums[index] for index in retained[size:]))
    return answer


ORACLE_METADATA.update({
    1959: _metadata("all resize partition endpoints", "length <= 14", "exponential partitions"),
    1977: _metadata("all decimal partitions with direct comparison", "length <= 18", "exponential partitions"),
    1987: _metadata("all subsequences deduplicated as strings", "length <= 18", "exponential"),
    1994: _metadata("all index subsets with prime-square test", "length <= 18", "exponential"),
    2009: _metadata("all candidate kept-value intervals", "length <= 80", "quadratic"),
    2045: _metadata("priority-ordered explicit arrival simulation", "nodes <= 30 and edges <= 80", "not max-constraint suitable"),
    2060: _metadata("state-space BFS over unmatched wildcard length", "encoded lengths <= 12", "state growth"),
    2092: _metadata("fixed-point same-time meeting simulation", "nodes <= 30 and meetings <= 80", "quadratic time groups"),
    2106: _metadata("all contiguous fruit intervals", "fruit count <= 100", "quadratic"),
    2127: _metadata("all invited subsets and circular arrangements", "people <= 9", "factorial"),
    2147: _metadata("direct seat-gap multiplication", "length <= 500", "not an exhaustive oracle"),
    2163: _metadata("all retained 2n index sets", "n <= 6", "combinatorial"),
})


@oracle(1723)
def finish_jobs(jobs: list[int], workers: int) -> int:
    return min(max(sum(jobs[index] for index, owner in enumerate(assignment) if owner == worker)
                   for worker in range(workers))
               for assignment in product(range(workers), repeat=len(jobs)))


@oracle(1735)
def fill_array(queries: list[list[int]]) -> list[int]:
    def count(length: int, product_value: int) -> int:
        @lru_cache(None)
        def distribute(position: int, remaining: int) -> int:
            if position == length:
                return int(remaining == 1)
            return sum(distribute(position + 1, remaining // factor)
                       for factor in range(1, remaining + 1) if remaining % factor == 0)
        return distribute(0, product_value)
    return [count(length, product_value) % MOD for length, product_value in queries]


@oracle(1751)
def attend_events(events: list[list[int]], limit: int) -> int:
    answer = 0
    for mask in range(1 << len(events)):
        if mask.bit_count() > limit:
            continue
        selected = sorted(events[index] for index in range(len(events)) if mask >> index & 1)
        if all(selected[index][1] < selected[index + 1][0] for index in range(len(selected) - 1)):
            answer = max(answer, sum(event[2] for event in selected))
    return answer


@oracle(1771)
def cross_word_palindrome(first: str, second: str) -> int:
    left = [''.join(first[index] for index in range(len(first)) if mask >> index & 1)
            for mask in range(1, 1 << len(first))]
    right = [''.join(second[index] for index in range(len(second)) if mask >> index & 1)
             for mask in range(1, 1 << len(second))]
    return max((len(a + b) for a in left for b in right if a + b == (a + b)[::-1]), default=0)


@oracle(1782)
def count_node_pairs(nodes: int, edges: list[list[int]], queries: list[int]) -> list[int]:
    degree = [0] * (nodes + 1)
    multiplicity: dict[tuple[int, int], int] = {}
    for left, right in edges:
        degree[left] += 1
        degree[right] += 1
        key = tuple(sorted((left, right)))
        multiplicity[key] = multiplicity.get(key, 0) + 1
    return [sum(degree[left] + degree[right] - multiplicity.get((left, right), 0) > query
                for left in range(1, nodes + 1) for right in range(left + 1, nodes + 1))
            for query in queries]


@oracle(1799)
def maximize_gcd_score(nums: list[int]) -> int:
    from math import gcd
    @lru_cache(None)
    def pair(remaining: tuple[int, ...], operation: int) -> int:
        if not remaining:
            return 0
        return max(operation * gcd(nums[first], nums[second]) + pair(
            tuple(index for index in remaining if index not in (first, second)), operation + 1)
            for first, second in combinations(remaining, 2))
    return pair(tuple(range(len(nums))), 1)


@oracle(1815)
def fresh_donuts(batch_size: int, groups: list[int]) -> int:
    return max(sum((sum(order[:index]) % batch_size) == 0 for index in range(len(order)))
               for order in __import__('itertools').permutations(groups))


@oracle(1830)
def string_sort_operations(s: str) -> int:
    return sorted(set(__import__('itertools').permutations(s))).index(tuple(s)) % MOD


@oracle(1857)
def largest_color_path(colors: str, edges: list[list[int]]) -> int:
    graph = [[] for _ in colors]
    for left, right in edges:
        graph[left].append(right)
    visiting, visited = set(), set()
    answer = 0
    def visit(node: int, counts: tuple[int, ...]) -> None:
        nonlocal answer
        if node in visiting:
            raise ValueError("cycle")
        next_counts = list(counts)
        next_counts[ord(colors[node]) - 97] += 1
        answer = max(answer, max(next_counts))
        visiting.add(node)
        for neighbour in graph[node]:
            visit(neighbour, tuple(next_counts))
        visiting.remove(node)
        visited.add(node)
    try:
        for node in range(len(colors)):
            visit(node, (0,) * 26)
    except ValueError:
        return -1
    return answer


@oracle(1866)
def visible_sticks(count: int, visible: int) -> int:
    return sum(sum(value > max(order[:index], default=0) for index, value in enumerate(order)) == visible
               for order in __import__('itertools').permutations(range(1, count + 1))) % MOD


@oracle(1872)
def stone_game_eight(stones: list[int]) -> int:
    prefix = []
    total = 0
    for stone in stones:
        total += stone
        prefix.append(total)

    @lru_cache(None)
    def play(last_merged: int) -> int:
        if last_merged == len(stones) - 1:
            return 0
        return max(prefix[next_merged] - play(next_merged)
                   for next_merged in range(last_merged + 1, len(stones)))
    # Index zero represents the first stone already included; the opening move
    # must include at least one additional stone.
    return play(0)


@oracle(1889)
def packaging_waste(packages: list[int], boxes: list[list[int]]) -> int:
    best = 10 ** 18
    for supplier in boxes:
        if max(supplier) < max(packages):
            continue
        best = min(best, sum(min(box for box in supplier if box >= package) - package
                             for package in packages))
    return -1 if best == 10 ** 18 else best % MOD


@oracle(1916)
def build_rooms(previous: list[int]) -> int:
    count = 0
    for order in __import__('itertools').permutations(range(1, len(previous))):
        position = {0: 0, **{room: index + 1 for index, room in enumerate(order)}}
        if all(position[previous[room]] < position[room] for room in range(1, len(previous))):
            count += 1
    return count % MOD


@oracle(1931)
def color_grid(rows: int, columns: int) -> int:
    answer = 0
    for layout in product(range(3), repeat=rows * columns):
        if all((not row or layout[row * columns + column] != layout[(row - 1) * columns + column])
               and (not column or layout[row * columns + column] != layout[row * columns + column - 1])
               for row in range(rows) for column in range(columns)):
            answer += 1
    return answer % MOD


ORACLE_METADATA.update({
    1723: _metadata("all job-to-worker assignments", "jobs <= 10 and workers <= 5", "workers^jobs"),
    1735: _metadata("ordered factor tuple enumeration", "length <= 7 and product <= 200", "divisor recursion"),
    1751: _metadata("all event subsets", "events <= 16", "exponential"),
    1771: _metadata("all nonempty subsequences of both words", "both lengths <= 10", "quadratic subsets"),
    1782: _metadata("direct pair counting with multiplicities", "nodes <= 80 and edges <= 200", "quadratic nodes"),
    1799: _metadata("all perfect pairings", "length <= 12", "factorial matching count"),
    1815: _metadata("all group permutations", "groups <= 9", "factorial"),
    1830: _metadata("all distinct multiset permutations", "length <= 9", "factorial"),
    1857: _metadata("explicit path DFS with cycle detection", "nodes <= 12", "path explosion"),
    1866: _metadata("all stick permutations", "n <= 9", "factorial"),
    1872: _metadata("direct minimax move tree", "stone count <= 15", "quadratic memoized states"),
    1889: _metadata("direct smallest-fitting-box simulation", "packages <= 100 and boxes <= 10x20", "quadratic"),
    1916: _metadata("all room construction orders", "rooms <= 9", "factorial"),
    1931: _metadata("all 3-color cell assignments", "cells <= 10", "3^cells"),
})
