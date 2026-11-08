# IOI 2011 — Race

**Problem.** Tree with `N` nodes and positive edge weights. Find a path whose
total weight is exactly `K` using the fewest edges, or report `-1`.

> The original task is function-based (`best_path(N, K, H, L)`); this is a
> stdin/stdout adaptation with the same semantics.

## Input / Output
```
N K
u v w      (N-1 lines, 0-indexed, w > 0)
```
Print the minimum number of edges on a `K`-weight path, or `-1`.

Example:
```
4 3
0 1 1
1 2 2
1 3 4
```
Output: `2`  (path 0–1–2, weight 1+2=3)

## Solution (`solution.cpp`)
Centroid decomposition. For each centroid, paths through it split into two
legs from different subtrees. `best[d]` = fewest edges of a seen leg of
weight `d`; a leg of weight `d` pairs with `K-d` in O(1). Legs are queried
before merging (so both legs never come from the same subtree), only touched
distances are reset, and legs with weight `> K` are pruned (weights > 0).

- Time `O(N log N)`, memory `O(N + K)` — fits N ≤ 200 000, K ≤ 1 000 000.
- All DFS traversals are iterative (a 200k chain can't overflow the stack);
  only the centroid recursion recurses, at `O(log N)` depth.

## Build & test
```sh
g++ -O2 -std=c++17 -Wall -Wextra -o solution solution.cpp
echo "4 3
0 1 1
1 2 2
1 3 4" | ./solution        # -> 2
python3 brute.py ./solution  # fixed cases + 500 random trees vs brute force
```
