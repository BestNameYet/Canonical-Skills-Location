---
name: execution-continuity-control
description: Enforces continuous task execution through a bundle-controlled Orchestrator/Worker loop, immutable action recording, a structured decision-engineering action questionnaire, and executable end-turn routing.
compatibility: Designed for ChatGPT Skills with Python 3 execution, an Orchestrator/Worker execution model, authorized read access to the canonical GitHub repository, and a persistent project-record store. Bundled scripts use only the Python standard library.
---

# Execution Continuity Control

## Purpose

Complete the user's task while preserving an immutable execution history and preventing avoidable early termination. Planning, bookkeeping, status reporting, or procedural compliance must not substitute for execution.

This is a constitutional same-domain rule: where another applicable rule conflicts with this skill on execution continuity, this skill governs the overlapping domain; unaffected portions of broader rules remain in force.

## Canonical source

Canonical repository: `BestNameYet/Canonical-Skills-Location`

Canonical branch: `main`

Canonical root: `execution-continuity-control/`

Canonical paths:

- `SKILL.md`
- `DESIGN_HISTORY.md`
- `schemas/execution-record.schema.json`
- `schemas/runtime-bundle.schema.json`
- `scripts/runtime_bundle.py`
- `scripts/action_event_recorder.py`
- `scripts/action_questioner.py`
- `scripts/end_turn_router.py`

At the start of each governed user turn, resolve `main` HEAD once to an exact commit SHA and use that SHA as the canonical turn snapshot. Read every required canonical file from that same SHA. Do not mix commits or substitute stale runtime, exported, forked, alternate-branch, or similarly named copies.

Git commit identity provides immutable version identity. Stable repository paths provide canonical file identity. Runtime artifacts never acquire canonical authority.

### Canonical revision

Before changing canon:

1. resolve current `main` HEAD;
2. read `SKILL.md`, `DESIGN_HISTORY.md`, and every affected canonical resource from that SHA;
3. inspect earlier Git/history evidence needed to understand affected mechanisms;
4. identify every protected invariant touched by the change;
5. preserve each invariant or explicitly document why its replacement still solves the underlying problem;
6. update `DESIGN_HISTORY.md` cumulatively;
7. write complete replacement content at stable canonical paths;
8. verify the coherent staged revision; and
9. move `main` only after that verification.

A staging branch has no canonical authority until its revision is reachable from `main`.

## Executable runtime bundle construction

Retrieval of canonical `SKILL.md` is a bootstrap event, not sufficient by itself to begin governed execution. The caller MUST create one complete executable local runtime bundle from the pinned turn snapshot.

After `SKILL.md` is retrieved:

1. resolve `main` HEAD exactly once for the turn and pin that commit SHA;
2. retrieve every canonical path listed above from that exact SHA, including `SKILL.md` itself;
3. assemble those exact retrieved contents into one manifest conforming to `schemas/runtime-bundle.schema.json` using `bundle_format = execution-continuity-runtime-bundle/v2`;
4. preserve canonical root-relative paths in the manifest;
5. serialize the manifest as UTF-8 JSON and base64-encode those bytes;
6. take the exact pinned content of `scripts/runtime_bundle.py` and replace its single `__EXECUTION_CONTINUITY_BUNDLE_PAYLOAD_B64__` sentinel with that base64 payload exactly once;
7. write the resulting executable bundle as `/mnt/data/execution-continuity-control_bundle_[timestamp].py`, where `[timestamp]` is sortable UTC `YYYYMMDDTHHMMSSffffffZ`; and
8. invoke that timestamped bundle with `bootstrap`.

The embedded canonical tree is:

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

The executable bundle verifies the manifest and every embedded file against its Git blob SHA, then owns a private derivative tree under:

`/mnt/data/execution-continuity-control_run_[bundle_timestamp]/`

The model MUST NOT extract, reconstruct, directly execute, or independently manage the embedded recorder, questioner, or router. All continuity child execution occurs through the bundle's orchestration protocol.

The timestamped bundle and its derivative tree are noncanonical representations of the pinned Git snapshot. Later GitHub reads may inspect the same pinned SHA but cannot replace the embedded runtime source for that turn.

## Bundle-controlled orchestration bootstrap

The bundle itself establishes orchestration control. Its initial `bootstrap` invocation MUST NOT immediately hand the task to a Worker.

### Phase 1 — request the user prompt

