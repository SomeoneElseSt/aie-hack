# Demo benchmark results — Splitwise-lite, 12 turns

Same 12 scripted prompts (`prompts.json`, modelled on real session patterns: small setup/status turns mixed with big
build turns), replayed through Pi under three setups, all on Meta's API. Graded by a 12-point rubric: 5 objective
checks (commits, pushed, the app's own tests, two quick answers) + 7 items verified by an independent judge
(`google/gemini-pro-latest`) that drives the finished app from the outside. Costs are provider-reported usage plus
router overhead (SubQ + scratchpad writer, ~$0.015/session). Raw data: `results/`.

Setups:
- **wonder**: `meta/muse-wonder-1.0` on every turn.
- **naive**: SubQ picks the model per turn, one shared thread, no scratchpad (cache lost on every switch).
- **lanes**: our harness. *Before the fix*, every lane saw only its own turns; *after the fix*, the complex lane keeps
  the full conversation (cheap turns appended to its thread), cheap lanes stay isolated.

## Per run

| Run | Setup | Rubric | Small turns | Big turns | Total | Time |
|---|---|---|---|---|---|---|
| wonder | Always Wonder | 12/12 | $0.246 | $0.978 | $1.224 | 334s |
| wonder2 | Always Wonder | 12/12 | $0.271 | $1.095 | $1.366 | 279s |
| naive | Naive switching | 12/12 | $0.188 | $1.604 | $1.807 | 428s |
| lanes | Lanes, before fix | 12/12 | $0.065 | $1.566 | $1.647 | 495s |
| lanes2 | Lanes, after fix | 11/12 | $0.072 | $1.166 | $1.253 | 335s |
| lanes3 | Lanes, after fix | 12/12 | $0.111 | $1.186 | $1.310 | 344s |

Small turns = 1, 4, 5, 7, 9, 10, 12. Big turns = 2, 3, 6, 8, 11.

## Averages

| | Always Wonder | Lanes after fix | Naive switching |
|---|---|---|---|
| Rubric | 12/12 | 11.5/12 | 12/12 |
| Small turns | $0.259 | $0.092 (−65%) | $0.188 |
| Big turns | $1.037 | $1.176 (+13%) | $1.604 |
| **Total** | **$1.295** | **$1.282 (−1%)** | **$1.807 (+40%)** |
| Time | 307s | 340s (+11%) | 428s |

## Findings

- Small turns are ~65% cheaper on lanes (83% cheaper per small turn in run 1) at equal quality.
- The first design lost on big turns: the isolated complex lane re-read the project (2× file reads, 2–5× tool output).
  Letting the complex lane keep the full conversation cut that overhead from ~60% to ~13%.
- After the fix, total cost is break-even with always-Wonder; the two Wonder runs alone differ by 12%, so the remaining
  gap is within run-to-run noise. Lanes is ~29% cheaper than naive switching (the cache-thrash baseline).
- The one point lost (lanes2): the cheap straightforward lane kept `settle-up` as an alias when asked to rename it.
- Time: big turns take the same time; small turns look slower mostly because the benchmark waits for the
  post-turn scratchpad update before exiting each run (in interactive use it runs after the reply).

## Google models (same 12 turns)

Lanes = Gemini Flash-Lite / Flash / Pro (`LANES_MAPPING=google`). Judge: `meta/muse-wonder-1.0` (different family).

| Run | Setup | Rubric | Small turns | Big turns | Total | Requests | Time |
|---|---|---|---|---|---|---|---|
| gpro | Gemini Pro always | 11/12 | $0.238 | $0.441 | $0.679 | 30 | 240s |
| gnaive | Naive switching | 11/12 | $0.083 | $0.716 | $0.805 | 34 | 282s |
| glanes | Lanes | 11/12 | $0.395 | $0.774 | $1.180 | 120 | 461s |
| glanes2 | Lanes | 11/12 | $0.287 | $0.729 | $1.027 | 85 | 410s |

All four missed the same item (the SQLite answer). Lanes cost **+63%** vs Gemini Pro always: Gemini Flash is only
~25% cheaper than Pro and loops far more (49–81 requests vs Pro's 30 for the whole session). **The router only pays
off when the cheap models are much cheaper and about as efficient** — true for Meta's lineup, not Google's.

## Thinking-level routing (one top model, SubQ picks effort)

Same model on every turn (no model switching), SubQ maps one_shot → low, straightforward → medium, complex → high
(`LANES_MAPPING=meta-effort` / `google-effort` with `lanes/naive`).

| Provider | Setup | Rubric | Cost | vs always-high | Time |
|---|---|---|---|---|---|
| Meta (Wonder) | Medium, always (avg of 2) | 12/12 | $1.295 | +6% | 307s |
| Meta (Wonder) | High, always | 12/12 | $1.225 | — | 273s |
| Meta (Wonder) | SubQ picks effort | 12/12 | $1.388 | +13% | 283s |
| Google (Pro) | Medium, always | 11/12 | $0.679 | −19% | 240s |
| Google (Pro) | High, always | 12/12 | $0.835 | — | 277s |
| Google (Pro) | SubQ picks effort | 11/12 | $0.681 | −18% | 266s |

Cache hit on turns right after a thinking-level change vs turns without one: Meta 92% vs 99%, Google 66% vs 87%.
Switching effort partly breaks the cache, and picking effort per turn does not beat one fixed level.

## EvoCode-Bench (hard, all-complex sessions), lanes after the fix

| Task | Setup | Pass | Cost |
|---|---|---|---|
| nlsolve (5 rounds) | Always Wonder | 5/5 | $3.51 |
| nlsolve | Lanes, before fix | 2/5 | $3.39 |
| nlsolve | Lanes, after fix | 5/5 | $2.64 |
| repro-verify (7 rounds) | Always Wonder | 0/7 | $3.20 |
| repro-verify | Lanes, before fix | 0/7 | $2.63 |
| repro-verify | Lanes, after fix | 7/7 | $2.95 |

Nearly every round routes to the complex lane, so these show the fix removed the regression on hard sessions; with one
run each, cost and pass differences are mostly run-to-run variation. Summary: `evals/results/evocode-summary.txt`.

## Reproduce

```bash
python3 evals/demo/run_demo.py wonder meta/muse-wonder-1.0
python3 evals/demo/run_demo.py naive lanes/naive
python3 evals/demo/run_demo.py lanes lanes/auto
python3 evals/demo/grade_demo.py wonder naive lanes
```


## Wonder + local model

Same 12-turn workflow with `prompts-git.json`. Always Wonder uses the existing `gitw`/`gitw2` baseline;
Wonder + local uses `gitwl3`/`gitwl4`, run sequentially with `LANES_LOCAL=force` and adopted Qwen 1.5B adapter v1
served through MLX on port 8089. Git turns are **3, 5, 8, 10**. The mixed request on turn 12
("rename settle-up to settle. then commit and push") stays on Wonder.

| Setup (two-run average) | Rubric | Git-turn cost | Other-turn cost | Total | Total change | Time | Local git turns |
|---|---|---|---|---|---|---|---|
| Always Wonder (`gitw`, `gitw2`) | 11/11 | $0.096 | $1.363 | $1.459 | baseline | 308s | 0/4 |
| Wonder + local (`gitwl3`, `gitwl4`) | 11/11 | $0.000 | $1.396 | $1.396 | −4.3% | 293s | 4/4 |

| Run | Rubric | Git-turn cost | Other-turn cost | Total | Time | Local git turns |
|---|---|---|---|---|---|---|
| gitwl3 | 11/11 | $0.000 | $1.480 | $1.480 | 284s | 4/4 |
| gitwl4 | 11/11 | $0.000 | $1.312 | $1.312 | 302s | 4/4 |

All eight git turns executed successfully locally (`type: "local"`, `ok: true`), with no cloud usage on those
turns. Both mixed rename requests logged `local_skip: not_git` and ran on Wonder. The local classifier now
retries once with a 60-second timeout per attempt and logs every skip reason, including API/response failures.
Git-turn cloud cost fell 100%; total cost fell 4.3% and time fell 4.9%. With only two runs, the total-cost difference
is small relative to run-to-run variation.

Costs follow `costsplit.py`: provider-reported cloud usage, excluding local compute and the local lane's SubQ
intent-classification calls (not recorded by the existing cost accounting). Baseline rubric comes from the task's
recorded 11/11 scores. New independent judge reports: `results/report-wonder-local.json`; raw runs:
`runs/gitwl3/` and `runs/gitwl4/` (gitignored). Grading uses `UV_CACHE_DIR=/tmp/aie-hack-uv-cache` because the sandbox
cannot write UV's default cache; the initial `gitwl4` test-check failure was a cache-permission error, and all 85
of its tests pass with the writable cache.
