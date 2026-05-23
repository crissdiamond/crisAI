#!/usr/bin/env bash
# Launch the crisAI hcom development team.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HCOM_DIR="${HCOM_DIR:-$ROOT_DIR/.hcom}"
ASSIGNMENTS="$ROOT_DIR/reference/development/session_assignments.local.yaml"
TEAM_NAMES_REGISTRY="${HCOM_TEAM_NAMES_REGISTRY:-$ROOT_DIR/reference/development/team_names.yaml}"
DRY_RUN=0
HEADLESS=0
RESUME=0
AUTO_APPROVE_TOOLS="${HCOM_TEAM_TOOL_AUTO_APPROVE:-1}"
ORCHESTRATOR_CODEX_SANDBOX="${HCOM_TEAM_ORCHESTRATOR_CODEX_SANDBOX:-danger-full-access}"
AREA_CODEX_SANDBOX="${HCOM_TEAM_AREA_CODEX_SANDBOX:-workspace-write}"
REVIEW_LIFECYCLE="${HCOM_TEAM_REVIEW_LIFECYCLE:-${HCOM_TEAM_CLAUDE_MODE:-ephemeral}}"
REVIEW_PROVIDER_RAW="${HCOM_TEAM_REVIEW_PROVIDER:-claude-code}"
TEAM_HINTS="${HCOM_TEAM_HINTS:-Direct hcom requests are assignments; act or reply via hcom, without waiting for terminal-user input.}"
CLAUDE_PROMPT_SUGGESTIONS="${HCOM_TEAM_CLAUDE_PROMPT_SUGGESTIONS:-false}"
MEMORY_WRITE_POLICY="${HCOM_TEAM_MEMORY_WRITE_POLICY:-Use Claude memory as durable task context when available. Memory may be read-only in worker sessions; if a memory write is denied, do not block or ask the terminal user. Include the intended memory summary in your hcom handoff or final report and continue.}"
TEAM_TERMINAL="${HCOM_TEAM_TERMINAL:-}"
TEAM_TERMINAL_EXPLICIT=0
if [[ -n "$TEAM_TERMINAL" ]]; then
  TEAM_TERMINAL_EXPLICIT=1
fi
TEAM_TMUX_SESSION="${HCOM_TEAM_TMUX_SESSION:-crisai-hcom}"
EXTRA_ARGS=()
LAUNCHED_NAMES=()
EXISTING_NAMES=()
declare -A PREVIOUS_HCOM_NAMES=()
declare -A PREVIOUS_PROVIDER_SESSION_IDS=()

