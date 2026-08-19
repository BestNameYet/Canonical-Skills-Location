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

### Recording moved from pre-work to post-action

A history-first gate, per-turn history files, templates, and archive rotation were tried and later removed because bookkeeping itself could delay the task. Recording became prospective: a material action completes, then the recording machinery runs before the next material action begins.

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

### Explicit execution-record schema

Nominal format labels were replaced by one real canonical JSON Schema at `schemas/execution-record.schema.json`.

The project record is an immutable sequence of complete snapshots. Each successor preserves every earlier action unchanged, links to the predecessor filename and SHA-256, and appends one new action object.

Historical information belongs in the accumulated record rather than being repeated in every new action.

### Recorder, questioner, and router separation

The original recorder combined persistence with an action interview. This obscured responsibilities and made the recorder itself responsible for understanding what kind of action had occurred.

The mechanism was split into three scripts with strict dataflow:

`material action → recorder invocation → action questioner → optional end-turn router`

The recorder is now deliberately ignorant of why it was invoked. On external `invoke`, it appends only a timestamped `recorder_invocation` action and starts the questioner. Child-script callbacks enter through a separate append-only path that never starts another questionnaire.

The action questioner owns the eight-question interview. Its second question is an explicit binary discriminator: `Is this action an end-of-turn attempt? Answer YES or NO.` `Y/N` are accepted aliases but storage is normalized to `YES/NO`. This replaced free-form action-type interpretation so end-turn routing is mechanical rather than semantic guesswork.

After all eight answers, the questioner sends one formatted `action_questionnaire` object to the recorder. If AQ2 is `YES`, it then invokes the end-turn router from the newly appended snapshot.

The end-turn router remains the only owner of continuation traversal and directive classification. When a cycle reaches a directive, it sends one formatted `router_cycle` object containing the exact executed question/answer pairs and directive to the recorder before the directive is acted upon.

The execution record is therefore one chronological action stream with three variants: `recorder_invocation`, `action_questionnaire`, and `router_cycle`. There is no separate router-history array and no blank router placeholder.

**Retained invariants:** every material action triggers prospective recording; the recorder remains the sole snapshot writer; exact questionnaire and router Q/A evidence is preserved; end-turn detection is deterministic; router traversal remains executable and authoritative; audit callbacks cannot recursively create new interviews.

## Protected invariants

1. Task completion outranks procedural ceremony.
2. Execution outranks plans or intentions when execution is requested and available.
3. Completion, mutation, persistence, and validation claims require observable support.
4. Do not reconstruct unrecorded history as contemporaneous evidence.
5. Record completed material actions prospectively before the next material action.
6. Maintain one append-only project record across chats; corrections are new actions.
7. Every immutable successor preserves all predecessor actions unchanged and appends exactly one new action.
8. The recorder is the sole execution-record snapshot writer.
9. Recorder invocation does not classify or infer the action; it timestamps invocation and starts the questioner.
10. The action questioner owns exactly eight canonical questions and stores exact ordered Q/A pairs.
11. AQ2 is the sole end-turn discriminator and is normalized to explicit `YES` or `NO`.
12. AQ2 `YES` mechanically invokes the end-turn router only after the questionnaire object has been recorded.
13. The executed router owns traversal and `CONTINUE`/`COMPLETE`/`IMPASSE` classification.
14. Every completed router cycle sends its exact executed Q/A object to the recorder before its directive is acted upon.
15. Child-script data-object appends do not recursively launch the action questioner.
16. Worker terminal states end only the Worker lifecycle; only outer Orchestrator `COMPLETE` ends the user-facing turn.
17. The Orchestrator remains task-domain neutral and is itself continuity-governed.
18. Resolve one Git commit snapshot per governed turn and read all required canonical files from it.
19. Canonical files use one stable path each; Git provides version history.
20. Runtime Runnables are fresh derivatives with no canonical authority.
21. Persistent record semantics are storage-provider neutral.
22. Persistent record structure is controlled by the canonical JSON Schema plus recorder cross-snapshot invariants.
23. Historical information is not redundantly restated in every new action object.

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
- verbose per-action semantic categories that repeat record history;
- a recorder that interviews the model or attempts to infer action type;
- free-form action-type parsing for end-turn detection;
- parallel `router_cycles` history outside the chronological action stream;
- blank or prospective router-cycle placeholders.

## Revision rule

Before changing canon, resolve current `main`, read `SKILL.md`, this history, and affected canonical resources from the same commit; identify affected protected invariants; preserve or explicitly supersede them; update this history; commit complete replacement content at stable paths; and verify the resulting coherent `main` snapshot.
