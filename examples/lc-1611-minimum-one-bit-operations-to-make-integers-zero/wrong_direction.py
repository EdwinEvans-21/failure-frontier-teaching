from __future__ import annotations

from bisect import bisect_left
from collections import deque
from functools import lru_cache
from heapq import heappop, heappush
from itertools import combinations
from math import gcd, inf


def max_task_assign_reference(tasks: list[int], workers: list[int], pills: int,
                              strength: int) -> int:
    tasks = sorted(tasks); workers = sorted(workers)
    def possible(count: int) -> bool:
        available = deque(); j = 0; remaining = pills
        for worker in workers[-count:]:
            while j < count and tasks[j] <= worker + strength:
                available.append(tasks[j]); j += 1
            if not available: return False
            if available[0] <= worker: available.popleft()
            elif remaining: remaining -= 1; available.pop()
            else: return False
        return True
    low, high = 0, min(len(tasks), len(workers))
    while low < high:
        mid = (low + high + 1) // 2
        if possible(mid): low = mid
        else: high = mid - 1
    return low


def max_task_assign_bruteforce(tasks: list[int], workers: list[int], pills: int,
                               strength: int) -> int:
    n, m = len(tasks), len(workers)
    @lru_cache(None)
    def solve(mask_t: int, mask_w: int, left: int) -> int:
        best = 0
        for i in range(n):
            if mask_t >> i & 1: continue
            for j in range(m):
                if mask_w >> j & 1: continue
                if workers[j] >= tasks[i]:
                    best = max(best, 1 + solve(mask_t | 1 << i, mask_w | 1 << j, left))
                elif left and workers[j] + strength >= tasks[i]:
                    best = max(best, 1 + solve(mask_t | 1 << i, mask_w | 1 << j, left - 1))
        return best
    return solve(0, 0, pills)


def min_interval_reference(intervals: list[list[int]], queries: list[int]) -> list[int]:
    intervals = sorted(intervals); order = sorted(range(len(queries)), key=queries.__getitem__)
    heap = []; answer = [-1] * len(queries); j = 0
    for index in order:
        q = queries[index]
        while j < len(intervals) and intervals[j][0] <= q:
            left, right = intervals[j]; heappush(heap, (right - left + 1, right)); j += 1
        while heap and heap[0][1] < q: heappop(heap)
        if heap: answer[index] = heap[0][0]
    return answer


def min_interval_bruteforce(intervals: list[list[int]], queries: list[int]) -> list[int]:
    return [min((r - l + 1 for l, r in intervals if l <= q <= r), default=-1) for q in queries]


def leftmost_building_reference(heights: list[int], queries: list[list[int]]) -> list[int]:
    n = len(heights); tree = [0] * (4 * n)
    def build(node: int, left: int, right: int) -> None:
        if left == right: tree[node] = heights[left]; return
        mid = (left + right) // 2; build(node*2,left,mid); build(node*2+1,mid+1,right); tree[node]=max(tree[node*2],tree[node*2+1])
    def first(node: int, left: int, right: int, start: int, threshold: int) -> int:
        if right < start or tree[node] <= threshold: return -1
        if left == right: return left
        mid=(left+right)//2; result=first(node*2,left,mid,start,threshold)
        return result if result >= 0 else first(node*2+1,mid+1,right,start,threshold)
    build(1,0,n-1); answer=[]
    for a,b in queries:
        if a>b:a,b=b,a
        if a==b or heights[a] < heights[b]: answer.append(b)
        else: answer.append(first(1,0,n-1,b+1,heights[a]))
    return answer


def leftmost_building_bruteforce(heights: list[int], queries: list[list[int]]) -> list[int]:
    out=[]
    for a,b in queries:
        if a==b: out.append(a); continue
        out.append(next((i for i in range(max(a,b),len(heights)) if (i==a or heights[i]>heights[a]) and (i==b or heights[i]>heights[b])), -1))
    return out


class Fenwick:
    def __init__(self,n:int)->None:self.t=[0]*(n+1)
    def add(self,i:int,v:int)->None:
        while i<len(self.t):self.t[i]+=v;i+=i&-i
    def sum(self,i:int)->int:
        s=0
        while i:s+=self.t[i];i-=i&-i
        return s


def result_array_reference(nums: list[int]) -> list[int]:
    keys=sorted(set(nums)); a=[nums[0]];b=[nums[1]];fa=Fenwick(len(keys));fb=Fenwick(len(keys));fa.add(bisect_left(keys,nums[0])+1,1);fb.add(bisect_left(keys,nums[1])+1,1)
    for x in nums[2:]:
        p=bisect_left(keys,x)+1;ga=len(a)-fa.sum(p);gb=len(b)-fb.sum(p)
        if ga>gb or ga==gb and len(a)<=len(b):a.append(x);fa.add(p,1)
        else:b.append(x);fb.add(p,1)
    return a+b


