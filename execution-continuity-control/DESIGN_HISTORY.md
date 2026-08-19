# Execution Continuity Control — Design History

## Identity

- Canonical path: `execution-continuity-control/DESIGN_HISTORY.md`
- Canonical repository: `BestNameYet/Canonical-Skills-Location`
- Canonical branch: `main`
- Version identity: Git commit SHA
- History type: cumulative design-history dependency
- Operational authority: none by itself. `SKILL.md` controls execution.

## Purpose

This file preserves the observed failures, design decisions, superseded mechanisms, rejected alternatives, and protected invariants behind `execution-continuity-control`.

Its purpose is to prevent a future maintainer from treating a superficially simpler change as an improvement when that change would reintroduce a previously corrected failure.

This file contains only observable artifact history, chat decisions, tool outcomes, and concise design rationale. It must not contain private chain-of-thought.

## Precedence and revision method

For current execution:

1. Resolve `main` HEAD in `BestNameYet/Canonical-Skills-Location`.
2. Treat the resulting commit SHA as the immutable canonical snapshot.
3. Read `execution-continuity-control/SKILL.md`, this file, and required canonical scripts from that same commit.
4. Current `SKILL.md` controls operational behavior.
5. This history explains why operational rules exist and constrains revision analysis.
6. Earlier Git commits and pre-migration artifacts are historical evidence.
7. If a later revision replaces a mechanism while preserving the problem it solved, preserve the protected invariant rather than the obsolete mechanism.
8. If evidence is incomplete, record the uncertainty rather than filling gaps from assumption.

## Historical timeline

### 2026-08-15 — goal completion and action guidance

The early behavior-lookup architecture required identification of the user's goal, actual execution, validation, remediation, and delivery.

**Problem:** procedure could substitute for accomplishing the requested result.

**Protected invariant:** behavioral compliance never substitutes for accomplishing the user's goal.

**Later status:** mandatory action-category decomposition was superseded; the goal-completion invariant remains.

---

### 2026-08-15 — persistent audit evidence

Persistent execution history was added so validation could be grounded in observable execution rather than self-certification or reconstructed memory.

**Protected invariant:** completion, persistence, mutation, and validation claims require observable evidence; corrections append evidence instead of silently rewriting history.

---

### 2026-08-16 — history-first hard gate

History initialization became a universal prerequisite and used per-turn files, a template, and archive rotation.

**Problem addressed:** later reconstruction could masquerade as contemporaneous governance.

**Protected invariant retained:** do not fabricate retrospective compliance evidence.

**Superseded mechanisms:** universal history-first gating, one history file per turn, mandatory history-template initialization, and fixed-count archive rotation.

**Reason for supersession:** bookkeeping itself had become front-loaded work capable of delaying the user's task.

---

### 2026-08-16 to 2026-08-17 — one logical record per project

Record identity changed from per-turn/per-chat histories to one logical append-only project record represented by immutable timestamped snapshots.

**Problem:** per-turn files fragmented long-lookback execution history across chats.

**Protected invariants:**

- cross-chat project continuity;
- append-only predecessor lineage;
- corrections are new entries;
- stale runtime state never overrides the newest persisted snapshot.

---

### 2026-08-16 to 2026-08-17 — prospective post-material-unit recording

The history-first gate was replaced by:

`material unit completes → recorder logs that unit → next material unit may begin`

The first material unit of a new turn has no predecessor gate, and prior-turn activity is not reconstructed merely because a new turn begins.

**Protected invariant:** journal completed reality in order without making bookkeeping a substitute for execution.

---

### 2026-08-16 to 2026-08-18 — executable end-turn continuation router

Repeated premature stopping led to a Python router whose executed questionnaire selects `CONTINUE`, `COMPLETE`, or `IMPASSE`.

**Protected invariants:**

- one failed method is not an impasse while a viable alternative exists;
- `CONTINUE` requires actual continuation;
- the executable, not improvised model prose, selects questionnaire traversal and directive classification;
- the executed trace is the audit source of truth.

---

### 2026-08-18 — forced-continuation test

A deliberate stop was attempted before all requested release-readiness work was complete. The router returned `CONTINUE`; the missing work was performed and verified; a later router cycle returned `COMPLETE`.

**Protected invariant:** the router must alter execution behavior rather than merely document unfinished work.

---

### 2026-08-18 — obsolete atomic/planning clauses removed

Mandatory up-front decomposition and planning were removed because they could become nonessential pre-work.