usage() {
  cat <<'EOF'
Usage: scripts/hcom_start.sh [--dry-run] [--headless] [--resume] [--tool-auto-approve|--no-tool-auto-approve] [--terminal PRESET_OR_COMMAND] [-- extra hcom args]

Launches:
  - one Codex orchestrator from repo root
  - runtime Codex, Gem Codex, and web Codex from repo root
  - reviewer agents only when HCOM_TEAM_REVIEW_LIFECYCLE=persistent

State:
  HCOM_DIR defaults to ./.hcom and is ignored by git.
  HCOM_TEAM_NAMES_REGISTRY defaults to reference/development/team_names.yaml
  and controls preferred static hcom base names for each stable role.
  Generated session assignments are written to
  reference/development/session_assignments.local.yaml.
  Use --resume to resume previous hcom/provider sessions from that assignment
  file when available.

Terminal:
  HCOM_TEAM_TERMINAL or --terminal controls where hcom opens shells.
  The default is a dedicated tmux session named crisai-hcom when available.
  Override the tmux session name with HCOM_TEAM_TMUX_SESSION.
  Windows Terminal can be requested explicitly with a wt.exe terminal command.

Approvals:
  Tool auto-approval is enabled by default. Set HCOM_TEAM_TOOL_AUTO_APPROVE=0
  or pass --no-tool-auto-approve to keep Codex/Claude permission prompts.
  The orchestrator Codex uses HCOM_TEAM_ORCHESTRATOR_CODEX_SANDBOX, defaulting
  to danger-full-access so it can write .git metadata. Area Codex agents use
  HCOM_TEAM_AREA_CODEX_SANDBOX, defaulting to workspace-write.

Message handling:
  HCOM_TEAM_HINTS is appended to every received hcom message. Keep it short:
  the default only reminds agents that direct hcom requests are assignments.
  HCOM_TEAM_CLAUDE_PROMPT_SUGGESTIONS controls Claude Code prompt suggestions
  for reviewer sessions. It defaults to false so idle reviewer panes do not
  fill their input bar with suggested follow-up prompts.
  HCOM_TEAM_MEMORY_WRITE_POLICY is included in bootstrap instructions so agents
  degrade gracefully when Claude memory is read-only.

Reviewers:
  HCOM_TEAM_REVIEW_LIFECYCLE defaults to ephemeral. In ephemeral mode only Codex
  agents are permanent, and reviewers are launched on demand by the
  orchestrator. Set it to persistent to launch reviewer agents with the standing
  team. HCOM_TEAM_CLAUDE_MODE remains as a deprecated compatibility alias.

  HCOM_TEAM_REVIEW_PROVIDER defaults to claude-code. Supported values are
  claude-code and antigravity. Antigravity reviewers require reusable local auth
  and a persisted Claude model selection in agy. Use `agy`, enter `/model`,
  select the required Claude model, then rerun the launcher. The preflight
  verifies the active agy model before any reviewer is launched.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --headless)
      HEADLESS=1
      shift
      ;;
    --resume)
      RESUME=1
      shift
      ;;
    --tool-auto-approve)
      AUTO_APPROVE_TOOLS=1
      shift
      ;;
    --no-tool-auto-approve)
      AUTO_APPROVE_TOOLS=0
      shift
      ;;
    --terminal)
      TEAM_TERMINAL="$2"
      TEAM_TERMINAL_EXPLICIT=1
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
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

role_prompt() {
  local role_file="$1"
  local role="${2:-}"
  cat "$ROOT_DIR/$role_file"
  printf '\n\n'
  cat <<'EOF'
Start by identifying your hcom session name, stable role, area, and peer from
reference/development/session_assignments.local.yaml when it exists. Use hcom
for concise coordination and the Claude memory MCP server for durable task
context. Do not store secrets in memory.
EOF
  printf '\nFollow this memory policy:\n%s\n' "$MEMORY_WRITE_POLICY"
}

extract_names() {
  sed -n 's/^Names: //p' | tr ' ' '\n' | sed '/^$/d'
}

load_previous_assignments() {
  [[ -f "$ASSIGNMENTS" ]] || return 0
  while IFS='|' read -r role hcom_name provider_session_id; do
    [[ -n "$role" && -n "$hcom_name" ]] || continue
    PREVIOUS_HCOM_NAMES["$role"]="$hcom_name"
    if [[ -n "$provider_session_id" ]]; then
      PREVIOUS_PROVIDER_SESSION_IDS["$role"]="$provider_session_id"
    fi
  done < <(awk '
function flush() {
  if (role != "" && name != "") {
    print role "|" name "|" provider_session_id
  }
}
/^  [^[:space:]][^:]*:$/ {
  flush()
  name=$1
  sub(":$", "", name)
  role=""
  provider_session_id=""
}
/^[[:space:]]+role:/ { role=$2 }
/^[[:space:]]+provider_session_id:/ { provider_session_id=$2 }
END { flush() }
' "$ASSIGNMENTS")
}

preferred_hcom_name() {
  local role="$1"
  [[ -f "$TEAM_NAMES_REGISTRY" ]] || return 0
  awk -v role="$role" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*names:[[:space:]]*$/ { in_names = 1; next }
    in_names && /^[^[:space:]]/ { in_names = 0 }
    in_names && $1 == role ":" {
      value = $2
      gsub(/^"/, "", value)
      gsub(/"$/, "", value)
      print value
      exit
    }
  ' "$TEAM_NAMES_REGISTRY"
}

default_team_terminal() {
  if [[ -n "$TEAM_TERMINAL" ]]; then
    printf '%s\n' "$TEAM_TERMINAL"
    return 0
  fi
  if command -v tmux >/dev/null 2>&1; then
    printf '__crisai_tmux_direct__\n'
    return 0
  fi
  if [[ -n "${WSL_DISTRO_NAME:-}" ]] && command -v wt.exe >/dev/null 2>&1; then
    printf 'wt.exe -w 0 new-tab --title hcom -- wsl.exe -d %s bash {script}\n' "$WSL_DISTRO_NAME"
  fi
}

role_terminal_label() {
  case "$1" in
    orchestrator_codex)
      printf 'orchestrator\n'
      ;;
    runtime_codex)
      printf 'run_codex\n'
      ;;
    runtime_claude)
      printf 'run_claude\n'
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

hcom_display_name() {
  local role="$1"
  local name="$2"
  local label
  label="$(role_terminal_label "$role")"

  case "$role" in
    orchestrator_codex)
      name="${name#crisai-orchestrator-}"
      ;;
    gem_codex | gem_claude)
      name="${name#crisai-gem-}"
      ;;
    web_codex | web_claude)
      name="${name#crisai-web-}"
      ;;
    runtime_codex | runtime_claude)
      name="${name#crisai-runtime-}"
      ;;
  esac

  printf '%s(%s)\n' "$label" "$name"
}

