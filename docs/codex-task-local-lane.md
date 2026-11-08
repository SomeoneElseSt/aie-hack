# Task for Codex: make the local git lane reliable, then rerun the Wonder + local benchmark

Repo: /Users/steve/Documents/Files/code/aie-hack. Read docs/PROJECT.md and distill/README.md first. Keys are in .env
(source it: `set -a; source .env; set +a`). A local MLX server must be running on port 8089 (check with
`curl -s localhost:8089/v1/models`; if down: `~/.local/bin/mlx_lm.server --model mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit --adapter-path distill/models/v1 --port 8089 &`).

## Problem
`extensions/lane-router/local-lane.ts` (Pi extension, `input` hook) should hand routine git requests ("commit it",
"commit and push", "commit and push it in my style, no coauthor") to the local model. In benchmark runs several such
turns silently skipped the local model and went to the cloud. SubQ classifies them correctly (~99% commit_push) when
called directly, so the skip is likely a SubQ fetch failure/timeout under parallel load, but the handler returns
`continue` without logging why.

## Do
1. In `local-lane.ts`: log every skip reason to `.lanes/log.jsonl` as `{"type":"local_skip","reason":...,"prompt":...}`
   (no roster, not router/forced, too long, subq_error, not_git, low_confidence). Retry the SubQ call once on failure
   (and raise its timeout). Keep code flat, no throws, small functions.
2. Mixed requests like "rename settle-up to settle. then commit and push" must stay on the cloud: tighten the SubQ
   question/criteria so requests that also ask for code changes are `not_git_mechanics`.
3. Rerun, ONE AT A TIME (not in parallel):
   `DEMO_PROMPTS=prompts-git.json LANES_LOCAL=force python3 evals/demo/run_demo.py gitwl3 meta/muse-wonder-1.0`
   then the same for `gitwl4`. Verify 4 of 4 git turns (3,5,8,10) ran locally (`grep '"type":"local"'` in
   `evals/demo/runs/<run>/repo/.lanes/log.jsonl`); if not, read the local_skip reasons and fix.
4. Grade: `DEMO_PROMPTS=prompts-git.json python3 evals/demo/grade_demo.py gitwl3 gitwl4` and costs:
   `python3 evals/demo/costsplit.py 3,5,8,10 gitw gitw2 gitwl3 gitwl4`.
5. Write the results as a markdown table into `evals/demo/RESULTS.md` (new section "Wonder + local model"):
   Always Wonder (avg gitw, gitw2: $1.459, 308s, 11/11) vs Wonder + local (avg gitwl3, gitwl4): rubric, git-turn cost,
   other-turn cost, total, % change, time, local turns. Then `git add` only the files you changed and commit
   ("Make local git lane reliable; Wonder + local results"), and push to origin master. Never commit .env or
   distill/data/.
