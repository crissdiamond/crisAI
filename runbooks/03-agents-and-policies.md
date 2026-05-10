# Agents And Policies

crisAI routes requests into `single`, `pipeline`, or `peer` mode unless the user pins a mode or agent.

- `single`: one selected agent, commonly retrieval, review, operations, publisher, or orchestrator.
- `pipeline`: retrieval planner, context retrieval, context synthesizer, design, optional review, orchestrator.
- `peer`: optional retrieval/context stages, author, challenger, refiner, judge, bounded revise/escalation loops, orchestrator, peer verifier.

Runtime policy is not just prompt text. `workflow_policy.yaml` can require successful intranet fetch evidence or workspace file changes for matching user intent. Peer mode also infers a run contract and verifies final file-backed claims against changed workspace artefacts.

Deterministic retrieval context is computed once from `retrieval_association_graph.yaml` and reused across modes. Optional advisory MCP expansion is controlled by `CRISAI_DETERMINISTIC_MCP_ADVISORY`; canonical deterministic context remains authoritative.
