"""Per-run cost split (given turn set vs the rest), time, router overhead and local turns. Usage: costsplit.py <turns,csv> run..."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade_demo import costs

BASE = Path(__file__).resolve().parent / "runs"


def split(run: str, group: set[int]) -> tuple[float, float]:
	inside = outside = 0.0
	# Turn index = count of real user prompts; locally handled turns add a custom message, not a user message.
	turn_prompts = [t["prompt"] for t in json.loads((BASE / run / "turns.json").read_text())["turns"]]
	for session in (BASE / run / "sessions").glob("*.jsonl"):
		turn = 0
		for line in session.read_text().splitlines():
			entry = json.loads(line)
			message = entry.get("message") or {}
			if entry.get("type") == "message" and message.get("role") == "user":
				text = json.dumps(message.get("content"))
				# Longest full prompt contained in the message wins (short prompts like "commit and push" are substrings of longer ones).
				matches = sorted((len(p), i + 1) for i, p in enumerate(turn_prompts) if json.dumps(p)[1:-1] in text)
				turn = matches[-1][1] if matches else turn
			if entry.get("type") == "message" and message.get("role") == "assistant" and "usage" in message:
				cost = message["usage"]["cost"]["total"]
				inside, outside = (inside + cost, outside) if turn in group else (inside, outside + cost)
	return inside, outside


def local_turns(run: str) -> list[str]:
	log = BASE / run / "repo" / ".lanes" / "log.jsonl"
	if not log.exists():
		return []
	return [json.loads(l)["prompt"] for l in log.read_text().splitlines() if '"type": "local"' in l or '"type":"local"' in l]


group = {int(x) for x in sys.argv[1].split(",")}
for run in sys.argv[2:]:
	inside, outside = split(run, group)
	total = costs(BASE / run)
	seconds = sum(t["seconds"] for t in json.loads((BASE / run / "turns.json").read_text())["turns"])
	print(f"{run}|group {inside:.3f}|rest {outside:.3f}|router {total['router_overhead']:.3f}|total {total['total_cost']:.3f}|{seconds}s|local {local_turns(run)}")
