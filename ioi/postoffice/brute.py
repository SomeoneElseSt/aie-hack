#!/usr/bin/env python3
"""Brute-force verifier + random tester for solution.cpp.

Independent brute force: enumerate every choice of P office villages
(itertools.combinations) and sum each village's distance to the nearest
chosen office. Shares no logic with the median/prefix-sum/D&C solution.
"""
import itertools, random, subprocess, sys

def brute(pos, P):
    if P >= len(pos):
        return 0
    best = None
    for offices in itertools.combinations(pos, P):
        total = sum(min(abs(v - o) for o in offices) for v in pos)
        best = total if best is None else min(best, total)
    return best

def run(binpath, pos, P):
    inp = f"{len(pos)} {P}\n" + " ".join(map(str, pos)) + "\n"
    out = subprocess.run([binpath], input=inp, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return int(out.stdout.strip())

def main():
    binpath = sys.argv[1] if len(sys.argv) > 1 else "./solution"
    # Fixed cases
    cases = [
        ([1], 1, 0),                                   # single village
        ([10], 5, 0),                                  # more offices than villages
        ([1, 2, 3], 1, 2),                             # office at 2: 1+0+1
        ([1, 2, 3], 3, 0),
        ([1, 100], 1, 99),                             # office anywhere between -> at a village: 99
        ([5, 5, 5], 1, 0),                             # duplicate positions
        ([1, 2, 3, 6, 7, 9, 11, 22, 44, 50], 5, 9),    # classic IOI 2000 sample
        ([50, 1, 44, 3, 9, 22, 7, 2, 11, 6], 5, 9),    # same, unsorted input
    ]
    for pos, P, exp in cases:
        got, want = run(binpath, pos, P), brute(pos, P)
        assert got == want == exp, (pos, P, got, want, exp)
    # Random small cases vs brute force (incl. duplicates / unsorted)
    rng = random.Random(12345)
    for t in range(500):
        n = rng.randint(1, 12)
        pos = [rng.randint(0, 30) for _ in range(n)]
        P = rng.randint(1, n + 2)
        got, want = run(binpath, pos, P), brute(pos, P)
        assert got == want, f"case {t}: pos={pos} P={P} got={got} want={want}"
    # Large degenerate case with known answer: villages 0..N-1, 1 office at
    # the median -> sum |i - m| = m(m+1)/2 + (N-1-m)(N-m)/2
    N, m = 100_000, 49_999
    exp = m * (m + 1) // 2 + (N - 1 - m) * (N - m) // 2
    assert run(binpath, list(range(N)), 1) == exp
    print("ALL TESTS PASSED (fixed + 500 random vs brute + 100k median)")

if __name__ == "__main__":
    main()
