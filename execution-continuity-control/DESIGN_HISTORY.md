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

The logical record changed from per-turn/per-chat files to one append-only project record shared across chats.

**Retained invariants:** no retrospective fabrication; cross-chat project continuity; corrections append rather than rewrite history.

### Executable end-turn router

Premature stopping after one failed path, reporting intentions instead of acting, and stopping with executable work remaining led to `scripts/end_turn_router.py`. The executable owns questionnaire traversal and directive classification.

**Retained invariants:** exhaust viable continuation before impasse; router behavior must alter execution, not merely document it.

### Canonical source versus runtime copies

Canonical scripts and runtime executables were separated. Runtime copies never acquire canonical authority.

### Externalized Orchestrator gate

A self-invoked router was bypassable because the same Worker owned both the decision to invoke the gate and the actual turn boundary. Control moved to a higher-scope Orchestrator.

The Worker performs the substantive task but cannot actually end the user-facing turn. Worker stop attempts are lifecycle signals. The Orchestrator invokes continuity machinery, routes Worker-scoped answers, and is itself router-gated. Only outer Orchestrator completion can authorize final user-facing delivery.

**Retained invariant:** the actor that owns actual termination is outside the Worker and is itself continuity-governed.

### GitHub canonical migration

Canonical source moved to GitHub. Source identity is stable path + repository + commit SHA. `main` is resolved once per governed turn and all required canonical files are read from that exact commit so mixed revisions cannot occur.

Timestamped canonical source filenames and storage-surface collision rules became superseded environment-specific mechanisms. Their underlying invariants remain: mechanically resolvable authority, immutable revision identity, coherent multi-file snapshots, and no stale-copy authority.

### Single runtime bundle bootstrap

A later execution failure exposed an ambiguity in the phrase "copy canonical source into the execution environment": retrieving source through the GitHub connector did not itself create executable files under `/mnt/data`. The model could read canonical scripts yet never materialize or execute them.

Retrieval of `SKILL.md` therefore became a bootstrap event requiring one coherent pinned snapshot to be materialized locally as a bundle while preserving canonical root-relative paths.

### Executable bundle owns child materialization and dispatch

The first runtime-bundle design used a passive JSON document and still required the model to extract embedded script text into executable child files. That left a second avoidable failure boundary.

The bundle was changed into one executable Python file built from canonical `scripts/runtime_bundle.py` plus an embedded manifest. It verifies the embedded file set and Git blob SHAs, owns its private derivative tree, and became the sole model-facing continuity runtime entrypoint. The model no longer extracts or directly executes child scripts.

The bundle internally invokes recorder, questioner, and router and relays their protocol outputs while preserving child filesystem effects.

### Bundle-controlled orchestration loop

A remaining bypass existed above child dispatch: after bundle bootstrap the model still had to remember to assume the Orchestrator role, expose the user prompt to a Worker, invoke continuity after every action, and manually decide when to give the Worker another action. A model could successfully initialize the runtime yet free-run the Worker or skip the Orchestrator identity boundary.

The bundle therefore became the orchestration controller rather than only a subscript dispatcher.

On initial `bootstrap`, the bundle verifies/materializes the pinned snapshot, creates bundle-local control state, and returns `REQUEST_USER_PROMPT`. The complete current user prompt is supplied unchanged and stored as the session task payload.

The bundle then returns `ORCHESTRATOR_IDENTITY_CHECK` containing the canonical Orchestrator definition. The model must explicitly confirm `YES`. A `NO` response produces an instruction to adopt that role; no Worker command is issued until the gate is satisfied.

After confirmation, the bundle returns `ORCHESTRATE_WORKER` with the captured prompt and an explicit rule list. The command permits exactly one next Worker material action. Immediately after that action, the Orchestrator must invoke `after-action --scope worker`. The bundle internally runs recorder/questioner/router and owns the state needed to continue their protocol.

When a non-end-turn Worker action finishes its questionnaire, or a Worker router cycle returns `CONTINUE`, the bundle itself emits the next `ORCHESTRATE_WORKER` control result. This removes the model's discretion to let the Worker perform multiple material actions without passing through continuity control.

The phrase "the script invokes the Orchestrator" is implemented as a mandatory script-to-model control protocol: the Python bundle emits a role-targeted control result that the caller must execute. The script does not claim to instantiate a separate model process by itself.

