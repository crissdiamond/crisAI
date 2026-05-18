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
WINDOW_STATUS_FORMAT='#{?#{==:#{window_index},0},#[fg=#581c87],#{?#{==:#{window_index},2},#[fg=#374151],#{?#{==:#{window_index},4},#[fg=#374151],#{?#{==:#{window_index},6},#[fg=#374151],#[fg=#0369a1]}}}} #I:#W #[default]'
WINDOW_STATUS_CURRENT_FORMAT='#{?#{==:#{window_index},0},#[fg=#581c87]#[bold],#{?#{==:#{window_index},2},#[fg=#374151]#[bold],#{?#{==:#{window_index},4},#[fg=#374151]#[bold],#{?#{==:#{window_index},6},#[fg=#374151]#[bold],#[fg=#0369a1]#[bold]}}}} #I:#W #[default]'
STATUS_AGENTS_FORMAT='#[bg=#f3f4f6,fg=#111827] #[bold]crisAI hcom#[default] #{W:#{E:window-status-format} ,#{E:window-status-current-format} }'
STATUS_HELP_FORMAT='#[bg=#e5e7eb,fg=#374151] Ctrl-\\ 0-6 switch | Ctrl-\\ w list | Ctrl-\\ d detach | ./start hcom-attach #[default]'

configure_session() {
  tmux set-option -t "$SESSION" status 2 >/dev/null
  tmux set-option -t "$SESSION" status-position bottom >/dev/null
  tmux set-option -t "$SESSION" status-style "bg=#f3f4f6,fg=#111827" >/dev/null
  tmux set-option -t "$SESSION" prefix 'C-\' >/dev/null
  tmux set-option -t "$SESSION" prefix2 C-b >/dev/null
  tmux set-option -t "$SESSION" status-left-length 32 >/dev/null
  tmux set-option -t "$SESSION" status-left "" >/dev/null
  tmux set-option -t "$SESSION" status-right "" >/dev/null
  tmux set-option -t "$SESSION" status-format[0] "$STATUS_AGENTS_FORMAT" >/dev/null
  tmux set-option -t "$SESSION" status-format[1] "$STATUS_HELP_FORMAT" >/dev/null
  tmux set-option -t "$SESSION" window-status-separator " " >/dev/null
  tmux set-option -t "$SESSION" message-style "bg=#1f2937,fg=#f9fafb" >/dev/null
  tmux set-option -t "$SESSION" pane-border-status off >/dev/null
  tmux set-option -t "$SESSION" pane-border-style "fg=#374151" >/dev/null
  tmux set-option -t "$SESSION" pane-active-border-style "fg=#6b7280" >/dev/null
}

configure_window_status() {
  local target="$1"
  tmux set-window-option -t "$target" window-status-format "$WINDOW_STATUS_FORMAT" >/dev/null
  tmux set-window-option -t "$target" window-status-current-format "$WINDOW_STATUS_CURRENT_FORMAT" >/dev/null
}

if tmux has-session -t "$SESSION" 2>/dev/null; then
  PANE_ID="$(tmux new-window -d -P -F '#{pane_id}' -t "$SESSION:" -n "$WINDOW_NAME" "exec $COMMAND")"
else
  PANE_ID="$(tmux new-session -d -P -F '#{pane_id}' -s "$SESSION" -n "$WINDOW_NAME" "exec $COMMAND")"
fi

configure_session
configure_window_status "$PANE_ID"

case "$ROLE_LABEL" in
  *claude)
    tmux select-pane -t "$PANE_ID" -P "bg=#140d1f,fg=#f3e8ff" >/dev/null 2>&1 || true
    ;;
  *codex | orchestrator)
    tmux select-pane -t "$PANE_ID" -P "bg=#07131f,fg=#e0f2fe" >/dev/null 2>&1 || true
    ;;
esac

printf '%s\n' "$PANE_ID"
