# Execution Continuity Control — Design History

## Identity

- Canonical repository: `BestNameYet/Canonical-Skills-Location`
- Canonical branch: `main`
- Canonical path: `execution-continuity-control/DESIGN_HISTORY.md`
- Version identity: Git commit SHA
- Operational authority: `SKILL.md`

## Purpose

Preserve why current mechanisms exist so later revisions do not reintroduce resolved failures.

## Design timeline

### Goal completion and observable execution

The original objective was actual task execution, validation, remediation, and delivery rather than procedural self-certification. Persistent execution evidence was added so completion claims could be checked against observable state.

### Recording moved post-action

History-first gating, per-turn files, templates, and archive rotation delayed work. Recording became prospective: a material action completes, then recording occurs before another material action. The logical record became one append-only project record shared across chats.

### Executable end-turn router

Stopping after one failed path and substituting intentions/status for action led to `scripts/end_turn_router.py`. The executable owns traversal and `CONTINUE`/`COMPLETE`/`IMPASSE` classification.

### Canonical source/runtime separation

Canonical authority moved to stable GitHub paths plus exact commit SHA. Construction pins one commit and all required files come from that commit. Runtime copies are derivatives only.

### Single executable runtime bundle

A retrieval failure showed that connector-fetched source text was not equivalent to executable `/mnt/data` files. Retrieval of `SKILL.md` therefore became a bootstrap-discovery event producing one timestamped local bundle containing one coherent pinned snapshot when a bundle needed to be built. Canonical relative paths are preserved.

A passive JSON bundle still left model-managed extraction as a failure point. `scripts/runtime_bundle.py` therefore became an executable template that embeds the manifest, verifies it, owns the private derivative tree, internally dispatches recorder/questioner/router, and is the sole model-facing runtime entrypoint.

### External model-Orchestrator phase

To stop Worker free-running, an intermediate design added a model-Orchestrator identity gate, one-action Worker commands, Orchestrator-scoped end-turn routing, and a final-delivery packet after outer completion. This established important protections: the Worker could not own the user-facing boundary, action cadence became externally controlled, and final delivery used the newest execution record plus a canonical narrative heuristic.

That phase was useful but redundant: the bundle already held deterministic control state and mostly used the model-Orchestrator as a relay.

### Bundle becomes sole Orchestrator through action leases

The model-Orchestrator layer was removed. The executable bundle itself is now the sole Orchestrator and the model is always a Worker acting under one current `WORKER_PAYLOAD`.

A payload is an action lease with monotonically increasing sequence, unique `action_id`, one authority, one `next_instruction`, captured prompt, context, Worker rules, and an exact return contract. The authorities are `TASK_ACTION`, `CONTINUITY_RESPONSE`, and `FINAL_RESPONSE`.

The central fail-closed rule is `NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY`. Exactly one unconsumed lease may exist. A task-action lease is consumed before recorder/questioner/router processing; stale, duplicated, mismatched, or wrong-authority IDs are rejected; and a second lease cannot be issued until the first is consumed. Re-entering bootstrap replays an outstanding lease rather than duplicating authority. Control errors grant zero execution authority.

After a nonterminal action or router `CONTINUE`, the bundle issues one new `TASK_ACTION`. Each protocol question gets its own `CONTINUITY_RESPONSE`, which cannot authorize task work. Terminal Worker `COMPLETE` or `IMPASSE`, after persistence of its `end_turn_result`, causes the bundle to resolve the newest record and issue one `FINAL_RESPONSE` containing the narrative heuristic and file-delivery context.

The separate Orchestrator identity gate, Orchestrator questionnaire/router scope, `WORKER_TERMINAL_TO_ORCHESTRATOR`, outer completion, and `FINAL_DELIVERY_TO_ORCHESTRATOR` are superseded. Their protections remain through the lease state machine.

### Reusable bundle freshness gate

Unconditional per-turn bundle construction was found to be redundant and expensive. A previously constructed bundle already contains an exact coherent canonical snapshot and does not need to be rebuilt merely because a new governed user turn begins.

The repository commit SHA is retained as exact provenance, but it is intentionally not the rebuild discriminator. A commit SHA changes when any part of the repository changes, including unrelated skills. The Git tree SHA for the canonical `execution-continuity-control/` directory changes only when that directory tree changes. It therefore became the freshness identity for reusable bundles.

