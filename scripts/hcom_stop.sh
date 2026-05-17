#!/usr/bin/env bash
# Stop the crisAI hcom development team.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HCOM_DIR="${HCOM_DIR:-$ROOT_DIR/.hcom}"

if ! command -v hcom >/dev/null 2>&1; then
  echo "Missing required command: hcom" >&2
  exit 1
fi

for tag in crisai-orchestrator crisai-runtime crisai-gem crisai-web; do
  hcom kill "tag:$tag" || true
done
