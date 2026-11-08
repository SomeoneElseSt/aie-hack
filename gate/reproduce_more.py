"""Reproduce review-gating benchmarks using real, persisted SubQ responses only."""
import hashlib
import json
import math
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import subq_gate as original

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'cache_more'
WORKERS = 4
RETRIES = 6
TIMEOUT = 180
MAX_CHARS = 1_000_000
MAX_QUESTIONS = 128
RETRY_CODES = {429, 500, 502, 503, 504}
JUDGES = ['anthropic_claude-sonnet-4-5-20250929', 'openai_gpt-5.2']
CR_QUESTION = {
    'type': 'noul',
    'instructions': 'Is this target review comment technically correct and trustworthy in the supplied PR and file context? Assess the comment itself; it need not describe a merge-blocking defect.\nTARGET COMMENT: {c}',
    'criteria': {'true': 'Technically correct and trustworthy in context',
                 'false': 'Technically incorrect, misleading, or invalid in context'},
}
LOCK = threading.Lock()
COUNTS = defaultdict(int)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def record(event):
    with LOCK:
        with (CACHE / 'requests.jsonl').open('a') as stream:
            stream.write(json.dumps(event) + '\n')
        COUNTS[event['benchmark'] + ':attempts'] += 1
        COUNTS[event['benchmark'] + (':errors' if 'error' in event else ':successes')] += 1


def parse_answers(response, names):
    if not isinstance(response, dict) or not isinstance(response.get('answers'), dict):
        return {'error': 'Missing answers object'}
    values = {}
    for name in names:
        answer = response['answers'].get(name)
        value = answer.get('noul') if isinstance(answer, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return {'error': 'Non-numeric or missing probability: ' + name}
        if not math.isfinite(value) or not 0 <= value <= 1:
            return {'error': 'Invalid probability: ' + name}
        values[name] = value
    return values


def request_subq(benchmark, state, comments, template):
    questions = {f'c{i}': {**template, 'instructions': template['instructions'].format(c=c)}
                 for i, c in enumerate(comments)}
    payload = {'model': 'subq-snap-1.1', 'state': state, 'questions': questions}
    identity = digest(payload)
    path = CACHE / (identity + '.json')
    if path.exists():
        result = parse_answers(json.loads(path.read_text()), questions)
        if 'error' not in result:
            with LOCK:
                COUNTS[benchmark + ':cached_requests'] += 1
            return {c: result[f'c{i}'] for i, c in enumerate(comments)}
    req = urllib.request.Request('https://api.subq.ai/v1/systemone',
        data=json.dumps(payload).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + original.load_key(), 'Content-Type': 'application/json'})
    for attempt in range(RETRIES):
        with LOCK:
            with (CACHE / 'started.jsonl').open('a') as stream:
                stream.write(json.dumps({'benchmark': benchmark, 'request': identity, 'attempt': attempt}) + '\n')
        retry = False
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                raw = response.read().decode()
            parsed = json.loads(raw)
            result = parse_answers(parsed, questions)
            if 'error' not in result:
                path.write_text(raw)
                record({'benchmark': benchmark, 'request': identity, 'attempt': attempt, 'response_file': path.name})
                return {c: result[f'c{i}'] for i, c in enumerate(comments)}
            error = result['error']
            (CACHE / (identity + '.invalid.txt')).write_text(raw)
        except urllib.error.HTTPError as exc:
            error = f'HTTP {exc.code}: ' + exc.read().decode(errors='replace')[:500]
            retry = exc.code in RETRY_CODES
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            error = str(exc)
            retry = True
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            error = 'Invalid response: ' + str(exc)
        record({'benchmark': benchmark, 'request': identity, 'attempt': attempt, 'error': error})
        if not retry or attempt == RETRIES - 1:
            return {'error': error}
        time.sleep(2 ** attempt + 1)
    return {'error': 'Retry loop exhausted'}


def cr_input(row):
    targets = [entry for entry in row['code_review'] if entry.get('id') == row['judged_entry_id']]
    if len(targets) != 1:
        return None, None
    target = {key: targets[0].get(key) for key in ('type', 'body', 'review_path', 'diff_hunk')}
    pr = row['pull_request']
    state = {'patch_to_review': pr['patch_to_review'], 'repo': row['repo'],
             'title': pr['title'], 'body': pr['body'], 'base_commit': pr['base_commit'],
             'resolved_issues': row['resolved_issues'], 'hint_text': row['hint_text']}
    return json.dumps(state, ensure_ascii=False)[:MAX_CHARS], json.dumps(target, ensure_ascii=False)