Each constructed bundle carries a machine-readable `EXECUTION_CONTINUITY_PIN` header containing both the construction `commit_sha` and the `skill_tree_sha`. The manifest's existing commit SHA continues to identify the exact source snapshot used for construction; the header's skill-tree SHA controls reuse.

On first bootstrap immediately after construction, no GitHub comparison is performed because the just-built bundle is already known to match the exact source pin used to build it. On later initialization, the caller first locates an existing bundle, resolves current `main` and the current skill-subtree tree SHA, and compares the stored tree SHA. An equal tree SHA reuses the bundle even if `main` now points to a different repository commit. A mismatch, missing bundle, or malformed pin invalidates reuse and causes reconstruction from the current exact commit.

This freshness check is deliberately earlier than full canonical retrieval. Only a mismatch pays the cost of retrieving all canonical files and constructing another bundle.

A persistent derivative cache, such as the ChatGPT Library, may preserve the exact bundle across runtime reallocations. A Library copy is still noncanonical and must be materialized into the execution environment before execution when a local pathname is required. If only `/mnt/data` is available, reuse lasts only as long as that runtime artifact survives.

This revision supersedes the earlier protected invariant that retrieval of `SKILL.md` necessarily triggered construction of a new timestamped bundle for every governed turn. Retrieval remains necessary for reconstruction, but reconstruction is now conditional on freshness failure or cache absence.

### Execution record and recorder/questioner/router responsibilities

The execution record is an immutable sequence of complete snapshots. Each successor preserves prior actions unchanged, links its predecessor, and appends exactly one action. The recorder is the sole writer. It records invocation and starts the questioner but does not infer action meaning.

The questioner owns structured post-action capture. `AQ1` is the mechanical end-turn discriminator. The router is invoked only after an end-turn-classified questionnaire is persisted, never writes the record, and returns both a directive and `router_cycle`. The questioner wraps the router object as `end_turn_result` and returns it to the recorder before the directive is acted on.

The generic free-form interview was replaced by structured intent/action/plan/evidence/outcome/decision/counterfactual data using `UI#`, `A#`, `P#`, and `E#` references and a finite action ontology. This is post-action representation, not microscopic execution segmentation.

### Final narrative and file delivery

`FINAL_NARRATIVE_HEURISTIC` maps the captured prompt and newest record to the final response. The predecessor action count establishes `current_turn_action_range`, so current-turn work is primary while earlier project actions are prior history only when relevant to inherited state, dependencies, constraints, or changes.

The heuristic prefers newer supported state, does not convert plans/self-report into accomplishments, includes meaningful gaps/impasse causes, compresses bookkeeping, and exposes real deliverables while suppressing internal continuity artifacts by default. The final UI response is not routed again because the terminal Worker action has already been recorded/questioned/routed.

## Protected invariants