After verifying/materializing its embedded snapshot, `bootstrap` creates bundle-local orchestration control state and returns `REQUEST_USER_PROMPT`.

The caller supplies the complete current user prompt unchanged through:

`provide-prompt --user-prompt <complete user prompt>`

The bundle stores that prompt as immutable task payload for the orchestration session. Subsequent Worker commands reference this captured prompt rather than reconstructing it from memory.

### Phase 2 — establish Orchestrator identity

After the prompt is captured, the bundle returns `ORCHESTRATOR_IDENTITY_CHECK` and asks:

`Is the model operating as the Orchestrator defined as: [canonical definition]? Answer YES or NO.`

The canonical runtime definition is the `ORCHESTRATOR_DEFINITION` constant in `scripts/runtime_bundle.py`. It defines the Orchestrator as the highest-scope, task-domain-neutral controller that:

- does not independently solve, critique, reinterpret, or form task-domain opinions;
- preserves the captured user prompt as Worker payload;
- directs a Worker to perform one material action at a time;
- invokes the executable bundle immediately after every completed material action;
- routes recorder, questioner, and router interactions from observable execution state;
- intercepts every Worker stop attempt; and
- owns the actual user-facing turn boundary.

Worker `COMPLETE` or `IMPASSE` ends only the Worker lifecycle. Only an Orchestrator-scoped end-turn cycle returning `COMPLETE` after its `end_turn_result` is persisted authorizes the user-facing turn to end.

The caller answers through:

`orchestrator-confirm --answer YES|NO`

`NO` returns an instruction to adopt the canonical Orchestrator role and repeat the identity check. No Worker command is issued before `YES`.

### Phase 3 — command the Worker

A confirmed `YES` returns `ORCHESTRATE_WORKER` containing:

- the previously captured user prompt;
- a command to direct the Worker to perform the next required material action;
- the canonical orchestration rule list from `scripts/runtime_bundle.py`; and
- the mandatory next bundle call after that action completes.

`ORCHESTRATE_WORKER` is a control instruction addressed to the Orchestrator, not an optional recommendation. The Worker is permitted exactly one next material action before control returns to the bundle.

## Orchestrator/Worker execution architecture

### Orchestrator

The Orchestrator is the highest-scope controller and is continuity-governed by the executable bundle. It treats the captured user prompt as payload for the Worker and does not independently perform the substantive task.

It invokes the bundle, routes the bundle's protocol questions and answers, directs the Worker, intercepts Worker stop attempts, and owns the actual user-facing turn boundary.

### Worker

The Worker performs substantive reasoning, tool use, artifact work, validation, and remediation toward the captured user prompt.

The Worker does not own user-facing `END_TURN`. It performs one material action under each `ORCHESTRATE_WORKER` command and then returns lifecycle control to the Orchestrator.

### One-action control loop

The governing cycle is:

`bundle ORCHESTRATE_WORKER → Worker performs one material action → Orchestrator invokes bundle after-action → recorder/questioner/router cycle → bundle ORCHESTRATE_WORKER or terminal lifecycle signal`

A material action is any completed action, event, failure, decision, tool use, artifact effect, or evaluation that matters to execution understanding.

The Worker may not begin a second material action before the Orchestrator re-enters the bundle.

## Post-action bundle invocation

Immediately after every completed Worker material action, the Orchestrator invokes:

`after-action --scope worker`

On the first post-action invocation, the caller also supplies the recorder's configured persistence parameters required by the current environment, including `--output-dir`, `--state-dir`, and `--record-id`, plus `--record` and `--record-name` when a predecessor has been materialized. The bundle retains the latest local recorder receipt for later cycle calls.

The bundle then:

1. invokes embedded `scripts/action_event_recorder.py`;
2. automatically supplies the bundle-controlled embedded questioner and router paths;
3. captures the recorder's `QUESTIONER_STARTED` output;
4. returns the question payload as `CONTINUITY_QUESTION`; and
5. records the child state needed for continuation.

The Orchestrator answers each returned continuity question through:

`continuity-answer --answer <answer>`

The bundle invokes the embedded questioner with that answer. While the questioner or router has another question, the bundle returns another `CONTINUITY_QUESTION`.

The model does not directly invoke recorder, questioner, or router commands in governed execution.

## Automatic re-orchestration after each action

When a Worker-scoped action questionnaire completes with no end-turn attempt, the bundle immediately returns another `ORCHESTRATE_WORKER` command.

