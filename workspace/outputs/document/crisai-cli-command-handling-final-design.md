# crisAI CLI command handling design

## Purpose
Improve command handling in the crisAI CLI with a simple, deterministic design that is easy to understand, test, and maintain.

## Proposed design
Use a small five-step pipeline:

1. **Parse**
   - Read the raw CLI input.
   - Separate the first token as the command name.
   - Keep the remaining tokens as arguments.
   - Treat empty or whitespace-only input as `not_found`.
   - Treat malformed quoting as `error` when the input cannot be parsed safely.

2. **Validate**
   - Validate command registrations at startup.
   - Require each command to have a name, handler, and metadata.
   - Reject duplicate aliases.
   - Reject malformed registrations before the CLI starts handling commands.

3. **Resolve**
   - Resolve commands in this order:
     1. exact command name
     2. alias
     3. near-match suggestions only
   - Exact matches always win.
   - Alias matches are second priority.
   - Fuzzy matches must never auto-execute.
   - If multiple commands match at the same priority, return `ambiguous`.

4. **Apply policy**
   - Keep policy separate from routing.
   - Return `confirm` when the command is allowed but needs approval.
   - Return `blocked` when the command is not allowed.
   - Base policy decisions on metadata, user role, and environment.

5. **Execute**
   - Execute only after resolution and policy succeed.
   - Catch handler runtime errors so the CLI session stays alive after recoverable failures.
   - Treat malformed registrations and broken metadata as startup failures, not runtime recoveries.

## Outcome codes
Use these result codes consistently:
- `matched`
- `not_found`
- `ambiguous`
- `confirm`
- `blocked`
- `error`

### Meaning
- `matched`: a single command was resolved successfully.
- `not_found`: no usable command matched.
- `ambiguous`: more than one equally valid match exists at the same routing stage.
- `confirm`: execution requires explicit user approval.
- `blocked`: execution is disallowed.
- `error`: parse failure or unrecoverable execution failure.

## Governance
Keep ownership explicit for:
- registry structure
- aliases
- validation rules
- policy rules
- compatibility exceptions

If ownership is unclear, default to the stricter interpretation until resolved.

## Assurance baseline
At minimum, verify:
- startup validation rejects missing handlers, duplicate aliases, and malformed metadata
- exact match, alias match, ambiguous match, and not-found behave differently and deterministically
- malformed quoting and empty input are classified consistently
- near-match suggestions never execute automatically
- policy decisions are separate from routing outcomes
- runtime handler failures do not crash the session
- validation failures and policy denials are logged
- regression tests protect existing command behaviour

## Rollout approach
- Start in warning mode if the current registry may contain legacy issues.
- Log validation issues and compatibility gaps during the warning phase.
- Move to strict fail-fast validation after blocking issues are cleared.
- Keep legacy command behaviour stable during rollout unless a command is explicitly retired or approved as incompatible.

## Assumptions
- Command resolution should be deterministic.
- Exact matches take precedence over aliases.
- Duplicate aliases are invalid.
- Suggestions help the user but never change execution behaviour.
- Policy is evaluated separately from routing.
- Command arguments are preserved for the handler to interpret later.
- Help and unknown-command responses are normal CLI responses.

## Why this design is simple
- It is deterministic.
- It separates parsing, validation, routing, policy, and execution.
- It avoids accidental execution from fuzzy matching.
- It fails early on bad command definitions.
- It is straightforward to test and operate safely.

## Conclusion
This design keeps crisAI CLI command handling simple, predictable, and safe while making error boundaries, governance, and rollout behavior explicit.