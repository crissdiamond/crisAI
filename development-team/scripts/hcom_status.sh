#!/usr/bin/env bash
# Show crisAI hcom development team status for a target repository.
set -euo pipefail

TEAM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_REPO="$TEAM_DIR"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-repo)
      TARGET_REPO="$(cd "$2" && pwd)"
      shift 2
      ;;
    -h|--help)
      echo "Usage: scripts/hcom_status.sh [--target-repo PATH]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

export HCOM_DIR="${HCOM_DIR:-$TARGET_REPO/.hcom}"
ASSIGNMENTS="${HCOM_ASSIGNMENTS:-$TARGET_REPO/.hcom-development/session_assignments.local.yaml}"

if ! command -v hcom >/dev/null 2>&1; then
  echo "Missing required command: hcom" >&2
  exit 1
fi

echo "Target repo=$TARGET_REPO"
echo "Team repo=$TEAM_DIR"
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
