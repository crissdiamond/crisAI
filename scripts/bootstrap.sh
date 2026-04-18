#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
fi

mkdir -p workspace/inputs workspace/outputs workspace/reference workspace/scratch logs registry prompts runbooks

echo "crisAI bootstrap complete."
echo "Next:"
echo "  1. Edit .env"
echo "  2. source .venv/bin/activate"
echo "  3. export PYTHONPATH=./src"
echo "  4. python -m crisai.cli.main list-servers"