1. Actual requested-task completion outranks procedural ceremony.
2. Completion/mutation/persistence/validation claims require observable support.
3. Do not reconstruct unrecorded history as contemporaneous evidence.
4. Record a completed material action before another material action is authorized.
5. Maintain one append-only project record; corrections append.
6. Every successor preserves predecessor actions unchanged and appends exactly one action.
7. Recorder is the sole execution-record writer and does not infer action meaning.
8. Questioner captures canonical structured answers; `AQ1` alone discriminates end-turn attempts.
9. Atomic decomposition is post-action representation, not an execution-delay gate.
10. Router alone classifies `CONTINUE`/`COMPLETE`/`IMPASSE`, never writes the record, and returns complete audit data through the questioner.
11. When reconstruction is required, pin one Git commit and read all canonical files from it.
12. Runtime derivatives never acquire canonical authority.
13. Bundle construction is conditional: reuse a valid existing bundle when its stored skill-tree SHA matches the current canonical skill-tree SHA; construct only when no valid candidate exists or freshness fails.
14. The bundle verifies/owns its derivative tree and internally controls recorder/questioner/router paths.
15. The model never directly manages embedded continuity child scripts after bundle creation.
16. The bundle itself is the sole Orchestrator; the model acts as Worker only under a current bundle-issued payload.
17. `NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY`.
18. Exactly one unconsumed Worker lease may exist.
19. Every lease has unique monotonically ordered `action_id`/sequence and exactly one authority.
20. `TASK_ACTION` authorizes exactly one material action and must be consumed by matching `after-action --action-id` before another task action can be authorized.
21. `CONTINUITY_RESPONSE` authorizes protocol answering only.
22. `FINAL_RESPONSE` authorizes terminal UI delivery only.
23. Missing/stale/duplicate/mismatched/wrong-authority lease IDs are rejected.
24. A task lease is consumed before recorder/questioner/router processing, leaving no substantive execution authority during continuity processing.
25. No new Worker lease may be issued while another is unconsumed.
26. Bootstrap with an outstanding lease replays it rather than duplicating authority.
27. Control/runtime errors grant zero execution authority.
28. Capture the complete current user prompt unchanged before the first task lease.
29. After every Worker material action, bundle re-entry precedes another Worker material action.
30. Nonterminal questionnaire completion or router `CONTINUE` produces exactly one new `TASK_ACTION` lease.
31. Worker `COMPLETE`/`IMPASSE` is terminal after its `end_turn_result` is persisted.
32. Terminal routing resolves the newest execution-record snapshot before `FINAL_RESPONSE` issuance.
33. `current_turn_action_range` distinguishes current-turn execution from prior project history where mechanically possible.
34. `FINAL_NARRATIVE_HEURISTIC` governs evidence-based final synthesis and must not turn plans, intentions, questionnaire self-report, or unsupported claims into accomplishments.
35. Newer supported state outranks stale conflicting prior state.
36. Appropriate Worker-created/user-relevant files are exposed at final delivery; internal continuity artifacts are suppressed by default.
37. Final UI delivery does not start another continuity cycle.
38. Bundle-local control state is tied to the exact timestamped bundle and pinned source commit SHA from which that bundle was constructed.
39. Direct model-facing child-script dispatch remains superseded.
40. The Git tree SHA of `execution-continuity-control/` is the reusable-bundle freshness discriminator; repository commit SHA remains provenance rather than freshness identity.
41. A repository commit change with unchanged skill-tree SHA must not force bundle reconstruction.
42. First bootstrap of a just-constructed bundle does not perform a redundant freshness comparison.
43. Later initialization of a previously constructed bundle requires freshness comparison before `bootstrap`.
44. A missing, malformed, wrong-scope, or mismatched bundle pin grants no execution authority and requires reconstruction from the current exact commit.
45. Persistent cache copies of bundles are runtime derivatives only; materialization or copying does not give them canonical authority.

## Superseded mechanisms

Do not restore these merely because older artifacts contain them:

- universal history-first gating; per-turn history files; history templates/archive rotation;
- timestamped canonical source filenames or greatest-filename-timestamp authority;
- storage-surface collision rules as canonical identity;
- mandatory microscopic action decomposition before execution;
- free-form end-turn inference or generic eight-question interview;
- recorder-owned interviewing; router-to-recorder writes; parallel router history; blank router placeholders;
- treating connector retrieval as local runtime materialization;
- passive JSON bundle requiring model extraction; direct model invocation of child paths; caller-supplied recorder child paths;
- allowing multiple Worker material actions before bundle re-entry;
- a separate model-Orchestrator identity/YES gate;
- `ORCHESTRATE_WORKER`, Orchestrator-scoped recorder/questioner/router cycles, `WORKER_TERMINAL_TO_ORCHESTRATOR`, outer `COMPLETE`, or `FINAL_DELIVERY_TO_ORCHESTRATOR`;
- any design in which the Worker may continue merely because no new script instruction was emitted;
- issuing a second Worker authorization before the first lease is consumed;
- routing the final UI response through another continuity cycle;
- unconditional construction of a new bundle merely because a new governed turn began;
- using repository commit SHA alone as the rebuild discriminator when the canonical skill subtree is unchanged;
- rechecking GitHub freshness immediately after constructing a bundle from the just-resolved current source pin.

## Revision rule

Before changing canon, resolve current `main`; read `SKILL.md`, this history, and affected canonical resources from that same commit; identify affected protected invariants; preserve or explicitly supersede them; stage complete replacements at stable paths; verify coherence; then move `main`.
