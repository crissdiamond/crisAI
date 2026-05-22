#!/usr/bin/env bash
# Show provider-backed review agents and local generic leases.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HCOM_DIR="${HCOM_DIR:-$ROOT_DIR/.hcom}"
STATE_DIR="${HCOM_DEVELOPMENT_DIR:-$ROOT_DIR/.hcom-development}"
LEASES="${HCOM_REVIEW_LEASES:-$STATE_DIR/review_leases.local.yaml}"

"$ROOT_DIR/scripts/hcom_claude_status.sh" || true

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
    if str(agent.get("tool", "")).lower() == "agy"
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
    raise SystemExit(0)

now = int(time())
print("Antigravity reviewers:")
for name in names:
    lease = leases.get(name, {})
    agent = live.get(name, {})
    expires_epoch = int(lease.get("expires_at_epoch") or "0")
    lease_state = "no lease"
    if expires_epoch:
        lease_state = "expired" if expires_epoch < now else f"{max(0, (expires_epoch - now) // 60)}m remaining"
    status = agent.get("status") or lease.get("status") or "not-live"
    print(f"- {name}: {lease.get('role', 'unknown')} thread={lease.get('thread', 'unknown')} tag={agent.get('tag') or lease.get('tag', '')} status={status} lease={lease_state}")
PY
