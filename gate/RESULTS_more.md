# SubQ review gate: additional benchmarks

All SubQ metrics derive from saved API probabilities; no missing probabilities were imputed. Published comparator scores are explicitly identified.

**CRJudgeBench**

| Method | Test accuracy | Test AUROC | Accuracy at 0.5 |
|---|---:|---:|---:|
| SubQ Snap, validation-selected threshold | 85.79% | 0.916 | 85.79% |
| Sentinel, published | 76.60% | Not reported | Not applicable |
| GLM-5.3, published | 70.47% | Not reported | Not applicable |

Validation threshold **0.497327805**; validation accuracy 88.89%. Complete coverage: 126 validation and 359 test rows.

Focused context: patch, PR description, linked issues, target body/path/hunk; shared-context questions batched. No labels, provenance, reviewer identities, other timeline entries, or repository browsing. Published agents could inspect repositories, so context budgets differ. [Dataset](https://huggingface.co/datasets/dcloud347/CRJudgeBenchmark), revision `66bd8ac78d566c10325b57e9c384755320fd63d8`; [published results](https://arxiv.org/html/2609.37216v1).

101 recorded completed API attempts: 94 successful responses; errors: 7 HTTP 429. Final failed prediction groups: none.

**Martian robustness**

Same strict categories, threshold grid, sorted-PR alternating halves, and mean bidirectional held-out F1 gain as `subq_gate.py`. Each cell is **ungated F1 / held-out gain**.

| Tool | Sonnet 4.5 judge | GPT-5.2 judge |
|---|---:|---:|
| coderabbit | 0.417 / +0.124 | 0.374 / +0.135 |
| augment | 0.550 / -0.013 | 0.519 / +0.056 |
| baz | 0.449 / +0.004 | 0.395 / +0.009 |
| bito | Unscorable* | Unscorable* |
| bugbot | 0.489 / +0.013 | 0.485 / +0.027 |
| claude | 0.367 / +0.085 | 0.378 / +0.076 |
| claude-code | 0.379 / +0.042 | 0.405 / +0.006 |
| codeant | Unscorable* | Unscorable* |
| codeant-v2 | 0.340 / +0.019 | 0.331 / +0.033 |
| copilot | Unscorable* | Unscorable* |
| copilot-v2 | 0.416 / +0.125 | 0.411 / +0.100 |
| cubic-dev | Unscorable* | Unscorable* |
| cubic-v2 | 0.561 / -0.006 | 0.563 / -0.000 |
| devin | 0.532 / +0.000 | 0.490 / -0.013 |
| entelligence | Unscorable* | Unscorable* |
| gemini | Unscorable* | Unscorable* |
| gemini-v2 | 0.430 / +0.087 | 0.434 / +0.100 |
| gitar | Unscorable* | Unscorable* |
| gitlab | 0.467 / +0.052 | 0.453 / +0.047 |
| graphite | 0.147 / +0.000 | 0.131 / +0.000 |
| greptile | Unscorable* | Unscorable* |
| greptile-v4 | Unscorable* | Unscorable* |
| greptile-v4-1 | 0.475 / +0.017 | 0.447 / +0.046 |
| greptile-v5 | 0.399 / +0.038 | 0.395 / +0.021 |
| kg | 0.231 / -0.020 | 0.253 / -0.012 |
| kodus | Unscorable* | Unscorable* |
| kodus-v2 | 0.451 / +0.026 | 0.420 / +0.013 |
| linearb | Unscorable* | Unscorable* |
| macroscope | 0.477 / +0.013 | 0.461 / +0.013 |
| mergemonkey | Unscorable* | Unscorable* |
| mesa | Unscorable* | Unscorable* |
| mra-a | Unscorable* | Unscorable* |
| mra-b | Unscorable* | Unscorable* |
| mra-claude | 0.247 / +0.093 | 0.224 / +0.102 |
| mra-max | Unscorable* | Unscorable* |
| mra-mix | 0.254 / +0.094 | 0.250 / +0.102 |
| mra-nano | Unscorable* | Unscorable* |
| mra-openai | 0.265 / +0.040 | 0.233 / +0.061 |
| mra-ultra | Unscorable* | Unscorable* |
| propel | Unscorable* | Unscorable* |
| propel-v2 | 0.482 / +0.025 | Unscorable* |
| qodo | Unscorable* | Unscorable* |
| qodo-extended | Unscorable* | Unscorable* |
| qodo-extended-summary | Unscorable* | Unscorable* |
| qodo-extended-v2 | 0.559 / -0.000 | 0.584 / -0.017 |
| qodo-v2 | 0.511 / +0.037 | 0.525 / +0.067 |
| qodo-v2-2 | Unscorable* | Unscorable* |
| qodo-v22 | Unscorable* | Unscorable* |
| sourcery | 0.402 / +0.091 | 0.401 / +0.074 |

*Unscorable: no category-labelled strict positives; the original script returns a degenerate zero F1 here. This is missing benchmark category coverage, not a SubQ failure.

Reused 3256 candidate-probability assignments from earlier successful responses. Final missing probabilities: none.

454 recorded completed API attempts: 344 successful responses; errors: 46 HTTP 422, 64 HTTP 429.
An initial per-tool run was interrupted during rebatching; its in-flight request count is unavailable. Thus the recorded completed-attempt count is not a verified total of all requests sent. Oversized batches were rejected, then capped at the API-reported question limit; rate-limit failures were retried.

**ReviewBench bonus: public sample only**

| Producer | Labelled findings | Ungated retention F1 | Held-out retention F1 gain |
|---|---:|---:|---:|
| gpt-4o | 94 | 0.139 | -0.044 |
| gemini-2.5-pro | 85 | 0.496 | +0.027 |

The clone ships producer-labelled pooled golden findings, rather than complete stored agent runs. Evaluated the noisiest AI producers on the public sample (23 PRs with relevant findings), using pinned base/head diffs. Retention F1 counts dropped labelled true findings as misses; it cannot measure additional undiscovered defects or official ReviewBench recall. Same held-out split/grid as Martian.

23 recorded completed API attempts: 23 successful responses; errors: none. Final API/diff failures: none.

- SubQ exceeds the published CRJudgeBench accuracy comparators under the stated focused-context protocol.
- CodeRabbit’s positive held-out gain reproduces under both additional judges; benefit varies by tool and judge.
- Gating is not universally beneficial: ReviewBench’s public sample improves for Gemini but worsens for GPT-4o; full-run conclusions remain unsupported.

Evidence: `cache_more/*.json` (raw SubQ responses), `cache_more/requests.jsonl` (completed attempts/errors), `crjudge_predictions.json`, `martian_probabilities.json`, `reviewbench_predictions.json`, `more_metrics.json`, and `verification.json`. Reproduce with `python3 gate/reproduce_more.py crjudge`, `python3 gate/reproduce_more.py martian`, then `python3 gate/reviewbench_more.py` and `python3 gate/write_more_results.py`.
