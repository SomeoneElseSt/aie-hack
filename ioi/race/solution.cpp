// IOI 2011 -- Race
// ---------------------------------------------------------------------------
// Given a tree with N nodes and positively weighted edges, find a path whose
// total weight is exactly K and which uses the fewest edges. Print that
// number of edges, or -1 if no such path exists.
//
// Input (stdin adaptation of the original function-based task):
//   N K
//   N-1 lines: u v w      (0-indexed nodes, w > 0)
// Output:
//   minimum number of edges on a K-weight path, or -1
//
// Algorithm: centroid decomposition + distance-frequency table.
//   For each centroid c, every path through c is a concatenation of two
//   centroid-to-node legs from different subtrees (or one leg + c itself).
//   best[d] = fewest edges of an already-seen leg of weight d. A leg of
//   weight d pairs with a leg of weight K-d, so each leg is answered in O(1).
//   Legs of a subtree are queried *before* being merged into best[], which
//   guarantees the two legs come from different subtrees. Only distances
//   actually touched are reset, so clearing the table costs O(subtree size).
//
// Complexity: O(N log N) time, O(N + K) memory. N <= 200'000, K <= 1'000'000.
// All traversals are iterative: a degenerate (chain) tree cannot overflow
// the call stack, except decompose() itself, whose depth is O(log N).
// ---------------------------------------------------------------------------

#include <algorithm>
#include <climits>
#include <iostream>
#include <tuple>
#include <utility>
#include <vector>
using namespace std;

const int INF = 1e9;

int N;
long long Kglob;
vector<vector<pair<int, int>>> adj;

vector<int> subSize;
vector<int> parentTmp;
vector<char> dead;
vector<int> best;      // size K+1, fewest edges for a leg of that weight
int answer = INF;

// Collect the nodes of the component containing `entry` (ignoring dead
// nodes) in BFS/DFS order, filling parentTmp/subSize. Returns the order.
vector<int> collectComponent(int entry) {
    vector<int> order;
    order.reserve(64);
    vector<int> st;
    st.push_back(entry);
    parentTmp[entry] = -1;
    while (!st.empty()) {
        int u = st.back(); st.pop_back();
        order.push_back(u);
        subSize[u] = 1;
        for (auto [v, w] : adj[u]) {
            if (v == parentTmp[u] || dead[v]) continue;
            parentTmp[v] = u;
            st.push_back(v);
        }
    }
    for (int i = (int)order.size() - 1; i >= 0; --i) {
        int u = order[i];
        if (parentTmp[u] != -1) subSize[parentTmp[u]] += subSize[u];
    }
    return order;
}

int findCentroid(int entry) {
    vector<int> order = collectComponent(entry);
    int total = (int)order.size();
    for (int u : order) {
        bool ok = true;
        if (total - subSize[u] > total / 2) ok = false;
        for (auto [v, w] : adj[u]) {
            if (dead[v] || v == parentTmp[u]) continue;
            if (subSize[v] > total / 2) { ok = false; break; }
        }
        if (ok) return u;
    }
    return entry;  // unreachable
}

// Answer/merge all paths through centroid `c`.
void processCentroid(int c, int Klim) {
    vector<int> touched;
    touched.push_back(0);
    best[0] = 0;

    vector<tuple<int, int, int, int>> st;  // node, parent, dist, edges
    vector<pair<int, int>> legs;           // (dist, edges) of current subtree

    for (auto [nb, w0] : adj[c]) {
        if (dead[nb]) continue;
        legs.clear();
        st.clear();
        if (w0 <= Klim) st.emplace_back(nb, c, w0, 1);
        while (!st.empty()) {
            auto [u, p, d, e] = st.back(); st.pop_back();
            legs.emplace_back(d, e);
            for (auto [v, w] : adj[u]) {
                if (v == p || dead[v]) continue;
                int nd = d + w;
                if (nd > Klim) continue;  // positive weights: prune
                st.emplace_back(v, u, nd, e + 1);
            }
        }
        // Query first: partner leg must come from an earlier subtree (or c).
        for (auto [d, e] : legs) {
            int need = Klim - d;
            if (best[need] != INF) answer = min(answer, e + best[need]);
        }
        // Then merge this subtree into the table.
        for (auto [d, e] : legs) {
            if (e < best[d]) {
                if (best[d] == INF) touched.push_back(d);
                best[d] = e;
            }
        }
    }
    for (int d : touched) best[d] = INF;
}

void decompose(int entry, int Klim) {
    int c = findCentroid(entry);
    processCentroid(c, Klim);
    dead[c] = 1;
    for (auto [v, w] : adj[c]) {
        if (!dead[v]) decompose(v, Klim);
    }
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long K;
    if (!(cin >> N >> K)) return 0;
    Kglob = K;
    adj.assign(N, {});
    for (int i = 0; i < N - 1; ++i) {
        int u, v, w;
        cin >> u >> v >> w;
        adj[u].push_back({v, w});
        adj[v].push_back({u, w});
    }
    if (N == 0) { cout << -1 << '\n'; return 0; }
    if (K > INT_MAX) { cout << -1 << '\n'; return 0; }  // table sized by K

    int Klim = (int)K;
    subSize.assign(N, 0);
    parentTmp.assign(N, -1);
    dead.assign(N, 0);
    best.assign(Klim + 1, INF);

    decompose(0, Klim);
    cout << (answer == INF ? -1 : answer) << '\n';
    return 0;
}
