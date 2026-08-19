---
name: execution-continuity-control
description: Enforce execution continuity by routing each material action through a single bundle-owned state machine, recording execution evidence, and preventing premature end-of-turn behavior.
---

# Execution Continuity Control

This skill is the canonical entry point for execution continuity. The runtime is `bundle.py` in this directory.

## Runtime authority

- `bundle.py` is the sole Orchestrator.
- The model acts only as the Worker under a current bundle-issued payload.
- No current payload means no execution authority.
- `TASK_ACTION` authorizes exactly one material task action.
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

The bundle owns the resulting state, action routing, execution record, and end-turn decision.

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

Execution strategy is therefore separate from task semantics. Execution-plan actions may determine the first `TASK_ACTION`, but they may not be recompiled into `task_prompt`.

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

Relationships are also first-class map objects. The map therefore preserves not merely salient words but semantic edges such as modifier attachment, comparison dimensions, and whether/how relationships.

### Semantic-attention map

Attention is explicit semantic salience/fragility metadata, not hidden transformer attention. Each mapped semantic item receives:

- an attention level (`CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`);
- a rewrite class (`LOCKED`, `SEMANTICALLY_LOCKED`, `STRUCTURALLY_MOVABLE`, `COMPRESSIBLE`, `EXPANDABLE`, or `STYLE_FREE`);
- protected semantic features;
- a short reason.

Higher semantic attention implies lower rewrite freedom.

### Constrained edits

The semantic engine proposes source-relative edit operations rather than a complete regenerated prompt. Supported operations are:

- `REPLACE`;
- `DELETE`;
- `INSERT_BEFORE`;
- `INSERT_AFTER`.

Each edit identifies an exact source anchor, replacement text, purpose, affected semantic items, and whether it adds a semantic requirement.

The deterministic patcher rejects edits that:

- do not resolve to the claimed source anchor;
- overlap;
- violate a locked span;
- alter a protected semantic feature;
- add a semantic requirement without source entailment;
- otherwise violate the attention map.

Unedited text is inherited directly from the original prompt.

### Independent remapping and equivalence

After patching, the candidate is independently remapped. The final semantic audit compares the source and candidate maps and reports:

- missing semantic items;
- added semantic items;
- changed semantic features;
- changed relationships;
- other semantic changes.

Any material difference causes fallback to the exact original prompt. The audit is a safety boundary, not a mechanism for promoting execution strategy into user requirements.

### Material ambiguity

If the source context map identifies a material ambiguity, the preprocessor falls back to the exact original prompt rather than inventing a resolution. Candidate-side material ambiguity likewise causes fallback.

### Failure behavior

Any preprocessing protocol error or failed semantic audit falls back to the exact original user prompt. Preprocessing failure never grants authority to execute a reconstructed approximation.

## Execution record

The bundle owns the append-only execution record. Material actions are followed by the action questionnaire and recorded with observable evidence. End-of-turn attempts additionally run the router before the bundle may issue `FINAL_RESPONSE`.

The execution record is evidence of execution state, not a substitute for execution.

## End-turn control

A Worker end-turn attempt is only a signal to invoke bundle end-turn control. It does not itself end the turn.

The bundle's router may return:

- `CONTINUE` — further material execution is required;
- `COMPLETE` — requested work is complete;
- `IMPASSE` — no legitimate continuation path remains.

Only `COMPLETE` or `IMPASSE` can lead to `FINAL_RESPONSE`.

## Canonicality and runtime freshness

Canonical authority comes from this repository location. Runtime copies and generated artifacts have no independent canonical authority.

A materialized runtime should be checked against the canonical source identity before reuse. When the canonical source changes, materialize the current bundle rather than relying on a stale runtime copy.

## Design rationale

See `DESIGN_HISTORY.md` for the architectural history and the reasons behind the current control boundaries, including the separation between semantic task preservation and execution planning.
