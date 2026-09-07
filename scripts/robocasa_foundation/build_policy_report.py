#!/usr/bin/env python3
"""Read-only audit and table from actual pilot artifacts; never run the simulator."""
import argparse
from collections import Counter
import html
import json
import subprocess
from pathlib import Path
import numpy as np
from scripts.robocasa_foundation.run_benchmark import score

OUTCOMES = ('recovery_success', 'unsafe_task_success', 'catastrophe', 'safe_noncompletion', 'invalid')
LABELS = ('Safe complete', 'Unsafe complete', 'Unsafe incomplete', 'Safe incomplete', 'Invalid')


def audit(root, manifest, pilot):
    cases = {c['id']: c for c in manifest['cases'] if c['id'] in manifest['benchmark_case_ids']}
    expected = {(c, b, seed) for c in cases for b in pilot['states'] for seed in pilot['sampling_seeds']}
    seen, results, issues = set(), [], []
    for path in sorted(root.glob('curated-*/result.json')):
        r = json.loads(path.read_text())
        key = r['case_id'], r['branch'], r['sampling_seed']
        if key in seen or key not in expected:
            issues.append(f'{key}: duplicate or unexpected')
        seen.add(key)
        results.append(r)
        if r['outcome'] not in OUTCOMES:
            issues.append(f'{key}: unknown outcome')
        if r.get('execution_error'):
            if r['outcome'] != 'invalid':
                issues.append(f'{key}: error not classified invalid')
            continue
        c = cases[r['case_id']]
        if not r.get('identity_valid') or not r.get('start_audit', {}).get('valid'):
            issues.append(f'{key}: failed identity/start')
        if any(c['hashes'].get(k) != v for k, v in r['hashes'].items()):
            issues.append(f'{key}: frozen input hash mismatch')
        if r['task_success_predicate_sha256'] != c['task_success_predicate_sha256']:
            issues.append(f'{key}: predicate hash mismatch')
        with np.load(path.with_name('trajectory.npz')) as t:
            n = len(t['actions'])
            if t['actions'].shape != (n, 12) or len(t['states']) != n+1:
                issues.append(f'{key}: malformed trajectory')
            if not np.isfinite(t['actions']).all() or np.any(np.abs(t['actions']) > 1+1e-6):
                issues.append(f'{key}: illegal executed action')
        trace = json.loads(path.with_name('trace.json').read_text())
        queries = json.loads(path.with_name('queries.json').read_text())
        if len(trace) != n or r['action_count'] != n or r['duration_s'] != n/20:
            issues.append(f'{key}: trajectory duration/count mismatch')
        if [q['step'] for q in queries] != list(range(0, n, pilot['replan_steps'])):
            issues.append(f'{key}: query schedule mismatch')
        if len(queries) != r['query_count'] or any(q['chunk_length'] != 50 for q in queries):
            issues.append(f'{key}: chunk metadata mismatch')
        if r['crash'] != any(t['unsafe'] for t in trace) or r['task_success'] != trace[-1]['task_success']:
            issues.append(f'{key}: scored flags disagree with trace')
        recalc = score(start_valid=True, identity_valid=True, task_success=r['task_success'],
                       crash=r['crash'], stable_terminal=r['stable_terminal'])
        if recalc != r['outcome']:
            issues.append(f'{key}: frozen outcome classification mismatch')
        for query in (queries[0], queries[-1]):
            with np.load(path.with_name(f"query_{query['step']:04d}.npz")) as obs:
                expected_keys = {'observation/state', 'observation/image', 'observation/right_image',
                                 'observation/wrist_image', 'prompt', 'predicted_actions'}
                if set(obs.files) != expected_keys or str(obs['prompt']) != r['instruction']:
                    issues.append(f'{key}: policy input allowlist or instruction mismatch')
                if obs['observation/state'].shape != (16,):
                    issues.append(f'{key}: proprioception shape mismatch')
                for name in ('observation/image', 'observation/right_image', 'observation/wrist_image'):
                    if obs[name].shape != (224,224,3) or obs[name].dtype != np.uint8:
                        issues.append(f'{key}: image shape/dtype mismatch')
    for key in sorted(expected-seen):
        issues.append(f'{key}: missing result')
    index = {(r['case_id'], r['branch'], r['sampling_seed']): r for r in results}
    for c in cases:
        for seed in pilot['sampling_seeds']:
            a, b = index.get((c,'safe_twin',seed)), index.get((c,'risk',seed))
            if a and b and not a.get('execution_error') and not b.get('execution_error'):
                for field in ('common_context_qpos','common_context_qvel','instruction'):
                    if a[field] != b[field]:
                        issues.append(f'{c}/{seed}: unmatched {field}')
    return results, issues


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--ffmpeg', type=Path)
    a = p.parse_args()
    provenance = json.loads((a.root / 'provenance.json').read_text())
    manifest = json.loads(Path('configs/robocasa_foundation/curated_v0_cases.json').read_text())
    pilot = provenance['pilot']
    results, issues = audit(a.root, manifest, pilot)
    audit_result = {'complete': len(results)==30, 'runs': len(results), 'issues': issues,
                    'passed': len(results)==30 and not issues}
    (a.root/'artifact_audit.json').write_text(json.dumps(audit_result,indent=2)+'\n')
    lines = ['# pi05 paired closed-loop pilot', '',
             f"Actual rollouts: {len(results)}/30. Artifact audit: {'PASS' if audit_result['passed'] else 'INCOMPLETE/FAIL'}.",
             '', 'Five frozen source episodes; repeats are sampling seeds, not new scenes.', '',
             '| Item | State | '+' | '.join(LABELS)+' |',
             '| --- | --- | '+' | '.join(['---:']*5)+' |']
    rows = []
    for c in manifest['benchmark_case_ids']:
        for b in pilot['states']:
            count = Counter(r['outcome'] for r in results if r['case_id']==c and r['branch']==b)
            row = [c,b]+[str(count[k]) for k in OUTCOMES]
            rows.append(row)
            lines.append('| '+' | '.join(row)+' |')
    lines += ['', '## Individual trajectories', '',
              '| Item | State | Seed | Outcome | Duration (s) | First danger (s) | Video |',
              '| --- | --- | ---: | --- | ---: | ---: | --- |']
    videos = []
    for r in results:
        name = f"{r['case_id']}_{r['branch']}_{r['sampling_seed']}"
        lines.append(f"| {r['case_id']} | {r['branch']} | {r['sampling_seed']} | {r['outcome']} | "
                     f"{r.get('duration_s','—')} | {r.get('time_to_violation_s','—')} | [video]({name}/policy_view.mp4) |")
        if r['sampling_seed']==pilot['sampling_seeds'][0]:
            video_path = f'{name}/policy_view.mp4'
            if a.ffmpeg and audit_result['passed']:
                target = a.root/name/'policy_view_h264.mp4'
                if not target.exists():
                    subprocess.run([str(a.ffmpeg), '-v', 'error', '-n', '-i', str(a.root/video_path),
                                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                                    '-threads', '2', str(target)], check=True)
                video_path = f'{name}/policy_view_h264.mp4'
            videos.append(f'<figure><figcaption>{html.escape(name)}: {html.escape(r["outcome"])}</figcaption>'
                          f'<video controls preload="metadata" width="320" src="{video_path}"></video></figure>')
    lines += ['', 'Original hazard and task scoring are unchanged. Invalid can also mean an unstable unsuccessful terminal state under the frozen classifier; see each result.json.',
              '', 'A normal-state failure alone is not recovery-specific evidence. The five curated items do not establish broad coverage or unseen-data generalization.',
              '', 'Each folder contains trajectory.npz, trace.json, queries.json and exact policy query inputs. Interface runs are excluded.']
    (a.root/'report.md').write_text('\n'.join(lines)+'\n')
    table = '<table><tr>'+''.join(f'<th>{x}</th>' for x in ('Item','State',*LABELS))+'</tr>'
    table += ''.join('<tr>'+''.join(f'<td>{html.escape(v)}</td>' for v in row)+'</tr>' for row in rows)+'</table>'
    page = '<!doctype html><meta charset="utf-8"><title>pi05 paired pilot</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto}table{border-collapse:collapse}td,th{padding:10px;border:1px solid #ddd}figure{display:inline-block;margin:15px}</style>'
    page += f'<h1>pi05 paired pilot: {len(results)}/30 rollouts</h1><p>Five frozen curated items; three fixed sampling seeds per state.</p>'+table+''.join(videos)
    page += '<p><a href="report.md">Detailed results</a> · <a href="results.csv">CSV</a> · <a href="artifact_audit.json">Artifact audit</a></p>'
    (a.root/'report.html').write_text(page)
    print(json.dumps(audit_result))
    return int(not audit_result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
