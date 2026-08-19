---
name: execution-continuity-control
description: Enforces continuous task execution through an orchestrator-controlled Worker, immutable action recording, an executable eight-question action classifier, and executable end-turn routing.
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

It does not independently solve, critique, reinterpret, or form task-domain opinions. It:

- initializes and runs the Worker;
- passes the user prompt to the Worker;
- owns continuity-script invocation;
- routes script questions and answers at the correct scope;
- intercepts every Worker stop attempt; and
- owns the actual user-facing turn boundary.

### Worker

The Worker receives the user's prompt as its operative task and performs the substantive reasoning, tool use, artifact work, validation, and remediation.

The Worker never owns actual user-facing `END_TURN`.

When continuity requires a script, the Worker yields invocation to the Orchestrator. For Worker-scoped script questions, the Orchestrator obtains the answer from Worker execution state rather than inventing a task-domain answer.

## Action recording rule

For current-turn material work:

`action completes → recorder invoke → eight-question action questionnaire completes → next action may begin`

A material action is any completed action, event, failure, decision, tool use, artifact effect, or evaluation that matters to understanding execution. Prior-turn events are not reconstructed merely because a new turn begins.

The recorder is invoked after every such action. The recorder does not receive or infer the reason for invocation. It records only that it was invoked, timestamps that invocation, and starts the action questioner.

Recorder or questionnaire failure does not authorize stopping or change a router directive. Preserve pending audit facts, continue as required where safe, and complete recording when the mechanism becomes available.

## Project execution record

Each project has one logical append-only execution record represented by immutable complete snapshots named:

`execution-record_[timestamp].json`

where `[timestamp]` is sortable UTC `YYYYMMDDTHHMMSSffffffZ`.

Before every append, re-resolve the latest matching snapshot from the configured persistent project-record store. Never assume a runtime copy remains latest.

Each successor copies every predecessor action unchanged and in order, links to the predecessor filename and SHA-256, and appends exactly one new action object. Corrections are later actions; historical persisted snapshots are never rewritten.

The canonical machine-readable contract is `schemas/execution-record.schema.json` from the canonical turn snapshot.

The record is one chronological `actions` stream. It has three action types:

1. `recorder_invocation` — created by the recorder immediately when externally invoked; contains only the mechanically necessary invocation metadata and timestamp.
2. `action_questionnaire` — emitted by the action questioner after all eight canonical questions are answered; contains the exact ordered question/answer pairs.
3. `router_cycle` — emitted by the end-turn router when a router cycle reaches a directive; contains the exact ordered router question/answer pairs and the resulting directive.

There is no parallel router-history collection and no blank router placeholder. A router-cycle action exists only after a router cycle actually occurs.

## Runtime executables

Canonical scripts are source; local executable copies are noncanonical Runnables.

Whenever a canonical script is required during a turn, copy its content from the canonical turn snapshot into the execution environment as a fresh file whose name includes `_run_[timestamp]`, then execute the newest valid Runnable derived from that same canonical script and turn snapshot.

A Runnable never acquires canonical authority.

## Recorder

Canonical source: `scripts/action_event_recorder.py`

The recorder is the sole writer of execution-record snapshots. It has two distinct entry paths:

- `invoke` — used by the Orchestrator after a material action. The recorder appends one `recorder_invocation` action, timestamps it, and immediately invokes the action questioner.
- `append` — used only for formatted action objects returned by canonical child scripts. It appends the supplied object and does not start another questionnaire.

The recorder does not classify the action and does not ask the eight questions. It never attempts to determine whether an invocation represents end-of-turn behavior.

## Action questioner

Canonical source: `scripts/action_questioner.py`

The action questioner asks exactly eight questions and preserves each exact question/answer pair in order.

The second question is the routing discriminator:

`AQ2: Is this action an end-of-turn attempt? Answer YES or NO.`

Accepted answers are `YES`, `NO`, `Y`, or `N`; the stored canonical values are `YES` or `NO`. End-turn routing must depend only on this explicit binary answer, never on interpreting free-form prose from another question.

After AQ8, the questioner constructs one schema-conforming `action_questionnaire` object and sends it to the recorder. The recorder appends it to a new immutable snapshot.

- AQ2 `NO` → the questionnaire completes without invoking the end-turn router.
- AQ2 `YES` → after the questionnaire object has been appended, the questioner invokes `scripts/end_turn_router.py` using that new snapshot as the router cycle's predecessor.

## Pre-END-TURN router

Canonical source: `scripts/end_turn_router.py`

The router owns questionnaire traversal and classifies the current scope as `CONTINUE`, `COMPLETE`, or `IMPASSE`. The model supplies answers from observable state; it does not reconstruct or replace router branching in prose.

When a cycle reaches any directive, the router constructs one schema-conforming `router_cycle` object containing every router question actually reached and its answer, in executed order, plus the directive and any directive-specific data. The router sends that object to the recorder, and the recorder appends it before the directive is acted upon.

The stored router action is the audit source of truth for that cycle.

### Worker scope

Every Worker stop attempt is only a simulated Worker end signal. Its recorder invocation must lead AQ2 to `YES` and therefore to a Worker-scoped router cycle.

- `CONTINUE` → return the continuation instruction to the Worker and resume substantive execution.
- `COMPLETE` → Worker execution stops and control returns to the Orchestrator.
- `IMPASSE` → Worker execution stops and control returns to the Orchestrator.

Worker `COMPLETE` and `IMPASSE` never authorize actual user-facing `END_TURN`.

### Orchestrator scope

When the Orchestrator proposes actual termination, that proposed end is recorded through the same recorder → questioner → router path at Orchestrator scope.

- `CONTINUE` → execute the returned continuation, including resuming the Worker if required.
- `IMPASSE` → record/process the state; actual `END_TURN` remains prohibited.
- `COMPLETE` → actual user-facing `END_TURN` is authorized.

Only outer Orchestrator `COMPLETE`, after its router-cycle object has been appended, permits actual turn termination.

## Required execution cycle

1. Resolve one canonical turn snapshot and load required files from it.
2. Initialize the Orchestrator and Worker; expose the user prompt to the Worker.
3. Let the Worker perform one substantive material action.
4. Orchestrator invokes the recorder.
5. Recorder appends `recorder_invocation`, timestamps it, and starts the action questioner.
6. Orchestrator supplies the eight questionnaire answers from the correct execution scope.
7. Questioner sends its formatted `action_questionnaire` object to the recorder; recorder appends it.
8. If AQ2 is `NO`, continue to the next action.
9. If AQ2 is `YES`, the questioner invokes the end-turn router.
10. Orchestrator supplies router answers from the correct execution scope.
11. When the router reaches a directive, it sends its formatted `router_cycle` object to the recorder; recorder appends it.
12. Act on the recorded directive: Worker `CONTINUE` resumes Worker execution; Worker terminal states return lifecycle control to Orchestrator; outer `CONTINUE` resumes required work; only outer `COMPLETE` permits user-facing turn termination.

Do not expose router internals or audit bookkeeping to the user unless doing so is useful to the requested task.
