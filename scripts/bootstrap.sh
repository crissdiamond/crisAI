#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install it first:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

uv sync --extra litellm

if command -v npm >/dev/null 2>&1; then
  npm --prefix ui install
else
  echo "npm not found; skipping React web and Ink Gem dependencies."
  echo "Install Node.js/npm and run: npm --prefix ui install"
fi

if [ ! -f .env ]; then
  cp .env.example .env
fi

mkdir -p workspace/knowledge workspace/knowledge_staging workspace/tasks workspace/outputs logs registry prompts runbooks

echo "crisAI bootstrap complete."
echo "Next:"
echo "  1. Edit .env with your API keys"
echo "  2. uv run crisai doctor"
echo "  3. ./start api, then ./start gem or ./start web"
