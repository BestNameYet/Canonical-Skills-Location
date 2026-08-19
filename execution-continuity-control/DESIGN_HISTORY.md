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

The action questioner owns the post-action interrogation. End-turn detection is an explicit binary question rather than a semantic inference from free-form text.

### Router return-path ownership and dual output

An intermediate design allowed `end_turn_router.py` to call the recorder directly. That violated the caller hierarchy: the end-turn router had been invoked by the action questioner, so its completed result should return to that caller rather than reaching sideways into persistence.

The corrected flow is:

`recorder invoke → questioner → router → questioner → recorder`

The action questioner remains the router's caller for the entire router cycle. When the router reaches a directive, it produces both a model-facing control result (`CONTINUE`, `COMPLETE`, or `IMPASSE`) and a formatted `router_cycle` audit object. The questioner wraps the audit object as `end_turn_result` for the recorder and relays the control result toward the model. Neither product substitutes for the other.

The execution record therefore has one chronological `actions` stream with three top-level variants: `recorder_invocation`, `action_questionnaire`, and `end_turn_result`. The `end_turn_result` contains the router-produced `router_cycle` object nested unchanged. There is no separate router history and no blank router placeholder.

### Decision-engineering questionnaire replaces generic eight-question interview

The original eight generic free-form questions preserved broad descriptions such as what happened, why, status, and evidence, but they were poorly normalized for future decision modeling. They also encouraged narrative answers where a finite decision vocabulary was available.

The questionnaire was replaced with a structured post-action decision record. It now captures:

- explicit end-turn classification;
- concise user intent;
- numbered independently testable user-intent items (`UI#`);
- ordered atomic action units (`A#`);
- whether a prior plan existed and, when it did, numbered plan items (`P#`);
- action-to-intent mappings;
- numbered evidence objects (`E#`);
- per-intent outcomes and remaining gaps;
- plan/path divergence and causes;
- material decision-point bases;
- overall activity outcome;
- supported decision-boundary counterfactuals; and
- a final constrained narrative mapping note.

The atomic action vocabulary is intentionally finite even for meta-level work. Seven parent types (`ACQUIRE`, `TRANSFORM`, `EVALUATE`, `DECIDE`, `ACT`, `OBSERVE`, `COMMUNICATE`) have canonical subtypes. This is representational decomposition after an activity, not a mandate to interrupt execution after every tiny operation. The earlier problem with mandatory atomic bookkeeping is therefore not reintroduced.

Every enumerated question co-presents a canonical definition table so classifications are selected against stable meanings rather than inferred from enum names alone. Free-form text is retained only where semantics cannot be usefully reduced to an enum, especially intent text, action targets, evidence references, short exception notes, and the final narrative mapping.

The final `NARRATIVE_MAPPING` note is required because normalized graph-like fields alone do not preserve how the model understood the whole activity as a coherent sequence. The note must reference the already-created `UI#`, `A#`, `P#`, and `E#` identifiers and cannot introduce new actions, requirements, plans, or outcomes. It is treated as a constrained post-action self-report, not raw chain-of-thought and not independent evidence.

The questioner is intentionally non-evaluative. It validates answer shape, canonical enum membership, identifier ordering, and internal references; it does not decide whether the model's answers are true. At completion it emits `QUESTIONER_ACTION_OVER` with the formatted questionnaire object. That signal means only that the interrogation action is complete.

**Retained invariants:** exact Q/A evidence remains first-class; end-turn detection remains mechanical; recorder remains sole persistent snapshot writer; questioner does not infer hidden reasons; structured decision data is cross-checkable against observable execution evidence; representational decomposition must not become an execution gate.

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
10. The action questioner preserves exact ordered canonical Q/A pairs, including native structured JSON answers where required.
11. `AQ1` is the sole action-questionnaire end-turn discriminator and is normalized to explicit `YES` or `NO`.
12. Every enumerated action-questionnaire question co-presents its canonical definition table.
13. Atomic action decomposition is post-action representation only; it must not force artificial execution segmentation or become a prerequisite that delays substantive work.
14. Structured identifiers (`UI#`, `A#`, `P#`, `E#`) are ordered and cross-referenced rather than replaced by prose-only descriptions.
15. The final `NARRATIVE_MAPPING` note may explain existing structured data but may not introduce new actions, requirements, plans, outcomes, or identifiers.
16. The questioner validates form and reference consistency, not truth, hidden reasoning, or correctness of the model's self-report.
17. `QUESTIONER_ACTION_OVER` means only that the questionnaire action is complete; it grants no Worker, router, or turn-completion authority.
18. An end-turn-classified questionnaire invokes the end-turn router only after the questionnaire object has been recorded.
19. The action questioner remains the caller/proxy for the entire router cycle.
20. The end-turn router never invokes the recorder and has no execution-record write authority.
21. The executed router owns traversal and `CONTINUE`/`COMPLETE`/`IMPASSE` classification.
22. A completed router cycle produces both a model-facing control result and a formatted audit data object.
23. The questioner wraps the returned router object as `end_turn_result` and returns that wrapper to the recorder before the directive is acted upon.
24. Child-script data-object appends do not recursively launch the action questioner.
25. Worker terminal states end only the Worker lifecycle; only outer Orchestrator `COMPLETE` ends the user-facing turn.
26. The Orchestrator remains task-domain neutral and is itself continuity-governed.
27. Resolve one Git commit snapshot per governed turn and read all required canonical files from it.
28. Canonical files use one stable path each; Git provides version history.
29. Runtime Runnables are fresh derivatives with no canonical authority.
30. Persistent record semantics are storage-provider neutral.
31. Persistent record structure is controlled by the canonical JSON Schema plus recorder cross-snapshot invariants.
32. Historical information is not redundantly restated in every new action object.

## Superseded mechanisms

Do not restore these merely because older artifacts contain them:

- mandatory action-category decomposition as an execution gate;
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
- verbose generic per-action semantic categories that repeat record history;
- the generic eight-question free-form action interview;
- a recorder that interviews the model or attempts to infer action type;
- free-form action-type parsing for end-turn detection;
- parallel router-cycle history outside the chronological action stream;
- blank or prospective router-cycle placeholders;
- direct router-to-recorder persistence calls;
- treating a post-action narrative self-report as raw chain-of-thought or independent evidence.

## Revision rule

Before changing canon, resolve current `main`, read `SKILL.md`, this history, and affected canonical resources from the same commit; identify affected protected invariants; preserve or explicitly supersede them; update this history; commit complete replacement content at stable paths; and verify the resulting coherent `main` snapshot.
