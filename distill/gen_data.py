"""Step 2 — build the training and held-out sets by distilling the teacher (Muse Wonder).

Phrasings: the user's real mined requests plus teacher-written paraphrases in the same voice. For each (phrasing,
fresh sandbox repo) the teacher writes the commands; we EXECUTE them and keep only examples whose result passes the
intent's checker (verified distillation). Held-out = real phrasings + scenario seeds never used in training.
Usage: python3 distill/gen_data.py
"""

import json
import os
import random
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scenarios import INTENTS, build, check, clean_commands, prompt_messages, run_commands

DATA = Path(__file__).resolve().parent / "data"
META_URL = "https://api.meta.ai/v1/responses"
TEACHER = "muse-wonder-1.0"
PARAPHRASES_PER_INTENT = 12
TRAIN_PER_INTENT = 40
HELDOUT_PER_INTENT = 10
HELDOUT_SEED_OFFSET = 100_000
WORKERS = 8


def teacher(messages: list[dict], effort: str = "low") -> str:
	body = {"model": TEACHER, "input": messages, "reasoning": {"effort": effort}}
	request = urllib.request.Request(
		META_URL, data=json.dumps(body).encode(), method="POST",
		headers={"Authorization": f"Bearer {os.environ['META_API_KEY']}", "Content-Type": "application/json"},
	)
	with urllib.request.urlopen(request, timeout=120) as response:
		result = json.load(response)
	texts = [c.get("text", "") for item in result.get("output", []) if item.get("type") == "message" for c in item.get("content", [])]
	return "\n".join(texts)


def paraphrases(intent: str, real: list[str]) -> list[str]:
	examples = "\n".join(f"- {text}" for text in real[:6]) or "- commit and push it"
	prompt = (
		f"Here are real messages a developer sent to their coding agent for the git action '{intent}':\n{examples}\n\n"
		f"Write {PARAPHRASES_PER_INTENT} NEW messages this same person might send for the same action: same terse, casual "
		"voice (lowercase, typos ok, sometimes mid-thought). One per line, no numbering, no quotes."
	)
	lines = teacher([{"role": "user", "content": prompt}]).splitlines()
	return [line.strip("-• \t") for line in lines if line.strip()][:PARAPHRASES_PER_INTENT]


def make_example(job: tuple[str, str, int]) -> dict | None:
	intent, request, seed = job
	scenario = build(intent, seed)
	try:
		messages = prompt_messages(scenario, request)
		commands = clean_commands(teacher(messages))
		ran, error = run_commands(scenario, commands)
		passed, reason = check(scenario) if ran else (False, error)
		if not passed:
			return None
		return {"messages": messages + [{"role": "assistant", "content": "\n".join(commands)}]}
	except Exception:  # teacher/API failure: drop this example
		return None
	finally:
		scenario.cleanup()


def main() -> None:
	mined = json.loads((DATA / "mined.json").read_text())["git_mechanics"]
	real = {intent: [m["text"] for m in mined if m["intent"] == intent] for intent in INTENTS}
	rng = random.Random(7)

	with ThreadPoolExecutor(len(INTENTS)) as pool:
		generated = dict(zip(INTENTS, pool.map(lambda i: paraphrases(i, real[i]), INTENTS)))

	train_jobs, heldout = [], []
	for intent in INTENTS:
		real_texts = real[intent][:]
		rng.shuffle(real_texts)
		held_real, train_real = real_texts[: len(real_texts) // 2], real_texts[len(real_texts) // 2 :]
		train_pool = train_real + generated[intent][:-3]
		held_pool = (held_real + generated[intent][-3:]) or generated[intent][-3:]
		for i in range(TRAIN_PER_INTENT):
			train_jobs.append((intent, rng.choice(train_pool), rng.randint(0, HELDOUT_SEED_OFFSET - 1)))
		for i in range(HELDOUT_PER_INTENT):
			heldout.append({"intent": intent, "request": held_pool[i % len(held_pool)], "seed": HELDOUT_SEED_OFFSET + i + 1000 * INTENTS.index(intent)})

	with ThreadPoolExecutor(WORKERS) as pool:
		examples = [e for e in pool.map(make_example, train_jobs) if e]
	rng.shuffle(examples)
	split = max(1, len(examples) // 10)
	(DATA / "train.jsonl").write_text("".join(json.dumps(e) + "\n" for e in examples[split:]))
	(DATA / "valid.jsonl").write_text("".join(json.dumps(e) + "\n" for e in examples[:split]))
	(DATA / "heldout.json").write_text(json.dumps(heldout, indent=1))
	(DATA / "phrasings.json").write_text(json.dumps({"real": real, "generated": generated}, indent=1))
	print(f"teacher examples kept (verified by execution): {len(examples)}/{len(train_jobs)}; held-out cases: {len(heldout)}")


if __name__ == "__main__":
	main()
