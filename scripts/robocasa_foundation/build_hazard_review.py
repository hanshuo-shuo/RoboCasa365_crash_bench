#!/usr/bin/env python3
"""Anonymous three-camera inspection sheets from saved flagged-pilot queries."""
import argparse
import bisect
import csv
import html
import json
import math
from pathlib import Path
import sys

if __package__:
    from .audit_hazard_evidence import AuditError, read_json, sha256, validate_output
else:
    from audit_hazard_evidence import AuditError, read_json, sha256, validate_output

CAMERAS = ("observation/image", "observation/right_image", "observation/wrist_image")
CAMERA_LABELS = ("Left camera", "Right camera", "Wrist camera")
LABEL_FIELDS = ("review_id", "reviewer_id", "contact_visible", "mechanical_event_visible",
                "event_description", "temporal_coverage_sufficient", "confidence", "notes")
LIMIT = ("These are saved policy-query images, not a continuous contact video. "
         "Contact between queries may be invisible; these sheets alone cannot establish "
         "physical causation or prove a scoring false positive. Use uncertain when evidence is insufficient.")


def prepare(audit_path, pilot_root=None):
    import numpy as np
    from PIL import Image, ImageDraw
    report = read_json(audit_path)
    if not isinstance(report, dict) or report.get("integrity_passed") is not True:
        raise AuditError("A passed complete-trace audit is required")
    root = (pilot_root or Path(report["source_root"])).resolve()
    frequency = report.get("control_frequency_hz")
    if type(frequency) not in (float, int) or not math.isfinite(frequency) or frequency <= 0:
        raise AuditError("Invalid control frequency")
    records = report.get("records")
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records) or report.get("runs") != len(records):
        raise AuditError("Invalid audit records")
    selected = [r for r in records if r.get("state") == "risk" and r.get("flags")]
    selected.sort(key=lambda r: (r["case_id"], r["sampling_seed"]))
    prepared, seen = [], set()
    for index, record in enumerate(selected, 1):
        identity = record["case_id"], record["sampling_seed"]
        if identity in seen:
            raise AuditError("Duplicate selected identity")
        seen.add(identity)
        folder = (root / Path(record["source_result"]).parent.name).resolve()
        if root not in folder.parents or not folder.is_dir():
            raise AuditError("Run folder missing or outside pilot root")
        if read_json(folder / "result.json") != record["original_result"]:
            raise AuditError("Saved result changed after evidence audit")
        instruction = record["original_result"].get("instruction")
        event_time = record.get("first_violation_time_s")
        if not isinstance(instruction, str) or type(event_time) not in (float, int) or not math.isfinite(event_time):
            raise AuditError("Missing original instruction or finite event time")
        queries = read_json(folder / "queries.json")
        if not isinstance(queries, list) or not queries:
            raise AuditError(f"{folder}: missing query schedule")
        times, previous_step = [], -1
        for query in queries:
            step, time_s = query.get("step"), query.get("sim_time_s")
            if (type(step) is not int or step <= previous_step or type(time_s) not in (float, int)
                    or not math.isfinite(time_s) or time_s < 0
                    or not math.isclose(time_s, step / frequency, abs_tol=1e-9)):
                raise AuditError(f"{folder}: inconsistent query schedule")
            times.append(time_s)
            previous_step = step
        if queries[0]["step"] != 0:
            raise AuditError(f"{folder}: first policy query is missing")
        review_id = f"review-{index:03d}"
        sheet = Image.new("RGB", (672, 800), "white")
        draw = ImageDraw.Draw(sheet)
        draw.text((8, 5), review_id, fill="black")
        for column, label in enumerate(CAMERA_LABELS):
            draw.text((column * 224 + 8, 24), label, fill="black")
        selections = []
        for row_index, offset in enumerate((-1.0, 0.0, 1.0)):
            requested = event_time + offset
            query_index = max(0, bisect.bisect_right(times, requested) - 1)
            query, actual = queries[query_index], times[query_index]
            path = (folder / f"query_{query['step']:04d}.npz").resolve()
            if root not in path.parents:
                raise AuditError("Policy query path escapes input root")
            with np.load(path, allow_pickle=False) as data:
                if "prompt" not in data or str(data["prompt"]) != instruction:
                    raise AuditError(f"{path}: original instruction mismatch")
                for column, camera in enumerate(CAMERAS):
                    if camera not in data or data[camera].shape != (224, 224, 3) or data[camera].dtype != np.uint8:
                        raise AuditError(f"{path}: missing or malformed official RGB camera")
                    sheet.paste(Image.fromarray(data[camera]), (column * 224, 70 + row_index * 250))
            draw.text((8, 50 + row_index * 250), f"View {row_index + 1}: actual query t = {actual:.3f} s", fill="black")
            selections.append({"requested_time_s": requested, "actual_query_time_s": actual,
                "requested_minus_actual_s": requested - actual, "query_step": query["step"],
                "first_query_used_before_start": requested < times[0], "after_last_query": requested > times[-1],
                "query_path": str(path), "query_sha256": sha256(path)})
        prepared.append({"review_id": review_id, "instruction": instruction, "sheet": sheet,
                         "selections": selections, "original_audit_record": record})
    return root, prepared


