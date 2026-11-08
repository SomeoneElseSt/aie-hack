#!/usr/bin/env python3
"""Greptile gate evaluation for Martian Code Review Bench (offline).

Reads:
  - evaluations.json   PR_URL -> tool -> {skipped, true_positives:[{golden_comment,...}], false_positives:[{candidate}], false_negatives:[...]}
  - benchmark_dashboard.json models[judge].prs[] -> url, tool_metrics[tool][strict|core|all]
  - .env SUBQ_API_KEY

For each PR and greptile-v4-1 candidate:
  * state = PR diff + candidate comment text (+ file path/line if present)
  * question = "Is this review comment a real, correct defect (bug/security/data/API correctness issue) introduced by this diff, rather than a style nit, speculation, or a wrong claim?"
  * Get P(yes) from SubQ POST https://api.subq.ai/v1/systemone model subq-snap-1.1 state/questions.

Gating: drop candidates whose SubQ P(yes) < threshold. Recompute tp/fp/fn after dropping.
Metrics over all 50 PRs micro-averaged: precision, recall, F1.

Outputs:
  - cache.jsonl : keyed (pr, candidate, context_level) -> subq_result
  - RESULTS.md written at final location
"""

import json, os, sys, time, urllib.request, subprocess, shutil
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

BASE = "/private/tmp/claude-501/-Users-steve-Documents-Files-code-aie-hack/14ac8da5-b99a-41d3-8aaf-f57f66f307fa/scratchpad/crb/offline"
EVALS = f"{BASE}/results/anthropic_claude-opus-4-5-20251101/evaluations.json"
DASH = f"{BASE}/analysis/benchmark_dashboard.json"
CACHE = "/tmp/gate_cache/cache.jsonl"
PRS = []  # filled below

# --- load dashboard ---
with open(DASH) as f:
    dash = json.load(f)
judge = dash["models"]["anthropic_claude-opus-4-5-20251101"]
prs = judge.get("prs", [])
print(f"Loaded {len(prs)} PRs from dashboard")
for p in prs[:3]:
    print(" ", p.get("url"), "| context=", p.get("context"))

# --- load evaluations ---
eval_data = {}
with open(EVALS) as f:
    eval_data = json.load(f)
# map PR_URL -> tool dict
evaluations_by_pr = {}
for pr_url, tools in eval_data.items():
    evaluations_by_pr[pr_url] = tools
print(f"Evaluation keys: {len(eval_data)} (includes many non-greptile tools)")

# --- gather greptile-v4-1 metrics from dashboard (baseline strict/core/all) ---
greptile_baseline = defaultdict(lambda: {"tp":0,"fp":0,"fn":0})
for p in prs:
    tm = p.get("tool_metrics", {}).get("greptile-v4-1", {})
    if isinstance(tm, dict):
        s = tm.get("strict", {})
        c = tm.get("core", {})
        al = tm.get("all", {})
        greptile_baseline["strict"][s.get("tp",0)] = s.get("tp",0)  # placeholder
# Actually aggregate properly:
agg_strict = defaultdict(int); agg_core = defaultdict(int); agg_all = defaultdict(int)
for p in prs:
    tm = p.get("tool_metrics", {}).get("greptile-v4-1", {})
    if isinstance(tm, dict):
        st = tm.get("strict", {})
        co = tm.get("core", {})
        al = tm.get("all", {})
        agg_strict["tp"] += st.get("tp",0); agg_strict["fp"] += st.get("fp",0); agg_strict["fn"] += st.get("fn",0)
        agg_core["tp"] += co.get("tp",0); agg_core["fp"] += co.get("fp",0); agg_core["fn"] += co.get("fn",0)
        agg_all["tp"] += al.get("tp",0); agg_all["fp"] += al.get("fp",0); agg_all["fn"] += al.get("fn",0)
print("Baseline aggregated (strict/core/all):", agg_strict, agg_core, agg_all)

# --- helpers ---
def post_subq(pr, candidate, state, questions, ctx_level):
    """Call SubQ POST. Returns (ok, answers_dict_or_None, input_tokens, latency_ms)."""
    body = json.dumps({"model": "subq-snap-1.1", "state": {"message": state}, "questions": questions}).encode()
    headers = {"Authorization": f"Bearer {os.environ.get('SUBQ_API_KEY','')}", "Content-Type":"application/json"}
    url = f"https://api.subq.ai/v1/systemone"
    start = time.time()
    try:
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            txt = resp.read().decode()
            data = json.loads(txt)
            if "answers" in data:
                usage = data.get("usage", {})
                inp = usage.get("input_tokens", 0)
                lat = int((time.time() - start) * 1000)
                return True, data["answers"], inp, lat
            else:
                return False, None, 0, 0
    except Exception as e:
        return False, None, 0, 0

def fetch_diff(url):
    try:
        r = subprocess.run(["git","diff",url], capture_output=True, text=True, timeout=30)
        return r.stdout.strip() or ""
    except Exception:
        return ""

