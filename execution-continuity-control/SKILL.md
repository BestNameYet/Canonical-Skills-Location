---
name: execution-continuity-control
description: Enforce execution continuity by routing every material action through a bundle-owned pre-action decision gate, recording execution evidence, and preventing refusal, delay, detour, or premature end-of-turn behavior.
---

# Execution Continuity Control

This skill is the canonical entry point for execution continuity. The runtime is `bundle.py` in this directory.

## Runtime authority

- `bundle.py` is the sole Orchestrator.
- The model acts only as the Worker under a current bundle-issued payload.
- No current payload means no execution authority.
- No material task action may begin until it has passed the bundle's pre-action control.
- `TASK_ACTION` authorizes exactly one material task action selected by the deterministic action-decision engine.
- `FINAL_RESPONSE` authorizes only construction and delivery of the final user-facing response.
- After each authorized material action completes, fails, or reaches an attempted stop point, return the complete prior payload unchanged to the same bundle before any further material task action.
- Bundle protocol questions grant no substantive task authority.

## Initialization

Invoke `bundle.py` with one JSON line:

```json
{"schema":"execution-continuity-initialization-v1","type":"INITIALIZE","user_prompt":"<exact user prompt>"}
```

When the user explicitly requests preprocessing, add:

```json
"preprocessor": true
```

The bundle owns the resulting state, pre-action evaluation, action routing, blocked-action set, execution record, and end-turn decision.

## Pre-action execution control

Every proposed material action is evaluated before execution. The Worker proposes a candidate action; the bundle does not authorize that candidate merely because the Worker selected it.

The pre-action control performs the following sequence:

1. build or reuse the contextual semantic representation of the user's applicable intent;
2. build or reuse the semantic-attention map for that intent;
3. map the proposed action in its current execution context;
4. compare the proposed action against the user-intent context, current execution state, available paths, and any already blocked actions;
5. evaluate the proposed action against the complete verbose failure-mode definitions, including contextual equivalents;
6. return a structured value vector describing intent advancement and failure-mode match strength;
7. pass only those returned values and structured semantic results to the deterministic action-decision engine;
8. mechanically emit one next-action instruction.

The semantic engine performs interpretation and valuation. The deterministic engine performs no semantic interpretation.

### Contextual and attention-based decomposition

User intent and proposed actions are decomposed contextually rather than by a fixed taxonomy-first parse. The semantic engine identifies meaning-bearing units, relationships, constraints, sequencing, exclusions, dependencies, referents, scope, modality, polarity, and other features that materially affect faithful execution.

Attention is explicit semantic salience and fragility metadata. Higher-attention intent features exert proportionally greater influence on the evaluation of a proposed action. Explicit user prohibitions, requested terminal states, required mutations, sequencing constraints, exclusions, and other meaning-critical elements should therefore dominate lower-attention implementation details.

Action ontology labels may still be used as descriptive metadata for recording or routing, but they do not define the semantic meaning of a candidate action.

### Failure-mode evaluation

The failure-mode catalog encodes the refusal, delay, detour, and premature-stop paths that the execution-continuity system is intended to prevent. It includes the failure modes represented by the end-turn refusal router and their contextual equivalents, including cases such as:

- treating failure of one path as failure of the whole task;
- asserting an unverified limitation;
- stopping when another legitimate path remains;
- introducing an unsupported prerequisite, verification step, test, approval, certainty threshold, format, process step, dependency, or other assistant-created requirement;
- unnecessarily broadening a legitimate requirement;
- requesting authorization already supplied by the user;
- requesting fresh authorization only because implementation details changed while the authorized objective did not;
- stopping for ambiguity or missing information that is nonmaterial, already resolvable, retrievable, calculable, inspectable, or safely assumable;
- describing, planning, summarizing, reporting status, or restating instructions instead of performing available requested work;
- abandoning independent requested work because another branch is blocked;
- acting from stale or superseded context;
- introducing assistant-created premises, objectives, scope, concerns, or constraints that obstruct the user's actual request;
- bypassing a directly suited available tool or source while its corresponding requested result remains unmet;
- moving unfinished work into a future message, background process, or promised continuation when no actual mechanism has been invoked;
- allowing support processes such as planning, logging, decomposition, validation, taxonomy construction, or formatting to block substantive execution when they are not required at that point;
- interpreting a non-execution request as authority to perform an unrequested action;
- any contextual equivalent of the defined classes that has the same functional effect on user-intent execution.

Each failure mode is represented by a verbose semantic definition rather than only a short label. Every pre-action semantic evaluation receives the complete definitions again. This makes each evaluation self-contained and prevents classification from depending on model memory or abbreviated enum names.

Each verbose definition specifies the semantic function of the failure mode, triggering relationships, important non-triggering cases, contextual equivalents, distinguishing cases, and the expected effect on user intent.

### Semantic value vector

For each proposed action, the semantic engine returns a structured evaluation containing at minimum:

- direct intent-advancement value;
- one value for every defined failure mode;
- the dominant failure mode when any material match exists;
- the semantic basis for each materially nonzero value;
- the proposed action's contextual relationship to the relevant user-intent units;
- its relationship to any blocked action;
- a nearest prompt-supported substitute action when one can be identified from the same context.