**Retained invariants:** Orchestrator remains task-domain neutral; captured user intent is preserved; every material action is followed by continuity before another Worker action; Worker terminal states do not own user-facing termination; recorder/questioner/router responsibilities remain distinct.

### Post-Orchestrator final-delivery packet

The next failure boundary was at the end of the lifecycle. A terminal Worker result could return control to the Orchestrator, but the Orchestrator still had to decide how to synthesize the turn's execution record into the user-facing answer, which record snapshot to use, how much prior project history to include, and which generated files to expose. If final-response construction happened before the Orchestrator's own questionnaire/router cycle, the final answer could be based on an execution record that did not yet contain the Orchestrator terminal action or its router result.

The terminal sequence was therefore made explicit and ordered:

`Worker COMPLETE/IMPASSE → WORKER_TERMINAL_TO_ORCHESTRATOR → Orchestrator finalization action → Orchestrator recorder/questioner/router cycle → persisted outer COMPLETE → FINAL_DELIVERY_TO_ORCHESTRATOR → final UI response`

A terminal Worker result now places the bundle in `awaiting_orchestrator_finalization`. Before any Worker resumption or final UI response, the Orchestrator performs its own terminal/finalization action and routes it through `after-action --scope orchestrator`.

Only after the Orchestrator's own `end_turn_result` has been appended and the outer router returns `COMPLETE` does the bundle construct a final-delivery packet. Outer `CONTINUE` resumes execution. Outer `IMPASSE` remains nonterminal and produces no final-delivery packet.

The packet contains the captured user prompt, the final Worker directive, the Orchestrator `COMPLETE`, and the newest execution-record snapshot known after the Orchestrator append. The bundle reads that record file and includes its complete JSON content rather than expecting the Orchestrator to locate or infer the newest snapshot.

To distinguish this turn from accumulated project history, the bundle records the predecessor action count at the first current-turn append and later emits `current_turn_action_range`. The final narrative heuristic treats that range as primary current-turn execution and earlier actions as relative prior history only when they establish dependencies, inherited state, earlier constraints, or changes needed to understand the current outcome.

`FINAL_NARRATIVE_HEURISTIC` is a canonical constant in `scripts/runtime_bundle.py`. It directs the Orchestrator to map the captured prompt to an evidence-backed outcome, prefer newer supported state over stale conflicting history, distinguish accomplishments from plans/self-report, include meaningful gaps or impasse causes, compress low-level continuity bookkeeping, and avoid inventing unrecorded work.

The packet also instructs the Orchestrator to expose Worker-created deliverable files and other user-relevant files when appropriate and available, while suppressing internal continuity runtime/control/questionnaire/record files unless requested or necessary as evidence.

The final UI response is deliberately exempt from another questionnaire cycle. It is the authorized terminal delivery produced immediately after the Orchestrator's own end-turn action has already been recorded/questioned/routed. Re-routing that final response would create infinite terminal recursion.

`FINAL_DELIVERY_TO_ORCHESTRATOR` with `turn_end_authorized = true` therefore replaces a bare `TURN_END_AUTHORIZED` response as the final control primitive.

**Retained invariants:** Worker terminal state remains nonfinal; Orchestrator is still continuity-governed; the final response uses the newest record after the Orchestrator terminal append; current-turn facts are mechanically separated from prior project history where possible; no unrecorded work is fabricated; file exposure is deliverable-oriented rather than an indiscriminate dump of internal runtime artifacts.

### Explicit execution-record schema

Nominal format labels were replaced by one canonical JSON Schema at `schemas/execution-record.schema.json`.

The project record is an immutable sequence of complete snapshots. Each successor preserves earlier actions unchanged, links to the predecessor filename and SHA-256, and appends exactly one new action object.

### Recorder and action-questioner separation

The original recorder combined persistence with an action interview. The recorder was made deliberately ignorant of why it was invoked. On external `invoke`, it appends only a timestamped `recorder_invocation` action and starts `scripts/action_questioner.py`. Child callbacks use a separate append path that never starts another questionnaire.

The action questioner owns post-action interrogation. End-turn detection is an explicit binary question rather than semantic inference from free-form text.

### Router return-path ownership and dual output

An intermediate design allowed `scripts/end_turn_router.py` to call the recorder directly. That violated caller hierarchy. The corrected flow is:

`recorder invoke → questioner → router → questioner → recorder`

