#!/usr/bin/env bash
# Report or remove rebuildable local crisAI artefacts.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPLY=0
CLEAN_REBUILDABLE=1
CLEAN_DEPS=0
CLEAN_HCOM=0
CLEAN_LOGS=0
CLEAN_WORKSPACE=0

usage() {
  cat <<'EOF'
Usage: scripts/clean_local.sh [options]

By default this reports rebuildable local artefacts without deleting anything.
Pass --apply to remove the selected categories.

Default selected category:
  --rebuildable       Python caches, test caches, build outputs, coverage files,
                      UI dist folders, and TypeScript build info.

Optional categories:
  --deps              Remove .venv and UI node_modules folders.
  --hcom              Remove local hcom state: .hcom and .hcom-development.
  --logs              Remove local logs and tests/logs.
  --workspace-state   Remove local runtime task/cache/input/output state, but
                      keep curated workspace/knowledge and staging README files.
  --all               Select rebuildable, deps, hcom, and logs. This does not
                      select --workspace-state.

Safety:
  The script never removes .env, .tokens, .auth, workspace/.auth, or
  workspace/knowledge.

Examples:
  scripts/clean_local.sh
  scripts/clean_local.sh --apply
  scripts/clean_local.sh --deps --apply
  scripts/clean_local.sh --all --apply
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --rebuildable)
      CLEAN_REBUILDABLE=1
      shift
      ;;
    --deps)
      CLEAN_DEPS=1
      shift
      ;;
    --hcom)
      CLEAN_HCOM=1
      shift
      ;;
    --logs)
      CLEAN_LOGS=1
      shift
      ;;
    --workspace-state)
      CLEAN_WORKSPACE=1
      shift
      ;;
    --all)
      CLEAN_REBUILDABLE=1
      CLEAN_DEPS=1
      CLEAN_HCOM=1
      CLEAN_LOGS=1
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

cd "$ROOT_DIR"
shopt -s nullglob globstar

declare -a TARGETS=()

add_target() {
  local path="$1"
  [[ -e "$path" || -L "$path" ]] || return 0
  TARGETS+=("$path")
}

add_find_targets() {
  local root="$1"
  shift
  [[ -e "$root" ]] || return 0
  while IFS= read -r -d '' path; do
    TARGETS+=("$path")
  done < <(find "$root" "$@" -print0)
}

add_repo_pycache_targets() {
  while IFS= read -r -d '' path; do
    TARGETS+=("$path")
  done < <(
    find . \
      \( -path './.git' -o \
         -path './.venv' -o \
         -path './tests/.cache' -o \
         -path './ui/node_modules' -o \
         -path './ui/*/node_modules' \) -prune \
      -o -type d -name "__pycache__" -print0
  )
}

add_ui_build_targets() {
  [[ -e "ui" ]] || return 0
  while IFS= read -r -d '' path; do
    TARGETS+=("$path")
  done < <(
    find ui \
      \( -path 'ui/node_modules' -o -path 'ui/*/node_modules' \) -prune \
      -o \( \
        -type d \( -name "dist" -o -name ".vite" -o -name "coverage" \) -o \
        -type f -name "*.tsbuildinfo" \
      \) -print0
  )
}

if [[ "$CLEAN_REBUILDABLE" -eq 1 ]]; then
  add_target ".pytest_cache"
  add_target ".ruff_cache"
  add_target ".mypy_cache"
  add_target ".coverage"
  add_target "htmlcov"
  add_target "dist"
  add_target "build"
  add_target "src/crisai.egg-info"
  add_target "tests/.cache"
  add_repo_pycache_targets
  add_ui_build_targets
fi

if [[ "$CLEAN_DEPS" -eq 1 ]]; then
  add_target ".venv"
  add_target "ui/node_modules"
  for path in ui/apps/*/node_modules ui/packages/*/node_modules; do
    add_target "$path"
  done
fi

if [[ "$CLEAN_HCOM" -eq 1 ]]; then
  add_target ".hcom"
  add_target ".hcom-development"
fi

if [[ "$CLEAN_LOGS" -eq 1 ]]; then
  add_target "logs"
  add_target "tests/logs"
fi

if [[ "$CLEAN_WORKSPACE" -eq 1 ]]; then
  add_target "workspace/.cache"
  add_target "workspace/chat_sessions"
  add_target "workspace/context_staging"
  add_target "workspace/inputs"
  add_target "workspace/outputs"
  add_target "workspace/scratch"
  add_target "workspace/__inputs"
  for path in workspace/tasks/*; do
    [[ "$path" == "workspace/tasks/README.md" ]] && continue
    add_target "$path"
  done
  for path in workspace/knowledge_staging/*; do
    case "$path" in
      workspace/knowledge_staging/README.md|workspace/knowledge_staging/_prompt*.md)
        continue
        ;;
    esac
    add_target "$path"
  done
fi

dedupe_targets() {
  local -A seen=()
  local -a deduped=()
  local path
  for path in "${TARGETS[@]}"; do
    [[ -n "${seen[$path]:-}" ]] && continue
    seen["$path"]=1
    deduped+=("$path")
  done
  TARGETS=("${deduped[@]}")
}

is_protected_path() {
  case "$1" in
    .env|.env.*|.tokens|.tokens/*|.auth|.auth/*|workspace/.auth|workspace/.auth/*|workspace/knowledge|workspace/knowledge/*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

dedupe_targets

echo "crisAI local disk usage:"
du -sh . 2>/dev/null || true
echo

if [[ "${#TARGETS[@]}" -eq 0 ]]; then
  echo "No selected clean targets found."
  exit 0
fi

echo "Selected clean targets:"
for path in "${TARGETS[@]}"; do
  if is_protected_path "$path"; then
    echo "  SKIP protected: $path"
    continue
  fi
  size="$(du -sh -- "$path" 2>/dev/null | awk '{print $1}')"
  printf '  %8s  %s\n' "${size:-?}" "$path"
done
echo

if [[ "$APPLY" -ne 1 ]]; then
  echo "Dry run only. Re-run with --apply to remove the selected targets."
  exit 0
fi

echo "Removing selected targets..."
for path in "${TARGETS[@]}"; do
  if is_protected_path "$path"; then
    echo "  skip protected: $path"
    continue
  fi
  rm -rf -- "$path"
  echo "  removed: $path"
done

echo
echo "Remaining crisAI local disk usage:"
du -sh . 2>/dev/null || true