terminal_for_role() {
  local role="$1"
  local terminal="$TEAM_TERMINAL"
  terminal="${terminal//\{role_label\}/$(role_terminal_label "$role")}"
  printf '%s\n' "$terminal"
}

name_from_hcom_list() {
  local tag="$1"
  local provider="$2"
  local attempt
  local assigned_csv
  local assigned_names=("${EXISTING_NAMES[@]}" "${LAUNCHED_NAMES[@]}")
  assigned_csv="$(IFS=,; printf '%s' "${assigned_names[*]-}")"

  for attempt in {1..30}; do
    local name
    name="$(hcom list --json | ASSIGNED_NAMES="$assigned_csv" python -c '
import json
import os
import sys

tag = sys.argv[1]
provider = sys.argv[2].lower()
assigned = {name for name in os.environ.get("ASSIGNED_NAMES", "").split(",") if name}

try:
    agents = json.load(sys.stdin)
except json.JSONDecodeError:
    agents = []

matches = []
for agent in agents:
    name = agent.get("name", "")
    if name in assigned:
        continue
    if agent.get("tag") != tag:
        continue
    if str(agent.get("tool", "")).lower() != provider:
        continue
    if str(agent.get("status", "")).lower() in {"inactive", "unknown"}:
        continue
    matches.append(agent)

matches.sort(key=lambda item: str(item.get("created_at", "")))
if matches:
    print(matches[-1].get("name", ""))
' "$tag" "$provider")"
    if [[ -n "$name" ]]; then
      printf '%s\n' "$name"
      return 0
    fi
    sleep 1
  done
}

snapshot_existing_names() {
  [[ "$DRY_RUN" -eq 0 ]] || return 0
  local json
  if ! json="$(hcom list --json 2>/dev/null)"; then
    return 0
  fi
  mapfile -t EXISTING_NAMES < <(printf '%s\n' "$json" | python -c '
import json
import sys

try:
    agents = json.load(sys.stdin)
except json.JSONDecodeError:
    agents = []

for agent in agents:
    status = str(agent.get("status", "")).lower()
    name = agent.get("name", "")
    if name and status not in {"inactive", "unknown"}:
        print(name)
')
}

provider_session_id_for_name() {
  local hcom_name="$1"
  local attempt json session_id
  for attempt in {1..5}; do
    if ! json="$(hcom list --json 2>/dev/null)"; then
      sleep 1
      continue
    fi
    session_id="$(printf '%s\n' "$json" | python -c '
import json
import sys

name = sys.argv[1]
try:
    agents = json.load(sys.stdin)
except json.JSONDecodeError:
    agents = []

for agent in agents:
    if name in {agent.get("name"), agent.get("base_name")} and agent.get("session_id"):
        print(agent["session_id"])
        break
' "$hcom_name")"
    if [[ -n "$session_id" ]]; then
      printf '%s\n' "$session_id"
      return 0
    fi
    sleep 1
  done
}

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'DRY RUN:' >&2
    printf ' %q' "$@" >&2
    printf '\n' >&2
    return 0
  fi
  "$@"
}