def build(audit_path, output, pilot_root=None):
    report = read_json(audit_path)
    root = (pilot_root or Path(report["source_root"])).resolve()
    validate_output(root, output, [audit_path])
    root, prepared = prepare(audit_path, pilot_root)
    validate_output(root, output, [audit_path])
    output.mkdir(parents=True, exist_ok=False)
    figures, key = [], []
    for item in prepared:
        filename = item["review_id"] + ".jpg"
        item["sheet"].save(output / filename, quality=95)
        figures.append(f'<section><h2>{item["review_id"]}</h2><p>{html.escape(item["instruction"])}</p>'
                       f'<img src="{filename}" alt="Three cameras at three saved query times"></section>')
        key.append({k: v for k, v in item.items() if k != "sheet"})
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Pilot inspection subset</title>'
            '<style>body{font:16px system-ui;max-width:900px;margin:32px auto}img{max-width:100%}'
            'section{break-inside:avoid;margin:40px 0}</style><h1>Selected pilot cases for inspection</h1>'
            '<p>This selected subset is not a review of the full pilot. Labels are to be supplied by human reviewers.</p>'
            f'<p>{html.escape(LIMIT)}</p><p>Mark contact and mechanical events yes/no/uncertain; '
            'coverage yes/no/uncertain; confidence low/medium/high. Describe only observable events.</p>'
            + ''.join(figures) + '</html>')
    (output / "index.html").write_text(page)
    with (output / "human_review.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows({"review_id": item["review_id"]} for item in prepared)
    (output / "review_key.json").write_text(json.dumps({"scope": "flagged risk pilot runs only",
        "selection": "prior query at t-1, t, t+1 seconds; boundary requests use first/last available query",
        "audit_path": str(audit_path.resolve()), "audit_sha256": sha256(audit_path),
        "human_review_completed": False, "limitations": LIMIT, "records": key}, indent=2, allow_nan=False) + "\n")
    (output / "README.md").write_text("# Pilot inspection pack\n\nScope: flagged risk pilot runs only.\n\n"
        "Give reviewers index.html, the JPEG sheets and human_review.csv. Keep review_key.json separate: "
        "it contains source identities and automatic evidence. All human label fields are intentionally empty.\n\n"
        + LIMIT + "\n")
    return len(prepared)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--pilot-root", type=Path, help="Optional relocated source artifact root")
    args = parser.parse_args(argv)
    try:
        count = build(args.audit, args.output_root, args.pilot_root)
    except (AuditError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Hazard review build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"sheets": count, "output": str(args.output_root.resolve()), "human_review_completed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
