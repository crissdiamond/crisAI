#!/usr/bin/env bash
# Open an hcom-generated launch script in a named tmux window.
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: hcom_tmux_terminal.sh SESSION ROLE_LABEL SCRIPT" >&2
  exit 2
fi

SESSION="$1"
ROLE_LABEL="$2"
LAUNCH_SCRIPT="$3"

if ! command -v tmux >/dev/null 2>&1; then
  echo "Missing required command: tmux" >&2
  exit 1
fi

if [[ ! -f "$LAUNCH_SCRIPT" ]]; then
  echo "Missing hcom launch script: $LAUNCH_SCRIPT" >&2
  exit 1
fi

HCOM_NAME="$(sed -n "s/.*HCOM_NAME=\([^;]*\);.*/\1/p" "$LAUNCH_SCRIPT" | head -n 1 | tr -d "'\"")"
if [[ -z "$HCOM_NAME" ]]; then
  HCOM_NAME="starting"
fi

WINDOW_NAME="${ROLE_LABEL}(${HCOM_NAME})"
SCRIPT_ARG="$(printf '%q' "$LAUNCH_SCRIPT")"
COMMAND="exec bash $SCRIPT_ARG"

if tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-window -d -P -F '#{pane_id}' -t "$SESSION:" -n "$WINDOW_NAME" "$COMMAND"
else
  tmux new-session -d -P -F '#{pane_id}' -s "$SESSION" -n "$WINDOW_NAME" "$COMMAND"
fi
