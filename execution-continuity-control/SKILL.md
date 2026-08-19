---
name: execution-continuity-control
description: Enforces continuous task execution through an orchestrator-controlled Worker, immutable action recording, a structured decision-engineering action questionnaire, and executable end-turn routing.
compatibility: Designed for ChatGPT Skills with Python 3 execution, a Worker/Orchestrator execution model, authorized read access to the canonical GitHub repository, and a persistent project-record store. Bundled scripts use only the Python standard library.
---

# Execution Continuity Control

## Purpose

Complete the user's task while preserving an immutable execution history and preventing avoidable early termination. Planning, bookkeeping, or procedural compliance must not substitute for execution.

This is a constitutional same-domain rule: where another applicable rule conflicts with this skill on execution continuity, this skill governs the overlapping domain; unaffected portions of broader rules remain in force.

## Canonical source

Canonical repository: `BestNameYet/Canonical-Skills-Location`

Canonical branch: `main`

Canonical root: `execution-continuity-control/`

Canonical paths:

- `SKILL.md`
- `DESIGN_HISTORY.md`
- `schemas/execution-record.schema.json`
- `scripts/action_event_recorder.py`
- `scripts/action_questioner.py`
- `scripts/end_turn_router.py`

At the start of each governed user turn, resolve `main` HEAD once to an exact commit SHA and use that SHA as the canonical turn snapshot. Read every required canonical file from that same SHA. Do not mix commits during the turn or substitute stale runtime, exported, forked, alternate-branch, or similarly named copies.

Git commit identity provides immutable version identity. Stable repository paths provide canonical file identity. Do not create timestamped or duplicate canonical source filenames.

### Canonical revision

Before changing canon:

1. resolve current `main` HEAD;
2. read `SKILL.md`, `DESIGN_HISTORY.md`, and every affected canonical resource from that SHA;
3. inspect earlier Git/history evidence needed to understand affected mechanisms;
4. identify every protected invariant touched by the change;
5. preserve each invariant or explicitly document why its replacement still solves the underlying problem;
6. update `DESIGN_HISTORY.md` cumulatively;
7. write complete replacement content at stable canonical paths;
8. commit and verify the coherent revision before moving `main` to it.

A staging branch has no canonical authority until its revision is reachable from `main`.

## Execution architecture

### Orchestrator

The Orchestrator is the highest-scope controller and is itself continuity-governed. It receives its role from its preprompt and treats the user's prompt as payload for a Worker.

It does not independently solve, critique, reinterpret, or form task-domain opinions. It initializes and runs the Worker, passes the user prompt to it, owns continuity-script invocation, routes script questions and answers at the correct scope, intercepts every Worker stop attempt, and owns the actual user-facing turn boundary.

### Worker

The Worker receives the user's prompt as its operative task and performs substantive reasoning, tool use, artifact work, validation, and remediation. The Worker never owns actual user-facing `END_TURN`.

When continuity requires a script, the Worker yields invocation to the Orchestrator. For Worker-scoped script questions, the Orchestrator obtains the answer from Worker execution state rather than inventing a task-domain answer.

## Action recording rule

For current-turn material work:

`material action completes → recorder invoke → structured action questioner → optional end-turn router → next material action`

A material action is any completed action, event, failure, decision, tool use, artifact effect, or evaluation that matters to understanding execution. Prior-turn events are not reconstructed merely because a new turn begins.

The recorder is invoked after every material action. The recorder does not receive or infer the reason for invocation. It records only that it was invoked, timestamps that invocation, appends that invocation to the project record, and starts the action questioner.

The questioner's atomic decomposition is representational only. It does not require the Worker to artificially segment execution into tiny steps and does not reintroduce a history-first or bookkeeping gate.

Recorder, questioner, or router failure does not authorize stopping or change a router directive. Preserve pending audit facts, continue as required where safe, and complete recording when the mechanism becomes available.

## Project execution record

Each project has one logical append-only execution record represented by immutable complete snapshots named:

`execution-record_[timestamp].json`

where `[timestamp]` is sortable UTC `YYYYMMDDTHHMMSSffffffZ`.

Before every append, re-resolve the latest matching snapshot from the configured persistent project-record store. Never assume a runtime copy remains latest.

Each successor copies every predecessor action unchanged and in order, links to the predecessor filename and SHA-256, and appends exactly one new action object. Corrections are later actions; historical persisted snapshots are never rewritten.

The canonical machine-readable contract is `schemas/execution-record.schema.json` from the canonical turn snapshot.

The record is one chronological `actions` stream with three action types:

