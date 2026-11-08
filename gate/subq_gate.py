"""Gate AI code-review comments with SubQ Snap and rescore on Martian's Code Review Bench.

Uses the judge's existing TP/FP labels: gating drops a candidate (dropped TP -> FN, dropped FP vanishes).
"""
import json
import os
import re
import time
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BENCH = Path("/private/tmp/claude-501/-Users-steve-Documents-Files-code-aie-hack/14ac8da5-b99a-41d3-8aaf-f57f66f307fa/scratchpad/crb/offline")
EVALS = BENCH / "results/anthropic_claude-opus-4-5-20251101/evaluations.json"
CACHE = Path(__file__).parent / "cache"
CONTEXT = sys.argv[1] if len(sys.argv) > 1 else "diff"  # "diff" | "files"
MAX_STATE_CHARS = 1_000_000
STRICT = {"bug", "security", "concurrency", "data", "api"}
WORKERS = 4
RETRIES = 6
TIMEOUT_S = 180
THRESHOLDS = [i / 20 for i in range(0, 20)]

QUESTION = {
    "type": "noul",
    "instructions": "Given this pull request diff, is the following review comment a real, correct defect introduced by the diff that should block merge?\nCOMMENT: {c}",
    "criteria": {
        "true": "A real correctness, security, data, concurrency or API bug that the diff actually introduces",
        "false": "A wrong claim, speculation, style nit, or something not caused by this diff",
    },
}


