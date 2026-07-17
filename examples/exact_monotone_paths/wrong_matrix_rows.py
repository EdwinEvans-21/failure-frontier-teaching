class Solution:

    def constructGrid(self, m: int, n: int, k: int) -> list[list[str]]:
        return [["." for _ in range(n)] for _ in range(m)]
