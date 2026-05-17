# crisAI Setup

1. Create a project virtual environment: `python3 -m venv .venv`.
2. Activate it: `source .venv/bin/activate`.
3. Install the package for the default multi-provider registry: `pip install -e ".[litellm]"`.
4. For development and tests, install the dev extra: `pip install -e ".[dev]"`.
5. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `DEEPSEEK_API_KEY`.
6. For a mono-provider setup, copy one of `registry/examples/agents.*.yaml` over `registry/agents.yaml`, then set only that provider's key.
7. Optional Microsoft Graph: set `MS_TENANT_ID` and `MS_CLIENT_ID`, then run SharePoint or intranet auth status/login tools from crisAI.
8. Validate local configuration: `crisai doctor`.
9. Validate artefact profiles: `crisai validate-artefacts`.
10. Start the FastAPI backend: `./start api`.
11. Start the Ink terminal client in another terminal: `./start gem`.
12. Or start the React web UI: `./start web`, then open `http://127.0.0.1:5173`.

Use `pytest` for the network-free regression suite after installing the dev extra. The manual Graph login smoke test remains `python tests/orchestration/test_graph_login.py`.