**Protected invariant:** planning may support execution but must not replace it.

---

### 2026-08-18 — canonical script versus runtime Runnable

Canonical Python source and local executable instances were separated. Each relevant user turn creates a fresh `_run_[timestamp]` Runnable from current canonical script content.

**Problem:** a stale local executable could otherwise be mistaken for current source.

**Protected invariant:** execute a fresh local Runnable from the current canonical turn snapshot; runtime copies never acquire canonical authority.

---

### 2026-08-18 — immutable timestamped canonical files introduced

The prior storage surface did not reliably support in-place replacement of one fixed canonical file. Canon therefore moved to immutable timestamped successor files, with exact filename grammar and the greatest encoded timestamp selecting current authority.

**Problem addressed:** pretending that a local or UI-visible copy had mutated a canonical object.

**Protected invariants introduced:**

- canonical revision identity must be mechanically resolvable;
- a stale or duplicate copy must not acquire authority accidentally;
- source history must remain recoverable.

**Later status:** the timestamped-file mechanism itself is superseded by Git commits in the 2026-08-19 migration. The invariants remain.

---

### 2026-08-18 — canonical location distinguished from runtime copies

Canonicality was made dependent on both exact source identity and exact canonical location. Similar files elsewhere were not authoritative.

**Protected invariant:** location is part of canonical identity; runtime, export, and working copies do not become canon by resemblance.

---

### 2026-08-18 — collision-suffixed duplicate artifacts observed

Persistence occasionally produced additional same-content objects with collision suffixes.

**Resolution at the time:** exact canonical filename grammar excluded those copies.

**Protected invariant:** duplicate presentation objects must not create a second source of authority.

**Later status:** Git's stable path plus commit object identity replaces the collision-specific filename workaround.

---

### 2026-08-18 — cumulative design history introduced

Operational canon alone showed what a mechanism required but not why it existed. A cumulative design-history dependency was therefore required for every canonical revision.

**Protected invariant:** a revision is not an improvement if it reintroduces a resolved failure; affected invariants must be preserved or explicitly superseded by a replacement solving the same underlying problem.

**Later status:** timestamp-pinned history filenames are superseded by stable `DESIGN_HISTORY.md` read from the same Git commit as `SKILL.md`.

---

### 2026-08-18 — constitutional same-domain precedence added

The skill was made constitutional within its subject domain. Conflicting same-domain rules are overridden; more granular rules in the skill replace only the overlapping portion of broader rules.

**Protected invariant:** continuity rules are not merely advisory when they govern the same subject matter.

---

### 2026-08-18 — self-invoked end-turn gate proved bypassable

A governed model prematurely ended after explaining a requested revision without actually completing it. The router existed, but the same actor both decided when to enter the router and owned the actual turn boundary.

**Problem:** a Worker could bypass a self-invoked end gate simply by ending.

**Resolution:** externalize continuity enforcement to a higher-scope Orchestrator.

The Orchestrator:

- receives its role from a preprompt;
- treats the user prompt as payload to a Worker;
- does not independently solve or reinterpret the substantive task;
- invokes recorder/router scripts in lieu of the Worker;
- obtains Worker-scoped answers from Worker state;
- treats a Worker end attempt only as a simulated control signal;
- returns Worker `CONTINUE` to the Worker;
- treats Worker `COMPLETE` or `IMPASSE` only as Worker-lifecycle terminal states;
- is itself router-gated;
- permits actual user-facing termination only after an outer Orchestrator router returns `COMPLETE`.

**Protected invariant:** the actor that owns actual termination is outside the Worker and is itself continuity-gated.

---

### 2026-08-19 — canonical source migrated to GitHub

The user replaced the project-file canonical-source mechanism with a GitHub repository.

Canonical source is now rooted at:

`BestNameYet/Canonical-Skills-Location/execution-continuity-control/`

The stable canonical files are:

- `SKILL.md`
- `DESIGN_HISTORY.md`
- `scripts/action_event_recorder.py`
- `scripts/end_turn_router.py`

**Problems being removed as environment-specific workarounds:**

- timestamped canonical skill filenames;
- greatest-filename-timestamp source selection;
- collision-suffix defenses for canonical source;
- duplicate UI-object ambiguity;
- special authoring-location rules tied to the previous project storage surface;
- timestamp-pinned design-history filenames;
- source persistence handoffs that existed only because canonical replacement was not a normal repository write.

**Replacement architecture:**