write_tmux_launch_script() {
  local role="$1"
  shift
  local launch_dir script_path
  launch_dir="$HCOM_DIR/.tmp/team_launch"
  mkdir -p "$launch_dir"
  script_path="$launch_dir/${role}.sh"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'set -euo pipefail\n'
    printf 'cd %q\n' "$ROOT_DIR"
    printf 'export HCOM_DIR=%q\n' "$HCOM_DIR"
    printf 'export HCOM_HINTS=%q\n' "$HCOM_HINTS"
    printf 'export CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=%q\n' "$CLAUDE_PROMPT_SUGGESTIONS"
    printf 'exec'
    printf ' %q' "$@"
    printf '\n'
  } >"$script_path"
  chmod 700 "$script_path"
  printf '%s\n' "$script_path"
}

tool_auto_approval_args() {
  local role="$1"
  local provider="$2"
  [[ "$AUTO_APPROVE_TOOLS" == "1" ]] || return 0

  case "$provider" in
    codex)
      local sandbox="$AREA_CODEX_SANDBOX"
      if [[ "$role" == "orchestrator_codex" ]]; then
        sandbox="$ORCHESTRATOR_CODEX_SANDBOX"
      fi
      printf '%s\n' --ask-for-approval never --sandbox "$sandbox"
      ;;
    claude)
      printf '%s\n' --permission-mode auto
      ;;
    agy)
      printf '%s\n' --dangerously-skip-permissions
      ;;
  esac
}

tool_provider_args() {
  local provider="$1"
  case "$provider" in
    agy)
      # agy has no public --model launch flag. The selected model is persisted
      # by Antigravity and verified by scripts/hcom_antigravity_preflight.sh.
      return 0
      ;;
  esac
}

normalize_review_provider() {
  case "$REVIEW_PROVIDER_RAW" in
    claude | claude-code | claude_code)
      printf 'claude-code\n'
      ;;
    antigravity | agy)
      printf 'antigravity\n'
      ;;
    *)
      echo "HCOM_TEAM_REVIEW_PROVIDER must be 'claude-code' or 'antigravity'." >&2
      exit 1
      ;;
  esac
}

review_provider_tool() {
  case "$REVIEW_PROVIDER" in
    claude-code)
      printf 'claude\n'
      ;;
    antigravity)
      printf 'agy\n'
      ;;
  esac
}

validate_review_config() {
  if [[ "$REVIEW_LIFECYCLE" != "ephemeral" && "$REVIEW_LIFECYCLE" != "persistent" ]]; then
    echo "HCOM_TEAM_REVIEW_LIFECYCLE must be 'ephemeral' or 'persistent'." >&2
    exit 1
  fi
  if [[ "$REVIEW_PROVIDER" == "antigravity" ]]; then
    validate_antigravity_config "$DRY_RUN"
  fi
}

validate_antigravity_config() {
  local dry_run="$1"
  local args=()
  if [[ "$dry_run" -eq 1 ]]; then
    args+=(--dry-run)
  fi
  "$ROOT_DIR/scripts/hcom_antigravity_preflight.sh" "${args[@]}" >/dev/null
}

