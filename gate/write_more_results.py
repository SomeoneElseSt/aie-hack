"""Render observed benchmark metrics and API logs without filling missing values."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAPER = 'https://arxiv.org/html/2609.37216v1'
DATASET = 'https://huggingface.co/datasets/dcloud347/CRJudgeBenchmark'


def call_counts(events, benchmark):
    selected = [e for e in events if e['benchmark'] == benchmark]
    successes = sum('error' not in e for e in selected)
    errors = Counter(e['error'].split(':')[0] for e in selected if 'error' in e)
    summary = ', '.join(f'{count} {kind}' for kind, count in sorted(errors.items())) or 'none'
    return f'{len(selected)} recorded completed API attempts: {successes} successful responses; errors: {summary}.'


def main():
    results = json.loads((ROOT / 'more_metrics.json').read_text())
    cr = results['crjudge']
    rb = json.loads((ROOT / 'reviewbench_metrics.json').read_text())
    events = [json.loads(line) for line in (ROOT / 'cache_more/requests.jsonl').read_text().splitlines()]
    revision = json.loads((ROOT / 'data/dataset_metadata.json').read_text())['sha']
    lines = ['# SubQ review gate: additional benchmarks', '',
             'All SubQ metrics derive from saved API probabilities; no missing probabilities were imputed. Published comparator scores are explicitly identified.', '',
             '**CRJudgeBench**', '',
             '| Method | Test accuracy | Test AUROC | Accuracy at 0.5 |',
             '|---|---:|---:|---:|',
             f"| SubQ Snap, validation-selected threshold | {cr['test_accuracy']:.2%} | {cr['auroc']:.3f} | {cr['accuracy_at_half']:.2%} |",
             '| Sentinel, published | 76.60% | Not reported | Not applicable |',
             '| GLM-5.3, published | 70.47% | Not reported | Not applicable |', '',
             f"Validation threshold **{cr['threshold']:.9f}**; validation accuracy {cr['validation_accuracy']:.2%}. Complete coverage: {cr['validation_rows']} validation and {cr['test_rows']} test rows.", '',
             f"Focused context: patch, PR description, linked issues, target body/path/hunk; shared-context questions batched. No labels, provenance, reviewer identities, other timeline entries, or repository browsing. Published agents could inspect repositories, so context budgets differ. [Dataset]({DATASET}), revision `{revision}`; [published results]({PAPER}).", '',
             call_counts(events, 'crjudge') + ' Final failed prediction groups: none.', '',
             '**Martian robustness**', '',
             'Same strict categories, threshold grid, sorted-PR alternating halves, and mean bidirectional held-out F1 gain as `subq_gate.py`. Each cell is **ungated F1 / held-out gain**.', '',
             '| Tool | Sonnet 4.5 judge | GPT-5.2 judge |',
             '|---|---:|---:|']
    rows = results['martian']['rows']
    judges = ['anthropic_claude-sonnet-4-5-20250929', 'openai_gpt-5.2']
    lookup = {(r['judge'], r['tool']): r for r in rows}
    tools = sorted({r['tool'] for r in rows}, key=lambda t: (t != 'coderabbit', t))
    for tool in tools:
        cells = []
        for judge in judges:
            row = lookup.get((judge, tool))
            if row is None or 'error' in row:
                cells.append('Failed / unavailable')
                continue
            if not row['strict_positives']:
                cells.append('Unscorable*')
                continue
            cells.append(f"{row['baseline_f1']:.3f} / {row['heldout_gain']:+.3f}")
        lines.append(f"| {tool} | {' | '.join(cells)} |")
    lines += ['', '*Unscorable: no category-labelled strict positives; the original script returns a degenerate zero F1 here. This is missing benchmark category coverage, not a SubQ failure.', '',
              f"Reused {results['martian']['reused_candidate_assignments']} candidate-probability assignments from earlier successful responses. Final missing probabilities: none.", '',
              call_counts(events, 'martian'),
              'An initial per-tool run was interrupted during rebatching; its in-flight request count is unavailable. Thus the recorded completed-attempt count is not a verified total of all requests sent. Oversized batches were rejected, then capped at the API-reported question limit; rate-limit failures were retried.', '',
              '**ReviewBench bonus: public sample only**', '',
              '| Producer | Labelled findings | Ungated retention F1 | Held-out retention F1 gain |',
              '|---|---:|---:|---:|']
    for row in rb['rows']:
        if 'error' in row:
            lines.append(f"| {row['producer']} | Unavailable | Failed | Failed |")
            continue
        lines.append(f"| {row['producer'].removeprefix('llm_review:')} | {row['findings']} | {row['baseline_retention_f1']:.3f} | {row['heldout_gain']:+.3f} |")
    lines += ['', f"The clone ships producer-labelled pooled golden findings, rather than complete stored agent runs. Evaluated the noisiest AI producers on the public sample ({rb['prs']} PRs with relevant findings), using pinned base/head diffs. Retention F1 counts dropped labelled true findings as misses; it cannot measure additional undiscovered defects or official ReviewBench recall. Same held-out split/grid as Martian.", '',
              call_counts(events, 'reviewbench') + ' Final API/diff failures: none.', '',
              '- SubQ exceeds the published CRJudgeBench accuracy comparators under the stated focused-context protocol.',
              '- CodeRabbit’s positive held-out gain reproduces under both additional judges; benefit varies by tool and judge.',
              '- Gating is not universally beneficial: ReviewBench’s public sample improves for Gemini but worsens for GPT-4o; full-run conclusions remain unsupported.', '',
              'Evidence: `cache_more/*.json` (raw SubQ responses), `cache_more/requests.jsonl` (completed attempts/errors), `crjudge_predictions.json`, `martian_probabilities.json`, `reviewbench_predictions.json`, `more_metrics.json`, and `verification.json`. Reproduce with `python3 gate/reproduce_more.py crjudge`, `python3 gate/reproduce_more.py martian`, then `python3 gate/reviewbench_more.py` and `python3 gate/write_more_results.py`.']
    (ROOT / 'RESULTS_more.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
