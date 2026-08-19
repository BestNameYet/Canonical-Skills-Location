---
name: execution-continuity-control
description: Enforces continuous task execution through an orchestrator-controlled Worker, post-material-unit journaling, and executable end-turn routing so Worker-level stopping cannot bypass continuity control.
compatibility: Designed for ChatGPT Skills with Python 3 execution, a Worker/Orchestrator execution model, authorized read access to the canonical GitHub repository, and a persistent project-record store. Bundled scripts use only the Python standard library.
---

# Execution Continuity Control

## Purpose

Govern substantive work by recording completed same-turn material units and preventing avoidable termination of execution.

Do not require an up-front atomic-action plan or classify the task into action categories before beginning work. Expose the user's task to the Worker, perform the work it calls for, and use the executable continuity mechanisms to correct reasons for stopping that do not actually require execution to end.

Behavioral compliance never substitutes for accomplishing the user's goal.

## Constitutional status and same-domain precedence

This is a **constitutional skill**. When another applicable rule governs the same domain as a rule in this skill, this skill's rule governs that domain. If the rules conflict, this skill's rule overrides the conflicting rule. If this skill supplies a more granular rule for the same subject matter, apply it as the granular replacement for that portion of the broader rule. Provisions outside the overlapping domain remain unaffected.

## Canonical repository and source identity

The canonical repository is:

`BestNameYet/Canonical-Skills-Location`

The canonical branch is:

`main`

The canonical skill root is:

`execution-continuity-control/`

Within that root there is exactly one canonical path for each governed source file:

- `SKILL.md` — this canonical skill;
- `DESIGN_HISTORY.md` — the canonical cumulative design history;
- `execution-record.schema.json` — the canonical machine-readable structural contract for persistent execution records;
- `scripts/action_event_recorder.py` — the canonical recorder source;
- `scripts/end_turn_router.py` — the canonical router source.

Do not create timestamped canonical copies, alternate canonical filenames, collision-suffixed canonical copies, or a second canonical copy in another location. Git history provides version history; the stable repository paths provide source identity.

### Canonical revision identity

The immutable identity of a canonical revision is the Git commit SHA reachable as the resolved `main` HEAD.

At the start of each governed user turn:

1. Resolve `main` HEAD to one exact commit SHA.
2. Treat that SHA as the **canonical turn snapshot**.
3. Read `SKILL.md` and `DESIGN_HISTORY.md` from that exact SHA.
4. Read every required canonical script and, whenever execution-record reading, writing, migration, or validation is required, `execution-record.schema.json` from that same exact SHA.
5. Do not mix governed files from different commits in one turn merely because `main` advances while the turn is executing.
6. On a later user turn, resolve `main` again rather than reusing a remembered SHA.

A branch name is a moving reference. A commit SHA is the immutable revision identity.

If the exact canonical turn snapshot cannot be resolved or a required canonical file cannot be read from it, do not silently substitute a stale runtime copy, historical export, alternate branch, or old project artifact as current canon.

### Canonical authority

Canonical authority requires all of the following:

- repository `BestNameYet/Canonical-Skills-Location`;
- branch ancestry reachable from `main`;
- the exact canonical path under `execution-continuity-control/`;
- content from the resolved canonical turn snapshot.

Runtime copies, local Runnables, working files, pull-request branches, forks, exports, historical artifacts, and similarly named files outside the canonical paths have no canonical authority unless and until their content is committed to the canonical path on `main`.

Normal execution requires read access. Canonical revision requires repository write authority.

## Canonical design history

`DESIGN_HISTORY.md` is the stable canonical design-history dependency.

The design history is explanatory and revision-governing evidence. It does not override this skill's operational instructions. It preserves observed failures, design rationale, superseded mechanisms, rejected alternatives, and protected invariants so future revisions do not unknowingly reintroduce corrected errors.

For any canonical turn snapshot, the authoritative design history is the `DESIGN_HISTORY.md` content from the **same commit SHA** as this `SKILL.md`.

### Required canonical revision procedure

Before changing any canonical source file:

