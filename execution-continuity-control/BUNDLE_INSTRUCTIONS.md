# Execution Continuity Control — Bundle Instructions

## Authority

This file is the full operational contract loaded from the exact pinned GitHub source archive selected by `SKILL.md`. `SKILL.md` owns only bootstrap discovery, reusable-bundle freshness selection, and the one-shot archive acquisition path. After this file is loaded, these instructions govern the remainder of the governed turn.

Complete the user's task while preserving an immutable execution history and preventing avoidable early termination. Planning, bookkeeping, status reporting, or procedural compliance must not substitute for execution.

## Canonical source and archive integrity

Repository: `BestNameYet/Canonical-Skills-Location`  
Branch: `main`  
Root: `execution-continuity-control/`

Canonical source paths used to construct the executable runtime bundle are:

- `SKILL.md`
- `DESIGN_HISTORY.md`
- `schemas/execution-record.schema.json`
- `schemas/runtime-bundle.schema.json`
- `scripts/runtime_bundle.py`
- `scripts/action_event_recorder.py`
- `scripts/action_questioner.py`
- `scripts/end_turn_router.py`

This file, `BUNDLE_INSTRUCTIONS.md`, is also canonical source and is carried in the downloaded source archive so the bootstrap entry point can remain small. It is not a substitute for any executable child resource.

Canonical construction authority is always the exact Git commit SHA resolved before the archive download. All files used for one construction must come from that one extracted commit archive. Do not mix commits or substitute stale runtime, exported, forked, alternate-branch, or similarly named copies. Runtime artifacts never acquire canonical authority.

The Git tree SHA for `execution-continuity-control/` is the reusable-runtime-bundle freshness identity. It is not a substitute for the commit SHA used to construct a runtime bundle. The commit SHA records exact provenance; the skill-tree SHA answers only whether the canonical skill subtree changed.

The repository archive is a transport container, not an additional authority layer. Authority comes from the exact resolved commit that the archive represents.

Before revising canon, resolve current `main`; read `SKILL.md`, this file, `DESIGN_HISTORY.md`, and affected canonical resources from one current exact commit archive; preserve or explicitly supersede affected protected invariants; stage complete replacements; verify coherence; then move `main`.

## Reusable runtime-bundle freshness gate

A governed turn does **not** automatically require construction of a new executable runtime bundle.

Before reconstruction, the bootstrap caller first attempts to resolve an existing reusable bundle candidate. The candidate may already exist in the live execution environment or may be held in a persistent derivative cache and materialized into the execution environment. A cached or materialized bundle remains a runtime derivative and never becomes canonical source.

Every newly constructed runtime bundle contains exactly one machine-readable pin header before the canonical template content:

```text
# EXECUTION_CONTINUITY_PIN {"repository":"BestNameYet/Canonical-Skills-Location","branch":"main","commit_sha":"<40-hex commit>","skill_tree_sha":"<40-hex tree>"}
```

`commit_sha` identifies the exact canonical snapshot from which the bundle was constructed. `skill_tree_sha` is the Git tree object for `execution-continuity-control/` at that commit.

### First bootstrap after construction

A runtime bundle constructed from the just-downloaded exact current commit archive is already known to match the source selected for construction. Its first `bootstrap` proceeds without a redundant freshness comparison.

### Later initialization of an existing runtime bundle

Before `bootstrap` of a previously constructed bundle:

1. locate the reusable bundle candidate and read its `EXECUTION_CONTINUITY_PIN` header;
2. reject it as non-reusable if the header is missing, malformed, or identifies another repository/branch/root;
3. resolve current `main` once to its exact commit SHA;
4. resolve from that commit the current Git tree SHA for `execution-continuity-control/`;
5. compare the current skill-tree SHA with the candidate's stored `skill_tree_sha`;
6. equal tree SHA means reuse the existing runtime bundle and invoke `bootstrap`; do not download the source archive and do not reconstruct merely because the repository commit SHA changed;
7. different tree SHA, missing candidate, or invalid candidate means the candidate grants no task execution authority; download the exact current commit archive once using `SKILL.md`, load this file from that archive, construct a new runtime bundle, and invoke its first `bootstrap` without another freshness comparison.