1. `recorder_invocation` — created by the recorder immediately when externally invoked; contains only mechanically necessary invocation metadata plus the recorder-generated timestamp.
2. `action_questionnaire` — created from the questioner's completed structured interrogation; contains the exact ordered canonical question/answer pairs, including native JSON arrays/objects for structured answers and the final narrative mapping note.
3. `end_turn_result` — returned by the action questioner after an invoked end-turn router reaches a directive; contains the complete router-produced `router_cycle` data object nested unchanged inside the questioner wrapper.

There is no parallel router-history collection and no blank or prospective router placeholder. An `end_turn_result` exists only after a router cycle actually occurs.

## Runtime executables

Canonical scripts are source; local executable copies are noncanonical Runnables.

Whenever a canonical script is required during a turn, copy its content from the canonical turn snapshot into the execution environment as a fresh file whose name includes `_run_[timestamp]`, then execute the newest valid Runnable derived from that same canonical script and turn snapshot. A Runnable never acquires canonical authority.

## Recorder

Canonical source: `scripts/action_event_recorder.py`

The recorder is the sole writer of execution-record snapshots. It has two entry paths:

- `invoke` — used by the Orchestrator after a material action. The recorder appends one `recorder_invocation`, timestamps it, and immediately starts the action questioner.
- `append` — used only for formatted action objects returned by canonical child scripts. It validates and appends the supplied object and does not start another questionnaire.

The recorder does not classify the action, answer questionnaire questions, infer intent, or determine whether an invocation is an end-turn attempt. It validates structural legality, canonical Q/A identity, reference consistency required by the record contract, and append-only snapshot invariants.

## Action questioner

Canonical source: `scripts/action_questioner.py`

The action questioner is a capture-and-format mechanism. It asks the canonical questions, validates answer syntax, enum legality, ordered identifiers, and internal references, and preserves the answers exactly in the structured data object. It does not judge whether an answer is true, infer a better answer, score the model, or derive a hidden rationale.

Questions using enumerated values must co-present their canonical definition table in the question payload. The model selects only values defined by those tables except where a question explicitly permits a short explanatory field. The table definitions are guidance for classification and are not redundantly persisted in every record entry.

### Canonical action ontology

Atomic action decomposition uses seven stable parent types with canonical subtypes:

- `ACQUIRE`: `READ`, `SEARCH`, `RETRIEVE`
- `TRANSFORM`: `CALCULATE`, `DECOMPOSE`, `SYNTHESIZE`, `CONVERT`, `EXTRACT`
- `EVALUATE`: `COMPARE`, `CLASSIFY`, `VALIDATE`, `SCORE`
- `DECIDE`: `SELECT`, `REJECT`, `PRIORITIZE`, `DEFER`
- `ACT`: `CREATE`, `MODIFY`, `DELETE`, `EXECUTE`, `CALL`
- `OBSERVE`: `INSPECT`, `RECEIVE`, `DETECT_ERROR`, `DETECT_CHANGE`
- `COMMUNICATE`: `ASK`, `RETURN`, `REPORT`, `INSTRUCT`, `SIGNAL`

The exact definitions presented to the model are canonical in `scripts/action_questioner.py`.

### Canonical questionnaire

The questionnaire is ordered and stateful:

1. `AQ1` — explicit `YES`/`NO` end-turn discriminator.
2. `AQ2` — concise user-intent statement describing the requested end state.
3. `AQ3` — numbered independently testable intent decomposition using `UI1`, `UI2`, ... .
4. `AQ4` — ordered atomic action-path decomposition using `A1`, `A2`, ... and the canonical action ontology.
5. `AQ5` — whether an explicit prior plan existed before the recorded activity began.
6. `AQ6` — prior plan using `P1`, `P2`, ... when one existed; `[]` otherwise. The actual path remains the `A#` sequence.
7. `AQ7` — mapping from every `A#` to `UI#` items using `DIRECT`, `SUPPORTING`, `NONE`, or `OBSTRUCTED`.
8. `AQ8` — observable evidence catalog using `E1`, `E2`, ... and canonical evidence types.
9. `AQ9` — independent outcome for every `UI#` using `SUCCESS`, `PARTIAL`, `FAILED`, `UNADDRESSED`, or `NOT_APPLICABLE`, with mapped actions, evidence, and remaining gap where applicable.
10. `AQ10` — prior-plan versus actual-path relationship and enumerated divergence causes.
11. `AQ11` — material decision points and their enumerated decision bases.
12. `AQ12` — overall activity outcome: `COMPLETE_SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`, `BLOCKED`, or `NO_EFFECT`.
13. `AQ13` — decision-boundary counterfactuals only when supported by the observed state; unsupported hypotheticals are represented by `[]`.
14. `AQ14` — required constrained free-form `NARRATIVE_MAPPING` note.

### Narrative mapping note

