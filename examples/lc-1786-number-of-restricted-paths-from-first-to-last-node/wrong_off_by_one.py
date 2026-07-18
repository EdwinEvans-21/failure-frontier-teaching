from __future__ import annotations

from collections import defaultdict, deque
from heapq import heappop, heappush
from math import inf


MOD = 1_000_000_007


class DSU:
    def __init__(self, n: int) -> None:
        self.p = list(range(n))
        self.s = [1] * n

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> int:
        a, b = self.find(a), self.find(b)
        if a == b:
            return a
        if self.s[a] < self.s[b]:
            a, b = b, a
        self.p[b] = a
        self.s[a] += self.s[b]
        return a


def _dijkstra(n: int, graph: list[list[tuple[int, int]]], source: int) -> list[int]:
    dist = [10**30] * n
    dist[source] = 0
    heap = [(0, source)]
    while heap:
        d, u = heappop(heap)
        if d != dist[u]:
            continue
        for v, w in graph[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heappush(heap, (nd, v))
    return dist


def find_answer_reference(n: int, edges: list[list[int]]) -> list[bool]:
    graph = [[] for _ in range(n)]
    for u, v, w in edges:
        graph[u].append((v, w))
        graph[v].append((u, w))
    left = _dijkstra(n, graph, 0)
    right = _dijkstra(n, graph, n - 1)
    best = left[n - 1]
    return [
        left[u] + w + right[v] == best or
        left[v] + w + right[u] == best
        for u, v, w in edges
    ]


def find_answer_bruteforce(n: int, edges: list[list[int]]) -> list[bool]:
    dist = [[inf] * n for _ in range(n)]
    for i in range(n):
        dist[i][i] = 0
    for u, v, w in edges:
        dist[u][v] = dist[v][u] = min(dist[u][v], w)
    for k in range(n):
        for i in range(n):
            for j in range(n):
                dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j])
    best = dist[0][n - 1]
    if best == inf:
        return [False] * len(edges)
    return [
        dist[0][u] + w + dist[v][n - 1] == best or
        dist[0][v] + w + dist[u][n - 1] == best
        for u, v, w in edges
    ]


def minimum_cost_walk_reference(n: int, edges: list[list[int]],
                                query: list[list[int]]) -> list[int]:
    dsu = DSU(n)
    for u, v, _ in edges:
        dsu.union(u, v)
    values: dict[int, int] = {}
    for u, _, w in edges:
        root = dsu.find(u)
        values[root] = values.get(root, w) & w
    return [values.get(dsu.find(s), 0) if dsu.find(s) == dsu.find(t) else -1
            for s, t in query]


def minimum_cost_walk_bruteforce(n: int, edges: list[list[int]],
                                 query: list[list[int]]) -> list[int]:
    graph = [[] for _ in range(n)]
    for u, v, w in edges:
        graph[u].append((v, w)); graph[v].append((u, w))
    out = []
    for s, t in query:
        seen = {s}; queue = deque([s]); nodes = []
        while queue:
            u = queue.popleft(); nodes.append(u)
            for v, _ in graph[u]:
                if v not in seen:
                    seen.add(v); queue.append(v)
        if t not in seen:
            out.append(-1); continue
        value = None
        for u in nodes:
            for v, w in graph[u]:
                if v in seen:
                    value = w if value is None else value & w
        out.append(0 if value is None else value)
    return out


