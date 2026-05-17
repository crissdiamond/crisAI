#!/usr/bin/env bash
# Stop crisAI hcom development team tags for a target repository.
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
      echo "Usage: scripts/hcom_stop.sh [--target-repo PATH]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

export HCOM_DIR="${HCOM_DIR:-$TARGET_REPO/.hcom}"

if ! command -v hcom >/dev/null 2>&1; then
  echo "Missing required command: hcom" >&2
  exit 1
fi

for tag in crisai-orchestrator crisai-runtime crisai-gem crisai-web; do
  hcom kill "tag:$tag" || true
done