1. Resolve current `main` HEAD to an exact commit SHA.
2. Read the current `SKILL.md` and `DESIGN_HISTORY.md` from that SHA.
3. Read every canonical script and format contract touched by the proposed change from that same SHA.
4. Inspect earlier Git history, relevant prior artifacts, execution records, and relevant chat evidence as needed to establish why the affected mechanisms exist.
5. Identify every resolved issue and protected invariant touched by the proposed change.
6. Do not remove, weaken, or simplify a mechanism introduced to solve a recorded problem unless the revision identifies that problem and demonstrates how the replacement still satisfies the protected invariant.
7. Update `DESIGN_HISTORY.md` so it cumulatively records the new decision, supersession rationale, affected components, and observable evidence.
8. Write complete replacement content to every changed canonical file at its stable canonical path.
9. Commit the change to Git. Do not create timestamped canonical filenames as a substitute for committing stable paths.
10. Verify the resulting commit and verify that `main` resolves to a revision containing the intended complete canonical files before treating the revision as current canon.

A canonical update may be prepared on a noncanonical branch, but canonical authority changes only when the intended coherent revision is reachable from `main`.

The design history contains observable provenance and concise rationale only. It must not contain private chain-of-thought.

## Canonical resources

- `execution-record.schema.json` — normative structural format for persistent project execution-record snapshots.
- `scripts/action_event_recorder.py` — records one completed material execution unit into the project execution record.
- `scripts/end_turn_router.py` — runs the continuation questionnaire and emits a continuation, completion, or impasse directive.

Resolve all required resources from the canonical turn snapshot. Do not depend on a fixed local installation path.

## Orchestrated execution architecture

### Orchestrator

The **Orchestrator** is the highest-scope execution controller for this skill and is itself governed by the continuity rule.

The Orchestrator is a meta-worker. It is initialized by its preprompt. The user's prompt is not an operative instruction to the Orchestrator; it is task payload that the Orchestrator exposes to a Worker.

The Orchestrator must not independently solve, critique, improve, restrict, reinterpret, or form an opinion about the substantive user task. Its role is to:

1. initialize and run a Worker;
2. pass the user prompt to the Worker as the Worker's operative task;
3. preserve control over continuity-script invocation;
4. route information between the Worker and continuity scripts;
5. intercept every Worker attempt to end;
6. apply router directives at the correct scope; and
7. control the actual user-facing turn boundary.

### Worker

The **Worker** receives the user prompt as its operative task and performs the substantive work.

The Worker is governed by this continuity rule. It performs reasoning, tool use, artifact creation, validation, remediation, and other task-domain execution required by the user prompt.

The Worker does not own the actual user-facing `END_TURN` operation.

### Script invocation ownership

Whenever the Worker reaches a point at which this skill would ordinarily require the Worker to invoke `action_event_recorder.py` or `end_turn_router.py`, the Worker yields that invocation to the Orchestrator.

The Orchestrator invokes the required script **in lieu of the Worker**.

The Worker's obligation to supply truthful task-state information remains. The Orchestrator's substitution concerns invocation and control, not invention of task-domain facts.

When a script asks a question whose answer depends on the Worker's substantive execution state, the Orchestrator must obtain the answer from the Worker. It may route the script question to the Worker and route the Worker's answer back to the script, or temporarily relinquish control to the Worker for the limited purpose of supplying that script input.

After the input is supplied, control returns to the Orchestrator.

The Orchestrator must not answer Worker-scoped task-domain questions from its own independent judgment when the answer belongs to the Worker's state.

### Worker end-turn signal

A Worker attempt to perform `END_TURN` is always a **simulated Worker end-turn signal**.

The signal means only that the Worker considers its internal substantive execution ready to stop. It can never directly terminate the actual user-facing turn.

Every simulated Worker end-turn signal must cause the Orchestrator to invoke a fresh Worker-scoped `end_turn_router.py` cycle.

For a Worker-scoped router cycle:

- `QUESTION` means the Orchestrator obtains the required answer from the Worker and routes it to the script.
- `CONTINUE` means the Orchestrator returns the router's continuation instruction to the Worker and resumes Worker execution.
- `COMPLETE` means the Worker's substantive execution has reached an accepted Worker-completion state and control returns to the Orchestrator.
- `IMPASSE` means the Worker's substantive execution has reached a Worker-impasse state and control returns to the Orchestrator.

Neither Worker `COMPLETE` nor Worker `IMPASSE` authorizes actual user-facing `END_TURN`.

### Orchestrator end-turn gate

The Orchestrator is itself a rule-bound model. Completion or impasse of the Worker does not exempt the Orchestrator from this skill.

