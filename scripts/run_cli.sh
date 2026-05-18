#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH=./src
exec uv run python -m crisai.cli.main "$@"