def cr_group(job):
    split, state, items = job
    comments = list(dict.fromkeys(comment for _, comment in items))
    result = request_subq('crjudge', state, comments, CR_QUESTION)
    return split, items, result


def accuracy(rows, probabilities, threshold):
    return sum((p >= threshold) == row['trustworthy'] for row, p in zip(rows, probabilities)) / len(rows)


def auc(rows, probabilities):
    positive = [p for r, p in zip(rows, probabilities) if r['trustworthy']]
    negative = [p for r, p in zip(rows, probabilities) if not r['trustworthy']]
    return sum((a > b) + (a == b) / 2 for a in positive for b in negative) / (len(positive) * len(negative))


def crjudge():
    splits = {name: [json.loads(line) for line in (ROOT / 'data' / (name + '.jsonl')).read_text().splitlines()]
              for name in ('validation', 'test')}
    jobs = []
    for split, rows in splits.items():
        groups = defaultdict(list)
        for index, row in enumerate(rows):
            state, comment = cr_input(row)
            if state is None:
                return {'error': 'Target comment missing or ambiguous'}
            groups[state].append((index, comment))
        jobs.extend((split, state, items) for state, items in groups.items())
    probabilities = {split: {} for split in splits}
    failures = []
    with ThreadPoolExecutor(WORKERS) as pool:
        for done, (split, items, result) in enumerate(pool.map(cr_group, jobs), start=1):
            if 'error' in result:
                failures.append({'split': split, 'rows': [i for i, _ in items], 'error': result['error']})
            else:
                probabilities[split].update({index: result[comment] for index, comment in items})
            print('CRJudge groups completed', done, '/', len(jobs), 'failed', len(failures), flush=True)
    artifact = {'probabilities': probabilities, 'failures': failures}
    (ROOT / 'crjudge_predictions.json').write_text(json.dumps(artifact, indent=2))
    if failures:
        return {'error': 'Incomplete API predictions; no benchmark metrics reported', 'failures': failures}
    validation = [probabilities['validation'][i] for i in range(len(splits['validation']))]
    thresholds = sorted({0.0, 0.5, 1.0, math.nextafter(max(validation), math.inf), *validation})
    threshold = max(thresholds, key=lambda t: accuracy(splits['validation'], validation, t))
    test = [probabilities['test'][i] for i in range(len(splits['test']))]
    return {'threshold': threshold, 'validation_accuracy': accuracy(splits['validation'], validation, threshold),
            'test_accuracy': accuracy(splits['test'], test, threshold), 'accuracy_at_half': accuracy(splits['test'], test, 0.5),
            'auroc': auc(splits['test'], test), 'validation_rows': len(validation), 'test_rows': len(test)}


def martian_job(job):
    pr, comments = job
    diff = original.fetch_diff(pr)
    if not diff:
        return pr, {'error': 'Missing PR diff'}
    return pr, request_subq('martian', diff[:MAX_CHARS], comments, original.QUESTION)


def recover_interrupted_cache(pr, comments):
    if not comments:
        return {}
    diff = original.fetch_diff(pr)
    questions = {f'c{i}': {**original.QUESTION, 'instructions': original.QUESTION['instructions'].format(c=c)}
                 for i, c in enumerate(comments)}
    identity = digest({'model': 'subq-snap-1.1', 'state': diff[:MAX_CHARS], 'questions': questions})
    path = CACHE / (identity + '.json')
    if not path.exists():
        return {}
    result = parse_answers(json.loads(path.read_text()), questions)
    if 'error' in result:
        return {}
    return {c: result[f'c{i}'] for i, c in enumerate(comments)}


