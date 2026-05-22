#!/usr/bin/env bash
# Validate that Antigravity can be used as an hcom review provider.
set -euo pipefail

DRY_RUN=0
MODEL="${HCOM_TEAM_ANTIGRAVITY_MODEL:-claude-sonnet-4.6}"
TOKEN_PATH="${HCOM_TEAM_ANTIGRAVITY_TOKEN_PATH:-$HOME/.gemini/antigravity-cli/antigravity-oauth-token}"

usage() {
  cat <<'EOF'
Usage: scripts/hcom_antigravity_preflight.sh [--dry-run]

Checks the local Antigravity setup required by hcom review launchers.
The OAuth token content is never printed.

Environment:
  HCOM_TEAM_ANTIGRAVITY_MODEL       Claude model to request through hcom agy.
                                   Default: claude-sonnet-4.6
  HCOM_TEAM_ANTIGRAVITY_TOKEN_PATH  Reusable Antigravity OAuth token path.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_bin() {
  local bin="$1"
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Missing required command: $bin" >&2
    exit 1
  fi
}

require_bin hcom
require_bin agy

shopt -s nocasematch
if [[ "$MODEL" != *claude* ]]; then
  echo "HCOM_TEAM_ANTIGRAVITY_MODEL must select a Claude model, got: $MODEL" >&2
  exit 2
fi
shopt -u nocasematch

if ! hcom agy --help >/dev/null 2>&1; then
  echo "Antigravity review requires an hcom build with native 'agy' launch support." >&2
  exit 1
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  if [[ ! -s "$TOKEN_PATH" ]]; then
    cat >&2 <<EOF
Antigravity is not authenticated for reusable hcom launch.

Run \`agy\` once manually, complete OAuth, confirm it reopens without asking
for authentication, then retry. Expected token path:
$TOKEN_PATH
EOF
    exit 2
  fi

  if [[ "$(uname -s)" != MINGW* && "$(uname -s)" != CYGWIN* ]]; then
    mode="$(stat -c '%a' "$TOKEN_PATH" 2>/dev/null || true)"
    if [[ -n "$mode" ]]; then
      perms=$((8#$mode))
      if (( perms & 077 )); then
        echo "Antigravity OAuth token must be private: chmod 600 $TOKEN_PATH" >&2
        exit 2
      fi
    fi
  fi
fi

echo "Antigravity preflight ok: model=$MODEL"