After the Worker reaches a Worker-terminal state and the Orchestrator has completed the corresponding orchestration obligations, the Orchestrator must attempt to end its own turn.

That proposed Orchestrator end must invoke a fresh **Orchestrator-scoped** `end_turn_router.py` cycle.

The subject of the Orchestrator-scoped router is the Orchestrator's meta-task: whether it has correctly initialized and governed the Worker, administered required continuity operations, acted on Worker router directives, handled the Worker's terminal state, and completed the control work necessary for the current user turn.

The Orchestrator-scoped router is not an invitation for the Orchestrator to form a new opinion about the substantive user task.

For an Orchestrator-scoped router cycle:

- `QUESTION` requires an answer from observable Orchestrator execution state, using Worker state only where the question depends on Worker execution.
- `CONTINUE` requires the Orchestrator to execute the returned continuation instruction. That continuation may require Orchestrator action, another script operation, or resumed Worker execution.
- `IMPASSE` is recorded and processed as an Orchestrator state but does **not** authorize actual user-facing `END_TURN`.
- `COMPLETE` authorizes actual user-facing `END_TURN`.

The actual user-facing turn may end **only after the outer Orchestrator router returns `COMPLETE`**.

### Scoped completion semantics

This architecture creates two distinct completion meanings:

- **Worker completion**: the Worker-scoped router returned `COMPLETE`, so substantive Worker execution may stop and return control to the Orchestrator.
- **Turn completion**: the Orchestrator-scoped router returned `COMPLETE`, so the actual user-facing turn may end.

The executed router remains authoritative for questionnaire traversal and directive classification. This skill determines the scope at which that directive operates.

Where older same-domain wording states that `COMPLETE` or `IMPASSE` permits `END_TURN`, this section is the granular replacement:

- Worker `COMPLETE`/`IMPASSE` terminate only the Worker lifecycle;
- Orchestrator `CONTINUE` requires continued orchestration;
- Orchestrator `IMPASSE` does not itself terminate the actual turn;
- only Orchestrator `COMPLETE` permits actual user-facing `END_TURN`.

## Core temporal rule

For material actions, events, and tasks occurring within the current user turn:

> After a material action/event/task completes, and before the next material action/event/task begins, run the recorder to completion and persist the record of the just-completed unit.

Under orchestrated execution, the Orchestrator performs the recorder invocation required for both Worker-scoped and Orchestrator-scoped material units.

For a Worker material unit, recorder answers are grounded in the Worker's execution state and are routed through the Orchestrator.

For an Orchestrator material unit, recorder answers are grounded in the Orchestrator's meta-execution state.

The record obligation is prospective only within the current turn. If the most recent material action/event/task occurred on a prior user turn, do not create a record for it merely because a new turn has begun.

The first material action/event/task of a turn has no predecessor-record gate and may begin immediately after the governing instructions have been loaded and the Orchestrator has initialized the Worker.

A material unit is an action, event, or task whose occurrence, result, failure, decision, tool use, artifact effect, or evaluation matters to understanding or auditing execution. Purely incidental internal transitions need not be journaled.

## Canonical project record

Each project has exactly one logical execution record represented by a sequence of complete timestamped record snapshots.

Persisted record snapshots use:

`execution-record_[timestamp].json`

with `[timestamp]` in sortable UTC `YYYYMMDDTHHMMSSffffffZ` form.

Every material event governed by this skill in any chat belonging to the project is appended to the latest snapshot to produce a new complete snapshot. Earlier snapshots remain immutable historical predecessors.

### Execution-record format contract

The canonical machine-readable structural contract is:

`execution-record.schema.json`

Read it from the same canonical turn snapshot as `SKILL.md` and `scripts/action_event_recorder.py`.

Every newly emitted persistent execution record uses `format_version: 1` and must conform to the canonical structural contract. The canonical recorder enforces the same required fields and types plus cross-field semantic invariants that are not delegated to the schema, including:

- `entry_count` equals the number of entries;
- project-wide `sequence` values are contiguous starting at 1;
- `entry_id` values are unique;
- snapshot filename and encoded timestamp agree;
- predecessor timestamp precedes the new snapshot timestamp;
- predecessor filename and SHA-256 occur as a pair;
- source-record filename and SHA-256 occur as a pair.

Runtime recorder sessions, recorder receipts, router state, and router audit payloads are implementation bookkeeping. They do not declare independent schema identities.