def martian():
    evaluations = {judge: json.loads((original.BENCH / 'results' / judge / 'evaluations.json').read_text()) for judge in JUDGES}
    needed = defaultdict(set)
    for evals in evaluations.values():
        for pr, entries in evals.items():
            for tool, entry in entries.items():
                if not entry['skipped']:
                    needed[pr, tool].update(original.candidates(entry))
    by_pr = defaultdict(dict)
    for pr in sorted({pr for pr, _ in needed}):
        suffix = pr.split('github.com/')[1].replace('/', '_')
        for path in sorted(original.CACHE.glob(f'subq_diff_*_{suffix}.json')):
            cached = json.loads(path.read_text())
            by_pr[pr].update({c: p for c, p in cached.items() if isinstance(p, (int, float)) and 0 <= p <= 1})
    for (pr, tool), comments in sorted(needed.items()):
        suffix = pr.split('github.com/')[1].replace('/', '_')
        path = original.CACHE / f'subq_diff_{tool}_{suffix}.json'
        cached = json.loads(path.read_text()) if path.exists() else {}
        missing = sorted(comments - cached.keys())
        by_pr[pr].update(recover_interrupted_cache(pr, missing))
    new = defaultdict(set)
    reused = 0
    for (pr, tool), comments in needed.items():
        reused += sum(c in by_pr[pr] for c in comments)
        new[pr].update(comments - by_pr[pr].keys())
    jobs = []
    for pr, comments in sorted(new.items()):
        ordered = sorted(comments)
        jobs.extend((pr, ordered[start:start + MAX_QUESTIONS]) for start in range(0, len(ordered), MAX_QUESTIONS))
    failures = []
    print('Martian reused candidate assignments', reused, 'new PR request groups', len(jobs), flush=True)
    with ThreadPoolExecutor(WORKERS) as pool:
        for done, (pr, result) in enumerate(pool.map(martian_job, jobs), start=1):
            if 'error' in result:
                failures.append({'pr': pr, 'error': result['error']})
            else:
                by_pr[pr].update(result)
            print('Martian PR groups completed', done, '/', len(jobs), 'failed', len(failures), flush=True)
    probabilities = {(pr, tool): {c: by_pr[pr][c] for c in comments if c in by_pr[pr]} for (pr, tool), comments in needed.items()}
    (ROOT / 'martian_probabilities.json').write_text(json.dumps([{'pr': pr, 'tool': tool, 'probabilities': values} for (pr, tool), values in sorted(probabilities.items())]))
    rows = []
    for judge, evals in evaluations.items():
        prs = sorted(evals)
        tools = sorted({t for entries in evals.values() for t in entries})
        for tool in tools:
            missing = missing_candidates(evals, probabilities, tool)
            if missing:
                rows.append({'judge': judge, 'tool': tool, 'error': 'Missing API probabilities'})
                continue
            gains = []
            for train, test in ((prs[::2], prs[1::2]), (prs[1::2], prs[::2])):
                threshold = original.best_threshold(evals, probabilities, tool, train)
                gains.append(original.score(evals, probabilities, tool, threshold, test)[2] - original.score(evals, probabilities, tool, 0.0, test)[2])
            categorized = sum(t.get('category') in original.STRICT for entries in evals.values() if tool in entries and not entries[tool]['skipped'] for t in entries[tool]['true_positives'] + entries[tool]['false_negatives'])
            rows.append({'judge': judge, 'tool': tool, 'baseline_f1': original.score(evals, probabilities, tool, 0.0, prs)[2],
                         'heldout_gain': sum(gains) / len(gains), 'fold_gains': gains, 'strict_positives': categorized})
    return {'rows': rows, 'failures': failures, 'reused_candidate_assignments': reused, 'new_request_groups': len(jobs)}


def missing_candidates(evals, probabilities, tool):
    return [(pr, c) for pr, entries in evals.items() if tool in entries and not entries[tool]['skipped']
            for c in original.candidates(entries[tool]) if c not in probabilities.get((pr, tool), {})]


def main():
    CACHE.mkdir(exist_ok=True)
    if not original.load_key():
        print('SUBQ_API_KEY missing')
        return
    result_path = ROOT / 'more_metrics.json'
    results = json.loads(result_path.read_text()) if result_path.exists() else {}
    mode = sys.argv[1] if len(sys.argv) > 1 else 'crjudge'
    result = crjudge() if mode == 'crjudge' else martian()
    results[mode] = result
    results.setdefault('runs', []).append({'mode': mode, 'counts': dict(COUNTS)})
    result_path.write_text(json.dumps(results, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
