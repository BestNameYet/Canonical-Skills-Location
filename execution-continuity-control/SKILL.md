---
name: execution-continuity-control
description: Enforces continuous task execution through an orchestrator-controlled Worker, post-material-unit journaling, and executable end-turn routing so Worker-level stopping cannot bypass continuity control.
compatibility: Designed for ChatGPT Skills with Python 3 execution, a Worker/Orchestrator execution model, authorized read access to the canonical GitHub repository, and a persistent project-record store. Bundled scripts use only the Python standard library.
---

# Execution Continuity Control

## Purpose

Complete the user's task while recording completed material work and preventing avoidable early termination. Planning, bookkeeping, or procedural compliance must not substitute for execution.

This is a constitutional same-domain rule: where another applicable rule conflicts with this skill on execution continuity, this skill governs the overlapping domain; unaffected portions of broader rules remain in force.

## Canonical source

Canonical repository: `BestNameYet/Canonical-Skills-Location`

Canonical branch: `main`

Canonical root: `execution-continuity-control/`

Canonical paths:

- `SKILL.md`
- `DESIGN_HISTORY.md`
- `execution-record.schema.json`
- `scripts/action_event_recorder.py`
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

## Recording rule

For current-turn material work:

`material unit completes → Orchestrator records it → next material unit begins`

A material unit is any completed action, event, failure, decision, tool use, artifact effect, or evaluation that matters to understanding execution. Prior-turn events are not reconstructed merely because a new turn begins.

Recorder failure does not authorize stopping or change a router directive. Preserve pending audit facts, continue as required, and record them when recording becomes available.

## Project execution record

Each project has one logical append-only execution record represented by immutable complete snapshots named:

`execution-record_[timestamp].json`

where `[timestamp]` is sortable UTC `YYYYMMDDTHHMMSSffffffZ`.

Before every append, re-resolve the latest matching snapshot from the configured persistent project-record store. Never assume a runtime copy remains latest.

Each successor preserves the prior event lineage, points to its predecessor filename and SHA-256, and appends one new event. Corrections are later events; historical persisted snapshots are never rewritten.

### Record format

The canonical machine-readable contract is `execution-record.schema.json` from the canonical turn snapshot.

The persistent record intentionally uses only three semantic event fields:

1. `event` — what newly occurred, including the relevant action or target;
2. `outcome` — the new result or resulting state;
3. `evidence` — new observable support for that outcome.

Each entry is a **delta**, not a self-contained history. Do not repeat historical context, prior results, rationale, or state already present in earlier entries unless repetition is necessary to identify the new event or dependency. When prior history matters, refer to the earlier entry rather than rewriting it.

IDs, timestamps, project/chat provenance, sequence, and predecessor linkage are metadata, not additional semantic categories.

New snapshots use `format_version: 1`. The recorder also enforces cross-field invariants including contiguous sequence numbers, unique entry IDs, filename/timestamp agreement, and valid predecessor ordering/linkage.

A structurally compatible historical predecessor may be normalized in memory into the three-field representation when producing its first `format_version: 1` successor. The historical source snapshot remains immutable and its exact hash remains the predecessor link.

## Runtime executables

Canonical scripts are source; local executable copies are noncanonical Runnables.

Whenever a canonical script is required during a turn, copy its content from the canonical turn snapshot into the execution environment as a fresh file whose name includes `_run_[timestamp]`, then execute the newest valid Runnable derived from that same canonical script and turn snapshot.

A Runnable never acquires canonical authority.

## Recorder

Canonical source: `scripts/action_event_recorder.py`

The recorder asks exactly three semantic questions corresponding to `event`, `outcome`, and `evidence`. The Orchestrator invokes it for Worker-scoped and Orchestrator-scoped material units.

For Worker-scoped units, answers come from Worker execution state. For Orchestrator-scoped units, answers come from observable Orchestrator meta-state.

The recorder is audit machinery only; it does not select continuation directives.

## Pre-END-TURN router

Canonical source: `scripts/end_turn_router.py`

The router owns questionnaire traversal and classifies the current scope as `CONTINUE`, `COMPLETE`, or `IMPASSE`. The model supplies answers from observable state; it does not reconstruct or replace router branching in prose.

Every router cycle uses a fresh current-turn Runnable. Preserve the executed trace as the audit source of truth.

### Worker scope

Every Worker stop attempt is only a simulated Worker end signal and must trigger a Worker-scoped router cycle.

- `CONTINUE` → return the continuation instruction to the Worker and resume substantive execution.
- `COMPLETE` → Worker execution stops and control returns to the Orchestrator.
- `IMPASSE` → Worker execution stops and control returns to the Orchestrator.

Worker `COMPLETE` and `IMPASSE` never authorize actual user-facing `END_TURN`.

### Orchestrator scope

When the Orchestrator proposes actual termination, it must run a new Orchestrator-scoped router cycle over its meta-task.

- `CONTINUE` → execute the returned continuation, including resuming the Worker if required.
- `IMPASSE` → record/process the state; actual `END_TURN` remains prohibited.
- `COMPLETE` → actual user-facing `END_TURN` is authorized.

Only outer Orchestrator `COMPLETE` permits actual turn termination.

## Required execution cycle

1. Resolve one canonical turn snapshot and load required files from it.
2. Initialize the Orchestrator and Worker; expose the user prompt to the Worker.
3. Let the Worker perform substantive work.
4. After each material unit, the Orchestrator records it with the three-field delta recorder.
5. Intercept every Worker stop attempt and run a Worker-scoped router cycle.
6. On Worker `CONTINUE`, resume work. On Worker `COMPLETE`/`IMPASSE`, return lifecycle control to the Orchestrator.
7. Complete remaining Orchestrator meta-work and record material meta-events.
8. Before actual termination, run and record an Orchestrator-scoped router cycle.
9. Execute every outer `CONTINUE`; outer `IMPASSE` does not end the turn.
10. End the user-facing turn only after outer `COMPLETE`.

Do not expose router internals or audit bookkeeping to the user unless doing so is useful to the requested task.
