#!/usr/bin/env bash
# Launch a provider-backed review agent for a crisAI hcom development task.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HCOM_DIR="${HCOM_DIR:-$ROOT_DIR/.hcom}"
STATE_DIR="${HCOM_DEVELOPMENT_DIR:-$ROOT_DIR/.hcom-development}"
LEASES="${HCOM_REVIEW_LEASES:-$STATE_DIR/review_leases.local.yaml}"
PROVIDER_RAW="${HCOM_TEAM_REVIEW_PROVIDER:-claude-code}"
ROLE=""
THREAD=""
TASK=""
LEASE_MINUTES="${HCOM_TEAM_REVIEW_LEASE_MINUTES:-180}"
VISIBILITY="${HCOM_TEAM_REVIEW_VISIBILITY:-headless}"
DRY_RUN=0
ALLOW_EXPERIMENTAL_AGY="${HCOM_TEAM_ALLOW_EXPERIMENTAL_AGY_REVIEW:-0}"

usage() {
  cat <<'EOF'
Usage: scripts/hcom_review.sh --role ROLE --thread THREAD [options]

Launch a review agent through the configured provider.

Roles:
  runtime_review
  gem_review
  web_review

Options:
  --provider claude-code|antigravity
  --task TEXT
  --lease-minutes N
  --visibility headless|tmux
  --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider)
      PROVIDER_RAW="$2"
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

if [[ -z "$ROLE" || -z "$THREAD" ]]; then
  usage >&2
  exit 2
fi
if [[ -z "$TASK" && ! -t 0 ]]; then
  TASK="$(cat)"
fi
if [[ -z "$TASK" ]]; then
  echo "Missing review task. Pass --task or pipe task text on stdin." >&2
  exit 2
fi
if ! [[ "$LEASE_MINUTES" =~ ^[0-9]+$ ]] || [[ "$LEASE_MINUTES" -lt 1 ]]; then
  echo "--lease-minutes must be a positive integer." >&2
  exit 2
fi

case "$ROLE" in
  runtime_review)
    AREA="runtime"
    CLAUDE_ROLE="runtime_claude"
    TAG="crisai-runtime-review"
    ;;
  gem_review)
    AREA="gem"
    CLAUDE_ROLE="gem_claude"
    TAG="crisai-gem-review"
    ;;
  web_review)
    AREA="web"
    CLAUDE_ROLE="web_claude"
    TAG="crisai-web-review"
    ;;
  *)
    echo "Unsupported review role: $ROLE" >&2
    exit 2
    ;;
esac

case "$PROVIDER_RAW" in
  claude | claude-code | claude_code)
    PROVIDER="claude-code"
    CLAUDE_CMD=("$ROOT_DIR/scripts/hcom_claude_review.sh" \
      --role "$CLAUDE_ROLE" \
      --thread "$THREAD" \
      --task "$TASK" \
      --lease-minutes "$LEASE_MINUTES" \
      --visibility "$VISIBILITY")
    if [[ "$DRY_RUN" -eq 1 ]]; then
      CLAUDE_CMD+=(--dry-run)
    fi
    exec "${CLAUDE_CMD[@]}"
    ;;
  antigravity|agy)
    PROVIDER="antigravity"
    ;;
  *)
    echo "Unsupported review provider: $PROVIDER_RAW" >&2
    exit 2
    ;;
esac

if [[ "$PROVIDER" == "antigravity" && "$DRY_RUN" -eq 0 && "$ALLOW_EXPERIMENTAL_AGY" != "1" ]]; then
  cat >&2 <<'EOF'
Antigravity review is experimental and disabled by default.

The local agy CLI can require interactive OAuth/model selection and may default
to Gemini, so it does not satisfy mandatory Claude review gates. Set
HCOM_TEAM_ALLOW_EXPERIMENTAL_AGY_REVIEW=1 only for an explicit manual smoke
test where that limitation is acceptable.
EOF
  exit 2
fi

require_bin() {
  local bin="$1"
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Missing required command: $bin" >&2
    exit 1
  fi
}

record_lease() {
  local name="$1"
  local started_at expires_epoch expires_at
  started_at="$(date -Is)"
  expires_epoch="$(( $(date +%s) + (LEASE_MINUTES * 60) ))"
  expires_at="$(date -Is -d "@$expires_epoch")"
  mkdir -p "$(dirname "$LEASES")"
  if [[ ! -f "$LEASES" ]]; then
    {
      echo "# Local generic review leases. Ignored by git."
      echo "reviews:"
    } >"$LEASES"
  fi
  cat >>"$LEASES" <<EOF
  $name:
    provider: $PROVIDER
    role: $ROLE
    area: $AREA
    thread: $THREAD
    tag: $TAG
    started_at: "$started_at"
    lease_minutes: $LEASE_MINUTES
    expires_at: "$expires_at"
    expires_at_epoch: $expires_epoch
    status: active
EOF
}

if [[ "$DRY_RUN" -eq 0 ]]; then
  require_bin hcom
  require_bin agy

  if ! hcom agy --help >/dev/null 2>&1; then
    echo "Antigravity review requires an hcom build with native 'agy' launch support." >&2
    exit 1
  fi
fi

PROMPT="$(cat <<EOF
You are an ephemeral Antigravity review agent for crisAI development.

Area: $AREA
Thread: $THREAD
Lease minutes: $LEASE_MINUTES

Review the assigned change independently. Challenge correctness, security,
tests, UX, and project alignment. Keep scope limited to review findings and
small focused patches only when explicitly useful. Report completion through
hcom on thread '$THREAD' and wait for the orchestrator to close or renew you.

Review assignment:
$TASK
EOF
)"

CMD=(hcom agy --tag "$TAG" --dir "$ROOT_DIR" --hcom-prompt "$PROMPT" --hcom-system-prompt "You are a crisAI development review agent. Do not ask the terminal user for next steps; communicate through hcom." --go)
if [[ "$VISIBILITY" == "headless" ]]; then
  CMD+=(--headless)
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'DRY RUN:'
  printf ' %q' "${CMD[@]}"
  printf '\n'
  echo "dry-run-$ROLE"
  exit 0
fi

output="$("${CMD[@]}" 2>&1)"
printf '%s\n' "$output" >&2
name="$(printf '%s\n' "$output" | sed -n 's/^Names: //p' | tr ' ' '\n' | sed '/^$/d' | head -n 1)"
if [[ -z "$name" ]]; then
  echo "Could not parse launched Antigravity reviewer name." >&2
  exit 1
fi
record_lease "$name"
echo "Started $ROLE reviewer via Antigravity as $name on thread '$THREAD' with a $LEASE_MINUTES minute lease."
