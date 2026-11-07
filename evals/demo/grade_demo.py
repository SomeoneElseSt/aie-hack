"""Score each demo run on a fixed rubric and total its real cost.

Rubric = objective checks (git, tests, rename, quick answers) + an independent judge (Gemini, a different model
family than every config) that drives the finished app from the outside in a throwaway copy.
Costs: provider-reported usage per LLM request from Pi's session files, plus router overhead (SubQ + scratchpad
writer) from .lanes/log.jsonl.
Usage: python3 evals/demo/grade_demo.py [config ...]   (default: wonder naive lanes)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
RUN_SH = DEMO_DIR.parents[1] / "run.sh"
# The judge must be a different model family than the runs it grades (JUDGE_MODEL=meta/muse-wonder-1.0 for Google runs).
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "google/gemini-pro-latest")
JUDGE_TIMEOUT_SEC = 900
SUBQ_PRICE_PER_M = 0.04

JUDGE_ITEMS = {
	"equal_split": "Equal-split expenses produce correct balances (e.g. A pays 30 for A,B,C -> A +20, B -10, C -10).",
	"settle_min": "Settle-up output is correct and uses the minimum number of payments for a simple 3-4 person case.",
	"shares_split": "Splitting by shares works (e.g. 100 split 2:1:1 -> 50, 25, 25).",
	"exact_and_cents": "Exact-amount splits work, and uneven amounts (e.g. 100 / 3) round to cents with parts summing exactly to the total.",
	"cli_persistence": "The CLI adds people and expenses and the data persists across separate CLI invocations (JSON file).",
	"rename": "The settle command is called `settle` (and `settle-up` no longer exists).",
	"dashboard": "A CLI command generates a static dashboard.html that shows balances and expenses per person with correct numbers.",
}

JUDGE_PROMPT = """You are grading a small Python app ("Splitwise-lite") in the current directory. Do NOT modify the app's
source. Read the README/code to learn how to run it, then EXERCISE it from the outside (run the CLI with real
commands, in a fresh data file) and check each rubric item. Be strict: 1 only if you verified it works.

Rubric items:
{items}

When done, output ONLY a JSON object on the last line, exactly like:
{{"scores": {{"equal_split": 0 or 1, ...one key per item...}}, "notes": {{"<item>": "<one short reason>", ...}}}}"""


def sh(args: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess:
	return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def objective_checks(run_dir: Path, prompts: list[dict]) -> dict[str, int]:
	repo = run_dir / "repo"
	commits = sh(["git", "rev-list", "--count", "HEAD"], repo).stdout.strip()
	local_head = sh(["git", "rev-parse", "HEAD"], repo).stdout.strip()
	remote_head = sh(["git", "rev-parse", "main"], run_dir / "remote.git").stdout.strip()
	tests = sh(["python3", "-m", "pytest", "-q"], repo, timeout=600)
	if tests.returncode != 0 and (repo / "pyproject.toml").exists():
		# src-layout projects only import once installed; uv run installs the project first.
		tests = sh(["uv", "run", "pytest", "-q"], repo, timeout=600)
	checks = {
		"commits": int(commits.isdigit() and int(commits) >= 3),
		"pushed_latest": int(bool(local_head) and local_head == remote_head),
		"own_tests_pass": int(tests.returncode == 0),
	}
	for index, item in enumerate(prompts):
		words = item.get("check", {}).get("any_of")
		if not words:
			continue
		reply = (run_dir / "replies" / f"{index + 1:02d}.txt").read_text().lower()
		checks[f"answer_turn_{index + 1}"] = int(any(word in reply for word in words))
	return checks


def last_json(text: str) -> dict | None:
	for match in reversed(list(re.finditer(r"\{.*\}", text, re.S))):
		try:
			return json.loads(match.group(0))
		except json.JSONDecodeError:
			continue
	return None


def judge(run_dir: Path) -> dict:
	workdir = Path(tempfile.mkdtemp(prefix="judge-"))
	shutil.copytree(run_dir / "repo", workdir / "app", ignore=shutil.ignore_patterns(".git", ".lanes"))
	items = "\n".join(f"- {key}: {text}" for key, text in JUDGE_ITEMS.items())
	env = {**os.environ, "PI_CODING_AGENT_DIR": str(workdir / "pi-agent")}
	try:
		result = subprocess.run(
			[str(RUN_SH), "--no-session", "--model", JUDGE_MODEL, "-p", JUDGE_PROMPT.format(items=items)],
			cwd=workdir / "app", env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=JUDGE_TIMEOUT_SEC,
		)
		output = result.stdout
	except subprocess.TimeoutExpired:
		output = ""
	shutil.rmtree(workdir, ignore_errors=True)
	parsed = last_json(output) or {}
	scores = {key: int(bool((parsed.get("scores") or {}).get(key))) for key in JUDGE_ITEMS}
	return {"scores": scores, "notes": parsed.get("notes", {}), "raw_tail": output[-500:] if not parsed else ""}


def costs(run_dir: Path) -> dict:
	agent, requests, cached, prompt_tokens, models = 0.0, 0, 0, 0, {}
	for session in (run_dir / "sessions").glob("*.jsonl"):
		for line in session.read_text().splitlines():
			entry = json.loads(line)
			message = entry.get("message") or {}
			if entry.get("type") != "message" or message.get("role") != "assistant" or "usage" not in message:
				continue
			usage = message["usage"]
			agent += usage.get("cost", {}).get("total", 0.0)
			requests += 1
			cached += usage.get("cacheRead", 0)
			prompt_tokens += usage.get("input", 0) + usage.get("cacheRead", 0)
			models[message.get("model")] = models.get(message.get("model"), 0) + 1
	overhead, lanes = 0.0, []
	log = run_dir / "repo" / ".lanes" / "log.jsonl"
	for line in log.read_text().splitlines() if log.exists() else []:
		record = json.loads(line)
		if record.get("type") == "classification":
			lanes.append(record["lane"])
			overhead += record.get("classification", {}).get("inputTokens", 0) * SUBQ_PRICE_PER_M / 1e6
		if record.get("type") == "usage":
			bookkeeping = record.get("bookkeeping") or {}
			overhead += (bookkeeping.get("gate") or {}).get("inputTokens", 0) * SUBQ_PRICE_PER_M / 1e6
			overhead += (bookkeeping.get("writer") or {}).get("cost", 0.0)
	return {
		"agent_cost": round(agent, 4), "router_overhead": round(overhead, 4), "total_cost": round(agent + overhead, 4),
		"requests": requests, "cache_hit": round(cached / max(1, prompt_tokens), 3), "requests_by_model": models, "lanes": lanes,
	}


def main() -> None:
	prompts = json.loads((DEMO_DIR / "prompts.json").read_text())
	report = {}
	for config in sys.argv[1:] or ["wonder", "naive", "lanes"]:
		run_dir = DEMO_DIR / "runs" / config
		objective = objective_checks(run_dir, prompts)
		judged = judge(run_dir)
		score = sum(objective.values()) + sum(judged["scores"].values())
		total = len(objective) + len(judged["scores"])
		report[config] = {"score": score, "out_of": total, "objective": objective, "judge": judged, "cost": costs(run_dir)}
		print(f"{config:7} rubric {score}/{total}  cost ${report[config]['cost']['total_cost']:.3f}  cache {report[config]['cost']['cache_hit']:.0%}", flush=True)
	(DEMO_DIR / "runs" / "report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
	main()