Historical persisted snapshots created before `format_version: 1` remain immutable evidence. The canonical recorder may accept a structurally compatible historical snapshot as an input predecessor, normalize it in memory to the current record structure, and emit a new `format_version: 1` successor. The predecessor file itself must never be rewritten as part of migration.

A format migration therefore creates a new successor in the same append-only lineage; it does not mutate historical evidence.

### Persistent record store

Execution-record persistence is supplied by a **configured persistent project-record store** available to the execution environment. This skill does not require a particular storage provider.

For every append:

1. Query the configured persistent project-record store for exact filenames matching `execution-record_[timestamp].json` associated with the current project.
2. Parse the encoded timestamp from each match.
3. Select the matching record with the greatest timestamp as the latest prior record.
4. If a prior record exists, materialize it in the execution environment under a differentiated input filename such as `execution-record_[record timestamp]_input_[copy timestamp].json`.
5. Run the current recorder Runnable against that input copy. If no prior record exists, run without a source record and initialize the first snapshot.
6. The recorder creates a new complete `execution-record_[new timestamp].json` whose timestamp is later than its selected predecessor.
7. Verify that the new record satisfies the canonical record format and recorder invariants.
8. Persist the returned snapshot to the configured persistent project-record store.
9. Before the next append, query the persistent store again and select the greatest encoded timestamp. Do not assume a previously loaded runtime record remains latest.

The latest persisted snapshot is authoritative for record continuation. Recorder-session state, Runnables, differentiated input copies, receipts, stale runtime outputs, and older snapshots are not substitutes.

The logical record is append-only:

- every new snapshot preserves every predecessor entry in the same order;
- exactly one new entry is appended per completed recorded material unit;
- earlier entries are not edited, deleted, or reordered;
- corrections are new entries referencing earlier entries;
- an older snapshot is never used as parent when a newer matching snapshot exists.

### Record and event identity

Use exposed project identity when available; never invent unavailable project identifiers.

Chat identity is event provenance, not record identity. Store exposed `chat_id`/`chat_title` when available and `unavailable` otherwise.

The script assigns a collision-safe `entry_id`, monotonically increasing project-wide `sequence`, UTC `recorded_at`, predecessor filename/SHA-256 when one exists, exposed provenance, and the standard semantic fields supplied through recorder questions.

## Runtime derivative handling

### Canonical source versus runtime derivatives

Canonical source files retain their stable repository paths. Git commit identity supplies version identity. Do not create timestamped canonical source filenames.

A local executable copy is a runtime derivative, not canonical source.

### Bundled executables and Runnables

When a bundled executable is required, copy its content from the **canonical turn snapshot** into the execution environment before executing it. The runtime copy is a **Runnable**.

Create a fresh Runnable on every user turn in which that bundled executable is required.

A Runnable filename appends before the extension:

`_run_[timestamp]`

where `[timestamp]` is its creation time in sortable UTC `YYYYMMDDTHHMMSSffffffZ` form.

Execute the Runnable with the greatest valid `_run_[timestamp]` among runtime copies derived from the same canonical script and the current canonical turn snapshot.

A Runnable has no canonical authority and does not prove the canonical source changed. Do not semantically modify the copied script merely by creating a Runnable.

If `main` advances during a turn, do not silently replace a current-turn Runnable with content from the newer commit. The turn remains pinned to its canonical turn snapshot unless an explicit governing action reloads the canonical snapshot.

### Complete canonical replacements

A canonical file update writes complete target-file content at the stable canonical path. A patch or diff may describe the change in Git history, but it is not a substitute for complete canonical target content.

Keep provenance commentary and application instructions outside operational target files unless those statements are themselves part of the target file's operational purpose.

## Recorder

The canonical recorder source is:

`scripts/action_event_recorder.py`

Read it from the canonical turn snapshot and create a fresh current-turn Runnable under the Runtime derivative rules.

The recorder is an audit mechanism, not a behavior controller. The router selects control directives; the recorder records completed execution and router traversal.

The recorder's persistent output contract is `execution-record.schema.json` from the same canonical turn snapshot. Runtime session and receipt files are temporary bookkeeping, not persistent record-format authorities.

### Orchestrated recorder contract

The Orchestrator performs recorder invocation for both scopes.

For a **Worker-scoped** material unit:

