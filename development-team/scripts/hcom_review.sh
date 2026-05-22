#!/usr/bin/env bash
# Delegate provider-backed review launch to the target crisAI repository.
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
Usage: scripts/hcom_review.sh --target-repo PATH --role ROLE --thread THREAD [options]

Delegates to PATH/scripts/hcom_review.sh. If --target-repo is omitted, the
packaged development-team repository itself is treated as the target.
EOF
      exit 0
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

exec "$TARGET_REPO/scripts/hcom_review.sh" "${ARGS[@]}"
