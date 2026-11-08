"""Real SubQ multi-pass experiment; original caches are read-only."""
import hashlib
import ast
import json
import math
import random
import sys
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import subq_gate as gate

ROOT = Path(__file__).parent
CACHE = ROOT / 'cache_kpass'
REPORT = ROOT / 'RESULTS_kpass.md'
TOOLS = ('coderabbit', 'copilot-v2', 'gemini-v2', 'sourcery')
WORKERS = 3
PASSES = 4
CHECK_PRS = 3
SEED = 1701
BACKOFF_MAX = 60
VARIANTS = [gate.QUESTION, {
    'type': 'noul',
    'instructions': 'Does this review comment correctly identify a merge-blocking defect introduced by the supplied pull request diff?\nCOMMENT: {c}',
    'criteria': {'true': 'The diff introduces the claimed correctness, security, data, concurrency, or API bug.',
                 'false': 'The claim is incorrect, speculative, stylistic, or not introduced by the diff.'},
}, {
    'type': 'noul',
    'instructions': 'Assess this comment against the pull request diff: is it a real defect caused by this change and serious enough to block merging?\nCOMMENT: {c}',
    'criteria': {'true': 'A correct finding of a correctness, security, data, concurrency, or API defect introduced by this change.',
                 'false': 'An unsupported or wrong finding, a style suggestion, or an issue not caused by this change.'},
}, {
    'type': 'noul',
    'instructions': 'Given the diff, should merge be blocked because this review comment reports an actual bug introduced in this pull request?\nCOMMENT: {c}',
    'criteria': {'true': 'The comment accurately describes a newly introduced correctness, security, data, concurrency, or API bug.',
                 'false': 'The comment is mistaken, speculative, about style, or about an issue this diff did not introduce.'},
}]
LOCK = threading.Lock()
COUNTS = {'attempts': 0, 'successes': 0, 'attempt_errors': 0, 'cache_hits': 0, 'original_cache_hits': 0}
ERRORS = []


def increment(name):
    with LOCK:
        COUNTS[name] += 1


def read_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


def valid_probs(probs, comments):
    if not isinstance(probs, dict) or set(probs) != set(comments):
        return False
    return all(isinstance(p, (int, float)) and not isinstance(p, bool) and math.isfinite(p) and 0 <= p <= 1 for p in probs.values())


def get_diff(pr):
    name = 'diff_' + pr.split('github.com/')[1].replace('/', '_') + '.diff'
    for directory in (gate.CACHE, CACHE):
        path = directory / name
        if path.exists():
            return path.read_text()
    result = subprocess.run(['gh', 'pr', 'diff', pr], capture_output=True, text=True)
    if result.returncode:
        return ''
    (CACHE / name).write_text(result.stdout)
    return result.stdout


def payload_for(pr, comments, variant, repeat):
    diff = get_diff(pr)
    if not diff:
        return None, comments
    ordered = comments.copy()
    if not repeat and variant:
        random.Random(SEED + variant).shuffle(ordered)
    framing = VARIANTS[0 if repeat else variant]
    questions = {f'c{i}': {**framing, 'instructions': framing['instructions'].format(c=c)} for i, c in enumerate(ordered)}
    return {'model': 'subq-snap-1.1', 'state': diff[:gate.MAX_STATE_CHARS], 'questions': questions}, ordered


