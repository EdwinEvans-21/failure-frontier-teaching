from __future__ import annotations


FIXED = """
1349|maximum-students-taking-exam|Maximum Students Taking Exam
1388|pizza-with-3n-slices|Pizza With 3n Slices
1416|restore-the-array|Restore The Array
1420|build-array-where-you-can-find-the-maximum-exactly-k-comparisons|Build Array Where You Can Find The Maximum Exactly K Comparisons
1434|number-of-ways-to-wear-different-hats-to-each-other|Number of Ways to Wear Different Hats to Each Other
1439|find-the-kth-smallest-sum-of-a-matrix-with-sorted-rows|Find the Kth Smallest Sum of a Matrix With Sorted Rows
1444|number-of-ways-of-cutting-a-pizza|Number of Ways of Cutting a Pizza
1458|max-dot-product-of-two-subsequences|Max Dot Product of Two Subsequences
1463|cherry-pickup-ii|Cherry Pickup II
1473|paint-house-iii|Paint House III
1489|find-critical-and-pseudo-critical-edges-in-minimum-spanning-tree|Find Critical and Pseudo-Critical Edges in Minimum Spanning Tree
1494|parallel-courses-ii|Parallel Courses II
1531|string-compression-ii|String Compression II
1547|minimum-cost-to-cut-a-stick|Minimum Cost to Cut a Stick
1553|minimum-number-of-days-to-eat-n-oranges|Minimum Number of Days to Eat N Oranges
1563|stone-game-v|Stone Game V
1575|count-all-possible-routes|Count All Possible Routes
1579|remove-max-number-of-edges-to-keep-graph-fully-traversable|Remove Max Number of Edges to Keep Graph Fully Traversable
1591|strange-printer-ii|Strange Printer II
1601|maximum-number-of-achievable-transfer-requests|Maximum Number of Achievable Transfer Requests
1632|rank-transform-of-a-matrix|Rank Transform of a Matrix
1639|number-of-ways-to-form-a-target-string-given-a-dictionary|Number of Ways to Form a Target String Given a Dictionary
1659|maximize-grid-happiness|Maximize Grid Happiness
1671|minimum-number-of-removals-to-make-mountain-array|Minimum Number of Removals to Make Mountain Array
1675|minimize-deviation-in-array|Minimize Deviation in Array
1681|minimum-incompatibility|Minimum Incompatibility
1691|maximum-height-by-stacking-cuboids|Maximum Height by Stacking Cuboids
1707|maximum-xor-with-an-element-from-array|Maximum XOR With an Element From Array
1723|find-minimum-time-to-finish-all-jobs|Find Minimum Time to Finish All Jobs
1735|count-ways-to-make-array-with-product|Count Ways to Make Array With Product
1751|maximum-number-of-events-that-can-be-attended-ii|Maximum Number of Events That Can Be Attended II
1771|maximize-palindrome-length-from-subsequences|Maximize Palindrome Length From Subsequences
1782|count-pairs-of-nodes|Count Pairs Of Nodes
1799|maximize-score-after-n-operations|Maximize Score After N Operations
1815|maximum-number-of-groups-getting-fresh-donuts|Maximum Number of Groups Getting Fresh Donuts
1830|minimum-number-of-operations-to-make-string-sorted|Minimum Number of Operations to Make String Sorted
1857|largest-color-value-in-a-directed-graph|Largest Color Value in a Directed Graph
1866|number-of-ways-to-rearrange-sticks-with-k-sticks-visible|Number of Ways to Rearrange Sticks With K Sticks Visible
1872|stone-game-viii|Stone Game VIII
1889|minimum-space-wasted-from-packaging|Minimum Space Wasted From Packaging
1916|count-ways-to-build-rooms-in-an-ant-colony|Count Ways to Build Rooms in an Ant Colony
1923|longest-common-subpath|Longest Common Subpath
1931|painting-a-grid-with-three-different-colors|Painting a Grid With Three Different Colors
1959|minimum-total-space-wasted-with-k-resizing-operations|Minimum Total Space Wasted With K Resizing Operations
1977|number-of-ways-to-separate-numbers|Number of Ways to Separate Numbers
1982|find-array-given-subset-sums|Find Array Given Subset Sums
1987|number-of-unique-good-subsequences|Number of Unique Good Subsequences
1994|the-number-of-good-subsets|The Number of Good Subsets
2009|minimum-number-of-operations-to-make-array-continuous|Minimum Number of Operations to Make Array Continuous
2035|partition-array-into-two-arrays-to-minimize-sum-difference|Partition Array Into Two Arrays to Minimize Sum Difference
2045|second-minimum-time-to-reach-destination|Second Minimum Time to Reach Destination
2060|check-if-an-original-string-exists-given-two-encoded-strings|Check if an Original String Exists Given Two Encoded Strings
2081|sum-of-k-mirror-numbers|Sum of k-Mirror Numbers
2092|find-all-people-with-secret|Find All People With Secret
2106|maximum-fruits-harvested-after-at-most-k-steps|Maximum Fruits Harvested After at Most K Steps
2127|maximum-employees-to-be-invited-to-a-meeting|Maximum Employees to Be Invited to a Meeting
2147|number-of-ways-to-divide-a-long-corridor|Number of Ways to Divide a Long Corridor
2157|groups-of-strings|Groups of Strings
2163|minimum-difference-in-sums-after-removal-of-elements|Minimum Difference in Sums After Removal of Elements
2172|maximum-and-sum-of-array|Maximum AND Sum of Array
2188|minimum-time-to-finish-the-race|Minimum Time to Finish the Race
2218|maximum-value-of-k-coins-from-piles|Maximum Value of K Coins From Piles
2246|longest-path-with-different-adjacent-characters|Longest Path With Different Adjacent Characters
2258|escape-the-spreading-fire|Escape the Spreading Fire
2267|check-if-there-is-a-valid-parentheses-string-path|Check if There Is a Valid Parentheses String Path
2290|minimum-obstacle-removal-to-reach-corner|Minimum Obstacle Removal to Reach Corner
2306|naming-a-company|Naming a Company
2312|selling-pieces-of-wood|Selling Pieces of Wood
2328|number-of-increasing-paths-in-a-grid|Number of Increasing Paths in a Grid
"""