An equal skill-tree SHA means the complete canonical `execution-continuity-control/` subtree is byte-for-byte the same Git tree even if unrelated repository content changed. A different skill-tree SHA invalidates reuse.

If a persistent derivative cache is available, persist the exact constructed runtime bundle there so it can survive runtime reallocation. If only `/mnt/data` is available, reuse lasts only while that runtime artifact survives.

## Executable runtime bundle

Loading this file is bootstrap discovery, not sufficient by itself to begin substantive task execution.

When construction is required, the caller must use only the files from the one exact extracted source archive selected by `SKILL.md` and must:

1. retain the resolved exact `main` commit SHA and the `execution-continuity-control/` skill-tree SHA already used for the reconstruction decision;
2. use the eight executable-construction source paths listed above from the extracted canonical root; do not retrieve those files individually from GitHub;
3. build one manifest conforming to `schemas/runtime-bundle.schema.json` with `bundle_format = execution-continuity-runtime-bundle/v2`;
4. preserve canonical root-relative paths and record each canonical Git blob SHA in the manifest;
5. UTF-8 JSON serialize and base64-encode the manifest;
6. replace the one `__EXECUTION_CONTINUITY_BUNDLE_PAYLOAD_B64__` sentinel in the pinned `scripts/runtime_bundle.py` with that payload;
7. prepend exactly one `EXECUTION_CONTINUITY_PIN` header containing the construction commit SHA and skill-tree SHA;
8. write exactly one `/mnt/data/execution-continuity-control_bundle_[timestamp].py`, where `[timestamp]` is sortable UTC `YYYYMMDDTHHMMSSffffffZ`;
9. when a persistent derivative cache is available, persist that exact constructed bundle for later reuse; and
10. invoke the newly constructed bundle with `bootstrap` without rechecking the pin that was just used to construct it.

The extracted canonical source tree contains:

```text
execution-continuity-control/
├── SKILL.md
├── BUNDLE_INSTRUCTIONS.md
├── DESIGN_HISTORY.md
├── schemas/
│   ├── execution-record.schema.json
│   └── runtime-bundle.schema.json
└── scripts/
    ├── runtime_bundle.py
    ├── action_event_recorder.py
    ├── action_questioner.py
    └── end_turn_router.py
```

The executable runtime bundle verifies every manifest-embedded file against its Git blob SHA and owns a private derivative tree under `/mnt/data/execution-continuity-control_run_[bundle_timestamp]/`. The model must not extract, reconstruct, directly execute, or independently manage the embedded recorder/questioner/router scripts after executable-bundle construction.

## Bundle is the sole Orchestrator

The executable runtime bundle is the Orchestrator. The model does not adopt a separate Orchestrator role. It acts as Worker only under a current bundle-issued `WORKER_PAYLOAD`.

**Governing invariant:** `NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY`.

A `WORKER_PAYLOAD` is an action lease containing a monotonically increasing sequence, unique `action_id`, one authority, the captured original user prompt, one `next_instruction`, Worker rules, context, and the exact return-to-bundle contract when continuation is required.

Exactly one unconsumed lease may exist. The bundle rejects missing, stale, duplicated, mismatched, or wrong-authority lease IDs and cannot issue a second lease while one remains unconsumed. Re-entering `bootstrap` with an outstanding lease replays that lease instead of creating duplicate authority. A `CONTROL_ERROR` carries `execution_authority = false` and authorizes no substantive continuation.

### Prompt capture

Initial `bootstrap` returns `REQUEST_USER_PROMPT` with no execution authority. Supply the complete current user prompt unchanged through:

`provide-prompt --user-prompt <complete user prompt>`

The bundle stores it once as the turn's task payload and issues the first Worker lease.

### Lease authorities

1. `TASK_ACTION` — exactly one material Worker action. After it completes or fails, immediately invoke `after-action --action-id <action_id>` before any further substantive action.
2. `CONTINUITY_RESPONSE` — only an answer to the supplied recorder/questioner/router protocol question. It authorizes no substantive task work. Return it through `continuity-answer --action-id <action_id> --answer <answer>`.
3. `FINAL_RESPONSE` — only construction and UI delivery of the final response from the supplied prompt, record, heuristic, terminal result, and file context. It authorizes no remediation or further continuity cycle.