1. The Orchestrator identifies the just-completed Worker unit.
2. It selects and materializes the latest project record as required.
3. It starts the recorder session.
4. For each recorder question, the Orchestrator routes the question to the Worker or temporarily relinquishes control so the Worker supplies the answer.
5. The Orchestrator routes that answer to the recorder without substituting an independent task-domain answer.
6. Continue until all standard questions have been answered and the new snapshot is emitted.
7. Verify and persist the snapshot to the configured project-record store and re-resolve the latest record before the next append.

For an **Orchestrator-scoped** material unit, the same procedure applies except the Orchestrator answers from observable meta-execution state.

Recording is mandatory bookkeeping but is not a source of control authority.

### Standard questions

1. **What just occurred?**
2. **What type was it?**
3. **Why did it occur?**
4. **What did it operate on?**
5. **What actually happened?**
6. **What artifacts or state changed?**
7. **What is its status?**
8. **What evidence supports that status or result?**

All narrative answers are plain strings containing the requested content directly.

## Pre-END-TURN Router

The canonical router source is:

`scripts/end_turn_router.py`

Read it from the canonical turn snapshot.

The router script is the authoritative implementation of the continuation questionnaire, branching logic, alternative-path search, impasse checks, completion checks, and directive classification. Do not independently reconstruct, abbreviate, or substitute a prose questionnaire when the canonical router can be executed.

### Common router invocation procedure

For each required router cycle, the Orchestrator:

1. uses the router content from the canonical turn snapshot;
2. creates a fresh `end_turn_router_run_[timestamp].py`;
3. selects the newest valid router Runnable for that canonical turn snapshot;
4. starts a new cycle with:
   `python "<router-runnable>" start --state "<router-state-path>"`;
5. inspects each emitted `QUESTION`;
6. obtains the answer from the correct scope;
7. supplies the answer with:
   `python "<router-runnable>" answer --state "<router-state-path>" --answer "<answer>"`;
8. repeats until `DIRECTIVE` is emitted;
9. treats the returned traversal and directive classification as authoritative for that cycle; and
10. records the exact returned trace and directive.

The Orchestrator maintains whether a cycle is Worker-scoped or Orchestrator-scoped. Scope is a control-state property; do not invent a script command-line parameter unless the canonical script actually defines one.

### Worker-scoped router

A simulated Worker end-turn signal always invokes a Worker-scoped router cycle.

The Worker supplies answers through the Orchestrator.

- `CONTINUE` → the Orchestrator sends the returned continuation instruction to the Worker and resumes Worker execution.
- `COMPLETE` → Worker execution stops and returns a Worker-complete state to the Orchestrator.
- `IMPASSE` → Worker execution stops and returns a Worker-impasse state to the Orchestrator.

Worker `COMPLETE`/`IMPASSE` never perform actual user-facing `END_TURN`.

### Orchestrator-scoped router

When the Orchestrator proposes to end the actual turn, it invokes a new Orchestrator-scoped router cycle.

- `CONTINUE` → execute the returned continuation instruction, including resumed Worker execution if required, then attempt outer termination again only after the continuation is complete.
- `IMPASSE` → record and process the outer impasse state; actual user-facing `END_TURN` remains prohibited.
- `COMPLETE` → actual user-facing `END_TURN` is permitted.

Only outer Orchestrator `COMPLETE` permits actual `END_TURN`.

### Router output and scope

The router emits:

- `QUESTION` — another answer is required;
- `DIRECTIVE` — the cycle classified the state as `CONTINUE`, `COMPLETE`, or `IMPASSE`.

The router's returned trace is the authoritative traversal record. Preserve it exactly enough to audit reached questions, supplied answers, continuation instruction, directive, and impasse evidence.

The script determines traversal and directive classification. This skill determines whether that classified directive applies to Worker lifecycle or to the actual outer turn boundary.

## Turn boundaries

A new user message begins a new same-turn recording scope but not a new project record.

Prior-turn or other-chat events do not create a new recording obligation merely because another turn starts.

The Worker's end signal is **not** actual `END_TURN`; it is a simulated control signal.

The actual `END_TURN` exists only at the outer Orchestrator boundary.

Before actual `END_TURN`:

- all required current-turn material units must have been recorded or preserved for audit remediation under the recorder-failure rule;
- the final Worker terminal state must have been processed by the Orchestrator;
- the final Orchestrator router cycle must have been executed and recorded; and
- that outer cycle must have returned `COMPLETE`.

