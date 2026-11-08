# SubQ gate K-pass experiment

Strict profile; existing anthropic_claude-opus-4-5-20251101 judge labels. All probabilities are real API responses or existing original API cache entries; metrics are computed from these and judge labels.

A/B are even/odd positions in the full sorted PR list, exactly as subq_gate.py. Threshold grid and scoring reuse that script. Each incomplete variant/aggregation is excluded entirely; missing probabilities are never filled.

## Identical-request check

- https://github.com/ai-code-review-evaluation/discourse-graphite/pull/1: identical=True; changed probabilities=0/6; max absolute difference=0.
- https://github.com/ai-code-review-evaluation/discourse-graphite/pull/10: identical=True; changed probabilities=0/11; max absolute difference=0.
- https://github.com/ai-code-review-evaluation/discourse-graphite/pull/2: identical=True; changed probabilities=0/7; max absolute difference=0.

Pass definition: equivalent question/criteria variants, with fixed-seed comment shuffles after the original pass.

Identical responses in this check establish observed repeatability only, not universal determinism.

| tool | K | agg | held-out F1 gain (A→B, B→A, avg) | in-sample P/R/F1 |
|---|---|---|---|---|
| coderabbit | variant 1 | single | +0.0959, +0.1162, **+0.1061** | 0.5620 / 0.5540 / 0.5580 (threshold 0.75) |
| coderabbit | variant 2 | single | +0.0744, +0.1237, **+0.0991** | 0.5032 / 0.5612 / 0.5306 (threshold 0.55) |
| coderabbit | variant 3 | single | +0.0876, +0.1323, **+0.1099** | 0.5407 / 0.5252 / 0.5328 (threshold 0.75) |
| coderabbit | variant 4 | single | +0.0800, +0.1292, **+0.1046** | 0.5132 / 0.5612 / 0.5361 (threshold 0.65) |
| coderabbit | 1 | mean | +0.0959, +0.1162, **+0.1061** | 0.5620 / 0.5540 / 0.5580 (threshold 0.75) |
| coderabbit | 1 | min | +0.0959, +0.1162, **+0.1061** | 0.5620 / 0.5540 / 0.5580 (threshold 0.75) |
| coderabbit | 2 | mean | +0.1070, +0.1380, **+0.1225** | 0.5159 / 0.5827 / 0.5473 (threshold 0.60) |
| coderabbit | 2 | min | +0.0868, +0.1389, **+0.1129** | 0.5310 / 0.5540 / 0.5423 (threshold 0.55) |
| coderabbit | 4 | mean | +0.1007, +0.1569, **+0.1288** | 0.5270 / 0.5612 / 0.5436 (threshold 0.65) |
| coderabbit | 4 | min | +0.0665, +0.1260, **+0.0962** | 0.5481 / 0.5324 / 0.5401 (threshold 0.55) |
| copilot-v2 | variant 1 | single | +0.0667, +0.0638, **+0.0653** | 0.4656 / 0.6331 / 0.5366 (threshold 0.65) |
| copilot-v2 | variant 2 | single | unavailable: incomplete API responses | unavailable |
| copilot-v2 | variant 3 | single | +0.0629, +0.0859, **+0.0744** | 0.5283 / 0.6043 / 0.5638 (threshold 0.75) |
| copilot-v2 | variant 4 | single | unavailable: incomplete API responses | unavailable |
| copilot-v2 | 1 | mean | +0.0667, +0.0638, **+0.0653** | 0.4656 / 0.6331 / 0.5366 (threshold 0.65) |
| copilot-v2 | 1 | min | +0.0667, +0.0638, **+0.0653** | 0.4656 / 0.6331 / 0.5366 (threshold 0.65) |
| copilot-v2 | 2 | mean | unavailable: incomplete API responses | unavailable |
| copilot-v2 | 2 | min | unavailable: incomplete API responses | unavailable |
| copilot-v2 | 4 | mean | unavailable: incomplete API responses | unavailable |
| copilot-v2 | 4 | min | unavailable: incomplete API responses | unavailable |
| gemini-v2 | variant 1 | single | +0.0557, +0.0525, **+0.0541** | 0.7303 / 0.4676 / 0.5702 (threshold 0.80) |
| gemini-v2 | variant 2 | single | unavailable: incomplete API responses | unavailable |
| gemini-v2 | variant 3 | single | unavailable: incomplete API responses | unavailable |
| gemini-v2 | variant 4 | single | unavailable: incomplete API responses | unavailable |
| gemini-v2 | 1 | mean | +0.0557, +0.0525, **+0.0541** | 0.7303 / 0.4676 / 0.5702 (threshold 0.80) |
| gemini-v2 | 1 | min | +0.0557, +0.0525, **+0.0541** | 0.7303 / 0.4676 / 0.5702 (threshold 0.80) |
| gemini-v2 | 2 | mean | unavailable: incomplete API responses | unavailable |
| gemini-v2 | 2 | min | unavailable: incomplete API responses | unavailable |
| gemini-v2 | 4 | mean | unavailable: incomplete API responses | unavailable |
| gemini-v2 | 4 | min | unavailable: incomplete API responses | unavailable |
| sourcery | variant 1 | single | +0.0546, +0.0566, **+0.0556** | 0.6818 / 0.4317 / 0.5286 (threshold 0.80) |
| sourcery | variant 2 | single | unavailable: incomplete API responses | unavailable |
| sourcery | variant 3 | single | unavailable: incomplete API responses | unavailable |
| sourcery | variant 4 | single | unavailable: incomplete API responses | unavailable |
| sourcery | 1 | mean | +0.0546, +0.0566, **+0.0556** | 0.6818 / 0.4317 / 0.5286 (threshold 0.80) |
| sourcery | 1 | min | +0.0546, +0.0566, **+0.0556** | 0.6818 / 0.4317 / 0.5286 (threshold 0.80) |
| sourcery | 2 | mean | unavailable: incomplete API responses | unavailable |
| sourcery | 2 | min | unavailable: incomplete API responses | unavailable |
| sourcery | 4 | mean | unavailable: incomplete API responses | unavailable |
| sourcery | 4 | min | unavailable: incomplete API responses | unavailable |

