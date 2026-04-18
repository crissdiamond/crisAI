# Security

- Keep API keys in `.env`, not in prompts or YAML files.
- Start with low-risk read and write tools only.
- Add approvals before enabling higher-risk actions.
- Treat SharePoint, Maps, and other enterprise connectors as separate servers with their own auth handling.
