class Solution:
    def minInterval(self, intervals, queries):
        order = sorted(range(len(queries)), key=queries.__getitem__)
        parent = list(range(len(order) + 1))
        ans = [-1] * len(queries)
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for left, right in sorted(intervals, key=lambda p: p[1] - p[0]):
            lo, hi = 0, len(order)
            while lo < hi:
                mid = (lo + hi) // 2
                if queries[order[mid]] < left: lo = mid + 1
                else: hi = mid
            pos = find(lo)
            while pos < len(order) and queries[order[pos]] <= right:
                ans[order[pos]] = right - left + 1
                parent[pos] = find(pos + 1)
                pos = find(pos)
        return ans
