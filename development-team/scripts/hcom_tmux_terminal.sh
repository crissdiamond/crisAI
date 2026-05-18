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

configure_session() {
  tmux set-option -t "$SESSION" status on >/dev/null
  tmux set-option -t "$SESSION" status-position bottom >/dev/null
  tmux set-option -t "$SESSION" status-style "bg=#111827,fg=#d1d5db" >/dev/null
  tmux set-option -t "$SESSION" prefix 'C-\' >/dev/null
  tmux set-option -t "$SESSION" prefix2 C-b >/dev/null
  tmux set-option -t "$SESSION" status-left-length 32 >/dev/null
  tmux set-option -t "$SESSION" status-left " crisAI hcom " >/dev/null
  tmux set-option -t "$SESSION" status-right " Ctrl-\\ 0-6 switch | Ctrl-\\ w list | Ctrl-\\ d detach " >/dev/null
  tmux set-option -t "$SESSION" window-status-separator " " >/dev/null
  tmux set-option -t "$SESSION" window-status-format "#{?#{m:*claude*,#{window_name}},#[fg=#c084fc],#{?#{m:*codex*,#{window_name}},#[fg=#38bdf8],#[fg=#86efac]}} #I:#W " >/dev/null
  tmux set-option -t "$SESSION" window-status-current-format "#{?#{m:*claude*,#{window_name}},#[bg=#581c87 fg=#f5d0fe bold],#{?#{m:*codex*,#{window_name}},#[bg=#164e63 fg=#cffafe bold],#[bg=#14532d fg=#dcfce7 bold]}} #I:#W " >/dev/null
  tmux set-option -t "$SESSION" message-style "bg=#1f2937,fg=#f9fafb" >/dev/null
}

if tmux has-session -t "$SESSION" 2>/dev/null; then
  PANE_ID="$(tmux new-window -d -P -F '#{pane_id}' -t "$SESSION:" -n "$WINDOW_NAME" "$COMMAND")"
else
  PANE_ID="$(tmux new-session -d -P -F '#{pane_id}' -s "$SESSION" -n "$WINDOW_NAME" "$COMMAND")"
fi

configure_session

case "$ROLE_LABEL" in
  *claude)
    tmux select-pane -t "$PANE_ID" -P "bg=#140d1f,fg=#f3e8ff" >/dev/null 2>&1 || true
    ;;
  *codex | orchestrator)
    tmux select-pane -t "$PANE_ID" -P "bg=#07131f,fg=#e0f2fe" >/dev/null 2>&1 || true
    ;;
esac