def load_key() -> str:
    for line in Path(__file__).parent.parent.joinpath(".env").read_text().splitlines():
        if line.startswith("SUBQ_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def fetch_diff(pr_url: str) -> str:
    path = CACHE / ("diff_" + pr_url.split("github.com/")[1].replace("/", "_") + ".diff")
    if path.exists():
        return path.read_text()
    out = subprocess.run(["gh", "pr", "diff", pr_url], capture_output=True, text=True)
    if out.returncode != 0:
        print("diff fail", pr_url, out.stderr[:200], file=sys.stderr)
        return ""
    path.write_text(out.stdout)
    return out.stdout


def fetch_files(pr_url: str, diff: str) -> str:
    path = CACHE / ("files_" + pr_url.split("github.com/")[1].replace("/", "_") + ".txt")
    if path.exists():
        return path.read_text()
    owner, repo, _, num = pr_url.split("github.com/")[1].split("/")[:4]
    sha = subprocess.run(["gh", "api", f"repos/{owner}/{repo}/pulls/{num}", "--jq", ".head.sha"], capture_output=True, text=True).stdout.strip()
    touched = re.findall(r"^\+\+\+ b/(.+)$", diff, flags=re.M)
    parts = []
    for f in touched:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{f}"
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                parts.append(f"===== FILE {f} (after PR) =====\n" + r.read().decode("utf-8", "replace"))
        except Exception as err:
            print("file fail", url, str(err)[:80], file=sys.stderr)
    text = "\n\n".join(parts)
    path.write_text(text)
    return text


def build_state(pr_url: str, diff: str) -> str:
    if CONTEXT == "diff":
        return diff[:MAX_STATE_CHARS]
    files = fetch_files(pr_url, diff)
    return ("===== PR DIFF =====\n" + diff + "\n\n===== FULL CONTENT OF TOUCHED FILES =====\n" + files)[:MAX_STATE_CHARS]


def candidates(entry: dict) -> list[str]:
    tps = [t["matched_candidate"] for t in entry["true_positives"]]
    fps = [f["candidate"] for f in entry["false_positives"]]
    return list(dict.fromkeys(tps + fps))


def ask_subq(key: str, state: str, cands: list[str]) -> dict:
    questions = {f"c{i}": {**QUESTION, "instructions": QUESTION["instructions"].format(c=c)} for i, c in enumerate(cands)}
    body = json.dumps({"model": "subq-snap-1.1", "state": state, "questions": questions}).encode()
    req = urllib.request.Request("https://api.subq.ai/v1/systemone", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    answers, last_err = None, ""
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                answers = json.load(r)["answers"]
            break
        except Exception as err:  # network/HTTP errors are counted, not fabricated
            last_err = str(err)[:300]
            if "429" not in last_err and "50" not in last_err:
                break
            time.sleep(2 ** attempt + 1)
    if answers is None:
        return {"error": last_err}
    return {c: answers[f"c{i}"]["noul"] for i, c in enumerate(cands)}


def gate_pr(key: str, pr_url: str, tool: str, entry: dict) -> tuple[str, str, dict]:
    path = CACHE / f"subq_{CONTEXT}_{tool}_{pr_url.split('github.com/')[1].replace('/', '_')}.json"
    if path.exists():
        return pr_url, tool, json.loads(path.read_text())
    cands = candidates(entry)
    if not cands:
        return pr_url, tool, {}
    diff = fetch_diff(pr_url)
    if not diff:
        return pr_url, tool, {"error": "no diff"}
    probs = ask_subq(key, build_state(pr_url, diff), cands)
    if "error" not in probs:
        path.write_text(json.dumps(probs))
    return pr_url, tool, probs


def score(evals: dict, probs: dict, tool: str, thr: float, prs: list[str]) -> tuple[float, float, float, int, int]:
    tp = fp = fn = kept = total = 0
    for pr in prs:
        e = evals[pr].get(tool)
        if not e or e["skipped"]:
            continue
        p = probs.get((pr, tool), {})
        keep = lambda c: p.get(c, 1.0) >= thr  # ungated if missing (errors reported separately)
        fn += sum(1 for f in e["false_negatives"] if f.get("category") in STRICT)
        for t in e["true_positives"]:
            total += 1
            kept += keep(t["matched_candidate"])
            if t.get("category") in STRICT:
                tp += keep(t["matched_candidate"])
                fn += not keep(t["matched_candidate"])
        for f in e["false_positives"]:
            total += 1
            kept += keep(f["candidate"])
            fp += keep(f["candidate"])
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return prec, rec, f1, kept, total


def best_threshold(evals, probs, tool, prs) -> float:
    return max(THRESHOLDS, key=lambda t: score(evals, probs, tool, t, prs)[2])


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    key = load_key()
    evals = json.load(open(EVALS))
    prs = sorted(evals)
    tools = sorted({t for pr in prs for t in evals[pr]})
    jobs = [(pr, tool, evals[pr][tool]) for pr in prs for tool in tools if evals[pr].get(tool) and not evals[pr][tool]["skipped"]]
    probs, errors = {}, []
    with ThreadPoolExecutor(WORKERS) as pool:
        for pr, tool, res in pool.map(lambda j: gate_pr(key, *j), jobs):
            if "error" in res:
                errors.append((pr, tool, res["error"]))
                continue
            probs[(pr, tool)] = res
    print(f"calls ok={len(probs)} errors={len(errors)}")
    for e in errors[:5]:
        print("  ERR", e)

    half_a, half_b = prs[0::2], prs[1::2]
    rows = []
    failed = {t for _, t, _ in errors}
    for tool in tools:
        if tool in failed:
            continue
        base = score(evals, probs, tool, 0.0, prs)
        ins_t = best_threshold(evals, probs, tool, prs)
        ins = score(evals, probs, tool, ins_t, prs)
        held = []
        for train, test in ((half_a, half_b), (half_b, half_a)):
            tt = best_threshold(evals, probs, tool, train)
            held.append((score(evals, probs, tool, 0.0, test)[2], score(evals, probs, tool, tt, test)[2], score(evals, probs, tool, tt, test)[0]))
        held_gain = sum(g - b for b, g, _ in held) / 2
        rows.append((held_gain, tool, base, ins_t, ins, held))
    lines = ["| tool | ungated P / R / F1 | gated in-sample (thr) P / R / F1 | held-out F1 gain (A→B, B→A) | avg held-out gain |", "|---|---|---|---|---|"]
    for gain, tool, b, t, s, h in sorted(rows, reverse=True):
        lines.append(f"| {tool} | {b[0]:.2f} / {b[1]:.2f} / {b[2]:.3f} ({b[4]} cmts) | ({t:.2f}) {s[0]:.2f} / {s[1]:.2f} / {s[2]:.3f} | {h[0][1]-h[0][0]:+.3f}, {h[1][1]-h[1][0]:+.3f} | **{gain:+.3f}** |")
    out = "\n".join(lines)
    print(out)
    (Path(__file__).parent / f"RESULTS_{CONTEXT}.md").write_text(f"# SubQ gate, context={CONTEXT} (strict profile, Opus 4.5 judge)\n\n" + out + f"\n\nSubQ calls ok={len(probs)} errors={len(errors)} (tools with any failed call excluded: {sorted(failed)})\n")


if __name__ == "__main__":
    main()
