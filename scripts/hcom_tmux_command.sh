#!/usr/bin/env bash
# Open a command in a named crisAI hcom tmux window.
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: hcom_tmux_command.sh SESSION ROLE_LABEL COMMAND [ARG...]" >&2
  exit 2
fi

SESSION="$1"
ROLE_LABEL="$2"
shift 2

if ! command -v tmux >/dev/null 2>&1; then
  echo "Missing required command: tmux" >&2
  exit 1
fi

WINDOW_NAME="${ROLE_LABEL}(starting)"
COMMAND="$(printf '%q ' "$@")"

configure_session() {
  tmux set-option -t "$SESSION" status on >/dev/null
  tmux set-option -t "$SESSION" status-position bottom >/dev/null
  tmux set-option -t "$SESSION" status-style "bg=#f3f4f6,fg=#111827" >/dev/null
  tmux set-option -t "$SESSION" prefix 'C-\' >/dev/null
  tmux set-option -t "$SESSION" prefix2 C-b >/dev/null
  tmux set-option -t "$SESSION" status-left-length 32 >/dev/null
  tmux set-option -t "$SESSION" status-left " #[bold]crisAI hcom#[default] " >/dev/null
  tmux set-option -t "$SESSION" status-right "" >/dev/null
  tmux set-option -t "$SESSION" window-status-separator " " >/dev/null
  tmux set-option -t "$SESSION" window-status-format "#{?#{m:*claude*,#{window_name}},#[fg=#7e22ce],#{?#{m:*codex*,#{window_name}},#[fg=#0369a1],#[fg=#374151]}} #I:#W " >/dev/null
  tmux set-option -t "$SESSION" window-status-current-format "#{?#{m:*claude*,#{window_name}},#[bg=#f3e8ff fg=#7e22ce bold],#{?#{m:*codex*,#{window_name}},#[bg=#dbeafe fg=#0369a1 bold],#[bg=#e5e7eb fg=#111827 bold]}} #I:#W " >/dev/null
  tmux set-option -t "$SESSION" message-style "bg=#1f2937,fg=#f9fafb" >/dev/null
  tmux set-option -t "$SESSION" pane-border-status top >/dev/null
  tmux set-option -t "$SESSION" pane-border-style "fg=#374151" >/dev/null
  tmux set-option -t "$SESSION" pane-active-border-style "fg=#6b7280" >/dev/null
  tmux set-option -t "$SESSION" pane-border-format " Ctrl-\\ 0-6 switch | Ctrl-\\ w list | Ctrl-\\ d detach | ./start hcom-attach " >/dev/null
}

if tmux has-session -t "$SESSION" 2>/dev/null; then
  PANE_ID="$(tmux new-window -d -P -F '#{pane_id}' -t "$SESSION:" -n "$WINDOW_NAME" "exec $COMMAND")"
else
  PANE_ID="$(tmux new-session -d -P -F '#{pane_id}' -s "$SESSION" -n "$WINDOW_NAME" "exec $COMMAND")"
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

printf '%s\n' "$PANE_ID"
