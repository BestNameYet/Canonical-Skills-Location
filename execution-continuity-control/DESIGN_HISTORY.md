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

Canonical scripts and runtime executables were separated. Runtime copies never acquire canonical authority.

### Externalized Orchestrator gate

A self-invoked router was bypassable because the same Worker owned both the decision to invoke the gate and the actual turn boundary. Control moved to a higher-scope Orchestrator.

The Worker performs the substantive task but cannot actually end the user-facing turn. Worker stop attempts are simulated signals. The Orchestrator invokes continuity machinery, routes Worker-scoped answers, and is itself router-gated. Only outer Orchestrator `COMPLETE` permits actual termination.

**Retained invariant:** the actor that owns actual termination is outside the Worker and is itself continuity-governed.

### GitHub canonical migration

Canonical source moved to GitHub. Source identity is stable path + repository + commit SHA. `main` is resolved once per governed turn and all required canonical files are read from that exact commit so mixed revisions cannot occur.

Timestamped canonical source filenames and storage-surface collision rules are superseded environment-specific mechanisms. Their underlying invariants remain: mechanically resolvable authority, immutable revision identity, coherent multi-file snapshots, and no stale-copy authority.

### Single runtime bundle bootstrap

A later execution failure exposed an ambiguity in the phrase "copy canonical source into the execution environment": retrieving source through the GitHub connector did not itself create executable files under `/mnt/data`. The model could read canonical scripts yet never materialize or execute them.

The bootstrap contract was therefore made explicit. Retrieval of canonical `SKILL.md` instructs the caller to pin one `main` commit, retrieve every canonical dependency from that exact SHA, and create exactly one timestamped local bundle representing that coherent snapshot.

The bundle preserves canonical root-relative paths rather than flattening filenames. Its embedded tree contains `SKILL.md`, `DESIGN_HISTORY.md`, both schema files under `schemas/`, and runtime/continuity scripts under `scripts/`.

**Retained invariants:** one coherent Git snapshot per turn; no mixed-revision runtime; runtime derivatives have no canonical authority; observable local materialization precedes script execution; canonical relative paths remain mechanically identifiable.

### Executable bundle owns subscript materialization and dispatch

The first runtime-bundle design used a JSON document as the local snapshot and still required the model to extract embedded script text into executable child files. That left a second avoidable failure boundary: a model could successfully create the bundle yet fail to reconstruct, write, address, or invoke its subscripts.

The bundle was therefore changed from a passive JSON container into one executable Python file. Canonical `scripts/runtime_bundle.py` is a deterministic template containing one payload sentinel. Bootstrap constructs a v2 manifest from the exact pinned canonical files, base64-encodes that manifest, substitutes it into the template exactly once, writes one timestamped `/mnt/data/execution-continuity-control_bundle_[timestamp].py`, and invokes `bootstrap`.

The executable bundle verifies the embedded file set and Git blob SHAs, owns the private derivative tree, and becomes the sole model-facing continuity runtime entrypoint for the turn. The model no longer extracts or directly executes child scripts.

The bundle exposes controlled dispatch commands for recorder, questioner, and router. It materializes exact embedded child source internally, preserves `scripts/` and `schemas/` paths, rejects caller replacement of recorder child paths, executes the selected canonical child with Python, relays child stdout/stderr and exit status, and leaves child-produced files/state in the execution environment.

This keeps the existing recorder → questioner → router → questioner → recorder protocol intact while moving filesystem plumbing out of model discretion. `schemas/runtime-bundle.schema.json` now describes the embedded v2 manifest rather than the outer executable Python file.

The bundle is still noncanonical. GitHub repository + stable path + commit SHA remain authoritative; the executable bundle and its private derivatives are runtime representations only.

**Retained invariants:** one pinned snapshot per turn; no mixed-version children; model-visible protocol output remains the child script's output; child scripts keep their existing responsibilities; recorder remains the sole execution-record writer; runtime implementation details cannot acquire canonical authority.

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

The questionnaire was replaced with a structured post-action decision record. It captures explicit end-turn classification; concise user intent; independently testable `UI#` intent items; ordered atomic `A#` actions; optional prior `P#` plan items; action-to-intent mappings; `E#` evidence; per-intent outcomes; plan/path divergence; decision bases; overall outcome; supported counterfactuals; and a constrained `NARRATIVE_MAPPING` note.

The atomic action vocabulary is intentionally finite even for meta-level work. Seven parent types (`ACQUIRE`, `TRANSFORM`, `EVALUATE`, `DECIDE`, `ACT`, `OBSERVE`, `COMMUNICATE`) have canonical subtypes. This is representational decomposition after an activity, not a mandate to interrupt execution after every tiny operation.

Every enumerated question co-presents a canonical definition table. The final narrative note references existing structured identifiers and cannot introduce new actions, requirements, plans, or outcomes. It is a constrained post-action self-report, not raw chain-of-thought and not independent evidence.

The questioner is intentionally non-evaluative. It validates answer shape, canonical enum membership, identifier ordering, and internal references; it does not decide whether the model's answers are true. At completion it emits `QUESTIONER_ACTION_OVER` with the formatted questionnaire object.

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
29. Runtime derivatives have no canonical authority.
30. Persistent record semantics are storage-provider neutral.
31. Persistent record structure is controlled by the canonical JSON Schema plus recorder cross-snapshot invariants.
32. Historical information is not redundantly restated in every new action object.
33. Retrieval of canonical `SKILL.md` triggers complete runtime-bundle construction before continuity runtime execution.
34. Exactly one timestamped executable runtime bundle represents the pinned canonical Git snapshot locally for a governed turn.
35. The embedded manifest preserves canonical root-relative paths, including `schemas/` and `scripts/` subfolder notation.
36. All continuity child execution for the turn is derived from the same verified executable bundle; later GitHub reads cannot become independent runtime sources.
37. Bundle construction, invocation, and `BUNDLE_READY` verification are observable prerequisites for claiming the continuity runtime was initialized.
38. The model never extracts or directly manages embedded continuity child scripts after the executable bundle exists.
39. `scripts/runtime_bundle.py` is the canonical executable-bundle template and contains exactly one payload substitution sentinel.
40. The executable bundle owns its private derivative tree and verifies existing derivatives byte-for-byte before use.
41. Recorder child paths are bundle-controlled; the caller cannot substitute a different questioner or router during bundle-dispatched recorder invocation.
42. Bundle dispatch relays child stdout/stderr and exit status without replacing the child protocol, while child filesystem/state effects remain available in the execution environment.

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
- treating a post-action narrative self-report as raw chain-of-thought or independent evidence;
- treating connector retrieval of source text as equivalent to local runtime materialization;
- independently fetching or copying individual runtime scripts after a verified turn bundle exists;
- flattening canonical `scripts/` or `schemas/` paths into ambiguous local source identities;
- a passive JSON-only runtime bundle that still requires the model to extract executable children;
- direct model invocation of bundle-derived child script paths;
- caller-supplied recorder questioner/router paths when the recorder is invoked through the executable bundle.

## Revision rule

Before changing canon, resolve current `main`, read `SKILL.md`, this history, and affected canonical resources from the same commit; identify affected protected invariants; preserve or explicitly supersede them; update this history; commit complete replacement content at stable paths; and verify the resulting coherent `main` snapshot.
