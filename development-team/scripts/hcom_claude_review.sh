#!/usr/bin/env bash
# Launch an on-demand Claude reviewer for a target crisAI hcom task.
set -euo pipefail

TEAM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_REPO="$TEAM_DIR"
ROLE=""
THREAD=""
LEASE_MINUTES=""
TASK=""
DRY_RUN=0
VISIBILITY="${HCOM_TEAM_CLAUDE_VISIBILITY:-headless}"
MAX_LEASE_MINUTES="${HCOM_TEAM_CLAUDE_MAX_LEASE_MINUTES:-180}"
AUTO_APPROVE_TOOLS="${HCOM_TEAM_TOOL_AUTO_APPROVE:-1}"
TEAM_HINTS="${HCOM_TEAM_HINTS:-When you receive a direct hcom request from the orchestrator or your paired agent, treat it as an actionable assignment and proceed without asking the terminal user to confirm. Do not leave suggested follow-up commands or draft prompts in the input bar. Do not monitor or ask status questions about unrelated agents. Only query another agent when that is directly required by your assigned task; otherwise report your own waiting state via hcom and return to listening.}"
CLAUDE_IDLE_PROMPT_POLICY="${HCOM_TEAM_CLAUDE_IDLE_PROMPT_POLICY:-When you finish onboarding or a task, do not draft idle prompts such as 'wait for assignment', 'check pending assignments', or 'check messages from another agent'. Do not ask the terminal user what to do next. Report readiness or waiting state via hcom when useful, then stop with an empty input bar.}"
MEMORY_WRITE_POLICY="${HCOM_TEAM_MEMORY_WRITE_POLICY:-Use Claude memory as durable task context when available. Memory may be read-only in worker sessions; if a memory write is denied, do not block or ask the terminal user. Include the intended memory summary in your hcom handoff or final report and continue.}"

usage() {
  cat <<'EOF'
Usage: scripts/hcom_claude_review.sh --target-repo PATH --role ROLE --thread THREAD [options]

Launch an ephemeral Claude reviewer for a target repository. The orchestrator
owns the lifecycle and should close the reviewer when no longer useful.

Required:
  --role runtime_claude|gem_claude|web_claude
  --thread NAME

Options:
  --target-repo PATH      Target crisAI repository. Defaults to this repo.
  --task TEXT             Review assignment. If omitted, stdin is used.
  --lease-minutes N       Stale-session safety cap. Defaults to max cap.
  --visibility MODE       headless or tmux. Defaults to HCOM_TEAM_CLAUDE_VISIBILITY.
  --dry-run               Print the launch command without running it.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-repo)
      TARGET_REPO="$(cd "$2" && pwd)"
      shift 2
      ;;
    --role)
      ROLE="$2"
      shift 2
      ;;
    --thread)
      THREAD="$2"
      shift 2
      ;;
    --task)
      TASK="$2"
      shift 2
      ;;
    --lease-minutes)
      LEASE_MINUTES="$2"
      shift 2
      ;;
    --visibility)
      VISIBILITY="$2"
      shift 2
      ;;
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

export HCOM_DIR="${HCOM_DIR:-$TARGET_REPO/.hcom}"
STATE_DIR="${HCOM_DEVELOPMENT_DIR:-$TARGET_REPO/.hcom-development}"
LEASES="${HCOM_CLAUDE_REVIEW_LEASES:-$STATE_DIR/claude_review_leases.local.yaml}"
TEAM_TMUX_SESSION="${HCOM_TEAM_TMUX_SESSION:-crisai-hcom}"

case "$ROLE" in
  runtime_claude)
    AREA="runtime"; TAG="crisai-runtime-review"; ROLE_FILE="reference/development/roles/runtime_claude.md"; LABEL="run_claude" ;;
  gem_claude)
    AREA="gem"; TAG="crisai-gem-review"; ROLE_FILE="reference/development/roles/gem_claude.md"; LABEL="gem_claude" ;;
  web_claude)
    AREA="web"; TAG="crisai-web-review"; ROLE_FILE="reference/development/roles/web_claude.md"; LABEL="web_claude" ;;
  "")
    usage >&2; exit 2 ;;
  *)
    echo "Unsupported Claude review role: $ROLE" >&2; exit 2 ;;