1. `main` is the moving canonical branch reference.
2. `main` HEAD is resolved once at the start of each governed turn.
3. The resolved commit SHA is the immutable canonical revision identity.
4. `SKILL.md`, `DESIGN_HISTORY.md`, and required scripts are all read from that exact SHA.
5. The turn stays pinned to that SHA so a concurrent commit cannot produce a mixed-version skill/script set.
6. A later turn resolves `main` again.
7. Canonical edits replace complete content at stable paths and are versioned by Git commits.
8. Git history preserves predecessor revisions and rationale.
9. Normal use requires authorized read access; canonical revision requires repository write authority.

**Protected invariants preserved:**

- immutable revision identity → commit SHA;
- mechanically resolvable current source → `main` HEAD;
- canonical name + canonical location → repository + branch ancestry + stable path;
- no stale-copy authority → only files read from the canonical snapshot are canonical;
- predecessor history → Git commit history;
- duplicate-source defense → one path per canonical file;
- coherent multi-file revision → all governed files read from one SHA;
- design-memory dependency → `DESIGN_HISTORY.md` at the same SHA;
- fresh local execution → Runnables remain unchanged as a runtime mechanism.

This migration supersedes the old timestamped-source mechanism rather than weakening the invariants that mechanism protected.

---

### 2026-08-19 — project-record persistence made provider-neutral

Canonical source migration and execution-record persistence are separate concerns.

The skill no longer names a particular persistence provider for project execution records. Instead it requires a configured persistent project-record store and retains the logical record protocol:

- one logical record per project;
- timestamped immutable snapshots;
- latest persisted snapshot selected before every append;
- append-only predecessor lineage;
- local differentiated input copy for recorder execution;
- persist the new complete snapshot before treating it as durable.

**Reason:** source-code canonicality is now solved by Git, while execution-record storage may vary by execution environment. Coupling the two would reintroduce an unnecessary environment-specific dependency.

**Protected invariant:** persistence semantics are mandatory; the storage provider is not.

## Resolved-issue register

| ID | Issue | Current resolution | Protected invariant |
|---|---|---|---|
| DH-001 | Procedure could substitute for task completion | Goal-completion/remediation gates | Accomplish requested result |
| DH-002 | Self-certification or reconstructed execution | Persistent observable audit evidence | Claims require observable support |
| DH-003 | Late history could masquerade as contemporaneous governance | Prospective post-unit recording | No retrospective fabrication |
| DH-004 | Per-turn files fragmented project history | One logical project-wide record | Cross-chat continuity |
| DH-005 | Bookkeeping delayed execution | Record completed units after they occur | Do work; journal completed reality |
| DH-006 | One failed method caused premature stop | Executable continuation router | Pursue viable alternatives before impasse |
| DH-007 | Recorder could be mistaken for controller | Router/recorder separation | Audit state does not select control directive |
| DH-008 | Router could be reconstructed inconsistently | Canonical executable router | Classification comes from executed router |
| DH-009 | Mandatory planning/taxonomy became overhead | Remove general atomic-plan clauses | Planning does not replace execution |
| DH-010 | Canonical replacement was not a reliable in-place operation | Git stable path + commit versioning | Never fake canonical mutation |
| DH-011 | Canonical source and runtime copy could be conflated | Repository/path/commit identity | Runtime copies have no canonical authority |
| DH-012 | Persistent script copy added redundant hops | Canonical script → fresh local Runnable | Execute fresh current script locally |
| DH-013 | Multiple canonical-looking filenames accumulated semantics | One stable canonical path per file | Canonical identity is singular |
| DH-014 | Duplicate presentation objects resembled canon | Git path + object identity | Duplicate copies do not create authority |
| DH-015 | Canon lacked rationale needed to prevent regressions | `DESIGN_HISTORY.md` at same commit | Preserve resolved invariants |
| DH-016 | Same-domain rules could dilute continuity semantics | Constitutional same-domain replacement | Skill governs overlapping domain |
| DH-017 | Worker could bypass self-invoked router | Higher-scope Orchestrator | Worker never owns actual turn boundary |
| DH-018 | Moving branch could yield mixed skill/script revisions | Resolve one commit SHA per turn | Coherent canonical snapshot |
| DH-019 | Canonical source rules were coupled to one storage surface | Git source + provider-neutral record store | Preserve semantics without environment hacks |

## Protected invariants for future revisions

