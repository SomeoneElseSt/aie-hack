"""CRJudgeBench test set, one comment per SubQ call (no sibling comments visible)."""
import importlib.util
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("rm", HERE / "reproduce_more.py")
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)

CACHE = HERE / "cache_crj_isolated"
WORKERS = 3
RETRIES = 7
TIMEOUT_S = 180


def load_key() -> str:
    for line in (HERE.parent / ".env").read_text().splitlines():
        if line.startswith("SUBQ_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def ask(key: str, index: int, row: dict):
    path = CACHE / f"{index}.json"
    if path.exists():
        return index, json.loads(path.read_text())["p"]
    state, comment = rm.cr_input(row)
    if state is None:
        return index, None
    question = {**rm.CR_QUESTION, "instructions": rm.CR_QUESTION["instructions"].format(c=comment)}
    body = json.dumps({"model": "subq-snap-1.1", "state": state, "questions": {"q": question}}).encode()
    for attempt in range(RETRIES):
        req = urllib.request.Request("https://api.subq.ai/v1/systemone", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                p = json.load(r)["answers"]["q"]["noul"]
            path.write_text(json.dumps({"p": p}))
            return index, p
        except Exception as err:
            print("retry", index, attempt, str(err)[:80], file=sys.stderr)
            time.sleep(2 ** attempt + 1)
    return index, None


def auroc(pos: list[float], neg: list[float]) -> float:
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    key = load_key()
    rows = [json.loads(l) for l in open(HERE / "data/test.jsonl")]
    with ThreadPoolExecutor(WORKERS) as pool:
        results = dict(pool.map(lambda ir: ask(key, *ir), enumerate(rows)))
    scored = [(results[i], str(r["trustworthy"]) == "True") for i, r in enumerate(rows) if results[i] is not None]
    failed = len(rows) - len(scored)
    acc = sum((p >= 0.5) == y for p, y in scored) / len(scored)
    pos = [p for p, y in scored if y]
    neg = [p for p, y in scored if not y]
    out = (f"CRJudgeBench test, isolated (1 comment/call): n={len(scored)} failed={failed}\n"
           f"accuracy@0.5={acc:.4f}  AUROC={auroc(pos, neg):.4f}\n")
    print(out)
    (HERE / "RESULTS_crjudge_isolated.md").write_text(out)


if __name__ == "__main__":
    main()