esac

if [[ -z "$THREAD" ]]; then
  usage >&2
  exit 2
fi
if [[ "$VISIBILITY" != "headless" && "$VISIBILITY" != "tmux" ]]; then
  echo "Visibility must be 'headless' or 'tmux'." >&2
  exit 2
fi
if [[ -z "$TASK" && ! -t 0 ]]; then
  TASK="$(cat)"
fi
if [[ -z "$TASK" ]]; then
  echo "Missing review task. Pass --task or pipe task text on stdin." >&2
  exit 2
fi
LEASE_MINUTES="${LEASE_MINUTES:-$MAX_LEASE_MINUTES}"
if ! [[ "$LEASE_MINUTES" =~ ^[0-9]+$ ]] || [[ "$LEASE_MINUTES" -lt 1 ]]; then
  echo "--lease-minutes must be a positive integer." >&2
  exit 2
fi
if ! [[ "$MAX_LEASE_MINUTES" =~ ^[0-9]+$ ]] || [[ "$MAX_LEASE_MINUTES" -lt 1 ]]; then
  echo "HCOM_TEAM_CLAUDE_MAX_LEASE_MINUTES must be a positive integer." >&2
  exit 2
fi
if [[ "$LEASE_MINUTES" -gt "$MAX_LEASE_MINUTES" ]]; then
  echo "--lease-minutes cannot exceed HCOM_TEAM_CLAUDE_MAX_LEASE_MINUTES ($MAX_LEASE_MINUTES)." >&2
  exit 2
fi
if ! command -v hcom >/dev/null 2>&1; then
  echo "Missing required command: hcom" >&2
  exit 1
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "Missing required command: claude" >&2
  exit 1
fi

role_prompt() {
  cat "$TEAM_DIR/$ROLE_FILE"
  printf '\n\n'
  cat <<EOF
This is an ephemeral Claude review session launched by the orchestrator.
Target repository: $TARGET_REPO
Team repository: $TEAM_DIR
Area: $AREA
Thread: $THREAD
Lease minutes: $LEASE_MINUTES

The orchestrator owns your lifecycle. Work only on the assigned review or small
patch. When done, send the handoff through hcom and wait for the orchestrator to
close or renew the review session. Do not draft idle prompts in the input bar.

Review assignment:
$TASK
EOF
  printf '\nIf you are a Claude review agent, follow this idle prompt policy:\n%s\n' "$CLAUDE_IDLE_PROMPT_POLICY"
  printf '\nFollow this memory policy:\n%s\n' "$MEMORY_WRITE_POLICY"
}

extract_names() {
  sed -n 's/^Names: //p' | tr ' ' '\n' | sed '/^$/d'
}

record_lease() {
  local name="$1"
  local started_at expires_at expires_epoch
  started_at="$(date -Is)"
  expires_epoch="$(( $(date +%s) + (LEASE_MINUTES * 60) ))"
  expires_at="$(date -Is -d "@$expires_epoch")"
  mkdir -p "$(dirname "$LEASES")"
  if [[ ! -f "$LEASES" ]]; then
    {
      echo "# Local ephemeral Claude review leases. Ignored by git."
      echo "reviews:"
    } >"$LEASES"
  fi
  cat >>"$LEASES" <<EOF
  $name:
    role: $ROLE
    area: $AREA
    thread: $THREAD
    tag: $TAG
    visibility: $VISIBILITY
    started_at: "$started_at"
    lease_minutes: $LEASE_MINUTES
    expires_at: "$expires_at"
    expires_at_epoch: $expires_epoch
    status: active
EOF
}

