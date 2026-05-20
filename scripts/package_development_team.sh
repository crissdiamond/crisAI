#!/usr/bin/env bash
# Build a portable crisAI development-team package.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/development-team"
OUTPUT="${HOME:-/home/diamond}/crisai-development-team.zip"

usage() {
  cat <<'EOF'
Usage: scripts/package_development_team.sh [--output PATH]

Creates a zip package containing the reusable crisAI hcom development-team
scripts, role prompts, launch context, and Codex hook/rule files.

The package excludes local hcom databases, local session assignments, logs,
temporary launch scripts, credentials, tokens, and auth caches.

Default output:
  $HOME/crisai-development-team.zip
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      OUTPUT="$2"
      shift 2
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

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Missing development-team directory: $SRC_DIR" >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "Missing required command: zip" >&2
  exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
  echo "Missing required command: unzip" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"
STAGE="$(mktemp -d)"
cleanup() {
  rm -rf -- "$STAGE"
}
trap cleanup EXIT

PACKAGE_ROOT="$STAGE/crisai-development-team"
cp -a "$SRC_DIR" "$PACKAGE_ROOT"

rm -rf -- \
  "$PACKAGE_ROOT/.hcom" \
  "$PACKAGE_ROOT/.hcom-development" \
  "$PACKAGE_ROOT/.claude" \
  "$PACKAGE_ROOT/.tokens" \
  "$PACKAGE_ROOT/.auth"

find "$PACKAGE_ROOT" \( \
  -name '*.log' -o \
  -name '*.tmp' -o \
  -name '*.db' -o \
  -name '.DS_Store' -o \
  -name '.env' -o \
  -name '.env.*' \
\) -type f -delete

blocked="$(
  find "$PACKAGE_ROOT" \( \
    -path '*/.hcom/*' -o \
    -path '*/.hcom-development/*' -o \
    -path '*/.claude/*' -o \
    -path '*/.tokens/*' -o \
    -path '*/.auth/*' -o \
    -name '*.db' -o \
    -name '.env' -o \
    -name '.env.*' \
  \) -print
)"
if [[ -n "$blocked" ]]; then
  echo "Refusing to package local state or secret-like files:" >&2
  printf '%s\n' "$blocked" >&2
  exit 1
fi

rm -f -- "$OUTPUT"
(cd "$STAGE" && zip -qr "$OUTPUT" crisai-development-team)
unzip -tq "$OUTPUT" >/dev/null

echo "Created development-team package:"
du -h "$OUTPUT"
echo
echo "Top-level package contents:"
if unzip -Z1 "$OUTPUT" >/dev/null 2>&1; then
  unzip -Z1 "$OUTPUT" | sed -n '1,40p'
else
  echo "Package integrity is verified; this unzip build cannot list entries with -Z1."
fi