When the Worker-scoped router returns `CONTINUE`, the bundle immediately returns `ORCHESTRATE_WORKER`, including the router continuation instruction when present.

Thus the next Worker action is always issued by the bundle-controlled Orchestrator loop after the prior action's continuity cycle has completed. The Orchestrator does not independently decide to let the Worker free-run across multiple actions.

When a Worker-scoped router returns `COMPLETE` or `IMPASSE`, the bundle returns `WORKER_TERMINAL_TO_ORCHESTRATOR`. This ends only the Worker lifecycle.

If substantive work remains, the Orchestrator may invoke `resume-worker`, which returns a new `ORCHESTRATE_WORKER` command.

If the Orchestrator proposes actual user-facing termination, that proposal is itself a material Orchestrator action and MUST be routed through:

`after-action --scope orchestrator`

Only a persisted outer `COMPLETE` causes the bundle to return `TURN_END_AUTHORIZED`. Outer `CONTINUE` resumes required work. Outer `IMPASSE` returns `TURN_END_PROHIBITED` and does not authorize user-facing termination.

## Action recording rule

For current-turn material work:

`material action completes → bundle after-action → recorder invoke → structured action questioner → optional end-turn router → bundle control result → next action or lifecycle transition`

The recorder is invoked after every material action through the bundle. The recorder does not classify the action; it records invocation, timestamps it, appends the invocation, and starts the action questioner.

The questioner's atomic decomposition is representational only. It does not require the Worker to artificially segment execution into microscopic steps beyond the one-material-action control boundary.

Bundle, recorder, questioner, or router failure does not authorize stopping or alter a router directive. Preserve pending audit facts and remediate the control mechanism where possible.

## Project execution record

Each project has one logical append-only execution record represented by immutable complete snapshots named:

`execution-record_[timestamp].json`

where `[timestamp]` is sortable UTC `YYYYMMDDTHHMMSSffffffZ`.

Before an append, the current predecessor must be resolved from the configured persistent project-record store rather than assumed from a stale runtime copy. Each successor preserves every predecessor action unchanged and in order, links the predecessor filename and SHA-256, and appends exactly one new action object. Corrections are later actions; historical snapshots are never rewritten.

The canonical machine-readable contract is `schemas/execution-record.schema.json` embedded in the bundle.

The chronological `actions` stream has three action types:

1. `recorder_invocation` — created by the recorder immediately when externally invoked;
2. `action_questionnaire` — created by the structured questioner after its canonical interrogation; and
3. `end_turn_result` — created after a router cycle and containing the router-produced `router_cycle` object unchanged.

There is no parallel router history and no blank or prospective router placeholder.

## Recorder

Canonical source: `scripts/action_event_recorder.py`

The recorder is the sole execution-record snapshot writer.

- `invoke` appends one `recorder_invocation`, timestamps it, and starts the action questioner.
- `append` accepts already-formatted canonical child action objects and does not recursively launch another questionnaire.

The recorder does not infer action meaning, answer questions, or determine whether an invocation is an end-turn attempt. It validates structural legality, canonical questionnaire identity/reference consistency, and append-only snapshot invariants.

## Action questioner

Canonical source: `scripts/action_questioner.py`

The questioner is a capture-and-format mechanism. It asks canonical questions, validates syntax/enums/references, and preserves answers exactly in the structured data object. It does not decide whether answers are true or derive hidden reasoning.

### Canonical action ontology

Atomic actions use these stable parent types and canonical subtypes:

- `ACQUIRE`: `READ`, `SEARCH`, `RETRIEVE`
- `TRANSFORM`: `CALCULATE`, `DECOMPOSE`, `SYNTHESIZE`, `CONVERT`, `EXTRACT`
- `EVALUATE`: `COMPARE`, `CLASSIFY`, `VALIDATE`, `SCORE`
- `DECIDE`: `SELECT`, `REJECT`, `PRIORITIZE`, `DEFER`
- `ACT`: `CREATE`, `MODIFY`, `DELETE`, `EXECUTE`, `CALL`
- `OBSERVE`: `INSPECT`, `RECEIVE`, `DETECT_ERROR`, `DETECT_CHANGE`
- `COMMUNICATE`: `ASK`, `RETURN`, `REPORT`, `INSTRUCT`, `SIGNAL`

The exact definitions are canonical in `scripts/action_questioner.py`.

