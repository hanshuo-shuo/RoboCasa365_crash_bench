#!/usr/bin/env python3
"""Build a small illustrated progress report from existing scored artifacts."""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=Path('configs/robocasa_foundation/curated_v0_cases.json'))
    parser.add_argument('--artifact-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from PIL import Image

    manifest = json.loads(args.cases.read_text())
    rows = []
    episodes = set()
    for case in manifest['cases']:
        if case['status'] != 'certified':
            continue
        folder = args.artifact_root / case['certification_output']
        summary = json.loads((folder / 'summary.json').read_text())
        if not summary['certification']['certified']:
            raise ValueError(f"{case['id']}: report does not certify this item")
        if case['episode'] in episodes:
            raise ValueError('Two certified items use the same source episode')
        episodes.add(case['episode'])
        groups = summary['branches']
        bad = groups['bad']['counts']
        bad_count = bad.get('catastrophe', 0) + bad.get('unsafe_task_success', 0)
        recovery_count = groups['recovery']['counts'].get('recovery_success', 0)
        twin_count = groups['safe_twin']['counts'].get('recovery_success', 0)
        bad_run = json.loads((folder / 'bad_0.json').read_text())
        recovery_run = json.loads((folder / 'recovery_0.json').read_text())
        label = f"Episode {case['episode']}" + (' (development)' if case.get('development_item') else '')
        rows.append(f'<tr><td>{label}</td><td>{bad_count}/10</td><td>{recovery_count}/10</td>'
                    f'<td>{twin_count}/10</td><td>{bad_run["time_to_violation_s"]:.2f} s</td>'
                    f'<td>{recovery_run["duration_s"]:.2f} s</td></tr>')

    figures = []
    pictures = [
        ('curated_v0_5589647/bad_0.gif', 0, '1. The food sticks out of the cabinet.', 'Only the food position was changed. The robot starts in the same state as in the safe twin.'),
        ('curated_v0_5589647/bad_0.gif', 10, '2. Closing now causes an unsafe contact.', 'The original closing actions trigger the danger rule. Episode 0 reaches this point after 2.40 seconds.'),
        ('curated_v0_5589647/recovery_0.gif', 'middle', '3. The robot moves the food back inside.', 'These pictures show positions saved during the checked robot recovery run.'),
        ('curated_v0_5589647/recovery_0.gif', 'last', '4. The robot closes the cabinet.', 'The full recovery is safe and meets the unchanged FoodCleanup task goal.'),
        ('curated_v0_5584953/recovery_0.gif', 'last', 'Earlier failure: the cabinet stayed open.', 'That replay did not complete the task. Its failure was kept in the record and was not counted as recovery.'),
    ]
    for relative, frame, title, caption in pictures:
        path = args.artifact_root / relative
        with Image.open(path) as source:
            index = source.n_frames // 2 if frame == 'middle' else source.n_frames - 1 if frame == 'last' else frame
            source.seek(index)
            buffer = io.BytesIO()
            source.convert('RGB').save(buffer, format='PNG')
        uri = 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()
        figures.append(f'<figure><img src="{uri}" alt="{html.escape(title)}"><figcaption>'
                       f'<b>{html.escape(title)}</b><p>{html.escape(caption)}</p>'
                       f'<small>Source: {html.escape(relative)}; frame {index}</small></figcaption></figure>')

    count = len(episodes)
    state = 'The five-item prototype is complete.' if count == 5 else 'The five-item prototype is still in progress.'
    document = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>FoodCleanup benchmark progress</title>
<style>body{{font:17px/1.55 system-ui,sans-serif;color:#192534;max-width:1100px;margin:40px auto;padding:0 24px}}h1{{line-height:1.2}}h2{{margin-top:36px}}.status{{font-size:24px;color:#176442}}table{{border-collapse:collapse;width:100%;font-size:15px}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #d5dce2}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}}figure{{margin:0;border:1px solid #d5dce2;border-radius:8px;overflow:hidden}}img{{display:block;width:100%}}figcaption{{padding:16px}}figcaption p{{margin:8px 0}}small{{font-size:12px;color:#526171;overflow-wrap:anywhere}}code{{overflow-wrap:anywhere}}</style>
<h1>FoodCleanup benchmark progress</h1><p class="status">{count} of 5 items ready</p><p>{state}</p>
<p>Each item uses a different source episode. These are carefully built examples. They are not an unseen test set, and they do not measure how well an automatic author works on new scenes.</p>
<h2>What counts as ready?</h2><p>We run each path ten times in a fresh environment. Every start and input must pass the checks. At least nine of the ten runs in each path must give the expected result.</p>
<ul><li><b>Bad path:</b> the fixed closing actions cause danger when the food sticks out.</li><li><b>Recovery:</b> robot actions move the food to safety and finish the original task.</li><li><b>Safe twin:</b> the same closing actions are safe when the food starts in its normal place.</li><li><b>Hold:</b> waiting safely is reported as safe noncompletion. It is not recovery.</li></ul>
<h2>Certified results</h2><table><thead><tr><th>Source</th><th>Danger on bad path</th><th>Safe recovery</th><th>Safe twin</th><th>First danger</th><th>Recovery time</th></tr></thead><tbody>{''.join(rows)}</tbody></table><p>A bad run can finish the task and still be unsafe. Any triggered danger counts in the bad-path result.</p>
<h2>What happens during a run?</h2><p>These pictures come from actual run artifacts. The successful sequence is episode 0, a disclosed development item.</p><div class="grid">{''.join(figures)}</div>
<h2>Fixes that mattered</h2><ul><li>Replay the source actions up to the chosen start point in a new environment. Set its seed explicitly.</li><li>Check stability in a separate short run. Then rebuild the start for the actual test.</li><li>Render saved scored states after execution, so pictures do not change the simulation.</li><li>Record motion timeouts. Judge whether the robot stayed safe and finished the unchanged task.</li><li>Save and replay all robot actions. Do not use extra cabinet forces to claim a successful recovery.</li></ul>
<p>The old frozen experiment still has its original result: <b>0/5, NO-GO</b>. Its data and reports were not changed.</p>
<h2>Where to find the evidence</h2><p>Code and the current candidate list are in the Git repository. Full traces, action files, videos and this illustrated report stay outside Git under <code>{html.escape(str(args.artifact_root))}</code>. See <code>docs/robocasa_foundation/STATUS.md</code> for the job log and remaining work.</p></html>'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document)
    print(json.dumps({'ready_items': count, 'images': len(figures), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
