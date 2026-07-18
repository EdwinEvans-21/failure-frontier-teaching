from __future__ import annotations

import itertools
import random
import unittest

from ffjudge.oracles.expanded_graph import (
    count_restricted_paths_bruteforce,
    count_restricted_paths_reference,
    distance_limited_bruteforce,
    distance_limited_reference,
    find_answer_bruteforce,
    find_answer_reference,
    latest_day_bruteforce,
    latest_day_reference,
    min_grid_cost_bruteforce,
    min_grid_cost_reference,
    minimum_cost_walk_bruteforce,
    minimum_cost_walk_reference,
    minimum_weight_bruteforce,
    minimum_weight_reference,
    number_of_good_paths_bruteforce,
    number_of_good_paths_reference,
)


class ExpandedGraphOracleTests(unittest.TestCase):
    def test_3123_random_differential(self) -> None:
        rng = random.Random(3123)
        for n in range(2, 8):
            pairs = list(itertools.combinations(range(n), 2))
            for _ in range(80):
                rng.shuffle(pairs); chosen = pairs[:rng.randint(1, len(pairs))]
                edges = [[u, v, rng.randint(1, 12)] for u, v in chosen]
                self.assertEqual(find_answer_reference(n, edges),
                                 find_answer_bruteforce(n, edges))

    def test_3108_random_differential(self) -> None:
        rng = random.Random(3108)
        for n in range(2, 9):
            for _ in range(100):
                edges = [[rng.randrange(n), rng.randrange(n), rng.randrange(32)]
                         for _ in range(rng.randrange(15))]
                edges = [e for e in edges if e[0] != e[1]]
                queries = [[a, b] for a in range(n) for b in range(n) if a != b]
                self.assertEqual(minimum_cost_walk_reference(n, edges, queries),
                                 minimum_cost_walk_bruteforce(n, edges, queries))

    def test_2421_random_tree_differential(self) -> None:
        rng = random.Random(2421)
        for n in range(1, 10):
            for _ in range(100):
                vals = [rng.randrange(5) for _ in range(n)]
                edges = [[i, rng.randrange(i)] for i in range(1, n)]
                self.assertEqual(number_of_good_paths_reference(vals, edges),
                                 number_of_good_paths_bruteforce(vals, edges))

    def test_1697_random_differential(self) -> None:
        rng = random.Random(1697)
        for n in range(2, 9):
            for _ in range(100):
                edges = []
                for _ in range(rng.randrange(18)):
                    a, b = rng.sample(range(n), 2)
                    edges.append([a, b, rng.randint(1, 12)])
                queries = [[*rng.sample(range(n), 2), rng.randint(1, 14)]
                           for _ in range(20)]
                self.assertEqual(distance_limited_reference(n, edges, queries),
                                 distance_limited_bruteforce(n, edges, queries))

    def test_1786_random_connected_graph_differential(self) -> None:
        rng = random.Random(1786)
        for n in range(2, 9):
            for _ in range(80):
                pairs = {(i, rng.randrange(i)) for i in range(1, n)}
                for pair in itertools.combinations(range(n), 2):
                    if rng.random() < .25: pairs.add(pair)
                edges = [[a + 1, b + 1, rng.randint(1, 10)] for a, b in pairs]
                self.assertEqual(count_restricted_paths_reference(n, edges),
                                 count_restricted_paths_bruteforce(n, edges))

    def test_1970_all_small_permutations_sampled(self) -> None:
        rng = random.Random(1970)
        for row, col in ((2, 2), (2, 3), (3, 2), (3, 3)):
            cells = [[r, c] for r in range(1, row + 1)
                     for c in range(1, col + 1)]
            for _ in range(120):
                rng.shuffle(cells); case = [item[:] for item in cells]
                self.assertEqual(latest_day_reference(row, col, case),
                                 latest_day_bruteforce(row, col, case))

    def test_1368_exhaustive_tiny_and_random(self) -> None:
        for values in itertools.product(range(1, 5), repeat=4):
            grid = [list(values[:2]), list(values[2:])]
            self.assertEqual(min_grid_cost_reference(grid),
                             min_grid_cost_bruteforce(grid))
        rng = random.Random(1368)
        for _ in range(300):
            m, n = rng.randint(1, 5), rng.randint(1, 5)
            grid = [[rng.randint(1, 4) for _ in range(n)] for _ in range(m)]
            self.assertEqual(min_grid_cost_reference(grid),
                             min_grid_cost_bruteforce(grid))

    def test_2203_random_directed_graph_differential(self) -> None:
        rng = random.Random(2203)
        for n in range(3, 9):
            for _ in range(100):
                edges = []
                for _ in range(rng.randrange(25)):
                    a, b = rng.sample(range(n), 2)
                    edges.append([a, b, rng.randint(1, 15)])
                src1, src2, dest = rng.sample(range(n), 3)
                self.assertEqual(
                    minimum_weight_reference(n, edges, src1, src2, dest),
                    minimum_weight_bruteforce(n, edges, src1, src2, dest),
                )


if __name__ == "__main__":
    unittest.main()
