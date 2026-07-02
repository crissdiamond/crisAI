#!/usr/bin/env python3
"""Summarise a crisAI run: stages, gates, checkpoints, tokens, and cost.

READ-ONLY. Accepts either kind of run record this repo produces:

  1. A web run snapshot (schema ui_run_state_v1), i.e. one file under
     workspace/tasks/<session>/.crisai/runs/<run_id>.json
  2. The shared trace log logs/agent_trace.jsonl (optionally filtered
     with --run <run_id or prefix>; default = latest run in the file).

Usage:
    python3 summarise_run.py workspace/tasks/Test003/.crisai/runs/<run_id>.json
    python3 summarise_run.py logs/agent_trace.jsonl [--run <run_id_prefix>]

Exit codes: 0 = summarised; 1 = file unreadable / no matching run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _fmt_tokens(n: int) -> str:
    return f"{n:,}" if n else "-"


def _obs_row(obs: dict) -> tuple[int, int, int, float, str, int]:
    """Return (input, output, cached, cost_usd, model, duration_ms) from observability."""
    pu = obs.get("provider_usage") or {}
    cost = obs.get("cost") or {}
    model = obs.get("model") or {}
    et = obs.get("execution_time") or {}
    return (
        int(pu.get("input_tokens") or 0),
        int(pu.get("output_tokens") or 0),
        int(pu.get("cached_tokens") or 0),
        float(cost.get("total_cost_usd") or 0.0),
        str(model.get("model_name") or ""),
        int(et.get("duration_ms") or 0),
    )


def _print_stage_table(rows: list[dict]) -> None:
    if not rows:
        print("  (no stage output events found)")
        return
    header = f"  {'stage':<28} {'model':<22} {'in tok':>9} {'out tok':>9} {'cached':>9} {'ms':>8} {'cost USD':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    t_in = t_out = t_cached = 0
    t_cost = 0.0
    for r in rows:
        t_in += r["in"]
        t_out += r["out"]
        t_cached += r["cached"]
        t_cost += r["cost"]
        cost_s = f"{r['cost']:.6f}" if r["cost"] else "-"
        print(
            f"  {r['stage'][:28]:<28} {r['model'][:22]:<22} {_fmt_tokens(r['in']):>9}"
            f" {_fmt_tokens(r['out']):>9} {_fmt_tokens(r['cached']):>9} {r['ms']:>8} {cost_s:>10}"
        )
    total_cost_s = f"{t_cost:.6f}" if t_cost else "- (no pricing in registry/models.yaml)"
    print("  " + "-" * (len(header) - 2))
    print(
        f"  {'TOTAL':<28} {'':<22} {_fmt_tokens(t_in):>9} {_fmt_tokens(t_out):>9}"
        f" {_fmt_tokens(t_cached):>9} {'':>8} {total_cost_s:>10}"
    )


def summarise_snapshot(payload: dict) -> None:
    """Summarise a ui_run_state_v1 web run snapshot."""
    md = payload.get("metadata") or {}
    dec = payload.get("decision") or {}
    print(f"run_id:        {payload.get('run_id')}")
    print(f"session:       {payload.get('session')}")
    print(f"status:        {payload.get('status')}")
    print(f"created_at:    {md.get('created_at')}")
    print(f"completed_at:  {md.get('completed_at')}")
    print(f"trace_run_id:  {md.get('trace_run_id')}  (run_id inside logs/agent_trace.jsonl)")
    print(
        f"routing:       intent={dec.get('intent')} mode={dec.get('mode')} "
        f"agent={dec.get('agent')} confidence={dec.get('confidence')}"
    )
    rc = md.get("request_contract") or {}
    if rc:
        print(
            f"contract:      source_required={rc.get('source_required')} "
            f"evidence_level={rc.get('required_evidence_level')} "
            f"output_path={rc.get('output_path')}"
        )
    expected = [s.get("key") for s in payload.get("expected_stages") or []]
    print(f"expected:      {' -> '.join(str(s) for s in expected)}")

    events = payload.get("events") or []
    if len(events) >= 500:
        print(
            "WARNING:       events list is at the 500-event persistence cap "
            "(MAX_EVENTS_PER_RUN); later events were dropped. Use "
            "logs/agent_trace.jsonl with trace_run_id above for the full record."
        )

    rows: list[dict] = []
    checkpoints: list[str] = []
    problems: list[str] = []
    for e in events:
        et = e.get("event_type")
        emd = e.get("metadata") or {}
        if et == "stage_output":
            obs = emd.get("observability") or {}
            i, o, c, cost, model, ms = _obs_row(obs)
            rows.append(
                {"stage": str(e.get("stage") or "?"), "model": model, "in": i,
                 "out": o, "cached": c, "cost": cost, "ms": ms}
            )
        elif et == "checkpoint_requested":
            checkpoints.append(
                f"requested (attempt {emd.get('attempt')}, "
                f"remaining_redirects {emd.get('remaining_redirects')})"
            )
        elif et == "checkpoint_decision":
            checkpoints.append(f"decision: {emd.get('action')}")
        elif et in {"stage_error", "run_failed"}:
            problems.append(f"{et}: {str(e.get('summary') or e.get('content') or '')[:160]}")

    print("\nStages (from persisted events):")
    _print_stage_table(rows)
    if checkpoints:
        print("\nRetrieval checkpoint:")
        for c in checkpoints:
            print(f"  - {c}")
    err = str(payload.get("error") or "").strip()
    if err:
        problems.append(f"run error: {err[:300]}")
    if problems:
        print("\nGates / errors:")
        for p in problems:
            print(f"  - {p}")
    final = str(payload.get("final_output") or "").strip()
    print(f"\nfinal_output:  {len(final)} chars"
          + (f" | starts: {final[:120]!r}" if final else " (empty)"))


def summarise_trace(path: Path, run_filter: str | None) -> int:
    """Summarise one run from the JSONL agent trace (grouped by run_id)."""
    runs: dict[str, list[dict]] = {}
    order: list[str] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                e = json.loads(raw)
            except json.JSONDecodeError:
                continue
            rid = e.get("run_id")
            if not isinstance(rid, str) or not rid:
                continue
            if rid not in runs:
                runs[rid] = []
                order.append(rid)
            runs[rid].append(e)

    if run_filter:
        matches = [r for r in order if r == run_filter or r.startswith(run_filter)]
        if not matches:
            print(f"No run matching {run_filter!r} in {path}", file=sys.stderr)
            return 1
        rid = matches[-1]
    else:
        if not order:
            print(f"No run_id-bearing events in {path}", file=sys.stderr)
            return 1
        rid = order[-1]

    events = runs[rid]
    print(f"run_id:        {rid}   ({len(events)} trace events)")
    print(f"first event:   {events[0].get('timestamp')}")
    print(f"last event:    {events[-1].get('timestamp')}")
    for e in events:
        if e.get("stage") == "WORKFLOW_START":
            print(f"mode:          {(e.get('metadata') or {}).get('mode')}")
            break
    for e in events:
        if e.get("stage") == "REQUEST_CONTRACT":
            rc = (e.get("metadata") or {}).get("contract") or e.get("metadata") or {}
            print(
                f"contract:      source_required={rc.get('source_required')} "
                f"evidence_level={rc.get('required_evidence_level')}"
            )
            break

    rows: list[dict] = []
    checkpoints: list[str] = []
    problems: list[str] = []
    signals: list[str] = []
    for e in events:
        et = e.get("event_type")
        md = e.get("metadata") or {}
        if et == "stage_output" or (et == "workflow_output" and md.get("observability")):
            obs = md.get("observability") or {}
            i, o, c, cost, model, ms = _obs_row(obs)
            rows.append(
                {"stage": str(e.get("agent_id") or e.get("stage") or "?"), "model": model,
                 "in": i, "out": o, "cached": c, "cost": cost, "ms": ms}
            )
        elif et in {"checkpoint", "checkpoint_decision"}:
            checkpoints.append(f"{et}: {str(e.get('stage'))} {str(md.get('action') or '')}".strip())
        elif et in {"policy_violation", "stage_error"}:
            problems.append(f"{et} [{e.get('stage')}]: {str(e.get('content') or '')[:160]}")
        elif et == "policy_signal":
            signals.append(str(e.get("stage")))
        elif et == "stage_skipped":
            signals.append(f"skipped:{e.get('stage')}")

    print(f"policy signals: {', '.join(signals) if signals else '(none)'}")
    print("\nStages:")
    _print_stage_table(rows)
    if checkpoints:
        print("\nCheckpoints:")
        for c in checkpoints:
            print(f"  - {c}")
    if problems:
        print("\nGates / errors:")
        for p in problems:
            print(f"  - {p}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Run snapshot .json or agent_trace.jsonl")
    parser.add_argument("--run", default=None, help="run_id (prefix ok) when reading a .jsonl trace")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_file():
        print(f"Not a file: {path}", file=sys.stderr)
        return 1

    if path.suffix == ".jsonl":
        return summarise_trace(path, args.run)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not parse {path}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print(f"Unexpected JSON shape in {path}", file=sys.stderr)
        return 1
    if payload.get("schema_version") == "ui_run_state_v1":
        summarise_snapshot(payload)
        return 0
    print(
        f"Unrecognised schema_version={payload.get('schema_version')!r}; "
        "expected ui_run_state_v1 or a .jsonl trace.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