The questioner remains the router's caller for the full cycle. A terminal router produces both the model-facing directive and the complete `router_cycle` audit object. The questioner wraps the audit object as `end_turn_result` and returns it to the recorder before the directive is acted upon.

### Decision-engineering questionnaire

The generic eight-question free-form interview was replaced with a structured post-action decision record covering end-turn classification, user intent, `UI#` items, ordered `A#` actions, optional `P#` plans, action-to-intent mappings, `E#` evidence, per-intent outcomes, plan/path divergence, decision bases, overall outcome, supported counterfactuals, and a constrained `NARRATIVE_MAPPING` note.

Atomic action vocabulary remains finite (`ACQUIRE`, `TRANSFORM`, `EVALUATE`, `DECIDE`, `ACT`, `OBSERVE`, `COMMUNICATE`) with canonical subtypes. This decomposition is post-action representation, not a requirement to interrupt execution after microscopic operations.

The questioner validates form and references, not truth or hidden reasoning.

## Protected invariants

1. Task completion outranks procedural ceremony.
2. Execution outranks plans or intentions when execution is requested and available.
3. Completion, mutation, persistence, and validation claims require observable support.
4. Do not reconstruct unrecorded history as contemporaneous evidence.
5. Record completed material actions prospectively before the next material action.
6. Maintain one append-only project record across chats; corrections are new actions.
7. Every immutable successor preserves predecessor actions unchanged and appends exactly one new action.
8. The recorder is the sole execution-record snapshot writer.
9. Recorder invocation does not classify or infer the action; it timestamps invocation and starts the questioner.
10. The action questioner preserves exact ordered canonical Q/A pairs, including native structured JSON answers where required.
11. `AQ1` is the sole action-questionnaire end-turn discriminator and is normalized to explicit `YES` or `NO`.
12. Every enumerated action-questionnaire question co-presents its canonical definition table.
13. Atomic action decomposition is post-action representation only; it must not become an execution-delaying microscopic gate.
14. Structured identifiers (`UI#`, `A#`, `P#`, `E#`) are ordered and cross-referenced.
15. `NARRATIVE_MAPPING` may explain existing structured data but may not introduce new actions, requirements, plans, outcomes, or identifiers.
16. The questioner validates form/reference consistency, not truth, hidden reasoning, or correctness of the model's self-report.
17. `QUESTIONER_ACTION_OVER` means only that questionnaire execution completed.
18. An end-turn-classified questionnaire invokes the router only after the questionnaire object is recorded.
19. The questioner remains caller/proxy for the router cycle.
20. The router never invokes the recorder and has no execution-record write authority.
21. The executed router owns traversal and `CONTINUE`/`COMPLETE`/`IMPASSE` classification.
22. A completed router cycle produces both control output and a formatted audit object.
23. The questioner wraps router data as `end_turn_result` and returns it to recorder before directive execution.
24. Child-data append does not recursively launch the questioner.
25. Worker terminal states end only Worker lifecycle; they never directly authorize user-facing output.
26. The Orchestrator remains task-domain neutral and continuity-governed.
27. Resolve one Git commit snapshot per governed turn and read all canonical files from it.
28. Canonical files use stable paths; Git provides version history.
29. Runtime derivatives have no canonical authority.
30. Persistent record semantics are storage-provider neutral.
31. Persistent record structure is controlled by canonical schema plus recorder cross-snapshot invariants.
32. Historical information is not redundantly restated in every new action object.
33. Retrieval of canonical `SKILL.md` triggers complete executable-bundle construction before governed execution.
34. Exactly one timestamped executable runtime bundle represents the pinned Git snapshot locally for a governed turn.
35. The embedded manifest preserves canonical root-relative paths, including `schemas/` and `scripts/`.
36. All child execution for the turn derives from the same verified bundle; later GitHub reads cannot become independent runtime sources.
37. Bundle construction and successful bootstrap are observable prerequisites for initialized continuity runtime.
38. The model never extracts or directly manages embedded continuity child scripts after bundle creation.
39. `scripts/runtime_bundle.py` is the canonical executable-bundle template and contains exactly one payload sentinel.
40. The bundle owns and verifies its private derivative tree.
41. Recorder child paths are bundle-controlled.
42. Bundle child execution preserves child protocol output and filesystem/state effects.
43. Initial bundle invocation requests the complete current user prompt and stores it unchanged before Worker execution.
44. Orchestrator identity requires an explicit `YES` against the canonical bundle-provided definition before any Worker command.
45. The canonical Orchestrator definition is supplied by `scripts/runtime_bundle.py`, not reconstructed ad hoc by the caller.
46. Each `ORCHESTRATE_WORKER` permits exactly one next material Worker action.
47. After each completed Worker material action, the bundle must be invoked before another Worker material action starts.
48. Post-action recorder/questioner/router completion precedes issuance of the next Worker command.
49. The next Worker instruction after a nonterminal action or Worker `CONTINUE` is emitted by the bundle as `ORCHESTRATE_WORKER`.
50. Worker `COMPLETE`/`IMPASSE` triggers mandatory Orchestrator finalization; it does not directly permit Worker resumption or user-facing delivery.
51. The Orchestrator's finalization action is recorded, questioned, and routed before any final-delivery packet is constructed.
52. Outer `CONTINUE` resumes execution; outer `IMPASSE` remains nonterminal; only persisted outer `COMPLETE` permits final delivery.
53. The final-delivery packet uses the newest execution-record snapshot after the Orchestrator `end_turn_result` append.
54. The bundle records the predecessor action count on first current-turn append and exposes a mechanical `current_turn_action_range` when finalizing.
55. `FINAL_NARRATIVE_HEURISTIC` is canonical runtime text and governs current-turn versus prior-history summarization.
56. Final narrative construction must not convert plans, intentions, questionnaire self-report, or unsupported claims into accomplishments.
57. Newer supported state outranks stale conflicting prior state in final narrative construction.
58. Appropriate Worker-created deliverables and other user-relevant files are exposed in the final UI response when available; internal continuity artifacts are not exposed by default.
59. `FINAL_DELIVERY_TO_ORCHESTRATOR` with `turn_end_authorized = true` is the terminal response-construction authorization.
60. The final UI response does not trigger another continuity cycle because the immediately preceding Orchestrator finalization action already underwent recorder/questioner/router control.
61. Bundle-local orchestration control state is tied to the exact timestamped bundle and pinned source SHA.
62. Direct model-facing recorder/questioner/router dispatch remains superseded; child invocation is internal to the bundle.