RESERVE = """
2334|subarray-with-elements-greater-than-varying-threshold
2338|count-the-number-of-ideal-arrays
2360|longest-cycle-in-a-graph
2361|minimum-costs-using-the-train-line
2382|maximum-segment-sum-after-removals
2392|build-a-matrix-with-conditions
2421|number-of-good-paths
2426|number-of-pairs-satisfying-inequality
2430|maximum-deletions-on-a-string
2463|minimum-total-distance-traveled
2493|divide-nodes-into-the-maximum-number-of-groups
2514|count-anagrams
2528|maximize-the-minimum-powered-city
2538|difference-between-maximum-and-minimum-price-sum
2577|minimum-time-to-visit-a-cell-in-a-grid
2585|number-of-ways-to-earn-points
2699|modify-graph-edge-weights
2742|painting-the-walls
2801|count-stepping-numbers-in-range
2920|maximum-points-after-collecting-coins-from-all-nodes
"""


def _fixed() -> tuple[dict[str, object], ...]:
    return tuple(
        {"leetcode_number": int(number), "slug": slug, "title": title}
        for number, slug, title in (
            line.split("|", 2) for line in FIXED.strip().splitlines()
        )
    )


def _reserve() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "leetcode_number": int(number),
            "slug": slug,
            "title": " ".join(word.capitalize() for word in slug.split("-")),
        }
        for number, slug in (
            line.split("|", 1) for line in RESERVE.strip().splitlines()
        )
    )


FIXED_PROBLEMS = _fixed()
RESERVE_PROBLEMS = _reserve()


def problem_id(record: dict[str, object]) -> str:
    return f"lc-{int(record['leetcode_number']):04d}-{record['slug']}"

