from __future__ import annotations

from copy import deepcopy
import itertools
import random
from typing import Any

from .catalog import PROBLEMS

GENERATOR_VERSION = "oracle_hardened_generator_v3_1"


def _case(number: int, args: list[Any], case_id: str) -> dict[str, Any]:
    expected = PROBLEMS[number].oracle(*deepcopy(args))
    return {"case_id": case_id, "args": args, "expected": expected, "layer": "oracle_differential"}


def _graphs(rng: random.Random, directed: bool, one_indexed: bool = False) -> tuple[int, list[list[int]]]:
    n = rng.randint(3 if directed else 2, 7)
    off = 1 if one_indexed else 0
    edges: list[list[int]] = []
    for v in range(1, n):
        u = rng.randrange(v)
        edges.append([u + off, v + off, rng.randint(1, 9)])
        if directed and rng.random() < .35:
            edges[-1][0], edges[-1][1] = edges[-1][1], edges[-1][0]
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < .22 and not any({e[0]-off, e[1]-off} == {u, v} for e in edges):
                a, b = u + off, v + off
                if directed and rng.random() < .5:
                    a, b = b, a
                edges.append([a, b, rng.randint(1, 9)])
    return n, edges


def _expr(rng: random.Random, leaves: int) -> str:
    if leaves == 1:
        return rng.choice("01")
    left = rng.randint(1, leaves - 1)
    a, b = _expr(rng, left), _expr(rng, leaves-left)
    text = a + rng.choice("&|") + b
    return f"({text})" if rng.random() < .75 else text


def generate_cases(number: int, random_count: int = 220) -> list[dict[str, Any]]:
    if number not in PROBLEMS:
        raise KeyError(number)
    rng = random.Random(PROBLEMS[number].seed)
    args_list: list[list[Any]] = []
    if number == 1611:
        args_list = [[n] for n in range(256)] + [[(1 << b) + d] for b in range(1, 20) for d in (-1, 0, 1)]
    elif number in {1786, 3123}:
        for _ in range(random_count):
            n, edges = _graphs(rng, False, number == 1786)
            args_list.append([n, edges])
    elif number == 2203:
        for _ in range(random_count):
            n, edges = _graphs(rng, True)
            nodes = rng.sample(range(n), 3)
            args_list.append([n, edges, *nodes])
    elif number == 1851:
        args_list.extend([[[[1, 10], [3, 3], [3, 8]], [1, 3, 8, 10]], [[[2, 2], [2, 2]], [2, 1]]])
        for _ in range(random_count):
            intervals = []
            for __ in range(rng.randint(1, 7)):
                a, b = sorted((rng.randint(1, 9), rng.randint(1, 9)))
                intervals.append([a, b])
            args_list.append([intervals, [rng.randint(1, 9) for __ in range(rng.randint(1, 8))]])
    elif number == 1896:
        args_list += [[x] for x in ("0", "1", "1&1&1", "0|0|0", "(((1&0)|1)&0)", "(0&0)&(0&0&0)", "((0&0)|(0&0))", "1|(0&1)")]
        args_list += [[_expr(rng, rng.randint(2, 6))] for _ in range(random_count)]
    elif number == 2071:
        args_list += [[ [5], [0], 1, 5], [[3,3,3], [2,2,2], 2, 1], [[1,2,8], [0,3,7], 1, 5]]
        for _ in range(random_count):
            nt, nw = rng.randint(1, 6), rng.randint(1, 6)
            args_list.append([[rng.randint(0, 10) for __ in range(nt)], [rng.randint(0, 10) for __ in range(nw)], rng.randint(0, nw), rng.randint(0, 7)])
    elif number == 2478:
        args_list += [["2", 1, 1], ["21", 1, 2], ["235421", 2, 3], ["111111", 2, 2]]
        for _ in range(random_count):
            n = rng.randint(1, 10)
            args_list.append(["".join(rng.choice("1234567890") for __ in range(n)), rng.randint(1, n), rng.randint(1, n)])
    elif number == 2809:
        args_list += [[[], [], 0]] if False else []
        for _ in range(random_count):
            n = rng.randint(1, 7)
            a, b = [rng.randint(0, 8) for __ in range(n)], [rng.randint(0, 8) for __ in range(n)]
            args_list.append([a, b, rng.randint(0, sum(a) + n * sum(b) + 5)])
    elif number == 2940:
        args_list += [[[5], [[0, 0]]], [[3,3,4], [[0,1],[1,0],[0,2]]]]
        for _ in range(random_count):
            n = rng.randint(1, 9)
            qs = [[rng.randrange(n), rng.randrange(n)] for __ in range(rng.randint(1, 12))]
            args_list.append([[rng.randint(1, 9) for __ in range(n)], qs])
    elif number == 2945:
        args_list += [[[1]], [[5,2,2]], [[1,1,1,1]], [[8,1,1,1,7,1]]]
        for _ in range(random_count):
            args_list.append([[rng.randint(1, 9) for __ in range(rng.randint(1, 9))]])
    elif number in {3022, 3077}:
        for _ in range(random_count):
            n = rng.randint(1, 8)
            if number == 3022:
                args_list.append([[rng.randint(0, 31) for __ in range(n)], rng.randrange(n)])
            else:
                choices = [k for k in range(1, n + 1, 2)]
                args_list.append([[rng.randint(-9, 9) for __ in range(n)], rng.choice(choices)])
    elif number == 3045:
        args_list += [[['a','a','aa','aaa']], [['ab','aba','ab']]]
        for _ in range(random_count):
            words = ["".join(rng.choice("ab") for ___ in range(rng.randint(1, 6))) for __ in range(rng.randint(1, 7))]
            args_list.append([words])
    elif number == 3102:
        args_list += [[[[0,0],[0,0],[0,0]]], [[[0,0],[10,0],[0,10],[1,1]]]]
        for _ in range(random_count):
            args_list.append([[[rng.randint(-7, 7), rng.randint(-7, 7)] for __ in range(rng.randint(3, 8))]])
    elif number == 3117:
        args_list += [[ [1], [1]], [[7,7,3], [7,3]], [[7,3,3], [3,3]], [[1,2,3],[0]], [[0,0],[0,0]]]
        for _ in range(random_count * 2):
            n = rng.randint(1, 8)
            nums = [rng.randint(0, 15) for __ in range(n)]
            m = rng.randint(1, min(4, n))
            if rng.random() < .65:
                cuts = sorted(rng.sample(range(1, n), m-1)) if m > 1 else []
                targets=[]; start=0
                for end in cuts+[n]:
                    value=nums[start]
                    for x in nums[start+1:end]: value &= x
                    targets.append(value); start=end
            else:
                targets=[rng.randint(0,15) for __ in range(m)]
            args_list.append([nums, targets])
    else:
        raise AssertionError(number)
    unique: dict[str, list[Any]] = {}
    import json
    for args in args_list:
        unique.setdefault(json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":")), args)
    return [_case(number, args, f"lc{number}-small-{i:04d}") for i, args in enumerate(unique.values())]