launch_agent() {
  local role="$1"
  local provider="$2"
  local tag="$3"
  local launch_dir="$4"
  local role_file="$5"
  local area="$6"

  local prompt resume_target
  prompt="$(role_prompt "$role_file" "$role")"

  if [[ "$RESUME" -eq 1 ]]; then
    if [[ "$provider" == "agy" ]]; then
      # Antigravity hcom sessions do not currently resume reliably into a
      # persistent terminal panel. Start visible reviewers fresh instead.
      resume_target=""
    else
      resume_target="${PREVIOUS_PROVIDER_SESSION_IDS[$role]:-${PREVIOUS_HCOM_NAMES[$role]:-}}"
    fi
  else
    resume_target=""
  fi

  local cmd
  if [[ -n "$resume_target" ]]; then
    cmd=(hcom r "$resume_target" --tag "$tag" --dir "$ROOT_DIR/$launch_dir" --hcom-prompt "$prompt" --go)
  else
    cmd=(hcom "$provider" --tag "$tag" --dir "$ROOT_DIR/$launch_dir" --hcom-prompt "$prompt" --go)
    local preferred_name
    preferred_name="$(preferred_hcom_name "$role")"
    if [[ -n "$preferred_name" ]]; then
      cmd+=(--hcom-name "$preferred_name")
    fi
  fi
  if [[ "$provider" == "claude" || "$provider" == "agy" ]]; then
    cmd+=(--hcom-system-prompt "$MEMORY_WRITE_POLICY")
  fi
  if [[ "$HEADLESS" -eq 1 ]]; then
    cmd+=(--headless)
  elif [[ -n "$TEAM_TERMINAL" && "$TEAM_TERMINAL" != "__crisai_tmux_direct__" ]]; then
    cmd+=(--terminal "$(terminal_for_role "$role")")
  fi
  local tool_arg
  while IFS= read -r tool_arg; do
    cmd+=("$tool_arg")
  done < <(tool_provider_args "$provider")
  while IFS= read -r tool_arg; do
    cmd+=("$tool_arg")
  done < <(tool_auto_approval_args "$role" "$provider")
  if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then
    cmd+=("${EXTRA_ARGS[@]}")
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    run_cmd "${cmd[@]}"
    if [[ -n "$resume_target" ]]; then
      echo "${PREVIOUS_HCOM_NAMES[$role]:-dry-run-$role}"
    else
      echo "dry-run-$role"
    fi
    return 0
  fi

  local name output pane_id
  printf 'Starting %s (%s)...\n' "$role" "$provider" >&2
  if [[ "$TEAM_TERMINAL" == "__crisai_tmux_direct__" && "$HEADLESS" -eq 0 ]]; then
    cmd+=(--run-here)
    local launch_script
    launch_script="$(write_tmux_launch_script "$role" "${cmd[@]}")"
    pane_id="$("$ROOT_DIR/scripts/hcom_tmux_command.sh" "$TEAM_TMUX_SESSION" "$(role_terminal_label "$role")" bash "$launch_script")"
    name="$(name_from_hcom_list "$tag" "$provider" | head -n 1)"
  else
    output="$("${cmd[@]}" 2>&1)"
    printf '%s\n' "$output" >&2
    name="$(printf '%s\n' "$output" | extract_names | head -n 1)"
  fi
  if [[ -z "$name" && -n "$resume_target" && "$resume_target" == "${PREVIOUS_HCOM_NAMES[$role]:-}" ]]; then
    name="$resume_target"
  fi
  if [[ -z "$name" ]]; then
    name="$(name_from_hcom_list "$tag" "$provider" | head -n 1)"
  fi
  if [[ -z "$name" ]]; then
    echo "Could not parse hcom launched name for role $role." >&2
    exit 1
  fi
  if [[ -n "${pane_id:-}" ]]; then
    tmux rename-window -t "$pane_id" "$(hcom_display_name "$role" "$name")" >/dev/null 2>&1 || true
  fi
  printf 'Started %s as %s.\n' "$role" "$name" >&2
  printf '%s\n' "$name"
}

write_assignment() {
  local name="$1"
  local role="$2"
  local area="$3"
  local provider="$4"
  local tag="$5"
  local provider_session_id
  if [[ "$RESUME" -eq 1 ]]; then
    provider_session_id="${PREVIOUS_PROVIDER_SESSION_IDS[$role]:-}"
  else
    provider_session_id=""
  fi
  if [[ -z "$provider_session_id" && "$provider" == "codex" && "$DRY_RUN" -eq 0 ]]; then
    provider_session_id="$(provider_session_id_for_name "$name")"
  fi

  cat >>"$ASSIGNMENTS_WRITE_PATH" <<EOF
  $name:
    role: $role
    area: $area
    provider: $provider
    tag: $tag
    hcom_session_id: $name
EOF
  if [[ -n "$provider_session_id" ]]; then
    cat >>"$ASSIGNMENTS_WRITE_PATH" <<EOF
    provider_session_id: $provider_session_id
EOF
  fi
  cat >>"$ASSIGNMENTS_WRITE_PATH" <<EOF
    status: active
EOF
}

