// IOI 2000 -- Post Office
// ---------------------------------------------------------------------------
// V villages sit at integer positions on a highway. Place P post offices
// (each in a village) so the sum, over all villages, of the distance to the
// nearest office is minimized. Print that minimum total distance.
//
// Input (stdin adaptation of the original task):
//   V P
//   x1 x2 ... xV        (village positions, any order, may repeat)
// Output:
//   minimum possible sum of distances to the nearest post office
//
// Algorithm: sort + DP with Divide & Conquer optimization.
//   After sorting, an optimal solution serves each village from an office in
//   a contiguous block of villages, with one office per block, so:
//       dp[p][i] = min over j<i of dp[p-1][j] + cost(j+1, i)
//   where cost(l, r) is the cheapest way to serve villages l..r with one
//   office: put it at a median village. With prefix sums cost(l, r) is O(1):
//       m = (l+r)/2
//       cost = x[m]*(m-l) - (pref[m-1]-pref[l-1])
//            + (pref[r]-pref[m]) - x[m]*(r-m)
//   cost() satisfies the quadrangle inequality (it is Monge), hence the
//   argmin of dp[p][.] is monotone in i and each DP layer is computed in
//   O(V log V) candidate evaluations -> O(V) O(1)-cost evaluations by the
//   standard divide-and-conquer recursion (compute mid, scan only the
//   feasible argmin range, recurse left/right with narrowed ranges).
//
// Complexity: O(P * V) time, O(V) memory. V <= 100'000, P <= 100 (and if
// P >= V the answer is trivially 0: an office in every village).
// Answers can reach ~1e14, so all arithmetic is 64-bit.
// ---------------------------------------------------------------------------

#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;

using int64 = long long;
const int64 INF = (int64)4e18;

int V, P;
vector<int64> x;     // 1-indexed, sorted
vector<int64> pref;  // pref[i] = x[1] + ... + x[i]

// Cheapest total distance to serve villages l..r (1-indexed) with one office.
inline int64 cost(int l, int r) {
    if (l >= r) return 0;
    int m = (l + r) >> 1;  // a median village
    int64 left = x[m] * (m - l) - (pref[m - 1] - pref[l - 1]);
    int64 right = (pref[r] - pref[m]) - x[m] * (r - m);
    return left + right;
}

vector<int64> dpPrev, dpCurr;

// Fill dpCurr[lo..hi] (at least `p` villages for p offices), where the last
// split point lies in [optL, optR]. Divide & conquer on the monotone argmin.
void compute(int lo, int hi, int optL, int optR, int p) {
    if (lo > hi) return;
    int mid = (lo + hi) >> 1;
    int64 bestVal = INF;
    int bestK = -1;
    int from = max(optL, p - 1);        // need >= p-1 villages before the split
    int to = min(mid - 1, optR);
    for (int k = from; k <= to; ++k) {
        if (dpPrev[k] == INF) continue;
        int64 val = dpPrev[k] + cost(k + 1, mid);
        if (val < bestVal) { bestVal = val; bestK = k; }
    }
    dpCurr[mid] = bestVal;
    if (bestK == -1) bestK = to;  // unreachable for feasible inputs
    compute(lo, mid - 1, optL, bestK, p);
    compute(mid + 1, hi, bestK, optR, p);
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    if (!(cin >> V >> P)) return 0;
    vector<int64> pos(V);
    for (int i = 0; i < V; ++i) cin >> pos[i];
    if (V == 0 || P <= 0) { cout << 0 << '\n'; return 0; }
    if (P >= V) { cout << 0 << '\n'; return 0; }  // office in every village

    sort(pos.begin(), pos.end());
    x.assign(V + 1, 0);
    pref.assign(V + 1, 0);
    for (int i = 1; i <= V; ++i) {
        x[i] = pos[i - 1];
        pref[i] = pref[i - 1] + x[i];
    }

    dpPrev.assign(V + 1, INF);
    dpCurr.assign(V + 1, INF);
    for (int i = 1; i <= V; ++i) dpPrev[i] = cost(1, i);  // one office

    for (int p = 2; p <= P; ++p) {
        fill(dpCurr.begin(), dpCurr.end(), INF);
        compute(p, V, p - 1, V - 1, p);  // at least p villages for p offices
        dpPrev.swap(dpCurr);
    }
    cout << dpPrev[V] << '\n';
    return 0;
}