Evaluated tools (unavailable configurations are marked above): coderabbit, copilot-v2, gemini-v2, sourcery

Invocation counters (HTTP attempts include retries; cache hits are not calls): {"successful_fresh_responses": 284, "observed_error_responses": 60, "confirmed_completed_HTTP_attempts": 344}

Failure details: [cache_kpass/run_summary.json](cache_kpass/run_summary.json), `errors` field; request-level events are also in kpass_run.log.

## Takeaways

- CodeRabbit mean: held-out gains K=1 +0.1061, K=2 +0.1225, K=4 +0.1288; K=4 versus K=1 +0.0228.
- CodeRabbit min: held-out gains K=1 +0.1061, K=2 +0.1129, K=4 +0.0962; K=4 versus K=1 -0.0098.
- Best CodeRabbit single variant is 3 (+0.1099); K=4 mean versus that single variant is +0.0189. Averaging shows an empirical scaling effect on these folds beyond the best individual prompt; minimum aggregation does not show consistent scaling. This is a fixed-fold comparison, not a significance test.

Framings and shuffle seeds are recorded in kpass.py; full fresh API responses and exact request bodies are preserved in cache_kpass/. Original pass cache reuse matches diff context and exact candidate keys; legacy cache files do not contain request bodies.

Optional sweep interrupted after persistent HTTP 429 responses. Counters above are confirmed completed requests from saved API responses and logged errors. Any interrupted request without a response is uncounted; total initiated attempts is unknown. No further API calls were made to rebuild this report. Secondary-tool original K=1 results use existing original caches. Gemini and Sourcery additional passes were not attempted.
