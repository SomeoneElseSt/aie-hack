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

## Reproduce

```bash
python3 evals/demo/run_demo.py wonder meta/muse-wonder-1.0
python3 evals/demo/run_demo.py naive lanes/naive
python3 evals/demo/run_demo.py lanes lanes/auto
python3 evals/demo/grade_demo.py wonder naive lanes
```
