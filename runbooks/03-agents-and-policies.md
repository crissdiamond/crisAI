# Agents And Policies

crisAI routes requests into `single`, `pipeline`, or `peer` mode unless the user pins a mode or agent.

- `single`: one selected agent, commonly retrieval, review, operations, publisher, or orchestrator.
- `pipeline`: task contract, retrieval planner, context retrieval, retrieval checkpoint, context synthesizer, summary or design, optional review, orchestrator.
- `peer`: optional retrieval/context stages, author, challenger, refiner, judge, bounded revise/escalation loops, orchestrator, peer verifier.

Runtime policy is not just prompt text. `workflow_policy.yaml` can require successful intranet fetch evidence or workspace file changes for matching user intent. Peer mode also infers a run contract and verifies final file-backed claims against changed workspace artefacts.

Deterministic retrieval context and task-contract facts are computed from `semantic_graph.yaml` and reused across modes. Optional advisory MCP expansion is controlled by `CRISAI_DETERMINISTIC_MCP_ADVISORY`; canonical deterministic context remains authoritative.

Pipeline retrieval checkpoints are enabled by default with `CRISAI_RETRIEVAL_CHECKPOINT_ENABLED=true`. The checkpoint is a user-control gate after validated retrieval evidence and before downstream drafting. Users can continue, redirect retrieval, or stop the run; redirects are bounded by `CRISAI_RETRIEVAL_CHECKPOINT_MAX_REDIRECTS`.
