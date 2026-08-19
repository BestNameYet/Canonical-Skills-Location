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

A history-first gate, per-turn history files, templates, and archive rotation were removed because bookkeeping itself could delay the task. Recording became prospective: a material action completes, then recording machinery runs before the next material action begins.

The logical record also changed from per-turn/per-chat files to one append-only project record shared across chats.

**Retained invariants:** no retrospective fabrication; cross-chat project continuity; corrections append rather than rewrite history.

### Executable end-turn router

Premature stopping after one failed path, reporting intentions instead of acting, and stopping with executable work remaining led to `end_turn_router.py`. The executable owns questionnaire traversal and directive classification.

**Retained invariants:** exhaust viable continuation before impasse; router behavior must alter execution, not merely document it.

### Canonical source versus runtime copies

Canonical scripts and runtime executables were separated. Each relevant turn uses a fresh local Runnable copied from the current canonical source. Runtime copies never acquire canonical authority.

### Externalized Orchestrator gate

A self-invoked router was bypassable because the same Worker owned both the decision to invoke the gate and the actual turn boundary. Control moved to a higher-scope Orchestrator.

The Worker performs the substantive task but cannot actually end the user-facing turn. Worker stop attempts are simulated signals. The Orchestrator invokes continuity scripts, routes Worker-scoped answers, and is itself router-gated. Only outer Orchestrator `COMPLETE` permits actual termination.

**Retained invariant:** the actor that owns actual termination is outside the Worker and is itself continuity-governed.

### GitHub canonical migration

Canonical source moved to GitHub. Source identity is stable path + repository + commit SHA. `main` is resolved once per governed turn and all required canonical files are read from that exact commit so mixed revisions cannot occur.

Timestamped canonical source filenames and storage-surface collision rules are superseded environment-specific mechanisms. Their underlying invariants remain: mechanically resolvable authority, immutable revision identity, coherent multi-file snapshots, and no stale-copy authority.

### Explicit execution-record schema

Nominal format labels were replaced by one real canonical JSON Schema at `schemas/execution-record.schema.json`.

The project record is an immutable sequence of complete snapshots. Each successor preserves every earlier action unchanged, links to the predecessor filename and SHA-256, and appends exactly one new action object. Historical information belongs in the accumulated record rather than being repeated in every new action.

### Recorder and action-questioner separation

The original recorder combined persistence with an action interview. This obscured responsibilities and made the recorder itself responsible for understanding the action.

The recorder was made deliberately ignorant of why it was invoked. On external `invoke`, it appends only a timestamped `recorder_invocation` action and starts `action_questioner.py`. Child-script callbacks use a separate append path that never starts another questionnaire, preventing recursive audit machinery.

The action questioner owns the eight-question interview. Its binary discriminator is:

`AQ2: Is this action an end-of-turn attempt? Answer YES or NO.`

`Y/N` are accepted aliases but storage is normalized to `YES/NO`. This replaced free-form action-type interpretation so routing is mechanical rather than semantic guesswork.

After all eight answers, the questioner returns one formatted `action_questionnaire` object to the recorder. AQ2 `NO` ends the questioner cycle. AQ2 `YES` invokes the end-turn router.

### Router return-path ownership

An intermediate design allowed `end_turn_router.py` to call the recorder directly. That violated the caller hierarchy: the end-turn router had been invoked by the action questioner, so its completed result should return to that caller rather than reaching sideways into persistence.

The corrected flow is:

`recorder invoke → questioner → router → questioner → recorder`

The action questioner remains the router's caller for the entire router cycle. Router answers are supplied through the questioner, which forwards them to the router. When the router reaches a directive, it returns a formatted `router_cycle` data object to the questioner and performs no record write.

The questioner wraps the returned object as `end_turn_result` and sends that wrapper to the recorder. The recorder remains the sole execution-record writer. The router remains solely responsible for traversal and directive classification.

The execution record therefore has one chronological `actions` stream with three top-level variants: `recorder_invocation`, `action_questionnaire`, and `end_turn_result`. The `end_turn_result` contains the router-produced `router_cycle` object nested unchanged. There is no separate router history and no blank router placeholder.

**Retained invariants:** every material action triggers prospective recording; recorder invocation does not infer action type; exact action-question and router Q/A evidence is preserved; end-turn detection is deterministic; router traversal remains executable and authoritative; results return through the caller chain; only the recorder mutates persistent record state.

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
13. The action questioner remains the caller/proxy for the entire router cycle.
14. The end-turn router never invokes the recorder and has no execution-record write authority.
15. The executed router owns traversal and `CONTINUE`/`COMPLETE`/`IMPASSE` classification.
16. A completed router cycle returns its formatted data object to the action questioner.
17. The questioner wraps the returned router object as `end_turn_result` and returns that wrapper to the recorder.
18. Child-script data-object appends do not recursively launch the action questioner.
19. Worker terminal states end only the Worker lifecycle; only outer Orchestrator `COMPLETE` ends the user-facing turn.
20. The Orchestrator remains task-domain neutral and is itself continuity-governed.
21. Resolve one Git commit snapshot per governed turn and read all required canonical files from it.
22. Canonical files use one stable path each; Git provides version history.
23. Runtime Runnables are fresh derivatives with no canonical authority.
24. Persistent record semantics are storage-provider neutral.
25. Persistent record structure is controlled by the canonical JSON Schema plus recorder cross-snapshot invariants.
26. Historical information is not redundantly restated in every new action object.

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
- parallel router-cycle history outside the chronological action stream;
- blank or prospective router-cycle placeholders;
- direct router-to-recorder persistence calls.

## Revision rule

Before changing canon, resolve current `main`, read `SKILL.md`, this history, and affected canonical resources from the same commit; identify affected protected invariants; preserve or explicitly supersede them; update this history; commit complete replacement content at stable paths; and verify the resulting coherent `main` snapshot.
