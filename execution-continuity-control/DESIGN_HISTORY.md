# Execution Continuity Control — Design History

## Identity

- Canonical repository: `BestNameYet/Canonical-Skills-Location`
- Canonical branch: `main`
- Canonical path: `execution-continuity-control/DESIGN_HISTORY.md`
- Version identity: Git commit SHA
- Operational authority: `SKILL.md`

## Purpose

Preserve the reasons behind current mechanisms so later revisions do not reintroduce resolved failures. This file is cumulative but intentionally concise.

## Design timeline

### Goal completion and observable execution

The earliest behavior-control design required actual task execution, validation, remediation, and delivery rather than procedural compliance alone. Persistent execution evidence was added so completion claims would not depend on self-certification or reconstructed memory.

**Retained invariants:** accomplish the requested result; support completion claims with observable evidence.

### Recording moved from pre-work to post-event

A history-first gate, per-turn history files, templates, and archive rotation were tried and later removed because bookkeeping itself could delay the task. Recording became prospective:

`material unit completes → record it → next material unit begins`

The logical record also changed from per-turn/per-chat files to one append-only project record shared across chats.

**Retained invariants:** no retrospective fabrication; cross-chat project continuity; corrections append rather than rewrite history.

### Executable end-turn router

Premature stopping after one failed path, reporting intentions instead of acting, and stopping with executable work remaining led to `end_turn_router.py`. The executable owns questionnaire traversal and directive classification.

A forced-continuation test demonstrated that `CONTINUE` caused missing work to be performed before a later `COMPLETE`.

**Retained invariants:** exhaust viable continuation before impasse; router behavior must alter execution, not merely document it.

### Canonical source versus runtime copies

Canonical scripts and runtime executables were separated. Each relevant turn uses a fresh local Runnable copied from the current canonical source. Runtime copies never acquire canonical authority.

### Externalized Orchestrator gate

A self-invoked router was bypassable because the same Worker owned both the decision to invoke the gate and the actual turn boundary. Control was moved to a higher-scope Orchestrator.

The Worker performs the substantive task but cannot actually end the user-facing turn. Worker stop attempts are simulated signals. The Orchestrator invokes continuity scripts, routes Worker-scoped answers, and is itself router-gated. Only outer Orchestrator `COMPLETE` permits actual termination.

**Retained invariant:** the actor that owns actual termination is outside the Worker and is itself continuity-governed.

### GitHub canonical migration

The previous storage surface required timestamped canonical filenames and collision-handling rules because fixed-name canonical mutation was unreliable. Canonical source moved to GitHub.

Current source identity is stable path + repository + commit SHA. `main` is resolved once per governed turn and all required canonical files are read from that exact commit so mixed revisions cannot occur.

The old timestamped-canon, collision-suffix, and storage-surface authoring rules are superseded environment-specific mechanisms. Their underlying invariants remain: mechanically resolvable authority, immutable revision identity, coherent multi-file snapshots, and no stale-copy authority.

### Explicit minimal execution-record format

The legacy recorder emitted nominal `schema` labels without a separate normative format contract and stored many semantic categories per entry. That was ambiguous and unnecessarily repetitive.

The replacement introduces one real canonical JSON Schema:

`execution-record.schema.json`

New persistent snapshots use `format_version: 1`. Runtime recorder sessions, receipts, router state, and router audit payloads do not declare independent schema identities.

Each event entry has only three semantic fields:

- `event`
- `outcome`
- `evidence`

All other stored fields are mechanical metadata. Entries are incremental deltas: historical context already present in the record is not repeated unless necessary to identify a dependency. Compatible historical snapshots remain immutable and may be normalized in memory when producing their first version-1 successor.

**Retained invariants:** audit evidence remains sufficient to establish what happened; format control is explicit; migration preserves append-only historical lineage.

## Protected invariants

1. Task completion outranks procedural ceremony.
2. Execution outranks plans or intentions when execution is requested and available.
3. Completion, mutation, persistence, and validation claims require observable support.
4. Do not reconstruct unrecorded history as contemporaneous evidence.
5. Record completed material units prospectively, before the next material unit.
6. Maintain one append-only project record across chats; corrections are new entries.
7. The executed router owns traversal and `CONTINUE`/`COMPLETE`/`IMPASSE` classification.
8. Recorder/audit state does not override router control.
9. Worker terminal states end only the Worker lifecycle; only outer Orchestrator `COMPLETE` ends the user-facing turn.
10. The Orchestrator remains task-domain neutral and is itself continuity-governed.
11. Resolve one Git commit snapshot per governed turn and read all required canonical files from it.
12. Canonical files use one stable path each; Git provides version history.
13. Runtime Runnables are fresh derivatives with no canonical authority.
14. Persistent record semantics are storage-provider neutral.
15. Persistent record structure is controlled by the canonical JSON Schema and recorder invariants.
16. Record entries contain only new event delta information unless prior context must be referenced.

## Superseded mechanisms

Do not restore these merely because older artifacts contain them:

- mandatory action-category decomposition;
- universal history-first gating;
- one history file per turn;
- history-template initialization and fixed-count archive rotation;
- timestamped canonical skill filenames;
- greatest-filename-timestamp canonical-source selection;
- collision-suffix canonical defenses;
- storage-specific canonical persistence handoffs;
- allowing the Worker to own actual `END_TURN`;
- treating Worker `COMPLETE`/`IMPASSE` or outer `IMPASSE` as actual-turn completion;
- multiple nominal schema labels without a normative contract;
- verbose per-entry semantic categories that repeat record history.

## Revision rule

Before changing canon, resolve current `main`, read `SKILL.md`, this history, and affected canonical resources from the same commit; identify affected protected invariants; preserve or explicitly supersede them; update this history; commit complete replacement content at stable paths; and verify the resulting coherent `main` snapshot.
