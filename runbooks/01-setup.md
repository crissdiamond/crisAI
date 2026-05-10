# crisAI Setup

1. Create a project virtual environment: `python3 -m venv .venv`.
2. Activate it: `source .venv/bin/activate`.
3. Install the package: `pip install -e .`.
4. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
5. Optional provider keys: set `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` only when selected in `registry/models.yaml`.
6. Optional Microsoft Graph: set `MS_TENANT_ID` and `MS_CLIENT_ID`, then run SharePoint or intranet auth status/login tools from crisAI.
7. Validate local configuration: `crisai doctor`.
8. Validate artefact profiles: `crisai validate-artefacts`.
9. Start the CLI: `./start cli`.
10. Start the web UI: `./start web`, then open `http://127.0.0.1:8000`.

Use `pytest` for the network-free regression suite. The manual Graph login smoke test remains `python tests/orchestration/test_graph_login.py`.
