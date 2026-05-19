# Security

- Keep credentials in `.env` or delegated token caches only; do not put secrets in prompts, YAML, markdown artefacts, or tests.
- `uv run crisai doctor` checks for tracked `.env`, `.auth`, token-cache, and log paths.
- The default `.env.example` places Microsoft Graph token caches under `.tokens/`; keep any custom token-cache paths outside `workspace/`.
- Intranet page access is scoped by `registry/intranet.yaml`; neutral tools fetch only provider-issued `content_id` values, and SharePoint legacy tools accept only configured Graph site ids.
- Workspace writes are restricted by server-side path, extension, and size guards. Review knowledge promotion candidates under `workspace/knowledge_staging/` before promoting them to `workspace/knowledge/`.
- Treat registry `allowed_servers` as the authority for agent tool access, and keep high-risk tools out of agent allow lists until their runtime policy is explicit.
