"""Sandbox git repos in a given state, the context string a model sees, and an executable checker per intent."""

import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

INTENTS = ("commit", "commit_push", "push", "undo_last_commit")
COMMAND_TIMEOUT_SEC = 20
# Refuse anything that could reach outside the sandbox repo.
FORBIDDEN = ("sudo", "rm -rf /", "rm -rf ~", "~/", "cd /", "cd ~", "curl ", "wget ", "--force", "push -f", "reset --hard origin")

SYSTEM_PROMPT = (
	"You are a git assistant inside the user's repository. Given the repo state and the user's request, reply with ONLY "
	"the shell commands to run, one per line. No explanations, no code fences. Commit messages: short, lowercase, "
	"imperative, describing the change. Never add co-author lines. The remote is 'origin', the branch is shown in the state."
)

FILE_WORDS = ["parser", "ledger", "settle", "cli", "report", "utils", "config", "api", "models", "dashboard"]


def git(repo: Path, *args: str) -> str:
	return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True).stdout.strip()


@dataclass
class Scenario:
	intent: str
	root: Path
	repo: Path
	remote: Path
	head_before: str = ""
	changed_files: list[str] = field(default_factory=list)

	def cleanup(self) -> None:
		shutil.rmtree(self.root, ignore_errors=True)


def _write(repo: Path, name: str, rng: random.Random) -> None:
	(repo / name).write_text(f"def {name.split('.')[0]}():\n    return {rng.randint(1, 999)}\n")


def build(intent: str, seed: int) -> Scenario:
	rng = random.Random(seed)
	root = Path(tempfile.mkdtemp(prefix="gitsbx-"))
	repo, remote = root / "repo", root / "remote.git"
	subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
	repo.mkdir()
	git(repo, "init", "-q", "-b", "main")
	git(repo, "config", "user.email", "dev@example.com")
	git(repo, "config", "user.name", "Dev")
	git(repo, "remote", "add", "origin", str(remote))
	words = rng.sample(FILE_WORDS, 5)
	for word in words[:2]:
		_write(repo, f"{word}.py", rng)
	git(repo, "add", "-A")
	git(repo, "commit", "-q", "-m", "initial commit")
	git(repo, "push", "-q", "-u", "origin", "main")
	scenario = Scenario(intent, root, repo, remote)

	if intent in ("commit", "commit_push"):
		_write(repo, f"{words[0]}.py", rng)  # modify tracked
		_write(repo, f"{words[2]}.py", rng)  # new untracked
		scenario.changed_files = [f"{words[0]}.py", f"{words[2]}.py"]
	if intent == "push":
		for word in words[2 : 2 + rng.randint(1, 2)]:
			_write(repo, f"{word}.py", rng)
			git(repo, "add", "-A")
			git(repo, "commit", "-q", "-m", f"add {word}")
	if intent == "undo_last_commit":
		_write(repo, f"{words[3]}.py", rng)
		git(repo, "add", "-A")
		git(repo, "commit", "-q", "-m", f"add {words[3]}")
		scenario.changed_files = [f"{words[3]}.py"]
	scenario.head_before = git(repo, "rev-parse", "HEAD")
	return scenario


def context(scenario: Scenario) -> str:
	status = git(scenario.repo, "status", "--short", "--branch")
	log = git(scenario.repo, "log", "--oneline", "-3")
	return f"$ git status --short --branch\n{status}\n$ git log --oneline -3\n{log}"


def prompt_messages(scenario: Scenario, request: str) -> list[dict]:
	return [
		{"role": "system", "content": SYSTEM_PROMPT},
		{"role": "user", "content": f"{context(scenario)}\n\nRequest: {request}"},
	]


def clean_commands(text: str) -> list[str]:
	lines = [line.strip() for line in text.strip().splitlines()]
	return [line for line in lines if line and not line.startswith("```") and not line.startswith("#")]


def run_commands(scenario: Scenario, commands: list[str]) -> tuple[bool, str]:
	for command in commands:
		if any(bad in command for bad in FORBIDDEN):
			return False, f"refused: {command}"
		try:
			result = subprocess.run(["bash", "-c", command], cwd=scenario.repo, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SEC)
		except subprocess.TimeoutExpired:
			return False, f"timeout: {command}"
		if result.returncode != 0:
			return False, f"failed: {command}: {result.stderr.strip()[:200]}"
	return True, ""


def check(scenario: Scenario) -> tuple[bool, str]:
	repo = scenario.repo
	clean = git(repo, "status", "--porcelain") == ""
	head = git(repo, "rev-parse", "HEAD")
	remote_head = git(scenario.remote, "rev-parse", "main")
	message = git(repo, "log", "-1", "--format=%B")
	if scenario.intent in ("commit", "commit_push"):
		if not clean or head == scenario.head_before:
			return False, "changes not committed"
		committed = git(repo, "diff", "--name-only", f"{scenario.head_before}..HEAD").splitlines()
		if not set(scenario.changed_files) <= set(committed):
			return False, "not all changed files committed"
		if "co-authored-by" in message.lower():
			return False, "co-author line in commit message"
		if scenario.intent == "commit_push" and remote_head != head:
			return False, "not pushed"
		return True, ""
	if scenario.intent == "push":
		return (remote_head == head, "" if remote_head == head else "not pushed")
	if scenario.intent == "undo_last_commit":
		parent = git(repo, "rev-parse", f"{scenario.head_before}~1")
		if head != parent:
			return False, "last commit not undone"
		present = all((repo / name).exists() for name in scenario.changed_files)
		return (present, "" if present else "changes lost")
	return False, "unknown intent"