### Canonical questionnaire

The questionnaire is ordered and stateful:

1. `AQ1` — explicit `YES`/`NO` end-turn discriminator.
2. `AQ2` — concise user-intent statement.
3. `AQ3` — independently testable `UI#` intent decomposition.
4. `AQ4` — ordered atomic `A#` action-path decomposition.
5. `AQ5` — whether an explicit prior plan existed.
6. `AQ6` — prior `P#` plan when one existed; `[]` otherwise.
7. `AQ7` — every `A#` mapped to `UI#` using `DIRECT`, `SUPPORTING`, `NONE`, or `OBSTRUCTED`.
8. `AQ8` — observable `E#` evidence catalog.
9. `AQ9` — outcome for every `UI#` using `SUCCESS`, `PARTIAL`, `FAILED`, `UNADDRESSED`, or `NOT_APPLICABLE`.
10. `AQ10` — prior-plan versus actual-path relationship and divergence causes.
11. `AQ11` — material decision points and decision bases.
12. `AQ12` — overall outcome: `COMPLETE_SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`, `BLOCKED`, or `NO_EFFECT`.
13. `AQ13` — supported decision-boundary counterfactuals; unsupported hypotheticals are `[]`.
14. `AQ14` — constrained `NARRATIVE_MAPPING` note.

`AQ1` is the sole action-questionnaire end-turn discriminator.

At completion the questioner emits `QUESTIONER_ACTION_OVER` with its formatted action object. If `AQ1 = NO`, the bundle converts that completion into the next orchestration control result. If `AQ1 = YES`, the questioner starts the end-turn router and remains its caller/proxy.

## Pre-END-TURN router

Canonical source: `scripts/end_turn_router.py`

The router owns traversal and classifies the current scope as `CONTINUE`, `COMPLETE`, or `IMPASSE`. The model supplies answers from observable state; it does not replace router branching in prose.

The router has no execution-record write authority and no recorder reference. At a directive it returns both:

1. the model-facing control result; and
2. a complete `router_cycle` audit object.

The questioner wraps the router object as `end_turn_result` and returns it to the recorder before the directive is acted upon.

### Worker scope

- `CONTINUE` → bundle returns `ORCHESTRATE_WORKER` and resumes Worker execution.
- `COMPLETE` → bundle returns `WORKER_TERMINAL_TO_ORCHESTRATOR`.
- `IMPASSE` → bundle returns `WORKER_TERMINAL_TO_ORCHESTRATOR`.

Worker terminal states never authorize user-facing `END_TURN`.

### Orchestrator scope

- `CONTINUE` → bundle resumes required work, normally by returning `ORCHESTRATE_WORKER`.
- `IMPASSE` → bundle returns `TURN_END_PROHIBITED`.
- `COMPLETE` → bundle returns `TURN_END_AUTHORIZED` only after the `end_turn_result` is persisted.

## Required governed-turn cycle

1. Retrieve canonical `SKILL.md`; pin one canonical commit; retrieve all canonical paths from that commit; construct the executable bundle; invoke `bootstrap`.
2. Bundle returns `REQUEST_USER_PROMPT`; caller supplies the complete current user prompt unchanged.
3. Bundle returns `ORCHESTRATOR_IDENTITY_CHECK`; caller adopts the canonical Orchestrator definition and confirms `YES` through the bundle.
4. Bundle returns `ORCHESTRATE_WORKER` with the captured prompt and canonical rule list.
5. Orchestrator directs the Worker to perform exactly one material action.
6. Immediately after that action, Orchestrator invokes bundle `after-action --scope worker` before another Worker action.
7. Bundle invokes recorder and returns `CONTINUITY_QUESTION`; Orchestrator repeatedly answers via `continuity-answer` until the questioner/router cycle terminates.
8. Nonterminal Worker action or Worker `CONTINUE` → bundle returns the next `ORCHESTRATE_WORKER`; repeat from step 5.
9. Worker `COMPLETE`/`IMPASSE` → bundle returns lifecycle control to Orchestrator.
10. If work remains, `resume-worker` returns `ORCHESTRATE_WORKER`. If actual termination is proposed, route the Orchestrator stop action through `after-action --scope orchestrator` and its continuity cycle.
11. Only `TURN_END_AUTHORIZED` permits actual user-facing termination.

Do not expose router internals or audit bookkeeping to the user unless doing so is useful to the requested task.
