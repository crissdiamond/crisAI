#!/usr/bin/env bash
# Manage the persisted Antigravity CLI model used by hcom reviewers.
set -euo pipefail

SETTINGS_PATH="${HCOM_TEAM_ANTIGRAVITY_SETTINGS_PATH:-$HOME/.gemini/antigravity-cli/settings.json}"

usage() {
  cat <<'EOF'
Usage: scripts/hcom_antigravity_model.sh set MODEL

Updates the Antigravity CLI settings file so future `agy` sessions start with
the requested model. The update is atomic and preserves all other settings.

Environment:
  HCOM_TEAM_ANTIGRAVITY_SETTINGS_PATH  Antigravity settings JSON path.
                                      Default: ~/.gemini/antigravity-cli/settings.json
EOF
}

if [[ "${1:-}" != "set" || -z "${2:-}" || $# -ne 2 ]]; then
  usage >&2
  exit 2
fi

MODEL="$2"
SETTINGS_DIR="$(dirname "$SETTINGS_PATH")"
mkdir -p "$SETTINGS_DIR"

tmp="$(mktemp "$SETTINGS_DIR/settings.json.tmp.XXXXXX")"
cleanup() {
  rm -f "$tmp"
}
trap cleanup EXIT

python3 - "$SETTINGS_PATH" "$tmp" "$MODEL" <<'PY'
import json
import os
import sys

settings_path, tmp_path, model = sys.argv[1:4]

data = {}
if os.path.exists(settings_path) and os.path.getsize(settings_path) > 0:
    with open(settings_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

if not isinstance(data, dict):
    raise SystemExit(f"Antigravity settings must be a JSON object: {settings_path}")

data["model"] = model

with open(tmp_path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

chmod 600 "$tmp"
mv "$tmp" "$SETTINGS_PATH"
trap - EXIT

echo "Antigravity model set to: $MODEL"