def request_probs(key, payload, comments, tag):
    body = json.dumps(payload).encode()
    request = urllib.request.Request('https://api.subq.ai/v1/systemone', data=body, method='POST',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    for attempt in range(gate.RETRIES):
        increment('attempts')
        try:
            with urllib.request.urlopen(request, timeout=gate.TIMEOUT_S) as response:
                raw = json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            increment('attempt_errors')
            status = getattr(error, 'code', None)
            event = {'tag': tag, 'attempt': attempt + 1, 'error': str(error)}
            with LOCK:
                ERRORS.append(event)
            print('API ERROR', event, flush=True)
            if status != 429 and (status is None or status < 500):
                return None
            time.sleep(min(BACKOFF_MAX, 2 ** attempt + 1))
            continue
        answers = raw.get('answers', {}) if isinstance(raw, dict) else {}
        probs = {c: answers.get(f'c{i}', {}).get('noul') for i, c in enumerate(comments)}
        if not valid_probs(probs, comments):
            increment('attempt_errors')
            with LOCK:
                ERRORS.append({'tag': tag, 'error': 'Invalid or missing noul probability', 'response': raw})
            return None
        increment('successes')
        return {'probabilities': probs, 'response': raw}
    return None


def collect(key, pr, tool, entry, variant, repeat, check=None):
    comments = gate.candidates(entry)
    if not comments:
        return {}
    payload, ordered = payload_for(pr, comments, variant, repeat)
    if payload is None:
        return None
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    suffix = f'check{check}' if check is not None else f'pass{variant + 1}'
    path = CACHE / f'{tool}_{digest}_{suffix}.json'
    saved = read_json(path)
    if saved and saved.get('request') == payload and valid_probs(saved.get('probabilities'), comments):
        increment('cache_hits')
        return saved['probabilities']
    original = gate.CACHE / f"subq_diff_{tool}_{pr.split('github.com/')[1].replace('/', '_')}.json"
    if check is None and variant == 0:
        probs = read_json(original)
        if valid_probs(probs, comments):
            increment('original_cache_hits')
            return probs
    result = request_probs(key, payload, ordered, f'{tool} {pr} {suffix}')
    if result is None:
        return None
    path.write_text(json.dumps({'request': payload, 'pr': pr, 'tool': tool, **result}))
    return result['probabilities']


def result_row(evals, prs, tool, probs, label, agg):
    threshold = gate.best_threshold(evals, probs, tool, prs)
    ins = gate.score(evals, probs, tool, threshold, prs)
    gains = []
    for train, test in ((prs[::2], prs[1::2]), (prs[1::2], prs[::2])):
        selected = gate.best_threshold(evals, probs, tool, train)
        gains.append(gate.score(evals, probs, tool, selected, test)[2] - gate.score(evals, probs, tool, 0, test)[2])
    average = sum(gains) / len(gains)
    row = f'| {tool} | {label} | {agg} | {gains[0]:+.4f}, {gains[1]:+.4f}, **{average:+.4f}** | {ins[0]:.4f} / {ins[1]:.4f} / {ins[2]:.4f} (threshold {threshold:.2f}) |'
    return row, average


def score_tool(evals, prs, tool, passes):
    rows, summary = [], {}
    for variant, values in enumerate(passes):
        if any(p is None for p in values.values()):
            rows.append(f'| {tool} | variant {variant + 1} | single | unavailable: incomplete API responses | unavailable |')
            continue
        row, gain = result_row(evals, prs, tool, {(pr, tool): p for pr, p in values.items()}, f'variant {variant + 1}', 'single')
        rows.append(row)
        summary[f'variant{variant + 1}'] = gain
    for k in (1, 2, 4):
        for agg in ('mean', 'min'):
            if any(p is None for values in passes[:k] for p in values.values()):
                rows.append(f'| {tool} | {k} | {agg} | unavailable: incomplete API responses | unavailable |')
                continue
            probs = {}
            for pr in passes[0]:
                probs[(pr, tool)] = {}
                for comment in passes[0][pr]:
                    values = [p[pr][comment] for p in passes[:k]]
                    probs[(pr, tool)][comment] = sum(values) / len(values) if agg == 'mean' else min(values)
            row, gain = result_row(evals, prs, tool, probs, str(k), agg)
            rows.append(row)
            summary[f'{k}_{agg}'] = gain
    return rows, summary


def write_report(checks, repeat, rows, summaries, done):
    lines = ['# SubQ gate K-pass experiment', '',
        'Strict profile; existing anthropic_claude-opus-4-5-20251101 judge labels. All probabilities are real API responses or existing original API cache entries; metrics are computed from these and judge labels.', '',
        'A/B are even/odd positions in the full sorted PR list, exactly as subq_gate.py. Threshold grid and scoring reuse that script. Each incomplete variant/aggregation is excluded entirely; missing probabilities are never filled.', '',
        '## Identical-request check', '', *checks, '',
        'Pass definition: ' + ('identical requests repeated (variation observed).' if repeat else 'equivalent question/criteria variants, with fixed-seed comment shuffles after the original pass.'), '',
        'Identical responses in this check establish observed repeatability only, not universal determinism.', '',
        '| tool | K | agg | held-out F1 gain (A→B, B→A, avg) | in-sample P/R/F1 |',
        '|---|---|---|---|---|', *rows, '',
        'Evaluated tools (unavailable configurations are marked above): ' + ', '.join(done), '',
        'Invocation counters (HTTP attempts include retries; cache hits are not calls): ' + json.dumps(COUNTS),
        '', 'Failure details: [cache_kpass/run_summary.json](cache_kpass/run_summary.json), `errors` field; request-level events are also in kpass_run.log.', '', '## Takeaways', '']
    if 'coderabbit' in summaries and summaries['coderabbit']:
        s = summaries['coderabbit']
        for agg in ('mean', 'min'):
            lines.append(f"- CodeRabbit {agg}: held-out gains K=1 {s['1_'+agg]:+.4f}, K=2 {s['2_'+agg]:+.4f}, K=4 {s['4_'+agg]:+.4f}; K=4 versus K=1 {s['4_'+agg]-s['1_'+agg]:+.4f}.")
        best = max(range(PASSES), key=lambda v: s[f'variant{v+1}']) + 1
        lines.append(f"- Best CodeRabbit single variant is {best} ({s[f'variant{best}']:+.4f}); K=4 mean versus that single variant is {s['4_mean']-s[f'variant{best}']:+.4f}. Averaging shows an empirical scaling effect on these folds beyond the best individual prompt; minimum aggregation does not show consistent scaling. This is a fixed-fold comparison, not a significance test.")
    lines.extend(['', 'Framings and shuffle seeds are recorded in kpass.py; full fresh API responses and exact request bodies are preserved in cache_kpass/. Original pass cache reuse matches diff context and exact candidate keys; legacy cache files do not contain request bodies.', ''])
    REPORT.write_text('\n'.join(lines))
    (CACHE / 'run_summary.json').write_text(json.dumps({'counts': COUNTS, 'errors': ERRORS, 'checks': checks, 'repeat': repeat, 'summaries': summaries, 'completed': done}, indent=2))


def report_only():
    """Rebuild strictly from returned responses, with no API calls or imputation."""
    prior = read_json(CACHE / 'run_summary.json')
    if not prior:
        print('No completed determinism check; cannot rebuild report.')
        return
    evals = json.loads(gate.EVALS.read_text())
    prs = sorted(evals)
    responses = [read_json(path) for path in CACHE.glob('*.json')]
    success_count = sum(isinstance(r, dict) and 'response' in r and 'probabilities' in r for r in responses)
    log = ROOT / 'kpass_run.log'
    errors = [ast.literal_eval(line.removeprefix('API ERROR ')) for line in log.read_text().splitlines() if line.startswith('API ERROR ')]
    ERRORS.clear()
    ERRORS.extend(errors)
    COUNTS.clear()
    COUNTS.update({'successful_fresh_responses': success_count, 'observed_error_responses': len(errors),
                   'confirmed_completed_HTTP_attempts': success_count + len(errors)})
    rows, summaries = [], {}
    for tool in TOOLS:
        passes = []
        for variant in range(PASSES):
            values = {}
            for pr in prs:
                entry = evals[pr].get(tool)
                if not entry or entry['skipped']:
                    continue
                comments = gate.candidates(entry)
                if not comments:
                    values[pr] = {}
                    continue
                payload, _ = payload_for(pr, comments, variant, prior['repeat'])
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                saved = read_json(CACHE / f'{tool}_{digest}_pass{variant + 1}.json')
                probs = saved.get('probabilities') if saved and saved.get('request') == payload else None
                if variant == 0:
                    probs = read_json(gate.CACHE / f"subq_diff_{tool}_{pr.split('github.com/')[1].replace('/', '_')}.json")
                values[pr] = probs if valid_probs(probs, comments) else None
            passes.append(values)
        tool_rows, summary = score_tool(evals, prs, tool, passes)
        rows.extend(tool_rows)
        summaries[tool] = summary
    write_report(prior['checks'], prior['repeat'], rows, summaries, list(TOOLS))
    with REPORT.open('a') as report:
        report.write('\nOptional sweep interrupted after persistent HTTP 429 responses. Counters above are confirmed completed requests from saved API responses and logged errors. Any interrupted request without a response is uncounted; total initiated attempts is unknown. No further API calls were made to rebuild this report. Secondary-tool original K=1 results use existing original caches. Gemini and Sourcery additional passes were not attempted.\n')
    print(json.dumps({'counts': COUNTS, 'summaries': summaries}, indent=2))


def main():
    CACHE.mkdir(exist_ok=True)
    key = gate.load_key()
    if not key:
        REPORT.write_text('Experiment failed: SUBQ_API_KEY is missing. No results.\n')
        return
    evals = json.loads(gate.EVALS.read_text())
    prs = sorted(evals)
    selected = [pr for pr in prs if evals[pr].get('coderabbit') and not evals[pr]['coderabbit']['skipped'] and gate.candidates(evals[pr]['coderabbit'])][:CHECK_PRS]
    checks, repeat = [], False
    for pr in selected:
        a = collect(key, pr, 'coderabbit', evals[pr]['coderabbit'], 0, True, 'a')
        b = collect(key, pr, 'coderabbit', evals[pr]['coderabbit'], 0, True, 'b')
        if a is None or b is None:
            REPORT.write_text('Determinism check failed; no scaling results.\n' + json.dumps(ERRORS))
            return
        identical = a == b
        repeat = repeat or not identical
        changes = sum(a[c] != b[c] for c in a)
        checks.append(f'- {pr}: identical={identical}; changed probabilities={changes}/{len(a)}; max absolute difference={max(abs(a[c]-b[c]) for c in a):.12g}.')
        print(checks[-1], flush=True)
    rows, summaries, done = [], {}, []
    for tool in TOOLS:
        jobs = [(pr, evals[pr][tool]) for pr in prs if evals[pr].get(tool) and not evals[pr][tool]['skipped']]
        passes = []
        for variant in range(PASSES):
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                values = list(pool.map(lambda job: collect(key, job[0], tool, job[1], variant, repeat), jobs))
            passes.append(dict(zip((pr for pr, _ in jobs), values)))
            print(tool, 'pass', variant + 1, COUNTS, flush=True)
        tool_rows, summary = score_tool(evals, prs, tool, passes)
        rows.extend(tool_rows)
        summaries[tool] = summary
        done.append(tool)
        write_report(checks, repeat, rows, summaries, done)
        print('SCORED', tool, summary, flush=True)


if __name__ == '__main__':
    if '--report-only' in sys.argv:
        report_only()
    else:
        main()
