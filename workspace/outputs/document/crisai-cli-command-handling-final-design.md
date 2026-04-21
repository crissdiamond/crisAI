# crisAI CLI command handling final design

## Peer conversation

### Author
Propose a simple design for improving crisAI command handling in the CLI.

### Challenger
Identify weaknesses in the proposal.

### Refiner
Address the weaknesses and keep the design simple and deterministic.

### Judge
Decide whether the refined version is acceptable.

## Final recommendation

Adopt the **simple deterministic CLI command handling pipeline** for crisAI.

### Recommended design
Use a five-stage flow:

1. **Parse**
   - Split input into a command token and arguments.
   - Normalise only the command token.
   - Preserve arguments exactly as typed.
   - Treat empty input as `not_found`.
   - Treat malformed quoting as `error` when parsing cannot safely continue.

2. **Validate**
   - Validate the command registry at startup.
   - Require a name, handler, and metadata for each command.
   - Reject duplicate aliases.
   - Reject malformed registrations.

3. **Resolve**
   - Match in this order:
     - exact command name
     - alias
     - near-match suggestions only
   - Never auto-run fuzzy matches.
   - Return `ambiguous` when more than one command matches at the same priority.

4. **Apply policy**
   - Keep policy separate from routing.
   - Use `confirm` when the command is allowed but needs approval.
   - Use `blocked` when the command is not allowed.
   - Base policy on metadata, user role, and environment.

5. **Execute**
   - Execute only after resolution and policy succeed.
   - Catch handler runtime errors so the session stays alive after recoverable failures.

### Why this is the right design
- Deterministic and easy to test.
- Preserves user input safely.
- Avoids accidental execution from fuzzy matching.
- Fails early on bad registrations.
- Makes ownership, logging, and rollout responsibilities explicit.

### Governance and assurance
- Assign owners for registry structure, aliases, validation, policy, and compatibility exceptions.
- Log validation failures, ambiguous matches, policy denials, handler failures, and compatibility exceptions.
- Start in warning mode if the current registry has legacy issues, then move to strict mode once blocking issues are cleared.

### Bottom line
**Accept the refined design.** It is simple, predictable, and safe to roll out without introducing unnecessary framework complexity.
