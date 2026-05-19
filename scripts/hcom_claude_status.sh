#!/usr/bin/env bash
# Show active ephemeral Claude reviewers and their local leases.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HCOM_DIR="${HCOM_DIR:-$ROOT_DIR/.hcom}"
STATE_DIR="${HCOM_DEVELOPMENT_DIR:-$ROOT_DIR/.hcom-development}"
LEASES="${HCOM_CLAUDE_REVIEW_LEASES:-$STATE_DIR/claude_review_leases.local.yaml}"

if ! command -v hcom >/dev/null 2>&1; then
  echo "Missing required command: hcom" >&2
  exit 1
fi

HCOM_JSON="$(hcom list --json 2>/dev/null || echo "[]")"
HCOM_JSON="$HCOM_JSON" python - "$LEASES" <<'PY'
import json
import os
import sys
from pathlib import Path
from time import time

leases_path = Path(sys.argv[1])
try:
    agents = json.loads(os.environ.get("HCOM_JSON") or "[]")
except json.JSONDecodeError:
    agents = []

live = {
    agent.get("name"): agent
    for agent in agents
    if str(agent.get("tool", "")).lower() == "claude"
    and str(agent.get("tag", "")).endswith("-review")
}

leases: dict[str, dict[str, str]] = {}
if leases_path.exists():
    current = ""
    for raw in leases_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            current = line.strip()[:-1]
            leases[current] = {}
        elif current and line.startswith("    ") and ":" in line:
            key, value = line.strip().split(":", 1)
            leases[current][key] = value.strip().strip('"')

names = sorted(set(live) | set(leases))
if not names:
    print("No ephemeral Claude reviewers found.")
    raise SystemExit(0)

now = int(time())
print("Claude reviewers:")
for name in names:
    lease = leases.get(name, {})
    agent = live.get(name, {})
    expires_epoch = int(lease.get("expires_at_epoch") or "0")
    if expires_epoch and expires_epoch < now:
        lease_state = "expired"
    elif expires_epoch:
        lease_state = f"{max(0, (expires_epoch - now) // 60)}m remaining"
    else:
        lease_state = "no lease"
    status = agent.get("status") or lease.get("status") or "not-live"
    role = lease.get("role", "unknown")
    thread = lease.get("thread", "unknown")
    tag = agent.get("tag") or lease.get("tag", "")
    print(f"- {name}: {role} thread={thread} tag={tag} status={status} lease={lease_state}")
PY