A material action is a completed action, event, failure, decision, tool use, artifact effect, or evaluation that matters to execution understanding.

## One-action control loop

The normal cycle is:

`TASK_ACTION lease → Worker performs exactly one material action → after-action with matching action_id → lease consumed → recorder/questioner/router processing → next lease`

The lease is consumed before continuity processing begins, leaving no substantive execution authority during recorder/questioner/router work.

On the first `after-action`, also supply the environment's recorder persistence arguments: `--output-dir`, `--state-dir`, and `--record-id`, plus `--record` and `--record-name` when a predecessor is materialized. Optional chat metadata may be supplied. The bundle retains this configuration.

The bundle internally invokes `scripts/action_event_recorder.py` at Worker scope and supplies bundle-controlled questioner/router paths. Every returned protocol question receives a fresh `CONTINUITY_RESPONSE` lease. The Worker answers only that question and returns it through the lease-specific command.

When a non-end-turn questionnaire completes, the bundle issues one new `TASK_ACTION` lease. Router `CONTINUE` likewise produces one new `TASK_ACTION` lease and carries forward any continuation instruction. The Worker never independently decides that another material action is permitted.

## Terminal routing and final delivery

Every Worker stop/completion attempt is a material action and passes through recorder → questioner → router.

- `CONTINUE` → bundle issues another `TASK_ACTION` lease.
- `COMPLETE` → after persistence of the terminal `end_turn_result`, bundle resolves the newest execution record and issues one terminal `FINAL_RESPONSE` lease.
- `IMPASSE` → after persistence of the terminal `end_turn_result`, bundle resolves the newest execution record and issues one terminal `FINAL_RESPONSE` lease accurately describing the supported impasse.

There is no separate model-Orchestrator finalization action, Orchestrator questionnaire, Orchestrator router scope, or outer completion cycle.

The terminal payload contains the captured user prompt; Worker terminal directive; newest execution-record pathname, filename, record ID, complete JSON content, and `current_turn_action_range`; `FINAL_NARRATIVE_HEURISTIC`; terminal questioner/router result; and file-exposure guidance.

The narrative heuristic treats current-turn actions as primary evidence and earlier project actions only as relevant prior state/dependencies/constraints; prefers newer supported state over stale conflicts; does not convert plans, intentions, questionnaire self-report, or unsupported claims into accomplishments; compresses low-level continuity bookkeeping; and exposes Worker-created/user-relevant deliverables when appropriate while suppressing internal continuity artifacts by default.

The final UI response is not routed through another continuity cycle because the immediately preceding terminal Worker action has already been recorded, questioned, and routed.

## Project execution record

Each project has one logical append-only execution record represented by immutable snapshots named `execution-record_[timestamp].json` with sortable UTC `YYYYMMDDTHHMMSSffffffZ`.

Before append, resolve the current predecessor from the configured persistent project-record store. Each successor preserves all predecessor actions unchanged and in order, links predecessor filename and SHA-256, and appends exactly one new action. Corrections are later actions; history is never rewritten.

The canonical structure is `schemas/execution-record.schema.json`. The chronological `actions` stream has:

1. `recorder_invocation`;
2. `action_questionnaire`; and
3. `end_turn_result` containing the router-produced `router_cycle` unchanged.

There is no parallel router history and no blank/prospective router placeholder.

## Recorder

Canonical source: `scripts/action_event_recorder.py`. It is the sole execution-record writer.

`invoke` appends one timestamped `recorder_invocation` and starts the questioner. `append` accepts already formatted child action objects and does not recursively launch another questionnaire. The recorder does not infer action meaning or decide end-turn status.

## Action questioner

Canonical source: `scripts/action_questioner.py`. It captures and formats canonical answers and validates syntax/enums/references, not truth or hidden reasoning.

Atomic parent/subtype vocabulary:

