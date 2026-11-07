"""Step 1 — mine the user's real Claude Code sessions for repetitive git-mechanics requests.

A cheap keyword prefilter, then SubQ decides per message whether it is routine git mechanics a tiny local model could
handle with a few shell commands, and which intent it is. Output: distill/data/mined.json
Usage: python3 distill/mine.py
"""

import json
import os
import re
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SESSIONS_GLOB_ROOT = Path.home() / ".claude" / "projects"
OUT = Path(__file__).resolve().parent / "data" / "mined.json"
SUBQ_URL = "https://api.subq.ai/v1/systemone"
SUBQ_MODEL = "subq-snap-1.1"
MAX_WORDS = 25
PREFILTER = re.compile(r"\b(git|commit|push|branch|stash|merge|rebase|revert|undo|gitignore|pull)\b", re.I)
CONFIDENCE_FLOOR = 0.6
WORKERS = 8

INTENTS = {
	"commit": "Commit the current changes (no push).",
	"commit_push": "Commit the current changes and push them (e.g. 'commit and push', 'push it' with uncommitted work).",
	"push": "Push commits that are already made.",
	"stash": "Stash / set aside uncommitted changes.",
	"undo_last_commit": "Undo the last commit but keep the changes.",
	"not_git_mechanics": "Anything else: questions, code work, git used only incidentally, or not doable with a few git commands.",
}

QUESTION = {
	"intent": {
		"type": "choice",
		"instructions": "This is one message a user sent to a coding agent. Is it a routine git-mechanics request that a few "
		"git shell commands fully satisfy, and if so which one?",
		"criteria": INTENTS,
	}
}


def user_messages() -> list[str]:
	messages = []
	for path in SESSIONS_GLOB_ROOT.glob("*/*.jsonl"):
		for line in path.read_text(errors="ignore").splitlines():
			try:
				entry = json.loads(line)
			except json.JSONDecodeError:
				continue
			if entry.get("type") != "user":
				continue
			content = (entry.get("message") or {}).get("content")
			if isinstance(content, list):
				if any(isinstance(p, dict) and p.get("type") == "tool_result" for p in content):
					continue
				content = " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
			if not isinstance(content, str):
				continue
			text = content.strip()
			if not text or text.startswith("<") or len(text.split()) > MAX_WORDS:
				continue
			messages.append(text)
	return messages


def keep(text: str) -> bool:
	text = text.strip()
	return bool(text) and not text.startswith(("<", "#")) and len(text.split()) <= MAX_WORDS and bool(PREFILTER.search(text))


def codex_messages() -> list[str]:
	"""User turns from Codex rollouts; only lines mentioning a git keyword are parsed."""
	messages = []
	for path in (Path.home() / ".codex" / "sessions").rglob("rollout-*.jsonl"):
		for line in path.read_text(errors="ignore").splitlines():
			if '"role":"user"' not in line or not PREFILTER.search(line):
				continue
			payload = json.loads(line).get("payload") or {}
			if payload.get("type") != "message" or payload.get("role") != "user":
				continue
			# Each content part separately: injected context (AGENTS.md, environment) arrives as its own long parts.
			for part in payload.get("content", []):
				text = part.get("text", "") if isinstance(part, dict) else ""
				if keep(text):
					messages.append(text.strip())
	return messages


def opencode_messages(db_copy: Path) -> list[str]:
	"""User text parts from a read-only COPY of OpenCode's database, filtered in SQL by keyword first."""
	import sqlite3

	if not db_copy.exists():
		return []
	connection = sqlite3.connect(f"file:{db_copy}?mode=ro", uri=True)
	keyword_sql = " OR ".join(f"lower(json_extract(p.data,'$.text')) LIKE '%{word}%'" for word in ("git", "commit", "push", "branch", "stash", "merge", "revert", "undo"))
	rows = connection.execute(
		"SELECT json_extract(p.data,'$.text') FROM part p JOIN message m ON m.id = p.message_id "
		f"WHERE json_extract(m.data,'$.role') = 'user' AND json_extract(p.data,'$.type') = 'text' AND ({keyword_sql})"
	).fetchall()
	connection.close()
	return [text.strip() for (text,) in rows if text and keep(text)]


def classify(text: str) -> dict:
	body = json.dumps({"model": SUBQ_MODEL, "state": {"message": text}, "questions": QUESTION}).encode()
	request = urllib.request.Request(
		SUBQ_URL, data=body, method="POST",
		headers={"Authorization": f"Bearer {os.environ['SUBQ_API_KEY']}", "Content-Type": "application/json"},
	)
	try:
		with urllib.request.urlopen(request, timeout=30) as response:
			answer = json.load(response)["answers"]["intent"]
	except Exception as error:  # network/API failure: skip this message, keep mining
		return {"text": text, "intent": "error", "confidence": 0.0, "error": str(error)}
	return {"text": text, "intent": answer["choice"], "confidence": round(answer["confidence"], 3)}


def main() -> None:
	opencode_db = Path(os.environ.get("OPENCODE_DB_COPY", ""))
	sources = {"claude": user_messages(), "codex": codex_messages(), "opencode": opencode_messages(opencode_db) if opencode_db.name else []}
	print({name: len([t for t in texts if PREFILTER.search(t)]) for name, texts in sources.items()})
	candidates = [text for texts in sources.values() for text in texts if PREFILTER.search(text)]
	unique = list(dict.fromkeys(candidates))
	with ThreadPoolExecutor(WORKERS) as pool:
		results = list(pool.map(classify, unique))
	git = [r for r in results if r["intent"] in INTENTS and r["intent"] != "not_git_mechanics" and r["confidence"] >= CONFIDENCE_FLOOR]
	counts = Counter(r["intent"] for r in git)
	repeats = Counter(text for text in candidates if text in {r["text"] for r in git})
	OUT.parent.mkdir(parents=True, exist_ok=True)
	OUT.write_text(json.dumps({"scanned_candidates": len(candidates), "unique": len(unique), "git_mechanics": git, "by_intent": counts}, indent=1))
	print(f"user messages w/ git keywords: {len(candidates)} ({len(unique)} unique) -> git mechanics: {len(git)} ({sum(repeats.values())} incl. repeats)")
	for intent, count in counts.most_common():
		print(f"  {intent}: {count}")


if __name__ == "__main__":
	main()
