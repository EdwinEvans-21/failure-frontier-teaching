class Solution:

    def constructGrid(self, m: int, n: int, k: int) -> list[str]:
        def feasible() -> bool:
            if k == 1:
                return True
            if k == 2:
                return m >= 2 and n >= 2
            if k == 3:
                return min(m, n) >= 2 and max(m, n) >= 3
            return min(m, n) >= 3 or (
                min(m, n) == 2 and max(m, n) >= 4
            )

        if not feasible():
            return []

        grid = [["#" for _ in range(n)] for _ in range(m)]

        def open_rectangle(height: int, width: int) -> None:
            for row in range(height):
                for column in range(width):
                    grid[row][column] = "."

        if k == 1:
            height, width = 1, 1
            grid[0][0] = "."
        elif k == 2:
            height, width = 2, 2
            open_rectangle(height, width)
        elif k == 3:
            height, width = (2, 3) if n >= 3 else (3, 2)
            open_rectangle(height, width)
        elif min(m, n) == 2:
            height, width = (2, 4) if n >= 4 else (4, 2)
            open_rectangle(height, width)
        else:
            height, width = 3, 3
            open_rectangle(height, width)
            grid[0][2] = "#"
            grid[2][0] = "#"

        endpoint_row = height - 1
        endpoint_column = width - 1
        for column in range(endpoint_column, n):
            grid[endpoint_row][column] = "."
        for row in range(endpoint_row, m):
            grid[row][n - 1] = "."
        return ["".join(row) for row in grid]
