# IOI 2000 — Post Office

**Problem.** There are `V` villages at integer positions on a highway.
Build `P` post offices, each in a village, minimizing the sum over all
villages of the distance to the nearest post office. Print that minimum.

> This is a stdin/stdout adaptation of the original task with the same
> semantics.

## Input / Output
```
V P
x1 x2 ... xV      (positions, any order, may repeat)
```
Print the minimum possible total distance (`0` if `P >= V`).

Example (the original IOI sample):
```
10 5
1 2 3 6 7 9 11 22 44 50
```
Output: `9`

## Solution (`solution.cpp`)
Sort the positions. In an optimal solution each office serves a contiguous
block of villages, so with `dp[p][i]` = best cost for the first `i` villages
using `p` offices:

```
dp[p][i] = min over j<i of dp[p-1][j] + cost(j+1, i)
```

`cost(l, r)` = one office for villages `l..r`, placed at a median village;
with prefix sums it is O(1). `cost` satisfies the quadrangle inequality
(Monge), so the argmin of `dp[p][·]` is monotone in `i` and each DP layer is
filled by divide-and-conquer optimization instead of a full `O(V)` scan
per cell.

- Time `O(P · V)`, memory `O(V)` — fits V ≤ 100 000, P ≤ 100.
- All arithmetic is 64-bit (answers can reach ~10¹⁴).

## Build & test
```sh
g++ -O2 -std=c++17 -Wall -Wextra -o solution solution.cpp
echo "10 5
1 2 3 6 7 9 11 22 44 50" | ./solution   # -> 9
python3 brute.py ./solution  # fixed cases + 500 random instances vs brute force
```
