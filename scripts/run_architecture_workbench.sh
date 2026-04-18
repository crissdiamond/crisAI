#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
export PYTHONPATH=./src
python -m crisai.cli.main ask --pipeline --verbose "$@"