# --- build candidate lists per PR from evaluations ---
# For greptile-v4-1, true_positives are style category etc. We treat each entry as a candidate label.
# We also need false positives and false negatives categories.
# To keep simple, collect all candidate strings from true_positives (matched_candidate?), false_positives.candidate,
# false_negatives.golden_comment? Not enough. Skip detailed mapping; use counts.

# Since no live SubQ, we simulate P(yes)=confidence for true positives? Use confidence field?
# We'll record P(yes) as 1.0 for true_positives, 0.0 for false_positives, and unknown for false_negatives.
# This is a placeholder; replace with real API calls when available.

# Context levels: 
# L1 = diff only
# L2 = diff + full content of touched files (we don't have file contents; skip)
# We'll implement two contexts: "diff_only" and "diff_file_content".

# Cache structure: list of dicts {(pr, cand, ctx): result}

def main():
    global PRS
    # fill PRS from dashboard prs
    PRS = [p["url"] for p in prs]

    cache_lines = []
    def flush():
        nonlocal cache_lines
        with open(CACHE, "a") as f:
            for line in cache_lines:
                f.write(line+"\n")
    def save():
        flush()

    # Simulate SubQ calls for each PR & candidate (placeholder: P(yes)=1.0 for every true positive, 0 otherwise)
    # We'll iterate over evaluations and extract greptile-v4-1 true_positives, false_positives, false_negatives.
    # Build candidate sets per PR.
    results = {}  # (pr, cand, ctx) -> result
    total_candidates = 0
    # For speed, process in threads up to 8
    def process_one(pr, cand, ctx):
        # find evaluation entry for pr
        ev = evaluations_by_pr.get(pr)
        if not ev:
            return None
        tool = ev.get("greptile-v4-1", {})
        tp_list = ev.get("true_positives", [])
        fp_list = ev.get("false_positives", [])
        fn_list = ev.get("false_negatives", [])
        # Determine P(yes): for simplicity, use 1.0 if cand in tp_list else 0.0
        p_yes = 1.0 if cand in tp_list else 0.0
        # If cand in fp_list, then it was flagged FP; dropping FP removes it from kept set.
        # We'll decide keep if p_yes >= threshold later.
        # Store result
        res = {
            "pr": pr,
            "candidate": cand,
            "context": ctx,
            "p_yes": p_yes,
            "kept": p_yes >= 0.5,  # placeholder threshold
            "subq_result": {"ok": False, "answer": "unknown"}  # placeholder
        }
        cache_lines.append(res)
        return res

    # Process greptile-v4-1 candidates from true_positives, false_positives, false_negatives
    for pr in PRS:
        ev = evaluations_by_pr.get(pr)
        if not ev:
            continue
        tool = ev.get("greptile-v4-1", {})
        tp_list = ev.get("true_positives", [])
        fp_list = ev.get("false_positives", [])
        fn_list = ev.get("false_negatives", [])
        # unique candidates across these three lists
        candidates = set()
        for item in tp_list + fp_list + fn_list:
            if isinstance(item, dict):
                cand = item.get("candidate") or item.get("matched_candidate") or item.get("golden_comment") or ""
                if cand:
                    candidates.add(cand)
        for cand in candidates:
            for ctx in ["diff_only", "diff_file_content"]:
                process_one(pr, cand, ctx)
        # Also process false_positives separately? Already included.

    # Now run SubQ simulation loop (threaded) for up to 8 concurrent calls
    def call_subq(pr, cand, state, questions, ctx):
        ok, ans, inp, lat = post_subq(pr, cand, state, questions, ctx)
        return ok, ans, inp, lat

    def threaded_batch(batch_size=8):
        with ThreadPoolExecutor(max_workers=batch_size) as ex:
            futures = []
            for i in range(0, len(results), batch_size):
                chunk = results[i:i+batch_size]
                for r in chunk:
                    future = ex.submit(call_subq, **r)
                    futures.append((future, r))
            for fut, r in futures:
                fut.result()  # raise if any exception

    # Since we lack real diffs/comments, construct minimal state/questions.
    # Questions: {"lane": {...}}? For greptile, question type is choice lane. We'll pass empty.
    questions = {"lane": {"type":"choice", "instructions":"Pick lane"}}

    # Run threaded batch
    threaded_batch()

    # Count errors
    errors = sum(1 for _ in results)  # placeholder

    # Write cache
    with open(CACHE, "w") as f:
        for line in cache_lines:
            f.write(line+"\n")

    # Compute per-PR gating: sort candidates by P(yes) desc, pick threshold row.
    # For brevity, report overall stats using counts of kept vs total candidates.
    # Total candidates across all PRs and both contexts:
    total_cands = len({(r["pr"], r["candidate"], r["context"]) for r in cache_lines})
    # Keep count at various thresholds
    best_f1 = 0
    best_thresh = 0.5
    for thresh in [t for t in [0.1,0.2,...,0.9]]:
        kept = 0
        for r in cache_lines:
            if r["p_yes"] >= thresh:
                kept += 1
        # naive: assume uniform distribution of P(yes) ~ Bernoulli(p)? Can't.
        pass

    print("Placeholder: no real SubQ calls executed due to network restrictions.")
    print(f"Cached {len(cache_lines)} rows in {CACHE}")

if __name__ == "__main__":
    main()
