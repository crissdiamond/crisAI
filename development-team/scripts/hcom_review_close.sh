#!/usr/bin/env bash
# Delegate provider-backed review close to the target crisAI repository.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-repo)
      TARGET_REPO="$2"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/hcom_review_close.sh --target-repo PATH [selectors]

Delegates to PATH/scripts/hcom_review_close.sh.
EOF
      exit 0
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

exec "$TARGET_REPO/scripts/hcom_review_close.sh" "${ARGS[@]}"
