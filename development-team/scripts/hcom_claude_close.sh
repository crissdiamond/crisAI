#!/usr/bin/env bash
# Close ephemeral Claude reviewers for a target crisAI hcom task.
set -euo pipefail

TEAM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_REPO="$TEAM_DIR"
NAME=""
ROLE=""
THREAD=""
EXPIRED=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: scripts/hcom_claude_close.sh [--target-repo PATH] [selector] [--dry-run]

Selectors:
  --name HCOM_NAME
  --role runtime_claude|gem_claude|web_claude
  --thread THREAD
  --expired
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-repo)
      TARGET_REPO="$(cd "$2" && pwd)"
      shift 2
      ;;
    --name)
      NAME="$2"; shift 2 ;;
    --role)
      ROLE="$2"; shift 2 ;;
    --thread)
      THREAD="$2"; shift 2 ;;
    --expired)
      EXPIRED=1; shift ;;
    --dry-run)
      DRY_RUN=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$NAME" && -z "$ROLE" && -z "$THREAD" && "$EXPIRED" -eq 0 ]]; then
  echo "Pass at least one selector." >&2
  usage >&2
  exit 2
fi

export HCOM_DIR="${HCOM_DIR:-$TARGET_REPO/.hcom}"
STATE_DIR="${HCOM_DEVELOPMENT_DIR:-$TARGET_REPO/.hcom-development}"
LEASES="${HCOM_CLAUDE_REVIEW_LEASES:-$STATE_DIR/claude_review_leases.local.yaml}"

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

live_review_names = {
    agent.get("name")
    for agent in agents
    if str(agent.get("tool", "")).lower() == "claude"
    and str(agent.get("tag", "")).endswith("-review")
}

now = int(time())
targets = []
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
    targets.append(candidate)

for target in targets:
    print(target)
PY
)

if [[ "${#TARGETS[@]}" -eq 0 ]]; then
  echo "No matching ephemeral Claude reviewers found."
  exit 0
fi

for target in "${TARGETS[@]}"; do
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'DRY RUN: hcom kill %q\n' "$target"
  else
    hcom kill "$target" || true
  fi
done
