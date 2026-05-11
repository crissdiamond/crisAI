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

mkdir -p workspace/knowledge workspace/knowledge_staging workspace/tasks workspace/outputs logs registry prompts runbooks

echo "crisAI bootstrap complete."
echo "Next:"
echo "  1. Edit .env with your API keys"
echo "  2. source .venv/bin/activate"
echo "  3. crisai doctor"