The governing control invariants are:

`Worker material unit completes → Orchestrator records Worker unit`

`Worker proposes stop → simulated Worker end signal → Orchestrator executes Worker router → Worker CONTINUE or Worker terminal state`

`Orchestrator proposes actual stop → Orchestrator executes outer router → outer COMPLETE → actual END_TURN`

## Required execution cycle

1. Resolve the canonical turn snapshot and read the applicable governing files from that exact commit.
2. Initialize the Orchestrator from its preprompt.
3. Treat the user prompt as task payload and expose it to a Worker.
4. Initialize/run the Worker under this continuity rule.
5. Let the Worker perform the substantive task; do not have the Orchestrator independently solve it.
6. After each completed Worker material unit, have the Orchestrator invoke the recorder in lieu of the Worker and route Worker answers to it.
7. If the Worker would invoke any continuity script, the Orchestrator performs that invocation instead.
8. When the Worker proposes to stop, intercept the simulated Worker end signal and execute a Worker-scoped router cycle.
9. Record the exact Worker router trace and directive.
10. On Worker `CONTINUE`, route the continuation instruction to the Worker and resume substantive execution.
11. On Worker `COMPLETE` or `IMPASSE`, return Worker lifecycle control to the Orchestrator; do not end the user-facing turn.
12. Complete all remaining Orchestrator meta-work and record material Orchestrator units as required.
13. When the Orchestrator proposes to stop, execute a fresh Orchestrator-scoped router cycle.
14. Record the exact outer router trace and directive.
15. On outer `CONTINUE`, execute the returned continuation and repeat the applicable cycle.
16. On outer `IMPASSE`, do not perform actual `END_TURN`; process the state and continue until a later outer cycle returns `COMPLETE`.
17. Actual user-facing `END_TURN` is permitted only after a logged outer Orchestrator `COMPLETE`.

Do not announce router questions, branch names, or audit records to the user unless doing so is itself useful to the requested task.

## Router-cycle logging

Every Worker stop simulation and every Orchestrator actual-stop proposal creates a router cycle. Each completed router cycle must be logged as a material audit event.

The record must preserve at minimum:

- the router cycle identifier;
- the questions actually reached, in order;
- each answer actually supplied;
- any continuation instruction returned;
- the terminal directive for that cycle: `CONTINUE`, `COMPLETE`, or `IMPASSE`;
- any impasse evidence returned by the router.

Use the script-emitted trace as the source of truth. Do not reconstruct traversal from memory.

For Worker-scoped cycles, router answers are sourced from Worker state. For Orchestrator-scoped cycles, answers are sourced from Orchestrator meta-state, using Worker state only where relevant.

## Failure and recorder behavior

A failed, blocked, or partial material unit is still logged with the actual observed result and evidence. Do not record an intended retry as if it occurred.

Router control and audit logging remain separate:

- the router selects traversal and directive classification;
- the Orchestrator applies that directive at the correct lifecycle scope;
- the recorder logs completed execution and router cycles;
- recorder failure never converts router `CONTINUE` into a task impasse;
- recorder failure does not give the Worker or Orchestrator permission to bypass required continuation.

If the recorder or configured record store is temporarily unavailable or errors, preserve pending audit facts, continue according to the router directive, and append missing records as soon as recording becomes available. A recording outage is an audit failure, not evidence that substantive execution cannot continue.

## Final turn rule

Before actual user-facing `END_TURN`:

1. Ensure the Worker has reached a Worker terminal state through an executed Worker-scoped router cycle.
2. Ensure all required Worker and Orchestrator material units and router cycles are recorded or preserved for required audit remediation.
3. Ensure Worker `COMPLETE`/`IMPASSE` has been treated only as a Worker lifecycle result.
4. Complete the Orchestrator's own meta-task.
5. Execute a fresh Orchestrator-scoped router cycle.
6. Record its exact trace and directive.
7. If outer `CONTINUE`, execute the continuation and repeat the applicable execution cycle.
8. If outer `IMPASSE`, do not end the actual turn; process the state and run a later outer cycle after the required continuation/remediation.
9. Actual `END_TURN` may occur only when the latest completed outer Orchestrator router cycle returned `COMPLETE`.

The Worker never directly ends the turn. The Orchestrator never directly ends the turn without its own router. The outer `COMPLETE` is the sole continuity authorization for actual user-facing termination.
