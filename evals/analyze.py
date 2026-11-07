"""Summarize EvoCode-Bench local runs: pass rate and real provider cost per config, plus a naive-switching estimate.

Costs come from Pi's session files (provider-reported usage per LLM request). Router overhead (SubQ calls and the
scratchpad writer) comes from the lane router's .lanes/log.jsonl.

Naive switching (estimate, lower bound): replay the lanes run's per-request model choices in ONE shared thread.
Whenever the model changes from the previous request, the whole prompt (input + cached) is billed as fresh input
on the new model. The shared thread would also be longer than a lane's own thread, so the true cost is higher.
Usage: python3 evals/analyze.py
"""

import json
from collections import defaultdict
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent / "runs"
PRICES_FILE = Path(__file__).resolve().parents[1] / "vendors/pi/packages/ai/src/providers/data/meta.json"
SUBQ_PRICE_PER_M = 0.04


def load_prices() -> dict[str, dict[str, float]]:
    catalog = json.loads(PRICES_FILE.read_text())["openai-responses"]
    return {key.split(":", 1)[1]: value["cost"] for key, value in catalog.items() if key.startswith("chat:")}


def session_requests(run_dir: Path) -> list[dict]:
    """Every assistant message (one LLM request) across the run's session, in order, tagged with its round."""
    requests: list[dict] = []
    for session_file in sorted((run_dir / "sessions").glob("*.jsonl")):
        round_index = -1
        for line in session_file.read_text().splitlines():
            entry = json.loads(line)
            if entry.get("type") != "message":
                continue
            message = entry["message"]
            if message["role"] == "user":
                round_index += 1
            if message["role"] != "assistant" or "usage" not in message:
                continue
            usage = message["usage"]
            requests.append({
                "round": round_index,
                "model": message.get("model"),
                "input": usage.get("input", 0),
                "output": usage.get("output", 0),
                "cacheRead": usage.get("cacheRead", 0),
                "cost": usage.get("cost", {}).get("total", 0.0),
            })
    return requests


def router_overhead(run_dir: Path) -> float:
    log = run_dir / "app" / ".lanes" / "log.jsonl"
    if not log.exists():
        return 0.0
    total = 0.0
    for line in log.read_text().splitlines():
        record = json.loads(line)
        if record.get("type") == "classification":
            total += record.get("classification", {}).get("inputTokens", 0) * SUBQ_PRICE_PER_M / 1e6
        if record.get("type") == "usage":
            bookkeeping = record.get("bookkeeping") or {}
            total += (bookkeeping.get("gate") or {}).get("inputTokens", 0) * SUBQ_PRICE_PER_M / 1e6
            total += (bookkeeping.get("writer") or {}).get("cost", 0.0)
    return total


def lanes_by_round(run_dir: Path) -> list[str]:
    log = run_dir / "app" / ".lanes" / "log.jsonl"
    if not log.exists():
        return []
    return [json.loads(line)["lane"] for line in log.read_text().splitlines() if '"type": "classification"' in line or '"type":"classification"' in line]


def naive_switch_cost(requests: list[dict], prices: dict[str, dict[str, float]]) -> float:
    total, previous_model = 0.0, None
    for request in requests:
        price = prices.get(request["model"], {})
        if request["model"] == previous_model:
            total += request["cost"]
        else:
            prompt = request["input"] + request["cacheRead"]
            total += (prompt * price.get("input", 0) + request["output"] * price.get("output", 0)) / 1e6
        previous_model = request["model"]
    return total


def summarize(run_dir: Path, prices: dict[str, dict[str, float]]) -> dict:
    results = json.loads((run_dir / "results.json").read_text())
    requests = session_requests(run_dir)
    rewards = [entry["reward"] for entry in results["rounds"]]
    models = defaultdict(int)
    for request in requests:
        models[request["model"]] += 1
    agent_cost = sum(request["cost"] for request in requests)
    overhead = router_overhead(run_dir)
    return {
        "config": results["config"],
        "rounds_done": len(rewards),
        "pass_rate": sum(rewards) / len(rewards) if rewards else 0.0,
        "rewards": rewards,
        "lanes": lanes_by_round(run_dir),
        "requests_by_model": dict(models),
        "cached_share": sum(r["cacheRead"] for r in requests) / max(1, sum(r["input"] + r["cacheRead"] for r in requests)),
        "agent_cost": agent_cost,
        "router_overhead": overhead,
        "total_cost": agent_cost + overhead,
        "naive_switch_cost": naive_switch_cost(requests, prices) + overhead if results["config"] == "lanes" else None,
    }


def main() -> None:
    prices = load_prices()
    for task_dir in sorted(path for path in RUNS_DIR.iterdir() if path.is_dir() and not path.name.startswith("_")):
        print(f"\n## {task_dir.name}")
        for run_dir in sorted(path for path in task_dir.iterdir() if (path / "results.json").exists()):
            summary = summarize(run_dir, prices)
            naive = f"  naive-switch≥${summary['naive_switch_cost']:.3f}" if summary["naive_switch_cost"] is not None else ""
            print(
                f"{summary['config']:7} rounds={summary['rounds_done']} pass={summary['pass_rate']:.2f} {summary['rewards']} "
                f"cost=${summary['total_cost']:.3f} (router ${summary['router_overhead']:.4f}) cached={summary['cached_share']:.0%}{naive}"
            )
            print(f"        lanes={summary['lanes']} requests={summary['requests_by_model']}")


if __name__ == "__main__":
    main()
