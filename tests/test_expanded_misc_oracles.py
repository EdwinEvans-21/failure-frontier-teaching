from __future__ import annotations
import random, unittest
from ffjudge.oracles.expanded_misc import *

class ExpandedMiscOracleTests(unittest.TestCase):
    def test_random_differential(self):
        r=random.Random(7001)
        for _ in range(250):
            n=r.randint(1,7);tasks=[r.randrange(10) for _ in range(n)];workers=[r.randrange(10) for _ in range(r.randint(1,7))];p=r.randrange(len(workers)+1);s=r.randrange(6)
            self.assertEqual(max_task_assign_reference(tasks,workers,p,s),max_task_assign_bruteforce(tasks,workers,p,s))
        for _ in range(500):
            intervals=[]
            for _ in range(r.randint(1,10)):a=r.randint(1,15);b=r.randint(a,18);intervals.append([a,b])
            q=[r.randint(1,18) for _ in range(10)];self.assertEqual(min_interval_reference(intervals,q),min_interval_bruteforce(intervals,q))
        for _ in range(500):
            h=[r.randint(1,15) for _ in range(r.randint(1,12))];q=[[r.randrange(len(h)),r.randrange(len(h))] for _ in range(20)];self.assertEqual(leftmost_building_reference(h,q),leftmost_building_bruteforce(h,q))
        for _ in range(500):
            a=[r.randint(1,15) for _ in range(r.randint(3,12))];self.assertEqual(result_array_reference(a),result_array_bruteforce(a))
        for _ in range(300):
            a=[r.randint(1,12) for _ in range(r.randint(1,7))];self.assertEqual(minimum_replacement_reference(a),minimum_replacement_bruteforce(a))
        for _ in range(500):
            p=[[r.randint(1,20),r.randint(1,20)] for _ in range(r.randint(3,9))];self.assertEqual(minimum_manhattan_reference(p),minimum_manhattan_bruteforce(p))
        for _ in range(300):
            coins=r.sample(range(1,16),r.randint(1,6));k=r.randint(1,80);self.assertEqual(kth_amount_reference(coins,k),kth_amount_bruteforce(coins,k))

    def test_bits_strings_differential(self):
        for n in range(128):self.assertEqual(minimum_one_bit_reference(n),minimum_one_bit_bruteforce(n))
        r=random.Random(7002)
        for n in range(1,9):
            for _ in range(100):
                a=[r.randrange(2) for _ in range(n)];k=r.randint(1,n);self.assertEqual(min_k_flips_reference(a,k),min_k_flips_bruteforce(a,k))
                b=[r.randrange(32) for _ in range(n)];merges=r.randrange(n);self.assertEqual(min_or_reference(b,merges),min_or_bruteforce(b,merges))
        for _ in range(500):
            words=[''.join(r.choice('abc') for _ in range(r.randint(1,7))) for _ in range(r.randint(1,15))];self.assertEqual(prefix_suffix_reference(words),prefix_suffix_bruteforce(words))
        specials=['10','1100','1010','111000','110100','101100']
        for s in specials:self.assertEqual(largest_special_reference(s),largest_special_bruteforce(s))
        expressions=['0','1','1&0','1|0','(1&0)|1','1&(0|1)','(0|0)&(1|0)','1|0&0']
        for expression in expressions:self.assertEqual(expression_flip_reference(expression),expression_flip_bruteforce(expression))

if __name__=='__main__':unittest.main()