def result_array_bruteforce(nums: list[int]) -> list[int]:
    a=[nums[0]];b=[nums[1]]
    for x in nums[2:]:
        ga=sum(y>x for y in a);gb=sum(y>x for y in b)
        (a if ga>gb or ga==gb and len(a)<=len(b) else b).append(x)
    return a+b


def minimum_replacement_reference(nums: list[int]) -> int:
    bound=nums[-1];answer=0
    for value in reversed(nums[:-1]):
        parts=(value+bound-1)//bound;answer+=parts-1;bound=value//parts
    return answer


def minimum_replacement_bruteforce(nums: list[int]) -> int:
    @lru_cache(None)
    def solve(index:int,bound:int)->int:
        if index<0:return 0
        value=nums[index];best=inf
        for parts in range(1,value+1):
            if (value+parts-1)//parts<=bound:best=min(best,parts-1+solve(index-1,value//parts))
        return best
    return solve(len(nums)-2,nums[-1])


def minimum_manhattan_reference(points: list[list[int]]) -> int:
    transforms=[sorted((x+y,i) for i,(x,y) in enumerate(points)),sorted((x-y,i) for i,(x,y) in enumerate(points))];answer=inf
    for removed in range(len(points)):
        worst=0
        for values in transforms:
            lo=values[1][0] if values[0][1]==removed else values[0][0];hi=values[-2][0] if values[-1][1]==removed else values[-1][0];worst=max(worst,hi-lo)
        answer=min(answer,worst)
    return answer


def minimum_manhattan_bruteforce(points: list[list[int]]) -> int:
    return min(max((abs(points[i][0]-points[j][0])+abs(points[i][1]-points[j][1]) for i in range(len(points)) for j in range(i) if i!=r and j!=r),default=0) for r in range(len(points)))