`AQ14` supplies the human-readable mapping from the normalized decision graph back to a coherent description. It must use these headings in order:

```text
NARRATIVE_MAPPING

INTENT:
...

ACTION_PATH:
...

PLAN_RELATION:
...

OUTCOME_MAPPING:
...

DECISION_CONTEXT:
...
```

The note must reference existing `UI#` and `A#` identifiers, every `P#` identifier when a prior plan exists, and `E#` identifiers where applicable. It may not introduce new identifiers, actions, requirements, plans, or outcomes. When no prior plan existed, `PLAN_RELATION` must state `NO_PRIOR_PLAN`.

This note is a constrained post-action self-report, not raw hidden chain-of-thought and not independent evidence. Its value comes from being cross-referenceable against the structured answers and observable execution record.

### Questioner completion signal

After the last canonical question is validated, the questioner constructs one schema-conforming `action_questionnaire` object and emits:

`QUESTIONER_ACTION_OVER`

with the formatted data object. This signal means only that the questionnaire action has completed. It does not mean the user's task, Worker lifecycle, router cycle, or user-facing turn is complete.

The questionnaire object is appended through the recorder. For a non-end-turn action (`AQ1 = NO`), the questioner then completes. For an end-turn action (`AQ1 = YES`), after the questionnaire object is appended the questioner invokes `scripts/end_turn_router.py` and remains the router's caller/proxy for that cycle.

## Pre-END-TURN router

Canonical source: `scripts/end_turn_router.py`

The router owns questionnaire traversal and classifies the current scope as `CONTINUE`, `COMPLETE`, or `IMPASSE`. The model supplies answers from observable state; it does not reconstruct or replace router branching in prose.

The router has no execution-record write authority and no recorder reference. It is invoked only after the action questionnaire explicitly classified the activity as an end-turn attempt. When a cycle reaches a directive, the router produces two mandatory products from the same completed cycle:

1. a control result — `CONTINUE`, `COMPLETE`, or `IMPASSE` — supplied back toward the model; and
2. a formatted `router_cycle` audit data object containing cycle ID, scope, every reached router question and answer in order, the directive, and directive-specific instruction or impasse evidence where required.

The router returns both products to the action questioner. The questioner wraps the router data object as `end_turn_result` and sends that wrapper to the recorder before the directive is acted upon. The questioner relays the router's control result to the model-facing caller. Neither product substitutes for the other.

### Worker scope

Every Worker stop attempt is only a simulated Worker end signal. Its recorder invocation must lead `AQ1` to `YES` and therefore to a Worker-scoped router cycle.

- `CONTINUE` → return the continuation instruction to the Worker and resume substantive execution.
- `COMPLETE` → Worker execution stops and control returns to the Orchestrator.
- `IMPASSE` → Worker execution stops and control returns to the Orchestrator.

Worker `COMPLETE` and `IMPASSE` never authorize actual user-facing `END_TURN`.

### Orchestrator scope

When the Orchestrator proposes actual termination, that proposed end is recorded through the same recorder → questioner → router path at Orchestrator scope.

- `CONTINUE` → execute the returned continuation, including resuming the Worker if required.
- `IMPASSE` → record/process the state; actual `END_TURN` remains prohibited.
- `COMPLETE` → actual user-facing `END_TURN` is authorized.

Only outer Orchestrator `COMPLETE`, after its `end_turn_result` wrapper has been appended, permits actual turn termination.

## Required execution cycle

1. Resolve one canonical turn snapshot and load required files from it.
2. Initialize the Orchestrator and Worker; expose the user prompt to the Worker.
3. Let the Worker perform one substantive material action.
4. Orchestrator invokes the recorder.
5. Recorder appends `recorder_invocation`, timestamps it, and starts the action questioner.
6. Orchestrator supplies each structured questionnaire answer from the correct scope; every enumerated question is presented with its canonical definition table.
7. After `AQ14`, questioner emits `QUESTIONER_ACTION_OVER` plus its formatted `action_questionnaire`; recorder appends the object.
8. If `AQ1` is `NO`, continue to the next material action.
9. If `AQ1` is `YES`, the questioner invokes the end-turn router and remains the caller for the cycle.
10. Orchestrator supplies router answers through the action questioner; the questioner forwards them to the router.
11. At a directive, the router returns both its control result and formatted `router_cycle` object to the questioner.
12. Questioner wraps the router object as `end_turn_result` and returns it to the recorder; recorder appends it.
13. The questioner relays the router control result to the model. Worker `CONTINUE` resumes Worker execution; Worker terminal states return lifecycle control to Orchestrator; outer `CONTINUE` resumes required work; only outer `COMPLETE` permits user-facing turn termination.

Do not expose router internals or audit bookkeeping to the user unless doing so is useful to the requested task.
