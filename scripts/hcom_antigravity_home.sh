#!/usr/bin/env bash
# Prepare an isolated Antigravity HOME for an hcom reviewer role.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/hcom_antigravity_home.sh ROLE

Creates a role-scoped HOME for Antigravity reviewer sessions. The isolated home
copies only reusable auth/config files from the user's real Antigravity config
and intentionally omits conversations, brain artifacts, and implicit task state.

Environment:
  HCOM_TEAM_ANTIGRAVITY_HOME_BASE  Base directory for isolated homes.
                                   Default: .hcom/antigravity-homes
  HCOM_TEAM_ANTIGRAVITY_SETTINGS_PATH
                                   Source Antigravity settings JSON path.
  HCOM_TEAM_ANTIGRAVITY_TOKEN_PATH Source reusable OAuth token path.
EOF
}

if [[ $# -ne 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage >&2
  exit 2
fi

ROLE="$1"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_DIR="${HCOM_TEAM_ANTIGRAVITY_HOME_BASE:-$ROOT_DIR/.hcom/antigravity-homes}"
SOURCE_SETTINGS="${HCOM_TEAM_ANTIGRAVITY_SETTINGS_PATH:-$HOME/.gemini/antigravity-cli/settings.json}"
SOURCE_TOKEN="${HCOM_TEAM_ANTIGRAVITY_TOKEN_PATH:-$HOME/.gemini/antigravity-cli/antigravity-oauth-token}"
SOURCE_CONFIG_DIR="$(dirname "$SOURCE_SETTINGS")"
SOURCE_CACHE_DIR="$SOURCE_CONFIG_DIR/cache"
TARGET_HOME="$BASE_DIR/$ROLE"
TARGET_CONFIG="$TARGET_HOME/.gemini/antigravity-cli"
TARGET_CACHE_DIR="$TARGET_CONFIG/cache"

mkdir -p "$TARGET_CONFIG"
rm -rf \
  "$TARGET_CONFIG/conversations" \
  "$TARGET_CONFIG/brain" \
  "$TARGET_CONFIG/implicit" \
  "$TARGET_CACHE_DIR" \
  "$TARGET_CONFIG/history.jsonl"

if [[ ! -s "$SOURCE_TOKEN" ]]; then
  echo "Missing reusable Antigravity OAuth token: $SOURCE_TOKEN" >&2
  exit 2
fi

install -m 600 "$SOURCE_TOKEN" "$TARGET_CONFIG/antigravity-oauth-token"

if [[ -s "$SOURCE_SETTINGS" ]]; then
  install -m 600 "$SOURCE_SETTINGS" "$TARGET_CONFIG/settings.json"
else
  printf '{}\n' >"$TARGET_CONFIG/settings.json"
  chmod 600 "$TARGET_CONFIG/settings.json"
fi

for optional_file in keybindings.json installation_id; do
  if [[ -s "$SOURCE_CONFIG_DIR/$optional_file" ]]; then
    install -m 600 "$SOURCE_CONFIG_DIR/$optional_file" "$TARGET_CONFIG/$optional_file"
  fi
done

mkdir -p "$TARGET_CACHE_DIR"
if [[ -s "$SOURCE_CACHE_DIR/onboarding.json" ]]; then
  install -m 600 "$SOURCE_CACHE_DIR/onboarding.json" "$TARGET_CACHE_DIR/onboarding.json"
else
  cat >"$TARGET_CACHE_DIR/onboarding.json" <<'EOF'
{
  "consumerOnboardingComplete": true,
  "enterpriseOnboardingComplete": false,
  "onboardingComplete": true
}
EOF
  chmod 600 "$TARGET_CACHE_DIR/onboarding.json"
fi

mkdir -p "$TARGET_CONFIG/log"
chmod 700 "$TARGET_HOME" "$TARGET_HOME/.gemini" "$TARGET_CONFIG" "$TARGET_CONFIG/log" "$TARGET_CACHE_DIR"

printf '%s\n' "$TARGET_HOME"