set_lease_status() {
  local name="$1"
  local status="$2"
  [[ -f "$LEASES" ]] || return 0
  python - "$LEASES" "$name" "$status" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
name = sys.argv[2]
status = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
current = ""
updated = False
for index, line in enumerate(lines):
    if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
        current = line.strip()[:-1]
    elif current == name and line.startswith("    status:"):
        lines[index] = f"    status: {status}"
        updated = True
        break
if updated:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

reviewer_transcript_path() {
  local name="$1"
  hcom list --stopped "$name" -v 2>/dev/null | sed -n 's/^  Transcript: //p' | head -n 1
}

reviewer_failure_summary() {
  local name="$1"
  local transcript
  transcript="$(reviewer_transcript_path "$name")"
  if [[ -n "$transcript" && -f "$transcript" ]]; then
    python - "$transcript" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
for raw in path.read_text(encoding="utf-8").splitlines():
    try:
        entry = json.loads(raw)
    except json.JSONDecodeError:
        continue
    message = entry.get("message")
    if not isinstance(message, dict):
        continue
    if entry.get("isApiErrorMessage") or message.get("type") == "message":
        error = entry.get("error")
        status = entry.get("apiErrorStatus")
        texts = []
        for item in message.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(str(item.get("text") or ""))
        if error or status or texts:
            detail = " ".join(texts).strip()
            pieces = []
            if status:
                pieces.append(f"status={status}")
            if error:
                pieces.append(f"error={error}")
            if detail:
                pieces.append(detail)
            print("; ".join(pieces))
PY
  fi
}

export HCOM_HINTS="$TEAM_HINTS $MEMORY_WRITE_POLICY"
mkdir -p "$HCOM_DIR"
PROMPT="$(role_prompt)"
CMD=(hcom claude --tag "$TAG" --dir "$TARGET_REPO" --hcom-prompt "$PROMPT" --hcom-system-prompt "$CLAUDE_IDLE_PROMPT_POLICY $MEMORY_WRITE_POLICY" --go)
if [[ "$VISIBILITY" == "headless" ]]; then
  CMD+=(--headless)
else
  CMD+=(--run-here)
fi
if [[ "$AUTO_APPROVE_TOOLS" == "1" ]]; then
  CMD+=(--permission-mode auto)
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'DRY RUN:' >&2
  printf ' %q' "${CMD[@]}" >&2
  printf '\n' >&2
  echo "dry-run-$ROLE"
  exit 0
fi

if [[ "$VISIBILITY" == "tmux" ]]; then
  pane_id="$("$TEAM_DIR/scripts/hcom_tmux_command.sh" "$TEAM_TMUX_SESSION" "$LABEL" "${CMD[@]}")"
  sleep 1
  name="$(hcom list --json | TAG="$TAG" python -c 'import json, os, sys; agents=json.load(sys.stdin); matches=[a for a in agents if a.get("tag")==os.environ["TAG"] and str(a.get("tool","")).lower()=="claude"]; matches.sort(key=lambda a: a.get("created_at") or ""); print(matches[-1].get("name","") if matches else "")')"
  [[ -z "$pane_id" || -z "$name" ]] || tmux rename-window -t "$pane_id" "$LABEL(${name##*-})" >/dev/null 2>&1 || true
else
  output="$("${CMD[@]}" 2>&1)"
  printf '%s\n' "$output" >&2
  name="$(printf '%s\n' "$output" | extract_names | head -n 1)"
fi
if [[ -z "${name:-}" ]]; then
  echo "Could not parse launched Claude reviewer name." >&2
  exit 1
fi
record_lease "$name"
stopped_event="$(hcom events --agent "$name" --action stopped --wait 3 2>/dev/null || true)"
if [[ -n "$stopped_event" ]]; then
  set_lease_status "$name" inactive
  summary="$(reviewer_failure_summary "$name" || true)"
  if [[ -n "$summary" ]]; then
    echo "Reviewer $name exited during startup: $summary" >&2
  else
    echo "Reviewer $name exited during startup. Inspect with: hcom list --stopped $name -v" >&2
  fi
  exit 1
fi
echo "Started $ROLE reviewer as $name on thread '$THREAD' with a $LEASE_MINUTES minute lease."