## Superseded mechanisms

Do not restore these merely because older artifacts contain them:

- mandatory action-category decomposition as a pre-execution gate;
- universal history-first gating;
- one history file per turn;
- history-template initialization and fixed-count archive rotation;
- timestamped canonical skill filenames;
- greatest-filename-timestamp canonical-source selection;
- collision-suffix canonical defenses;
- storage-specific canonical persistence handoffs;
- allowing Worker to own actual `END_TURN`;
- treating Worker `COMPLETE`/`IMPASSE` or outer `IMPASSE` as actual-turn completion;
- multiple nominal schema labels without a normative contract;
- verbose generic per-action semantic categories that repeat record history;
- the generic eight-question free-form interview;
- a recorder that interviews the model or infers action type;
- free-form action parsing for end-turn detection;
- parallel router history outside the chronological action stream;
- blank/prospective router placeholders;
- direct router-to-recorder persistence calls;
- treating narrative self-report as raw chain-of-thought or independent evidence;
- treating connector retrieval as equivalent to local runtime materialization;
- independently fetching/copying runtime scripts after bundle creation;
- flattening canonical `scripts/` or `schemas/` paths;
- passive JSON-only bundle requiring model extraction of executable children;
- direct model invocation of bundle-derived child script paths;
- caller-supplied recorder questioner/router paths;
- bootstrap that only reports readiness and leaves prompt capture/role initialization to model memory;
- preprompt-only Orchestrator activation without an executable identity gate;
- allowing a Worker to perform multiple material actions before bundle re-entry;
- direct model-facing child-dispatch commands as the normal governed execution interface;
- treating `WORKER_TERMINAL_TO_ORCHESTRATOR` as permission to skip the Orchestrator's own final questionnaire/router cycle;
- exposing a bare `TURN_END_AUTHORIZED` without the latest record and final-response mapping contract;
- asking the Orchestrator to infer which accumulated project-record actions belong to the current turn when the predecessor boundary is mechanically available;
- routing the final UI response through another continuity cycle after the Orchestrator terminal action has already been recorded/questioned/routed.

## Revision rule

Before changing canon, resolve current `main`, read `SKILL.md`, this history, and affected canonical resources from the same commit; identify affected protected invariants; preserve or explicitly supersede them; update this history; stage complete replacement content at stable paths; verify coherence; then move `main`.
