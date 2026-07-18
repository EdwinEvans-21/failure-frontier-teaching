from __future__ import annotations

import random
import unittest

from ffjudge.oracles.expanded_dp import (
    beautiful_partitions_bruteforce, beautiful_partitions_reference,
    count_integers_bruteforce, count_integers_reference,
    max_balanced_sum_bruteforce, max_balanced_sum_reference,
    maximum_nondecreasing_length_bruteforce, maximum_nondecreasing_length_reference,
    maximum_strength_bruteforce, maximum_strength_reference,
    minimum_cut_cost_bruteforce, minimum_cut_cost_reference,
    minimum_difference_bruteforce, minimum_difference_reference,
    minimum_finish_time_bruteforce, minimum_finish_time_reference,
    minimum_time_bruteforce, minimum_time_reference,
    minimum_value_sum_bruteforce, minimum_value_sum_reference,
)


class ExpandedDpOracleTests(unittest.TestCase):
    def test_3117_random_differential(self) -> None:
        rng = random.Random(3117)
        for n in range(1, 9):
            for _ in range(250):
                nums = [rng.randint(1, 31) for _ in range(n)]
                m = rng.randint(1, min(n, 4)); targets = [rng.randint(0, 31) for _ in range(m)]
                self.assertEqual(minimum_value_sum_reference(nums, targets), minimum_value_sum_bruteforce(nums, targets))

    def test_3077_random_differential(self) -> None:
        rng = random.Random(3077)
        for n in range(1, 9):
            for _ in range(120):
                nums = [rng.randint(-8, 8) for _ in range(n)]; k = rng.choice([x for x in range(1, n + 1, 2)])
                self.assertEqual(maximum_strength_reference(nums, k), maximum_strength_bruteforce(nums, k))

    def test_2188_random_differential(self) -> None:
        rng = random.Random(2188)
        for laps in range(1, 8):
            for _ in range(100):
                tires = [[rng.randint(1, 8), rng.randint(2, 5)] for _ in range(rng.randint(1, 4))]; change = rng.randint(1, 8)
                self.assertEqual(minimum_finish_time_reference(tires, change, laps), minimum_finish_time_bruteforce(tires, change, laps))

    def test_2809_random_differential(self) -> None:
        rng = random.Random(2809)
        for n in range(1, 8):
            for _ in range(100):
                a = [rng.randint(1, 8) for _ in range(n)]; b = [rng.randint(0, 5) for _ in range(n)]; x = rng.randint(0, 60)
                self.assertEqual(minimum_time_reference(a, b, x), minimum_time_bruteforce(a, b, x))

    def test_2478_random_differential(self) -> None:
        rng = random.Random(2478)
        for n in range(1, 11):
            for _ in range(150):
                s = ''.join(str(rng.randint(1, 9)) for _ in range(n)); k = rng.randint(1, min(4, n)); length = rng.randint(1, n)
                self.assertEqual(beautiful_partitions_reference(s, k, length), beautiful_partitions_bruteforce(s, k, length))

    def test_2719_random_differential(self) -> None:
        rng = random.Random(2719)
        for _ in range(1000):
            low = rng.randint(1, 500); high = rng.randint(low, 1000); minimum = rng.randint(1, 20); maximum = rng.randint(minimum, 30)
            self.assertEqual(count_integers_reference(str(low), str(high), minimum, maximum), count_integers_bruteforce(str(low), str(high), minimum, maximum))

    def test_2945_random_differential(self) -> None:
        rng = random.Random(2945)
        for n in range(1, 11):
            for _ in range(500):
                nums = [rng.randint(1, 10) for _ in range(n)]
                self.assertEqual(maximum_nondecreasing_length_reference(nums), maximum_nondecreasing_length_bruteforce(nums))

    def test_2926_random_differential(self) -> None:
        rng = random.Random(2926)
        for n in range(1, 12):
            for _ in range(250):
                nums = [rng.randint(-12, 12) for _ in range(n)]
                self.assertEqual(max_balanced_sum_reference(nums), max_balanced_sum_bruteforce(nums))

    def test_2035_random_differential(self) -> None:
        rng = random.Random(2035)
        for half in range(1, 8):
            for _ in range(100):
                nums = [rng.randint(-20, 20) for _ in range(2 * half)]
                self.assertEqual(minimum_difference_reference(nums), minimum_difference_bruteforce(nums))

    def test_1547_random_differential(self) -> None:
        rng = random.Random(1547)
        for n in range(2, 15):
            for _ in range(100):
                population = list(range(1, n)); rng.shuffle(population); cuts = population[:rng.randint(0, min(6, n - 1))]
                self.assertEqual(minimum_cut_cost_reference(n, cuts), minimum_cut_cost_bruteforce(n, cuts))


if __name__ == '__main__': unittest.main()
