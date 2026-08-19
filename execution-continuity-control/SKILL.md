---
name: execution-continuity-control
description: Enforces continuous task execution through bundle-issued single-action Worker leases, immutable action recording, structured post-action questioning, executable end-turn routing, and evidence-based final delivery.
compatibility: Designed for ChatGPT Skills with Python 3 execution, a model that follows bundle-emitted Worker instructions, authorized read access to the canonical GitHub repository, and a persistent project-record store. Bundled scripts use only the Python standard library.
---

# Execution Continuity Control

## Purpose

Complete the user's task while preserving an immutable execution history and preventing avoidable early termination. Planning, bookkeeping, status reporting, or procedural compliance must not substitute for execution.

## Canonical source

Repository: `BestNameYet/Canonical-Skills-Location`  
Branch: `main`  
Root: `execution-continuity-control/`

Canonical paths:

- `SKILL.md`
- `DESIGN_HISTORY.md`
- `schemas/execution-record.schema.json`
- `schemas/runtime-bundle.schema.json`
- `scripts/runtime_bundle.py`
- `scripts/action_event_recorder.py`
- `scripts/action_questioner.py`
- `scripts/end_turn_router.py`

At the start of each governed user turn, resolve `main` once to an exact commit SHA. Read every canonical file from that same SHA. Do not mix commits or substitute stale runtime, exported, forked, alternate-branch, or similarly named copies. Runtime artifacts never acquire canonical authority.

Before revising canon, read current `SKILL.md`, `DESIGN_HISTORY.md`, and affected resources from one current `main` SHA; preserve or explicitly supersede affected protected invariants; stage complete replacements; verify coherence; then move `main`.

## Executable runtime bundle

Retrieval of `SKILL.md` is a bootstrap event, not sufficient by itself to begin governed execution. The caller MUST:

1. pin current `main` once for the turn;
2. retrieve every canonical path above from that SHA;
3. build one manifest conforming to `schemas/runtime-bundle.schema.json` with `bundle_format = execution-continuity-runtime-bundle/v2`;
4. preserve canonical root-relative paths;
5. UTF-8 JSON serialize and base64-encode the manifest;
6. replace the one `__EXECUTION_CONTINUITY_BUNDLE_PAYLOAD_B64__` sentinel in the pinned `scripts/runtime_bundle.py` with that payload;
7. write exactly one `/mnt/data/execution-continuity-control_bundle_[timestamp].py`, where `[timestamp]` is sortable UTC `YYYYMMDDTHHMMSSffffffZ`; and
8. invoke it with `bootstrap`.

The embedded tree is:

```text
execution-continuity-control/
├── SKILL.md
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

The bundle verifies every embedded file against its Git blob SHA and owns a private derivative tree under `/mnt/data/execution-continuity-control_run_[bundle_timestamp]/`. The model MUST NOT extract, reconstruct, directly execute, or independently manage embedded recorder/questioner/router scripts.

## Bundle is the sole Orchestrator

The executable bundle is the Orchestrator. The model does not adopt a separate Orchestrator role. It acts as Worker only under a current bundle-issued `WORKER_PAYLOAD`.

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

All governed routing is Worker-scoped because the bundle itself is the Orchestrator.

## Required governed-turn cycle

1. Pin one canonical commit; retrieve all canonical paths; construct the executable bundle; invoke `bootstrap`.
2. Supply the unchanged user prompt when requested.
3. Bundle issues one `TASK_ACTION` lease.
4. Worker performs exactly one material action and returns with that lease's `action_id`.
5. Bundle consumes it, invokes recorder, and issues `CONTINUITY_RESPONSE` leases until questioning/routing completes.
6. Nonterminal completion or `CONTINUE` → exactly one new `TASK_ACTION`; repeat.
7. `COMPLETE` or `IMPASSE` → after terminal persistence, exactly one `FINAL_RESPONSE` lease.
8. Worker uses only that payload for UI delivery and appropriate file exposure; no further cycle follows.
