# Security

- Keep credentials in `.env` or delegated token caches only; do not put secrets in prompts, YAML, markdown artefacts, or tests.
- `uv run crisai doctor` checks for tracked `.env`, `.auth`, token-cache, and log paths.
- SharePoint documents and SharePoint-backed intranet pages use separate Microsoft Graph token caches under `workspace/.auth/`.
- Intranet page access is scoped by `registry/intranet.yaml`; neutral tools fetch only provider-issued `content_id` values, and SharePoint legacy tools accept only configured Graph site ids.
- Workspace writes are restricted by server-side path, extension, and size guards. Review drafts under `workspace/context_staging/` before promoting them to `workspace/context/`.
- Treat registry `allowed_servers` as the authority for agent tool access, and keep high-risk tools out of agent allow lists until their runtime policy is explicit.