def number_of_good_paths_reference(vals: list[int], edges: list[list[int]]) -> int:
    n = len(vals); graph = [[] for _ in range(n)]
    for u, v in edges:
        graph[u].append(v); graph[v].append(u)
    groups: dict[int, list[int]] = defaultdict(list)
    for i, value in enumerate(vals): groups[value].append(i)
    dsu = DSU(n); active = [False] * n; answer = n
    for value in sorted(groups):
        for u in groups[value]:
            active[u] = True
            for v in graph[u]:
                if active[v]: dsu.union(u, v)
        counts: dict[int, int] = defaultdict(int)
        for u in groups[value]: counts[dsu.find(u)] += 1
        answer += sum(c * (c - 1) // 2 for c in counts.values())
    return answer


def number_of_good_paths_bruteforce(vals: list[int], edges: list[list[int]]) -> int:
    n = len(vals); graph = [[] for _ in range(n)]
    for u, v in edges: graph[u].append(v); graph[v].append(u)
    answer = n
    for s in range(n):
        parent = [-1] * n; parent[s] = s; queue = deque([s])
        while queue:
            u = queue.popleft()
            for v in graph[u]:
                if parent[v] < 0: parent[v] = u; queue.append(v)
        for t in range(s + 1, n):
            if vals[s] != vals[t]: continue
            u = t; maximum = vals[u]
            while u != s: maximum = max(maximum, vals[u]); u = parent[u]
            if maximum <= vals[s]: answer += 1
    return answer


def distance_limited_reference(n: int, edge_list: list[list[int]],
                               queries: list[list[int]]) -> list[bool]:
    order = sorted(range(len(queries)), key=lambda i: queries[i][2])
    edges = sorted(edge_list, key=lambda e: e[2]); dsu = DSU(n); j = 0
    answer = [False] * len(queries)
    for i in order:
        p, q, limit = queries[i]
        while j < len(edges) and edges[j][2] < limit:
            dsu.union(edges[j][0], edges[j][1]); j += 1
        answer[i] = dsu.find(p) == dsu.find(q)
    return answer


def distance_limited_bruteforce(n: int, edge_list: list[list[int]],
                                queries: list[list[int]]) -> list[bool]:
    out = []
    for source, target, limit in queries:
        graph = [[] for _ in range(n)]
        for u, v, w in edge_list:
            if w < limit: graph[u].append(v); graph[v].append(u)
        seen = {source}; queue = deque([source])
        while queue:
            u = queue.popleft()
            for v in graph[u]:
                if v not in seen: seen.add(v); queue.append(v)
        out.append(target in seen)
    return out


def count_restricted_paths_reference(n: int, edges: list[list[int]]) -> int:
    graph = [[] for _ in range(n)]
    for a, b, w in edges:
        a -= 1; b -= 1; graph[a].append((b, w)); graph[b].append((a, w))
    dist = _dijkstra(n, graph, n - 1); ways = [0] * n; ways[n - 1] = 1
    for u in sorted(range(n), key=dist.__getitem__):
        for v, _ in graph[u]:
            if dist[v] > dist[u]: ways[v] = (ways[v] + ways[u]) % MOD
    return ways[0]


def count_restricted_paths_bruteforce(n: int, edges: list[list[int]]) -> int:
    graph = [[] for _ in range(n)]
    for a, b, w in edges:
        a -= 1; b -= 1; graph[a].append((b, w)); graph[b].append((a, w))
    dist = _dijkstra(n, graph, n - 1)
    def dfs(u: int) -> int:
        if u == n - 1: return 1
        return sum(dfs(v) for v, _ in graph[u] if dist[v] < dist[u])
    return dfs(0) % MOD


def latest_day_reference(row: int, col: int, cells: list[list[int]]) -> int:
    total = row * col; top = total; bottom = total + 1; dsu = DSU(total + 2)
    land = [[False] * col for _ in range(row)]
    for day in range(total - 1, -1, -1):
        r, c = cells[day][0] - 1, cells[day][1] - 1; land[r][c] = True
        node = r * col + c
        if r == 0: dsu.union(node, top)
        if r == row - 1: dsu.union(node, bottom)
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < row and 0 <= nc < col and land[nr][nc]:
                dsu.union(node, nr * col + nc)
        if dsu.find(top) == dsu.find(bottom): return day
    return 0


def latest_day_bruteforce(row: int, col: int, cells: list[list[int]]) -> int:
    def possible(day: int) -> bool:
        water = {tuple(cell) for cell in cells[:day]}; queue = deque()
        seen = set()
        for c in range(1, col + 1):
            if (1, c) not in water: queue.append((1, c)); seen.add((1, c))
        while queue:
            r, c = queue.popleft()
            if r == row: return True
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (r + dr, c + dc)
                if 1 <= nxt[0] <= row and 1 <= nxt[1] <= col and nxt not in water and nxt not in seen:
                    seen.add(nxt); queue.append(nxt)
        return False
    return max(day for day in range(row * col + 1) if possible(day))


def min_grid_cost_reference(grid: list[list[int]]) -> int:
    m, n = len(grid), len(grid[0]); dist = [[10**9] * n for _ in range(m)]
    dist[0][0] = 0; queue = deque([(0, 0)]); dirs = ((0, 1), (0, -1), (1, 0), (-1, 0))
    while queue:
        r, c = queue.popleft()
        for i, (dr, dc) in enumerate(dirs, 1):
            nr, nc = r + dr, c + dc
            if 0 <= nr < m and 0 <= nc < n:
                nd = dist[r][c] + (grid[r][c] != i)
                if nd < dist[nr][nc]:
                    dist[nr][nc] = nd
                    (queue.appendleft if grid[r][c] == i else queue.append)((nr, nc))
    return dist[-1][-1]


def min_grid_cost_bruteforce(grid: list[list[int]]) -> int:
    m, n = len(grid), len(grid[0]); graph = [[] for _ in range(m * n)]
    dirs = ((0, 1), (0, -1), (1, 0), (-1, 0))
    for r in range(m):
        for c in range(n):
            for i, (dr, dc) in enumerate(dirs, 1):
                nr, nc = r + dr, c + dc
                if 0 <= nr < m and 0 <= nc < n:
                    graph[r*n+c].append((nr*n+nc, int(grid[r][c] != i)))
    return _dijkstra(m*n, graph, 0)[-1]


def minimum_weight_reference(n: int, edges: list[list[int]], src1: int,
                             src2: int, dest: int) -> int:
    graph = [[] for _ in range(n)]; reverse = [[] for _ in range(n)]
    for u, v, w in edges: graph[u].append((v, w)); reverse[v].append((u, w))
    a = _dijkstra(n, graph, src1); b = _dijkstra(n, graph, src2)
    c = _dijkstra(n, reverse, dest); answer = min(a[i] + b[i] + c[i] for i in range(n))
    return -1 if answer >= 10**30 else answer


def minimum_weight_bruteforce(n: int, edges: list[list[int]], src1: int,
                              src2: int, dest: int) -> int:
    dist = [[inf] * n for _ in range(n)]
    for i in range(n): dist[i][i] = 0
    for u, v, w in edges: dist[u][v] = min(dist[u][v], w)
    for k in range(n):
        for i in range(n):
            for j in range(n): dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j])
    answer = min(dist[src1][i] + dist[src2][i] + dist[i][dest] for i in range(n))
    return -1 if answer == inf else int(answer)


class Solution:
    def countRestrictedPaths(self, n, edges):
        answer = count_restricted_paths_reference(n, edges)
        return [not x if isinstance(x, bool) else x + 1 for x in answer] if isinstance(answer, list) else (answer[::-1] if isinstance(answer, str) else answer + 1)
