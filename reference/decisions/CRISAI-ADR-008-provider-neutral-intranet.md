# CRISAI-ADR-008: Intranet Retrieval Is Provider-Neutral

Status: accepted  
Date: 2026-05-11

## Context

One organisation may use SharePoint for both document repositories and intranet
pages, while another may use a wiki or a custom intranet platform. The intranet
MCP should not be structurally tied to SharePoint IDs and page leaves.

## Decision

Keep the intranet MCP standalone and provider-neutral. The default provider can
read SharePoint Site Pages, but the MCP contract should support replacement by a
wiki or custom provider.

## Consequences

- SharePoint document retrieval and intranet page retrieval remain separate MCP
  concerns.
- Intranet tools expose provider-neutral page concepts where possible.
- Provider-specific metadata can exist for compatibility but should not be the
  agent-facing abstraction.
- Future organisations can replace the intranet provider without redesigning the
  pipeline.

## Related

- `registry/intranet.yaml`
- `src/crisai/servers/intranet_server.py`
- `src/crisai/intranet/`