1. **Goal over ceremony.** Procedural compliance never substitutes for completing the user's task.
2. **Execution over description.** A plan, intention, or explanation is not execution when execution was requested and is available.
3. **Observable evidence.** Do not claim completion, mutation, persistence, or validation without observable support.
4. **No retrospective fabrication.** Do not reconstruct unrecorded prior events and treat them as contemporaneous records.
5. **Prospective material-unit journaling.** Record each completed current-turn material unit before the next begins; do not impose a new-turn predecessor gate for prior-turn events.
6. **Project-wide append-only lineage.** Preserve predecessor entries; corrections are new entries.
7. **Fresh canonical resolution.** Resolve `main` on each new governed user turn; do not rely on memory or stale runtime state.
8. **Single-snapshot coherence.** Read `SKILL.md`, design history, and required scripts from one exact commit SHA for the turn.
9. **Executable router authority.** The executed router determines questionnaire traversal and `CONTINUE`/`COMPLETE`/`IMPASSE` classification.
10. **Scoped termination authority.** Worker terminal directives terminate only Worker execution; only an outer Orchestrator `COMPLETE` authorizes actual user-facing `END_TURN`.
11. **Audit/control separation.** Recorder state does not override router control; recorder failure alone is not a user-task impasse.
12. **Fresh executable Runnables.** Required canonical executables are copied from the canonical turn snapshot into the local runtime each relevant turn and executed from fresh `_run_[timestamp]` derivatives.
13. **Git-versioned stable canon.** Canonical files retain stable paths; Git commits provide version history and immutable revision identity.
14. **Canonical repository + path + commit.** All are required for source authority.
15. **One canonical path per governed file.** Timestamped or alternate canonical source filenames are not used.
16. **Complete replacement content.** Canonical source files contain complete target content; diffs describe changes but do not replace canonical files.
17. **Design-memory dependency.** Before changing canon, read `DESIGN_HISTORY.md` from the same current commit and preserve or explicitly supersede every affected invariant.
18. **Constitutional same-domain precedence.** This skill's rules override conflicting same-domain rules or operate as granular replacements for the overlapping portion.
19. **Externalized Worker gate.** The Worker never owns actual turn termination and never directly performs continuity-script invocation when governed by the Orchestrator architecture.
20. **Orchestrator neutrality.** The Orchestrator transports and controls execution of the user task but does not independently solve, critique, reinterpret, or form task-domain opinions.
21. **Orchestrator self-governance.** The Orchestrator is itself continuity-governed; actual turn termination requires its own outer router cycle to return `COMPLETE`.
22. **Provider-neutral record persistence.** Execution-record semantics are mandatory even when the storage provider changes.

## Superseded mechanisms not to restore merely because older artifacts contain them

- mandatory action-category decomposition for every substantive turn;
- universal history-file-first gating;
- exactly one history file per turn;
- mandatory history-template initialization for current execution;
- fixed-count history archive rotation as part of current execution;
- timestamped canonical skill-source filenames;
- greatest-filename-timestamp selection for canonical source;
- timestamp-pinned design-history filenames;
- collision-suffix filename logic for canonical source;
- duplicate persistence handoffs used only to establish canonical source;
- adding extra semantic contexts to canonical filenames;
- persisting canonical scripts into every governed project merely as an intermediate hop before local execution;
- allowing a Worker to own the actual `END_TURN` operation;
- requiring the Worker itself to invoke the recorder/router when an Orchestrator is present;
- treating Worker `COMPLETE` or `IMPASSE` as permission for actual user-facing termination;
- treating outer Orchestrator `IMPASSE` as equivalent to actual-turn completion;
- mixing canonical files from different Git commits during one governed turn.

A later revision may reintroduce a superseded mechanism only when a new requirement justifies it and this history is updated to explain why doing so does not recreate the failure that caused its earlier removal.

## Revision protocol

For every future canonical rewrite:

1. Resolve current `main` HEAD to an exact commit SHA.
2. Read current `SKILL.md`, `DESIGN_HISTORY.md`, and affected scripts from that SHA.
3. Inspect earlier Git commits and any relevant pre-migration evidence needed to understand the affected design.
4. Construct or refresh the relevant chronology before resolving precedence.
5. Identify every resolved issue and protected invariant touched by a proposed removal, weakening, or simplification.
6. If replacing an existing mechanism, state which problem it solved and how the replacement still satisfies that invariant.
7. Update this file cumulatively.
8. Write complete replacement content to the stable canonical path of every changed file.
9. Commit the change.
10. Verify the resulting commit and verify that `main` resolves to the intended coherent canonical snapshot.