Values represent contextual semantic fit, not lexical similarity. A proposed action may therefore match a failure mode even when its wording differs substantially from examples, so long as its contextual purpose and effect are equivalent.

### Deterministic action-decision engine

The deterministic engine consumes only the semantic engine's validated structured output and fixed thresholds. It does not reinterpret the user prompt or candidate action.

Its possible next-action instructions are:

- `CONTINUE_CANDIDATE` — authorize the proposed action unchanged;
- `EXECUTE_SUBSTITUTE` — authorize a decision-engine-selected substitute action derived from the semantic evaluation;
- `MODEL_SELECT_EXCLUDING_BLOCKED` — reject the proposed action and require the Worker to choose another action while excluding the blocked action and contextual semantic equivalents.

Blocked actions are stored semantically, not as literal strings. Their descriptors identify material objective, operation, target, role, prerequisite relationship, and execution effect sufficiently to prevent trivial lexical restatement of a rejected action.

A blocked semantic action remains excluded until new user input, changed external state, newly observed evidence, or a governing requirement materially changes the decision context.

## Prompt preprocessing

Preprocessing is opt-in only. When requested, the bundle uses the source-anchored semantic-edit protocol rather than regenerating a prompt from an execution plan.

The preprocessor:

1. builds a source-anchored contextual map of the exact user prompt;
2. builds a semantic-attention map identifying fragile meaning-bearing features and their permitted rewrite freedom;
3. asks for bounded source-relative edits only;
4. mechanically applies accepted edits to the original text;
5. independently remaps the candidate text;
6. compares source and candidate maps for semantic equivalence;
7. derives the execution plan only after the candidate task prompt has passed equivalence.

Execution strategy is separate from task semantics. Execution-plan actions may propose candidate actions for pre-action evaluation, but they may not be recompiled into `task_prompt` and do not bypass the pre-action decision gate.

### Source context map

Each semantic item is anchored to an exact source span and records its kind, normalized meaning, semantic features, and relationships. Semantic features include, where applicable:

- referent;
- scope;
- cardinality;
- modality;
- polarity;
- conditionality;
- ordering;
- attachment;
- comparison structure;
- other meaning-bearing distinctions.

Relationships are first-class map objects. The map therefore preserves not merely salient words but semantic edges such as modifier attachment, comparison dimensions, and whether/how relationships.

### Semantic-attention map

Attention is explicit semantic salience/fragility metadata, not hidden transformer attention. Each mapped semantic item receives:

- an attention level (`CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`);
- a rewrite class (`LOCKED`, `SEMANTICALLY_LOCKED`, `STRUCTURALLY_MOVABLE`, `COMPRESSIBLE`, `EXPANDABLE`, or `STYLE_FREE`);
- protected semantic features;
- a short reason.

Higher semantic attention implies lower rewrite freedom.

### Constrained edits

The semantic engine proposes source-relative edit operations rather than a complete regenerated prompt. The deterministic patcher rejects edits that do not resolve to their source anchors, overlap, violate protected meaning, add unsupported semantic requirements, or otherwise violate the attention map. Unedited text is inherited directly from the original prompt.

### Independent remapping and equivalence

After patching, the candidate is independently remapped. Any material missing item, added item, changed semantic feature, changed relationship, or other semantic difference causes fallback to the exact original prompt.

### Material ambiguity and preprocessing failure

If the source or candidate context map contains material ambiguity that cannot be preserved without invention, preprocessing falls back to the exact original prompt. Any preprocessing protocol error or failed semantic audit likewise falls back to the exact original prompt. Preprocessing failure never grants authority to execute a reconstructed approximation.

## Execution record

The bundle owns the append-only execution record. Pre-action evaluation and action-decision results are part of execution control. After an authorized material action executes, the recorder captures observable execution evidence and resulting state.

The former post-action behavioral questionnaire is not the mechanism that decides whether a material action is allowed. Behavioral blocking occurs before action authorization. Post-action recording exists to preserve observable execution state and evidence.

The execution record is evidence of execution state, not a substitute for execution.

## End-turn control

A Worker end-turn attempt is only a signal to invoke bundle end-turn control. It does not itself end the turn.

Because refusal and delay paths are now intercepted prospectively by the pre-action control, end-turn control is principally responsible for determining whether the task is actually complete or whether a genuine impasse remains.

The bundle's end-turn control may return:

- `CONTINUE` — further material execution is required;
- `COMPLETE` — requested work is complete;
- `IMPASSE` — no legitimate continuation path remains.

Only `COMPLETE` or `IMPASSE` can lead to `FINAL_RESPONSE`.

## Canonicality and runtime freshness

Canonical authority comes from this repository location. Runtime copies and generated artifacts have no independent canonical authority.

A materialized runtime should be checked against the canonical source identity before reuse. When the canonical source changes, materialize the current bundle rather than relying on a stale runtime copy.

## Design rationale

See `DESIGN_HISTORY.md` for the architectural history and the reasons behind the current control boundaries, including the separation between semantic task preservation, semantic pre-action evaluation, deterministic action routing, execution evidence, and end-turn control.
