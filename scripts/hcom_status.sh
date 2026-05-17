#!/usr/bin/env bash
# Show crisAI hcom team status.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HCOM_DIR="${HCOM_DIR:-$ROOT_DIR/.hcom}"
ASSIGNMENTS="$ROOT_DIR/reference/development/session_assignments.local.yaml"

if ! command -v hcom >/dev/null 2>&1; then
  echo "Missing required command: hcom" >&2
  exit 1
fi

echo "HCOM_DIR=$HCOM_DIR"
if [[ -f "$ASSIGNMENTS" ]]; then
  echo
  echo "Session assignments:"
  sed -n '1,220p' "$ASSIGNMENTS"
else
  echo
  echo "No local session assignments found at $ASSIGNMENTS"
fi

echo
hcom list -v