def stress_cases(number: int) -> list[dict[str, Any]]:
    if number == 1611: args = [10**9]
    elif number == 1786:
        n=20000; args=[n, [[i,i+1,1] for i in range(1,n)]]
    elif number == 1851:
        n=50000; args=[[[i, n+i] for i in range(n)], list(range(n))]
    elif number == 1896: args=["("*20000 + "1" + "&1)"*20000]
    elif number == 2071:
        n=50000; args=[list(range(n)), list(range(n)), n//2, n//3]
    elif number == 2203:
        n=30000; args=[n, [[i,i+1,1] for i in range(n-1)] + [[0,n-1,10**5],[1,n-1,10**5]], 0,1,n-1]
    elif number == 2478: args=["21"*500, 100, 2]
    elif number == 2809:
        n=1000; args=[[i%1001 for i in range(n)], [(i*17)%1001 for i in range(n)], 250000]
    elif number == 2940:
        n=50000; args=[[i%97 for i in range(n)], [[i,n-1-i] for i in range(n//2)]]
    elif number == 2945: args=[[100000-(i%1000) for i in range(100000)]]
    elif number == 3022: args=[[((i*2654435761)&((1<<30)-1)) for i in range(100000)], 50000]
    elif number == 3045: args=[["a"*500 for _ in range(1000)]]
    elif number == 3077: args=[[(-1 if i%2 else 1)*100000 for i in range(10000)], 99]
    elif number == 3102: args=[[[i, -i if i%2 else i] for i in range(100000)]]
    elif number == 3117: args=[[65535-(i%16) for i in range(10000)], [0]*10]
    elif number == 3123:
        n=30000; args=[n, [[i,i+1,1] for i in range(n-1)] + [[0,n-1,50000]]]
    else: raise KeyError(number)
    expected = PROBLEMS[number].reference(*deepcopy(args))
    return [{"case_id": f"lc{number}-stress-0001", "args": args, "expected": expected, "layer": "complexity_stress"}]
