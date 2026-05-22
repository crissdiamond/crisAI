#!/usr/bin/env bash
# Close provider-backed review agents by delegating to provider-specific logic.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HCOM_DIR="${HCOM_DIR:-$ROOT_DIR/.hcom}"
STATE_DIR="${HCOM_DEVELOPMENT_DIR:-$ROOT_DIR/.hcom-development}"
LEASES="${HCOM_REVIEW_LEASES:-$STATE_DIR/review_leases.local.yaml}"
PROVIDER="${HCOM_TEAM_REVIEW_PROVIDER:-all}"
ARGS=()
NAME=""
ROLE=""
THREAD=""
EXPIRED=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider)
      PROVIDER="$2"
      shift 2
      ;;
    --name)
      NAME="$2"
      ARGS+=("$1" "$2")
      shift 2
      ;;
    --role)
      ROLE="$2"
      ARGS+=("$1" "$2")
      shift 2
      ;;
    --thread)
      THREAD="$2"
      ARGS+=("$1" "$2")
      shift 2
      ;;
    --expired)
      EXPIRED=1
      ARGS+=("$1")
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      ARGS+=("$1")
      shift
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

case "$PROVIDER" in
  claude|claude-code|claude_code)
    exec "$ROOT_DIR/scripts/hcom_claude_close.sh" "${ARGS[@]}"
    ;;
  antigravity|agy|all)
    ;;
  *)
    echo "Unsupported review provider: $PROVIDER" >&2
    exit 2
    ;;
esac

if [[ "$PROVIDER" == "all" ]]; then
  "$ROOT_DIR/scripts/hcom_claude_close.sh" "${ARGS[@]}" || true
fi

if ! command -v hcom >/dev/null 2>&1; then
  echo "Missing required command: hcom" >&2
  exit 1
fi

HCOM_JSON="$(hcom list --json 2>/dev/null || echo "[]")"
mapfile -t TARGETS < <(HCOM_JSON="$HCOM_JSON" python - "$LEASES" "$NAME" "$ROLE" "$THREAD" "$EXPIRED" <<'PY'
import json
import os
import sys
from pathlib import Path
from time import time

leases_path = Path(sys.argv[1])
name_filter = sys.argv[2]
role_filter = sys.argv[3]
thread_filter = sys.argv[4]
expired_only = sys.argv[5] == "1"

try:
    agents = json.loads(os.environ.get("HCOM_JSON") or "[]")
except json.JSONDecodeError:
    agents = []

leases = {}
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

live_review_names = {
    agent.get("name")
    for agent in agents
    if str(agent.get("tool", "")).lower() == "agy" and str(agent.get("tag", "")).endswith("-review")
}

now = int(time())
for candidate in sorted(set(live_review_names) | set(leases)):
    if not candidate:
        continue
    lease = leases.get(candidate, {})
    if name_filter and candidate != name_filter:
        continue
    if role_filter and lease.get("role") != role_filter:
        continue
    if thread_filter and lease.get("thread") != thread_filter:
        continue
    if expired_only:
        expires = int(lease.get("expires_at_epoch") or "0")
        if not expires or expires >= now:
            continue
    print(candidate)
PY
)

if [[ "${#TARGETS[@]}" -eq 0 ]]; then
  echo "No matching Antigravity reviewers found."
  exit 0
fi

for target in "${TARGETS[@]}"; do
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'DRY RUN: hcom kill %q\n' "$target"
  else
    hcom kill "$target" || true
  fi
done
