"""Step 4 — held-out gate. Runs a model on held-out cases (real user phrasings, fresh sandbox repos), EXECUTES its
commands and checks the repo state. Students run locally with MLX; the teacher (Muse Wonder) is the reference.

Adoption rule: a candidate adapter enters the roster only if its held-out pass rate >= ADOPT_THRESHOLD and it is within
MAX_GAP_TO_TEACHER of the teacher; otherwise it is rolled back. Every decision is appended to roster.json's history.
Run with the MLX python:  ~/.local/share/uv/tools/mlx-lm/bin/python distill/evaluate.py <name> [--adapter adapters/v1] [--teacher]
"""

import argparse
import json
import sys
import time
from pathlib import Path

from scenarios import INTENTS, build, check, clean_commands, prompt_messages, run_commands

HERE = Path(__file__).resolve().parent
DATA, ROSTER = HERE / "data", HERE / "roster.json"
BASE_MODEL = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
MAX_TOKENS = 120
# Real phrasings are often ambiguous ("commit that one"), so the bar is relative: match the cloud teacher (within
# 5 points) on the same held-out cases, with an absolute floor.
ADOPT_THRESHOLD = 0.6
MAX_GAP_TO_TEACHER = 0.05


def student_fn(adapter: str | None):
	from mlx_lm import generate, load

	model, tokenizer = load(BASE_MODEL, adapter_path=adapter)

	def answer(messages: list[dict]) -> str:
		prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
		return generate(model, tokenizer, prompt=prompt, max_tokens=MAX_TOKENS, verbose=False)

	return answer


def teacher_fn():
	from gen_data import teacher

	return lambda messages: teacher(messages)


def evaluate(answer) -> dict:
	cases = json.loads((DATA / "heldout.json").read_text())
	results = []
	for case in cases:
		scenario = build(case["intent"], case["seed"])
		try:
			started = time.time()
			commands = clean_commands(answer(prompt_messages(scenario, case["request"])))
			seconds = round(time.time() - started, 2)
			ran, error = run_commands(scenario, commands)
			passed, reason = check(scenario) if ran else (False, error)
		finally:
			scenario.cleanup()
		results.append({**case, "commands": commands, "passed": passed, "reason": reason, "seconds": seconds})
	by_intent = {i: sum(r["passed"] for r in results if r["intent"] == i) / max(1, sum(r["intent"] == i for r in results)) for i in INTENTS}
	return {
		"pass_rate": round(sum(r["passed"] for r in results) / len(results), 3),
		"by_intent": {k: round(v, 2) for k, v in by_intent.items()},
		"avg_seconds": round(sum(r["seconds"] for r in results) / len(results), 2),
		"failures": [{k: r[k] for k in ("intent", "request", "commands", "reason")} for r in results if not r["passed"]],
	}


def record(name: str, adapter: str | None, report: dict) -> None:
	roster = json.loads(ROSTER.read_text()) if ROSTER.exists() else {"active": None, "history": []}
	teacher_rate = next((h["pass_rate"] for h in reversed(roster["history"]) if h["name"] == "teacher"), None)
	decision = "reference"
	if adapter:
		# A candidate must clear the floor, match the cloud teacher, AND not regress the currently active local model.
		active_rate = (roster.get("active") or {}).get("pass_rate", 0.0)
		good_enough = (
			report["pass_rate"] >= ADOPT_THRESHOLD
			and (teacher_rate is None or report["pass_rate"] >= teacher_rate - MAX_GAP_TO_TEACHER)
			and report["pass_rate"] >= active_rate
		)
		decision = "adopted" if good_enough else "rolled_back"
		if good_enough:
			roster["active"] = {"name": name, "adapter": adapter, "base": BASE_MODEL, "intents": list(INTENTS), "pass_rate": report["pass_rate"]}
	roster["history"].append({"name": name, "adapter": adapter, "pass_rate": report["pass_rate"], "by_intent": report["by_intent"],
		"avg_seconds": report["avg_seconds"], "decision": decision, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
	ROSTER.write_text(json.dumps(roster, indent=1))
	print(f"{name}: held-out pass {report['pass_rate']:.0%} {report['by_intent']} avg {report['avg_seconds']}s -> {decision.upper()}")


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("name")
	parser.add_argument("--adapter")
	parser.add_argument("--teacher", action="store_true")
	args = parser.parse_args()
	answer = teacher_fn() if args.teacher else student_fn(args.adapter)
	report = evaluate(answer)
	(DATA / f"eval-{args.name}.json").write_text(json.dumps(report, indent=1))
	record(args.name, None if args.teacher or not args.adapter else args.adapter, report)
	for failure in report["failures"][:5]:
		print("  FAIL", failure["intent"], "|", failure["request"][:50], "|", failure["commands"][:3], "|", failure["reason"][:80])


if __name__ == "__main__":
	sys.exit(main())
