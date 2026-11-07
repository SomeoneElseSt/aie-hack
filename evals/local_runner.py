"""Run an EvoCode-Bench task locally (no Docker): replay each round's instruction through our Pi in one
continuous session, then score the round with the task's own cumulative test.sh.

Container paths are remapped: /app -> <run>/app, /logs/verifier -> <run>/verifier/<round>.
Usage: python3 evals/local_runner.py <task_dir> <config_name> <model>   (e.g. lanes lanes/auto)
"""

import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_SH = REPO_ROOT / "run.sh"
RUNS_DIR = REPO_ROOT / "evals" / "runs"
AGENT_TIMEOUT_SEC = 1500
TEST_TIMEOUT_SEC = 600
# GNU tools first: the tests were written for Ubuntu (bash 4+ associative arrays, GNU coreutils/sed).
GNU_PATH = ":".join([
    "/opt/homebrew/bin",
    "/opt/homebrew/opt/coreutils/libexec/gnubin",
    "/opt/homebrew/opt/gnu-sed/libexec/gnubin",
])


def round_names(task_dir: Path) -> list[str]:
    task = tomllib.loads((task_dir / "task.toml").read_text())
    return [step["name"] for step in task["steps"]]


def remap(text: str, app_dir: Path, verifier_dir: Path) -> str:
    return text.replace("/logs/verifier", str(verifier_dir)).replace("/app", str(app_dir))


def run_agent(app_dir: Path, session_dir: Path, model: str, instruction: str, first: bool, log_path: Path) -> int:
    args = [str(RUN_SH), "--model", model, "--session-dir", str(session_dir), "-p", instruction]
    # Isolated Pi config: no user-installed extensions (e.g. Murmur's, which starts its own turn) or skills.
    env = {**os.environ, "PI_CODING_AGENT_DIR": str(session_dir.parent / "pi-agent")}
    if not first:
        args.insert(1, "--continue")
    with log_path.open("a") as log:
        log.write(f"\n===== {time.strftime('%H:%M:%S')} =====\n")
        log.flush()
        try:
            result = subprocess.run(args, cwd=app_dir, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=AGENT_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            log.write("AGENT TIMEOUT\n")
            return -1
    return result.returncode


def run_test(task_dir: Path, round_name: str, app_dir: Path, verifier_dir: Path, log_path: Path) -> float:
    verifier_dir.mkdir(parents=True, exist_ok=True)
    tests_src = task_dir / "steps" / round_name / "tests"
    tests_dst = verifier_dir / "tests"
    shutil.copytree(tests_src, tests_dst, dirs_exist_ok=True)
    test_sh = tests_dst / "test.sh"
    test_sh.write_text(remap(test_sh.read_text(), app_dir, verifier_dir))
    env = {**os.environ, "PATH": f"{GNU_PATH}:{os.environ['PATH']}"}
    with log_path.open("a") as log:
        try:
            subprocess.run(["/opt/homebrew/bin/bash", str(test_sh)], cwd=app_dir, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=TEST_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            log.write("TEST TIMEOUT\n")
    reward_file = verifier_dir / "reward.txt"
    if not reward_file.exists():
        return 0.0
    return float(reward_file.read_text().strip() or 0)


def main() -> None:
    task_dir, config, model = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3]
    run_dir = RUNS_DIR / task_dir.name / config
    if run_dir.exists():
        shutil.rmtree(run_dir)
    app_dir, session_dir = run_dir / "app", run_dir / "sessions"
    app_source = task_dir / "environment" / "app"
    if app_source.exists():
        shutil.copytree(app_source, app_dir)
    app_dir.mkdir(parents=True, exist_ok=True)
    session_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=app_dir)

    results = []
    for index, round_name in enumerate(round_names(task_dir)):
        verifier_dir = run_dir / "verifier" / round_name
        instruction = remap((task_dir / "steps" / round_name / "instruction.md").read_text(), app_dir, verifier_dir)
        started = time.time()
        exit_code = run_agent(app_dir, session_dir, model, instruction, index == 0, run_dir / "agent.log")
        agent_sec = round(time.time() - started)
        reward = run_test(task_dir, round_name, app_dir, verifier_dir, run_dir / "tests.log")
        results.append({"round": round_name, "reward": reward, "agent_exit": exit_code, "agent_sec": agent_sec})
        (run_dir / "results.json").write_text(json.dumps({"task": task_dir.name, "config": config, "model": model, "rounds": results}, indent=2))
        print(f"{task_dir.name} {config} {round_name}: reward={reward} ({agent_sec}s)", flush=True)


if __name__ == "__main__":
    main()
