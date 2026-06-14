# CRISAI-ADR-015: Durable Source Anchors and Workspace Evidence Materialisation

Status: accepted
Date: 2026-06-14

## Context

The intended operating model is iterative (CRISAI-ADR-014): a user finds and
ranks sources in one turn, then in a natural follow-up asks to read, compare, or
author from "those" sources. This find → then act workflow is the backbone of
knowledge generation.

A concrete, reproducible failure (session `Test001`, 2026-06-14) shows the
backbone is missing:

1. Turn 1 — *"find all files in my OneDrive with 'UCL integration strategy' in
   the title, rank by authority"* — completed perfectly. It resolved the
   authoritative deck `UCL Integration Strategy_Full Presentation v2.pptx`
   (`sourcedoc {DD876D07-…}`), excluded Office lock files, and persisted the
   result to session memory as a source candidate (rank 1, working handle).
2. Turn 2 — *"compare the 2 versions slide by slide … author a knowledge
   artefact"* (peer mode) — **failed at the policy gate**. It bound the v3 deck
   from the prior candidates (its full filename was restated) but failed to bind
   v2: the resolver scores a candidate only when the new message restates enough
   of its full title, and *"the 2 versions" / "v2"* scored below threshold. Having
   dropped the v2 anchor, retrieval **live-searched OneDrive from scratch**,
   matched only the temporary Office lock file `~$UCL Integration Strategy_Full
   Presentation v2 (cd).pptx` (`sourcedoc {7D59EB57-…}`), could not read it (a
   `~$` file is a tiny owner stub, not OOXML), and the policy gate killed the run
   before any authoring happened.