require_bin hcom
require_bin codex
REVIEW_PROVIDER="$(normalize_review_provider)"
REVIEW_PROVIDER_TOOL="$(review_provider_tool)"
validate_review_config
if [[ "$REVIEW_LIFECYCLE" == "persistent" ]]; then
  require_bin "$REVIEW_PROVIDER_TOOL"
fi

export HCOM_DIR
export HCOM_HINTS="$TEAM_HINTS"
export CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION="$CLAUDE_PROMPT_SUGGESTIONS"
mkdir -p "$HCOM_DIR"
TEAM_TERMINAL="$(default_team_terminal)"
load_previous_assignments

if [[ "$DRY_RUN" -eq 0 ]]; then
  hcom config name_export HCOM_NAME >/dev/null
  hcom config auto_subscribe collision,created,blocked >/dev/null
  hcom config auto_approve true >/dev/null
  snapshot_existing_names
fi

ASSIGNMENTS_WRITE_PATH="$(mktemp)"
trap 'rm -f "$ASSIGNMENTS_WRITE_PATH"' EXIT

mkdir -p "$(dirname "$ASSIGNMENTS_WRITE_PATH")"
cat >"$ASSIGNMENTS_WRITE_PATH" <<EOF
# Generated by scripts/hcom_start.sh. This file is local and ignored by git.
# hcom names come from $TEAM_NAMES_REGISTRY when possible; roles are stable.
hcom_dir: $HCOM_DIR
tmux_session: $TEAM_TMUX_SESSION
generated_at: "$(date -Is)"
sessions:
EOF

name="$(launch_agent orchestrator_codex codex crisai-orchestrator . reference/development/roles/orchestrator_codex.md root)"
LAUNCHED_NAMES+=("$name")
write_assignment "$name" orchestrator_codex root codex crisai-orchestrator

name="$(launch_agent gem_codex codex crisai-gem . reference/development/roles/gem_codex.md gem)"
LAUNCHED_NAMES+=("$name")
write_assignment "$name" gem_codex gem codex crisai-gem

if [[ "$REVIEW_LIFECYCLE" == "persistent" ]]; then
  name="$(launch_agent gem_claude "$REVIEW_PROVIDER_TOOL" crisai-gem . reference/development/roles/gem_claude.md gem)"
  LAUNCHED_NAMES+=("$name")
  write_assignment "$name" gem_claude gem "$REVIEW_PROVIDER_TOOL" crisai-gem
fi

name="$(launch_agent web_codex codex crisai-web . reference/development/roles/web_codex.md web)"
LAUNCHED_NAMES+=("$name")
write_assignment "$name" web_codex web codex crisai-web

if [[ "$REVIEW_LIFECYCLE" == "persistent" ]]; then
  name="$(launch_agent web_claude "$REVIEW_PROVIDER_TOOL" crisai-web . reference/development/roles/web_claude.md web)"
  LAUNCHED_NAMES+=("$name")
  write_assignment "$name" web_claude web "$REVIEW_PROVIDER_TOOL" crisai-web
fi

name="$(launch_agent runtime_codex codex crisai-runtime . reference/development/roles/runtime_codex.md runtime)"
LAUNCHED_NAMES+=("$name")
write_assignment "$name" runtime_codex runtime codex crisai-runtime

if [[ "$REVIEW_LIFECYCLE" == "persistent" ]]; then
  name="$(launch_agent runtime_claude "$REVIEW_PROVIDER_TOOL" crisai-runtime . reference/development/roles/runtime_claude.md runtime)"
  LAUNCHED_NAMES+=("$name")
  write_assignment "$name" runtime_claude runtime "$REVIEW_PROVIDER_TOOL" crisai-runtime
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  mkdir -p "$(dirname "$ASSIGNMENTS")"
  mv "$ASSIGNMENTS_WRITE_PATH" "$ASSIGNMENTS"
  trap - EXIT
  echo "hcom team assignment written to $ASSIGNMENTS"
  hcom list
else
  echo "DRY RUN: hcom team assignment preview not written to $ASSIGNMENTS"
fi
