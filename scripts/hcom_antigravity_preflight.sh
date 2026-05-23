#!/usr/bin/env bash
# Validate that Antigravity can be used as an hcom review provider.
set -euo pipefail

DRY_RUN=0
TOKEN_PATH="${HCOM_TEAM_ANTIGRAVITY_TOKEN_PATH:-$HOME/.gemini/antigravity-cli/antigravity-oauth-token}"
MODEL="${HCOM_TEAM_REVIEW_MODEL:-${HCOM_TEAM_ANTIGRAVITY_MODEL:-}}"
PERSISTED_MODEL="${HCOM_TEAM_ANTIGRAVITY_MODEL:-Claude Sonnet 4.6}"
MODEL_PROBE_TIMEOUT="${HCOM_TEAM_ANTIGRAVITY_MODEL_PROBE_TIMEOUT:-60s}"

usage() {
  cat <<'EOF'
Usage: scripts/hcom_antigravity_preflight.sh [--dry-run]

Checks the local Antigravity setup required by hcom review launchers.
The OAuth token content is never printed.

Environment:
  HCOM_TEAM_ANTIGRAVITY_TOKEN_PATH  Reusable Antigravity OAuth token path.
  HCOM_TEAM_REVIEW_MODEL            Explicit model passed to `hcom agy --model`.
  HCOM_TEAM_ANTIGRAVITY_MODEL       Backward-compatible persisted agy model
                                    fragment used when HCOM_TEAM_REVIEW_MODEL
                                    is not set. Default: Claude Sonnet 4.6
  HCOM_TEAM_ANTIGRAVITY_MODEL_PROBE_TIMEOUT
                                    Timeout for the model verification probe.
                                    Default: 60s
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

if ! hcom agy --help >/dev/null 2>&1; then
  echo "Antigravity review requires an hcom build with native 'agy' launch support." >&2
  exit 1
fi

if [[ -n "$MODEL" ]] && ! hcom agy --help 2>/dev/null | grep -q -- "--model"; then
  echo "Antigravity review model selection requires hcom agy --model support." >&2
  exit 1
fi

normalize_model_text() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/ /g; s/[[:space:]]+/ /g; s/^ //; s/ $//'
}

verify_active_model() {
  local response normalized_response normalized_model
  response="$(
    timeout "$MODEL_PROBE_TIMEOUT" \
      agy --print-timeout "$MODEL_PROBE_TIMEOUT" \
        --print "Reply with only the human-readable name of the active model you are currently running." \
      2>&1
  )" || {
    cat >&2 <<EOF
Could not verify the active Antigravity model.

agy output:
$response

Run \`agy\` manually, use \`/model\` to select the required persisted model, then retry.
EOF
    exit 2
  }

  normalized_response="$(normalize_model_text "$response")"
  normalized_model="$(normalize_model_text "$PERSISTED_MODEL")"

  if [[ "$normalized_response" != *"$normalized_model"* ]]; then
    cat >&2 <<EOF
Antigravity is authenticated, but the active persisted agy model is not the
required model.

Required model fragment: $PERSISTED_MODEL
Probe response: $response

Run \`agy\`, enter \`/model\`, select the required model, confirm it is shown in
the Antigravity footer, then retry. When HCOM_TEAM_REVIEW_MODEL is set, crisAI
passes the model to \`hcom agy --model\` instead of relying on persisted
selection.
EOF
    exit 2
  fi
}

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

  if [[ -z "$MODEL" ]]; then
    verify_active_model
  fi
fi

if [[ -n "$MODEL" ]]; then
  echo "Antigravity preflight ok: reusable OAuth token present; hcom agy --model is available for '$MODEL'."
else
  echo "Antigravity preflight ok: reusable OAuth token present; active agy model matches '$PERSISTED_MODEL'."
fi
