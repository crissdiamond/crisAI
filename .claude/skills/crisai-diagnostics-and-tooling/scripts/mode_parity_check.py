#!/usr/bin/env python3
"""Mode-parity helper: diff the call graphs of the three execution modes.

READ-ONLY. Mode-parity gaps (a fix landing in run_pipeline/run_single but not
run_peer_pipeline) are this repo's dominant regression pattern. This script
parses src/crisai/cli/pipelines.py with ast, collects every function call made
inside run_single, run_pipeline, and run_peer_pipeline, and prints the calls
present in one mode but absent in another so a reviewer can ask "should the
peer path do this too?" for each line.

A difference is NOT automatically a bug — some asymmetries are intentional
(e.g. the pipeline-only _framing_only_planner_spec is a known open gap in
peer mode, TODO-057). Treat the output as a checklist, not a verdict.

Usage:
    python3 mode_parity_check.py [path/to/pipelines.py]
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

MODES = ("run_single", "run_pipeline", "run_peer_pipeline")

# Calls with no behavioural meaning for parity review.
NOISE = {
    "str", "len", "list", "dict", "set", "bool", "int", "float", "print",
    "isinstance", "getattr", "sorted", "join", "strip", "lower", "get",
    "append", "extend", "items", "keys", "values", "startswith", "endswith",
    "splitlines", "format", "Path", "enumerate", "repr", "max", "min",
}


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def collect_calls(tree: ast.Module) -> dict[str, set[str]]:
    calls: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in MODES:
            names: set[str] = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    name = _call_name(sub)
                    if name and name not in NOISE:
                        names.add(name)
            calls[node.name] = names
    return calls


def main() -> int:
    default = Path(__file__).resolve()
    # Walk up to the repo root (the directory containing src/).
    for parent in default.parents:
        if (parent / "src" / "crisai" / "cli" / "pipelines.py").is_file():
            default = parent / "src" / "crisai" / "cli" / "pipelines.py"
            break
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    if not path.is_file():
        print(f"Not a file: {path}", file=sys.stderr)
        return 1

    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = collect_calls(tree)
    missing = [m for m in MODES if m not in calls]
    if missing:
        print(f"Functions not found in {path}: {missing}", file=sys.stderr)
        return 1

    pairs = [
        ("run_pipeline", "run_peer_pipeline"),
        ("run_peer_pipeline", "run_pipeline"),
        ("run_single", "run_pipeline"),
    ]
    for present_in, absent_from in pairs:
        diff = sorted(calls[present_in] - calls[absent_from])
        print(f"\nCalls in {present_in} but NOT in {absent_from} ({len(diff)}):")
        for name in diff:
            print(f"  {name}")
    print(
        "\nReview question for each line: is the asymmetry intentional, or a "
        "parity gap like the ones fixed in PRs #29 (gate), #39 (planner "
        "fallback), #44 (materialisation)?"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
