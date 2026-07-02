#!/usr/bin/env bash
# cleanup_stray_auth_dirs.sh — remove pytest-flag droppings from the repo root.
#
# WHY THESE EXIST: every MCP server module resolves ROOT from sys.argv[1] at
# import time (e.g. src/crisai/servers/sharepoint_server.py:29-34) and then
# mkdirs "<ROOT>/.auth". When pytest is invoked with a flag before the test
# path (e.g. `pytest --no-cov tests/`), importing a server module during
# collection creates a directory literally named after the flag ("--no-cov/",
# "-q/", "--collect-only/") containing only ".auth/". They recur until the
# import-time side effect is fixed.
#
# THIS SCRIPT MUTATES THE WORKING TREE (deletion only). It is deliberately
# narrow: it removes a top-level directory only when ALL of these hold:
#   - its name starts with "-" (a CLI flag, never a legitimate repo path)
#   - it is untracked by git
#   - it contains nothing except a ".auth" directory whose files (if any)
#     are all MSAL/auth cache artefacts
# It always prints the candidate list first and asks for confirmation
# unless --yes is passed. --dry-run lists and exits.
#
# Usage:
#   ./cleanup_stray_auth_dirs.sh [--dry-run] [--yes]

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

DRY_RUN=0
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --yes) ASSUME_YES=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

candidates=()
# find handles the leading-dash names safely because of the ./ prefix.
while IFS= read -r dir; do
  name="${dir#./}"
  # Only flag-shaped names.
  [[ "$name" == -* ]] || continue
  # Must be untracked (git ls-files errors on option-like paths without --).
  if git ls-files --error-unmatch -- "./$name" >/dev/null 2>&1; then
    echo "SKIP (tracked by git): $name" >&2
    continue
  fi
  # Contents must be exactly one entry: .auth (a directory).
  entries="$(find "./$name" -mindepth 1 -maxdepth 1 | sed "s|^\./$name/||")"
  if [[ "$entries" != ".auth" ]]; then
    echo "SKIP (unexpected contents): $name -> [$entries]" >&2
    continue
  fi
  candidates+=("$name")
done < <(find . -mindepth 1 -maxdepth 1 -type d -name '-*')

if [[ ${#candidates[@]} -eq 0 ]]; then
  echo "No stray <flag>/.auth directories found at $REPO_ROOT."
  exit 0
fi

echo "Stray pytest-flag droppings found at $REPO_ROOT:"
for name in "${candidates[@]}"; do
  echo "  ./$name  ($(find "./$name" -type f | wc -l) file(s) under .auth)"
done

if [[ $DRY_RUN -eq 1 ]]; then
  echo "(dry run — nothing removed)"
  exit 0
fi

if [[ $ASSUME_YES -ne 1 ]]; then
  read -r -p "Remove these directories? [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Aborted."; exit 0; }
fi

for name in "${candidates[@]}"; do
  # The './' prefix and '--' stop rm from parsing the name as options.
  rm -rf -- "./$name"
  echo "Removed ./$name"
done
