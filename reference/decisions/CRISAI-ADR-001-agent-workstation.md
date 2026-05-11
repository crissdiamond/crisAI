# CRISAI-ADR-001: crisAI Is A Workstation Of Narrowly Scoped Agents

Status: accepted  
Date: 2026-05-11

## Context

crisAI needs to support architecture, retrieval, summarisation, critique,
documentation, and orchestration without one broad agent owning too many
responsibilities. The user must also be able to associate each agent with a
specific model through configuration.

## Decision

crisAI is designed as a workstation of agents. Each agent has a limited role and
responsibility. More narrowly scoped agents are preferred over fewer broad
agents when the role boundary is real.

Agent/model association belongs in registry configuration, not in code.

## Consequences

- Agents should avoid role overlap where a separate role is clearer.
- Model choices can vary by role, cost, and capability.
- New capabilities should usually start as a distinct agent or stage when they
  represent a different responsibility.
- Shared contracts and registries are needed so agent handoffs remain reliable.

## Related

- `registry/agents.yaml`
- `registry/models.yaml`
- `registry/examples/agents.*.yaml`
