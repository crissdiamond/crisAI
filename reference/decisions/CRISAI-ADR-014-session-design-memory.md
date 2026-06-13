# CRISAI-ADR-014: Session State as Living, Pulled, Status-Bearing Design Memory

Status: accepted  
Date: 2026-06-13

## Context

The intended operating model is one session per architecture task — a solution
design, an option paper, an integration design — worked over **weeks and many
iterations**, with stakeholder discussions, decisions, new discoveries, and gaps
identified along the way. By design, such a session accumulates "a bit of
everything": file discoveries, summary requests, drafts, decisions, and
discussion.

This creates a real tension. Prior iterations produce **genuinely useful state**
— the right files identified, artefacts created, decisions taken — that *should*
ground future iterations. But the same accumulated history also contains stale
intent and noise that, when fed back into the next turn, **corrupts what that
turn is asking to do**.

A concrete symptom: a "find / list / summarise" request in such a session was
mis-classified as `publish_artifact`, because the continuation step
(`continuation_intent_message`, `chat_context.py`) folds the *previous turn's raw
text* into the message that the request-contract classifier scores, and that
prior text (a deck summary) contained source filenames ending in `.pptx`. A
file-type token, useful only as a *reference*, was read as a *publish
instruction*; the policy gate then required a written file and killed an
otherwise-complete run.

The failure is structural, not prompt-specific: it treats "history" as one
undifferentiated blob that is pushed wholesale into the next turn and then scored
for intent. In a long, mixed-intent session most turns are continuations and the
prior turn is rich, so this misfires repeatedly.

This decision is about how a long session's accumulated state should be carried
forward. It builds on CRISAI-ADR-002 (registry-driven semantics), CRISAI-ADR-004
(task contracts), CRISAI-ADR-005 (session memory), and CRISAI-ADR-003 (evidence
transport).

## Decision

Long-lived, mixed-intent sessions are the **supported and recommended operating
model**. crisAI will not impose a stricter per-intent or per-artefact session
model on the user. Feasibility is achieved by how prior state is carried, not by
constraining the human.

A session's durable state is treated as a small, **evolving knowledge base for
that one task** — its canonical sources, its decisions, its current artefacts,
its open gaps — and it obeys three rules:

1. **Per-turn intent is sovereign to the new message.** What a turn is asking to
   *do* (its intent, actions, and policy — including any write/publish action) is
   classified from the user's new words only. The folded prior exchange may
   contribute to *reference resolution* ("it", "that deck") and nothing else. A
   file-type token, source filename, or prior decision must never become an
   action signal. (This is already stated in VISION; this ADR makes it binding
   and names the violation.)

2. **Prior output is typed by kind and persisted as structured, status-bearing
   state — pulled on relevance, not pushed into intent.** Each kind flows through
   its own channel with its own rule:
   - *Identified sources/files* → durable addressable source anchors, resolved
     when referenced or when retrieval scores them relevant; sources carry a
     status (e.g. canonical / superseded / stale).
   - *Decisions* → structured facts/constraints with a status
     (active / superseded), surfaced to drafting/design agents as grounding,
     never as intent.
   - *Artefacts* → workspace resources addressed by path, pulled when the user
     iterates on them.
   - *Summaries / discovery / discussion* → recall-only; searchable, not
     auto-injected.
   The system **grounds on** this state (pull, relevance, provenance); it does
   not **replay** it (push, transcript).

3. **Grounding is inspectable and correctable.** Relevance retrieval is never
   perfect, so the user can see which prior sources and decisions a turn is
   grounding on, **pin or retire** them, and confirm any inferred write/publish
   action before a costly run (CRISAI-ADR-001 / VISION Principle 3 — user control
   at costly decisions). Stale prior state is **demoted by status, not deleted**,
   so reversals and new discoveries are first-class.

The net effect: "a bit of everything in the history" becomes a cumulative asset —
each iteration grounds on a curated design-state — rather than a contamination
risk.

## Consequences

- **Routing and contract inference change**: action / intent / policy are scored
  on the new user message; the continuation fold is restricted to reference
  resolution. Semantic vocabulary for actions (e.g. `publication_terms`) must be
  *intent phrases*, not bare type tokens — a registry edit (CRISAI-ADR-002). The
  `publish_artifact` mis-classification fix is the first, smallest step of this.
- **Session memory gains structure and status**: sources and decisions carry
  provenance and a lifecycle (canonical/superseded/stale). This extends
  CRISAI-ADR-005 and interacts with durable-memory tuning for long sessions
  (TODO-023, so the compact state does not collapse over weeks).
- **Surfacing becomes pull-based and inspectable**: agents retrieve relevant
  prior state on demand; the UI exposes and lets the user pin/retire it, and
  confirm costly write/publish actions before they run.
- **What this deprecates**: pushing raw prior-turn text into the next turn's
  intent classifier; using file-type tokens or source references as action
  signals; treating session history as a replayable transcript.
- **Residual risk**: relevance retrieval can still surface a superseded decision
  or miss a relevant source. This is mitigated by inspectability, status, and the
  confirm-before-costly-write valve rather than by perfect retrieval.
- **Implementation is tracked separately** (intent sovereignty + living design
  memory) and sequenced: the publication-terms fix first, then "infer actions
  from the new message," then structured/status-bearing session state, alongside
  TODO-023. This ADR records the principle; it is not itself an implementation.
