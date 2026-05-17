# crisAI Setup

1. Create a project virtual environment: `python3 -m venv .venv`.
2. Activate it: `source .venv/bin/activate`.
3. Install the package for the default multi-provider registry: `pip install -e ".[litellm]"`.
4. For development and tests, install the dev extra: `pip install -e ".[dev]"`.
5. Install UI dependencies for Ink Gem and React web: `npm --prefix ui install`.
6. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `DEEPSEEK_API_KEY`.
7. For a mono-provider setup, copy one of `registry/examples/agents.*.yaml` over `registry/agents.yaml`, then set only that provider's key.
8. Optional Microsoft Graph: set `MS_TENANT_ID` and `MS_CLIENT_ID`, then run SharePoint or intranet auth status/login tools from crisAI.
9. Validate local configuration: `crisai doctor`.
10. Validate artefact profiles: `crisai validate-artefacts`.
11. Start the FastAPI backend: `./start api`.
12. Start the Ink terminal client in another terminal: `./start gem`.
13. Or start the React web UI: `./start web`, then open `http://127.0.0.1:5173`.

Use `pytest` for the network-free regression suite after installing the dev extra. The manual Graph login smoke test remains `python tests/orchestration/test_graph_login.py`.