def kth_amount_reference(coins: list[int], k: int) -> int:
    coins=sorted(c for c in coins if not any(c%d==0 for d in coins if d<c))
    def count(x:int)->int:
        total=0
        for mask in range(1,1<<len(coins)):
            multiple=1
            for i,c in enumerate(coins):
                if mask>>i&1:multiple=multiple//gcd(multiple,c)*c
            total += (1 if mask.bit_count()&1 else -1)*(x//multiple)
        return total
    low,high=1,min(coins)*k
    while low<high:
        mid=(low+high)//2
        if count(mid)>=k:high=mid
        else:low=mid+1
    return low


def kth_amount_bruteforce(coins: list[int], k: int) -> int:
    found=[];x=1
    while len(found)<k:
        if any(x%c==0 for c in coins):found.append(x)
        x+=1
    return found[-1]


def minimum_one_bit_reference(n: int) -> int:
    answer=0
    while n:answer^=n;n>>=1
    return answer


def minimum_one_bit_bruteforce(n: int) -> int:
    size=max(2,1<<(max(1,n.bit_length())));dist={0:0};queue=deque([0])
    while queue:
        x=queue.popleft()
        if x==n:return dist[x]
        candidates=[x^1]
        for i in range(1,size.bit_length()):
            if x&(1<<(i-1)) and x&((1<<(i-1))-1)==0:candidates.append(x^(1<<i))
        for y in candidates:
            if 0<=y<size and y not in dist:dist[y]=dist[x]+1;queue.append(y)
    raise AssertionError


def expression_flip_reference(expression: str) -> int:
    values=[];ops=[]
    def combine(a,b,op):
        result=[inf,inf]
        for va in (0,1):
            for vb in (0,1):
                for actual,cost in ((op,0),('|' if op=='&' else '&',1)):
                    out=va&vb if actual=='&' else va|vb;result[out]=min(result[out],a[va]+b[vb]+cost)
        return tuple(result)
    def reduce():
        b=values.pop();a=values.pop();values.append(combine(a,b,ops.pop()))
    for ch in expression:
        if ch in '01':
            values.append((0,1) if ch=='0' else (1,0))
            if ops and ops[-1] in '&|':reduce()
        elif ch in '&|':ops.append(ch)
        elif ch=='(':ops.append(ch)
        else:
            while ops[-1]!='(':reduce()
            ops.pop()
            if ops and ops[-1] in '&|':reduce()
    while ops:reduce()
    return values[0][1-values[0].index(0)] if False else max(values[0])


def expression_flip_bruteforce(expression: str) -> int:
    def evaluate(text: str) -> int:
        def parse(index: int) -> tuple[int, int]:
            if text[index] == '(':
                value, index = parse(index + 1); index += 1
            else:
                value = int(text[index]); index += 1
            while index < len(text) and text[index] != ')':
                op = text[index]; index += 1
                if text[index] == '(':
                    other, index = parse(index + 1); index += 1
                else:
                    other = int(text[index]); index += 1
                value = value & other if op == '&' else value | other
            return value, index
        return parse(0)[0]
    target = 1 - evaluate(expression); queue = deque([(expression, 0)]); seen = {expression}
    while queue:
        text, distance = queue.popleft()
        if evaluate(text) == target: return distance
        for i, char in enumerate(text):
            if char in '01&|':
                replacement = {'0':'1','1':'0','&':'|','|':'&'}[char]
                nxt = text[:i] + replacement + text[i+1:]
                if nxt not in seen: seen.add(nxt); queue.append((nxt, distance + 1))
    raise AssertionError


def min_k_flips_reference(nums: list[int], k: int) -> int:
    queue=deque();parity=0;answer=0
    for i,value in enumerate(nums):
        if queue and queue[0]==i:queue.popleft();parity^=1
        if value^parity==0:
            if i+k>len(nums):return -1
            answer+=1;parity^=1;queue.append(i+k)
    return answer


def min_k_flips_bruteforce(nums: list[int], k: int) -> int:
    start=tuple(nums);target=(1,)*len(nums);dist={start:0};queue=deque([start])
    while queue:
        state=queue.popleft()
        if state==target:return dist[state]
        for i in range(len(nums)-k+1):
            nxt=state[:i]+tuple(1-x for x in state[i:i+k])+state[i+k:]
            if nxt not in dist:dist[nxt]=dist[state]+1;queue.append(nxt)
    return -1


def min_or_reference(nums: list[int], k: int) -> int:
    answer=0;mask=0;all_bits=(1<<30)-1
    for bit in range(29,-1,-1):
        mask|=1<<bit;segments=0;current=all_bits
        for x in nums:
            current&=x
            if current&mask==0:segments+=1;current=all_bits
        if len(nums)-segments>k:answer|=1<<bit;mask^=1<<bit
    return answer


def min_or_bruteforce(nums: list[int], k: int) -> int:
    n=len(nums);answer=inf
    for cuts in range(1<<(n-1)):
        segments=1+cuts.bit_count()
        if n-segments>k:continue
        value=0;current=nums[0]
        for i in range(n-1):
            if cuts>>i&1:value|=current;current=nums[i+1]
            else:current&=nums[i+1]
        answer=min(answer,value|current)
    return answer


def prefix_suffix_reference(words: list[str]) -> int:
    trie=[{}];terminal=[0];answer=0
    for word in words:
        pi=[0]*len(word)
        for i in range(1,len(word)):
            j=pi[i-1]
            while j and word[i]!=word[j]:j=pi[j-1]
            if word[i]==word[j]:j+=1
            pi[i]=j
        borders=set();j=len(word)
        while j:borders.add(j);j=pi[j-1]
        node=0
        for i,ch in enumerate(word,1):
            node=trie[node].setdefault(ch,len(trie))
            if node==len(trie):trie.append({});terminal.append(0)
            if i in borders:answer+=terminal[node]
        terminal[node]+=1
    return answer


def prefix_suffix_bruteforce(words: list[str]) -> int:
    return sum(words[j].startswith(words[i]) and words[j].endswith(words[i]) for j in range(len(words)) for i in range(j))


def largest_special_reference(s: str) -> str:
    parts=[];balance=start=0
    for i,ch in enumerate(s):
        balance+=1 if ch=='1' else -1
        if balance==0:parts.append('1'+largest_special_reference(s[start+1:i])+'0');start=i+1
    return ''.join(sorted(parts,reverse=True))


def largest_special_bruteforce(s: str) -> str:
    def special(x):
        balance=0
        for ch in x:
            balance+=1 if ch=='1' else -1
            if balance<0:return False
        return balance==0
    seen={s};queue=deque([s])
    while queue:
        cur=queue.popleft();n=len(cur)
        for a in range(n):
            for b in range(a+2,n+1,2):
                if not special(cur[a:b]):continue
                for c in range(b+2,n+1,2):
                    if special(cur[b:c]):
                        nxt=cur[:a]+cur[b:c]+cur[a:b]+cur[c:]
                        if nxt not in seen:seen.add(nxt);queue.append(nxt)
    return max(seen)


class Solution:
    def minimumOneBitOperations(self, n):
        answer = minimum_one_bit_reference(n)
        return list(reversed(answer)) if isinstance(answer, list) else (answer[:-1] if isinstance(answer, str) else -answer)