- `ACQUIRE`: `READ`, `SEARCH`, `RETRIEVE`
- `TRANSFORM`: `CALCULATE`, `DECOMPOSE`, `SYNTHESIZE`, `CONVERT`, `EXTRACT`
- `EVALUATE`: `COMPARE`, `CLASSIFY`, `VALIDATE`, `SCORE`
- `DECIDE`: `SELECT`, `REJECT`, `PRIORITIZE`, `DEFER`
- `ACT`: `CREATE`, `MODIFY`, `DELETE`, `EXECUTE`, `CALL`
- `OBSERVE`: `INSPECT`, `RECEIVE`, `DETECT_ERROR`, `DETECT_CHANGE`
- `COMMUNICATE`: `ASK`, `RETURN`, `REPORT`, `INSTRUCT`, `SIGNAL`

Canonical questionnaire:

1. `AQ1` — explicit `YES`/`NO` end-turn discriminator.
2. `AQ2` — concise user intent.
3. `AQ3` — independently testable `UI#` intent items.
4. `AQ4` — ordered atomic `A#` action path.
5. `AQ5` — whether an explicit prior plan existed.
6. `AQ6` — prior `P#` plan or `[]`.
7. `AQ7` — every `A#` mapped to `UI#` via `DIRECT`, `SUPPORTING`, `NONE`, or `OBSTRUCTED`.
8. `AQ8` — observable `E#` evidence.
9. `AQ9` — each `UI#` outcome: `SUCCESS`, `PARTIAL`, `FAILED`, `UNADDRESSED`, or `NOT_APPLICABLE`.
10. `AQ10` — prior-plan versus actual-path relationship/divergence.
11. `AQ11` — material decisions and bases.
12. `AQ12` — overall outcome: `COMPLETE_SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`, `BLOCKED`, or `NO_EFFECT`.
13. `AQ13` — supported decision-boundary counterfactuals or `[]`.
14. `AQ14` — constrained `NARRATIVE_MAPPING` note.

`AQ1` is the sole end-turn discriminator. `AQ1 = YES` starts the router only after the questionnaire object is recorded.

## Pre-END-TURN router

Canonical source: `scripts/end_turn_router.py`. The router owns traversal and `CONTINUE`/`COMPLETE`/`IMPASSE` classification. It has no record-write authority and never invokes the recorder.

At a directive it returns both the model-facing control result and complete `router_cycle` audit data. The questioner wraps that object as `end_turn_result` and returns it to the recorder before the directive is acted upon.

All governed routing is Worker-scoped because the executable runtime bundle itself is the Orchestrator.

## Required governed-turn cycle

1. `SKILL.md` resolves a reusable runtime bundle candidate and current `main` plus current `execution-continuity-control/` tree SHA.
2. Equal skill-tree SHA → reuse the existing runtime bundle and `bootstrap` it without downloading source.
3. Missing/invalid/mismatched candidate → use the exact commit already resolved and download that commit archive once; extract it and load this file.
4. Construct one new pinned executable runtime bundle from the extracted canonical files, optionally persist its exact derivative cache copy, and bootstrap it without a redundant immediate freshness check.
5. Supply the unchanged user prompt when requested.
6. Bundle issues one `TASK_ACTION` lease.
7. Worker performs exactly one material action and returns with that lease's `action_id`.
8. Bundle consumes it, invokes recorder, and issues `CONTINUITY_RESPONSE` leases until questioning/routing completes.
9. Nonterminal questionnaire completion or router `CONTINUE` → exactly one new `TASK_ACTION`; repeat.
10. `COMPLETE` or `IMPASSE` → after terminal persistence, exactly one `FINAL_RESPONSE` lease.
11. Worker uses only that payload for UI delivery and appropriate file exposure; no further cycle follows.

## Source-acquisition failure

Failure of the one-shot archive transport does not authorize per-file reconstruction of a supposedly equivalent source snapshot. If no valid reusable runtime bundle exists and the exact pinned archive cannot be acquired, no new executable runtime bundle may be constructed from partial or mixed source. Report the acquisition blocker only after all available legitimate archive-download mechanisms for that exact commit have been exhausted.

## Revision rule

Before changing canon, resolve current `main`; acquire one exact current commit archive; read `SKILL.md`, this file, `DESIGN_HISTORY.md`, and affected canonical resources from that same archive; identify affected protected invariants; preserve or explicitly supersede them; stage complete replacement objects; verify internal coherence and archive-bootstrap correctness; then move `main`.
