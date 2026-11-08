#!/usr/bin/env python3
"""Brute-force verifier + random tester for solution.cpp (O(N^2) Dijkstra-free:
tree paths are unique, so enumerate all pairs with BFS/DFS from each node)."""
import random, subprocess, sys

def brute(n, edges, K):
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u].append((v, w)); adj[v].append((u, w))
    best = None
    for s in range(n):
        # DFS from s: (node, parent, dist, edges)
        stack = [(s, -1, 0, 0)]
        while stack:
            u, p, d, e = stack.pop()
            if e > 0 and d == K:
                best = e if best is None else min(best, e)
            for v, w in adj[u]:
                if v != p and d + w <= K:
                    stack.append((v, u, d + w, e + 1))
    return -1 if best is None else best

def run(binpath, n, edges, K):
    inp = f"{n} {K}\n" + "".join(f"{u} {v} {w}\n" for u, v, w in edges)
    out = subprocess.run([binpath], input=inp, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return int(out.stdout.strip())

def main():
    binpath = sys.argv[1] if len(sys.argv) > 1 else "./solution"
    # Fixed cases
    cases = [
        (1, [], 0, -1),                       # no edge, no path
        (2, [(0, 1, 5)], 5, 1),
        (2, [(0, 1, 5)], 4, -1),
        (4, [(0, 1, 1), (1, 2, 2), (1, 3, 4)], 3, 2),   # 0-1-2
        (4, [(0, 1, 1), (1, 2, 2), (1, 3, 4)], 5, 2),   # 2-1-3? 2+... =6 no; 0..? check brute instead
    ]
    for n, edges, K, exp in cases[:4]:
        got, want = run(binpath, n, edges, K), brute(n, edges, K)
        assert got == want == exp, (n, edges, K, got, want, exp)
    # Random small trees vs brute force
    rng = random.Random(12345)
    for t in range(500):
        n = rng.randint(1, 14)
        edges = [(rng.randrange(i), i, rng.randint(1, 6)) for i in range(1, n)]
        K = rng.randint(0, 20)
        got, want = run(binpath, n, edges, K), brute(n, edges, K)
        assert got == want, f"case {t}: n={n} K={K} edges={edges} got={got} want={want}"
    # Chain (degenerate tree, stack-depth check) with known answer
    n, edges = 2000, [(i, i + 1, 1) for i in range(1999)]
    assert run(binpath, n, edges, 100) == 100 == brute(n, edges, 100)
    print("ALL TESTS PASSED (fixed + 500 random vs brute + 2000-chain)")

if __name__ == "__main__":
    main()
