"""Replay the 12-turn Splitwise-lite session through Pi under one config, in one continuous session.

Usage: python3 evals/demo/run_demo.py <config> <model>
  wonder  meta/muse-wonder-1.0   always the biggest model
  naive   lanes/naive            SubQ routing, one shared thread, no scratchpad (cache lost on switch)
  lanes   lanes/auto             our harness
Writes evals/demo/runs/<config>/: repo/ (the app, with origin = remote.git), replies/, sessions/, turns.json
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
RUN_SH = DEMO_DIR.parents[1] / "run.sh"
TURN_TIMEOUT_SEC = 1200


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def prepare(run_dir: Path) -> Path:
    if run_dir.exists():
        shutil.rmtree(run_dir)
    repo, remote = run_dir / "repo", run_dir / "remote.git"
    for path in (repo, run_dir / "replies", run_dir / "sessions"):
        path.mkdir(parents=True)
    git("init", "-q", "--bare", "-b", "main", str(remote), cwd=run_dir)
    git("init", "-q", "-b", "main", cwd=repo)
    git("remote", "add", "origin", str(remote), cwd=repo)
    return repo


def run_turn(run_dir: Path, repo: Path, model: str, prompt: str, first: bool) -> tuple[str, int]:
    args = [str(RUN_SH), "--model", model, "--session-dir", str(run_dir / "sessions"), "-p", prompt]
    if not first:
        args.insert(1, "--continue")
    # Isolated Pi config: no user extensions (e.g. Murmur, which starts its own turn) or skills.
    env = {**os.environ, "PI_CODING_AGENT_DIR": str(run_dir / "pi-agent")}
    started = time.time()
    try:
        result = subprocess.run(args, cwd=repo, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=TURN_TIMEOUT_SEC)
        reply = result.stdout + (f"\n[stderr]\n{result.stderr}" if result.returncode != 0 else "")
    except subprocess.TimeoutExpired:
        reply = "TURN TIMEOUT"
    return reply, round(time.time() - started)


def main() -> None:
    config, model = sys.argv[1], sys.argv[2]
    run_dir = DEMO_DIR / "runs" / config
    repo = prepare(run_dir)
    prompts = json.loads((DEMO_DIR / os.environ.get("DEMO_PROMPTS", "prompts.json")).read_text())
    turns = []
    for index, item in enumerate(prompts):
        reply, seconds = run_turn(run_dir, repo, model, item["prompt"], index == 0)
        (run_dir / "replies" / f"{index + 1:02d}.txt").write_text(reply)
        turns.append({"turn": index + 1, "seconds": seconds, "prompt": item["prompt"]})
        (run_dir / "turns.json").write_text(json.dumps({"config": config, "model": model, "turns": turns}, indent=2))
        print(f"{config} turn {index + 1}/{len(prompts)} done in {seconds}s", flush=True)


if __name__ == "__main__":
    main()