The root cause is **not** the lock file. The authoritative v2 source — with a
working handle — was still in session memory. The failure is that **a resolved
source from a prior turn is persisted but not durably bound on reference**, so a
follow-up re-resolves against live, mutable OneDrive state (locks, renames,
permissions, transient failures) and can regress to a worse or unreadable object.
VISION names "wrong-source continuation" as one of the biggest current sources of
waste, and the near-term direction calls for a human checkpoint after retrieval
(#1) and caching validated retrieval evidence (#3) — this ADR is that work.

Tuning the title-match score would be a workaround. The user explicitly rejected
workarounds for this critical backbone. This ADR specifies the backbone instead.

It builds on CRISAI-ADR-002 (registry semantics), CRISAI-ADR-003 (evidence
transport), CRISAI-ADR-005 (session memory), CRISAI-ADR-011 (session anchors),
CRISAI-ADR-013 (source capability contract), and makes CRISAI-ADR-014's
"identified sources → durable addressable source anchors" concrete, adding the
materialisation half that ADR-014 left open.

## Decision

The source-grounding backbone has two parts, **designed and built as one**: the
anchor *is* the addressable handle to its materialised evidence.

### 1. Durable source anchors

An identified source becomes a first-class, addressable session entity keyed by
its **stable provider identity** (SharePoint/OneDrive `sourcedoc` GUID or
driveItem id; `content_id` for other families) — never its title. Each anchor
carries:

- identity (provider id) and known titles/aliases;
- provenance — the turn and query that found it;
- source family/type and capabilities (CRISAI-ADR-013);
- the highest evidence level reached (CRISAI-ADR-003);
- a durable handle (resolves to the materialised copy, see part 2);
- a provider revision token (ETag / `lastModifiedDateTime`);
- lifecycle status — `canonical` / `superseded` / `stale`.

Anchors are **resolved on reference before any live search**, by deterministic
matching over identity, aliases, version tokens (`v2`, `v3_cd`), and
ordinal/positional references (*"the two versions"*, *"those decks"*, *"the first
one"*). Live search runs only for references that bind to no anchor. This
replaces the brittle full-title scoring that dropped the v2 deck.

Junk objects (Office `~$` lock files, zero-byte, non-OOXML content) are filtered
at the connector and never become anchors. This is a *consequence* of
identity-based anchoring and confirmed materialisation, not the primary fix.

### 2. Workspace evidence materialisation

When a source is **confirmed** (at the retrieval checkpoint), crisAI fetches and
caches it in a bounded, per-task evidence store keyed by source-id + revision:

- the **raw file** (e.g. the `.pptx`/`.docx`), and
- an **extracted sidecar** — normalised text, tables, speaker notes, and
  image/vision descriptions (CRISAI-ADR-003 evidence).

The anchor's durable handle resolves to this cached copy (`workspace_path` +
`content_id`). Authoring and comparison read the cached copy — **never live
OneDrive** — so locks, renames, permissions, and transient failures cannot derail
a run. The cache is invalidated by provider revision: a changed upstream revision
marks the anchor `stale` and triggers re-materialisation on next use. Keeping the
raw file lets a later, different extraction (e.g. a new vision pass over slide
images) re-process the original; the sidecar avoids repeating extraction each run.

This is an **evidence cache, not a document management system** (a VISION
non-goal): it is scoped per task, addressable only by source identity, never a
system of record, and never user-browsable as a file store.

### Control and safety

- The bound source set is surfaced at the **retrieval checkpoint** (VISION
  near-term #1, Principle 3). The user can **pin or retire** anchors and confirm
  before a costly run; binding is inspectable and correctable (CRISAI-ADR-014
  item 3).
- Materialisation is a confirmed, least-privilege read into a bounded workspace
  path (Principle 8). Nothing is fetched or written without the confirmation that
  already gates costly runs.
- Stale prior state is **demoted by status, not deleted** (CRISAI-ADR-014), so
  new versions and reversals are first-class.

## Consequences

- **Wrong-source continuation is eliminated for referenced sources.** A follow-up
  binds to the prior resolution and reads a stable local copy; the `Test001`
  failure cannot recur, and not because of a lock-file special case.
- **Session memory evolves**: today's `source_candidates` become status-bearing
  anchors keyed by provider identity, with revision and lifecycle (extends
  CRISAI-ADR-005 / ADR-011 / ADR-014). Interacts with TODO-023 (durable memory
  tuning) so anchors survive long sessions.
- **New per-task evidence store**: a bounded cache (e.g.
  `workspace/tasks/<id>/sources/<source-id>/<revision>/{raw,extracted}`) with
  revision metadata. This is the concrete form of TODO-003 (cache validated
  retrieval evidence) and the near-term #3 item. The cache lives in a **visible,
  readable** per-task `sources/` directory — not the sensitive `.crisai/` tree
  (which holds session memory, history, and run snapshots agents must not read) —
  so the agent can read the cached copy via the workspace tools and the user can
  see and delete cached files. The candidate's `workspace_path` points at the
  cached copy, so resolution surfaces it for read-through.
- **Retrieval changes to resolve-against-anchors-first**; live search becomes the
  fallback for genuinely new references. The resolver gains robust
  identity/alias/version/ordinal matching.
- **Checkpoint UX gains a bound-source list** with pin/retire (ties to TODO-040
  surfaces and the existing retrieval checkpoint).
- **The policy gate no longer carries the burden** of distinguishing junk from a
  real missing source: confirmed sources are materialised before authoring, so a
  required read does not fail on live state. Connector-level junk filtering and
  graceful-degradation remain useful hardening but are secondary.
- **Storage cost**: raw binaries are cached per task; bounded, revision-invalidated,
  and documented. Not unbounded; not a DMS.
- **Implementation is tracked under TODO-048** (expanded to the source-grounding
  backbone). This ADR records the principle and the integrated design; the phased
  build follows, with the anchor-as-materialised-handle as the unifying contract.

## Residual risk

- Reference resolution can still mis-bind an ambiguous reference; mitigated by the
  inspectable checkpoint (pin/retire) and status, not by perfect matching.
- A source legitimately changes upstream mid-session; mitigated by revision-based
  invalidation and the `stale` status with re-materialisation on next use.
- Cache growth on large binary sources; mitigated by per-task scoping, revision
  de-duplication, and documented retention expectations.
