#!/usr/bin/env bash
# Attach to the crisAI hcom tmux team session.
set -euo pipefail

SESSION="${HCOM_TEAM_TMUX_SESSION:-crisai-hcom}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "Missing required command: tmux" >&2
  exit 1
fi

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "No tmux session named '$SESSION' is running."
  echo "Start the team with: scripts/hcom_start.sh"
  exit 1
fi

cat <<EOF
Attaching to $SESSION

Keys:
  Ctrl-\ 0..6  switch directly to an agent
  Ctrl-\ w     show the window list
  Ctrl-\ n/p   next/previous agent
  Ctrl-\ d     detach without stopping agents

Fallback:
  Ctrl-b also works as a secondary tmux prefix.

Window colours:
  cyan    Codex
  purple  Claude
  green   orchestrator/other
EOF

exec tmux attach -t "$SESSION"
