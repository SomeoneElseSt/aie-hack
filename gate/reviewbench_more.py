"""Gate the labeled producer findings in ReviewBench's public sample."""
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import reproduce_more as run

BENCH = Path('/private/tmp/claude-501/-Users-steve-Documents-Files-code-aie-hack/14ac8da5-b99a-41d3-8aaf-f57f66f307fa/scratchpad/rb')
PRODUCERS = ('llm_review:gpt-4o', 'llm_review:gemini-2.5-pro')


def get_diff(pr):
    identity = run.digest({'base': pr['base'], 'head': pr['head'], 'repo': pr['repo']})
    path = run.CACHE / (identity + '.diff')
    if path.exists():
        return path.read_bytes().decode(), None
    url = f"{pr['repo']}/compare/{pr['base']}...{pr['head']}.diff"
    try:
        with urllib.request.urlopen(url, timeout=run.TIMEOUT) as response:
            diff = response.read().decode()
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as error:
        return '', str(error)
    if not diff.strip():
        return '', 'Empty diff'
    path.write_text(diff)
    return diff, None


def gate_pr(job):
    key, pr, findings = job
    diff, error = get_diff(pr)
    if error:
        return key, {'error': error}
    comments = list(dict.fromkeys(json.dumps({k: f[k] for k in ('file', 'start_line', 'end_line', 'message')}) for f in findings))
    return key, run.request_subq('reviewbench', diff[:run.MAX_CHARS], comments, run.original.QUESTION)


def score(findings, probabilities, producer, threshold, prs):
    tp = fp = fn = 0
    for key in prs:
        for f in findings[key]:
            if f['producer'] != producer:
                continue
            comment = json.dumps({k: f[k] for k in ('file', 'start_line', 'end_line', 'message')})
            keep = probabilities[key][comment] >= threshold
            tp += f['tp_fp'] == 'tp' and keep
            fp += f['tp_fp'] == 'fp' and keep
            fn += f['tp_fp'] == 'tp' and not keep
    denominator = 2 * tp + fp + fn
    return 2 * tp / denominator if denominator else 0


def main():
    run.CACHE.mkdir(exist_ok=True)
    sample = json.loads((BENCH / 'corpus/test/test.json').read_text())
    allowed = {(r['repo'], r['pr_number']) for r in sample}
    findings, jobs = {}, []
    for path in sorted((BENCH / 'golden').glob('*.json')):
        data = json.loads(path.read_text())
        if (data['pr']['repo'], data['pr']['pr_number']) not in allowed:
            continue
        selected = [f for f in data['findings'] if f['producer'] in PRODUCERS]
        if not selected:
            continue
        findings[data['pr_key']] = selected
        jobs.append((data['pr_key'], data['pr'], selected))
    probabilities, failures = {}, []
    with ThreadPoolExecutor(run.WORKERS) as pool:
        for key, result in pool.map(gate_pr, jobs):
            if 'error' in result:
                failures.append({'pr': key, 'error': result['error']})
                continue
            probabilities[key] = result
    result = {'scope': 'public sample; pooled producer-labeled findings, not complete agent runs',
              'failures': failures, 'prs': len(jobs), 'counts': dict(run.COUNTS), 'rows': []}
    for producer in PRODUCERS:
        if any(any(f['producer'] == producer for f in findings[e['pr']]) for e in failures):
            result['rows'].append({'producer': producer, 'error': 'Incomplete API or diff coverage'})
            continue
        prs = sorted(findings)
        gains = []
        for train, test in ((prs[::2], prs[1::2]), (prs[1::2], prs[::2])):
            threshold = max(run.original.THRESHOLDS, key=lambda t: score(findings, probabilities, producer, t, train))
            gains.append(score(findings, probabilities, producer, threshold, test) - score(findings, probabilities, producer, 0.0, test))
        result['rows'].append({'producer': producer, 'baseline_retention_f1': score(findings, probabilities, producer, 0.0, prs),
                              'heldout_gain': sum(gains) / len(gains), 'findings': sum(f['producer'] == producer for fs in findings.values() for f in fs)})
    (run.ROOT / 'reviewbench_metrics.json').write_text(json.dumps(result, indent=2))
    (run.ROOT / 'reviewbench_predictions.json').write_text(json.dumps(probabilities))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
