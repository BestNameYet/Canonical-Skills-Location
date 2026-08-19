---
name: execution-continuity-control
description: Enforces continuous task execution through a single generated runtime bundle that owns prompt intake, post-action recording, questioning, end-turn routing, and Worker authorization.
compatibility: Designed for ChatGPT Skills with GitHub artifact access, interactive Python 3 execution, and writable `/mnt/data` storage.
---

# Execution Continuity Control

Canonical repository: `BestNameYet/Canonical-Skills-Location`  
Canonical branch: `main`  
Bundle pointer: repository-root `execution-continuity-bundle.json`

For every governed invocation:

1. Resolve current `main` and fetch the current repository-root `execution-continuity-bundle.json` from that exact revision.
2. Read its `artifact_id`, `bundle_filename`, `bundle_sha256`, and source provenance.
3. Download that GitHub Actions artifact and extract the single file named by `bundle_filename` directly into `/mnt/data` as `/mnt/data/bundle.py`. Do not create a bundle-specific directory. Downloading or extracting the file does not invoke it; the file remains inert until explicitly executed.
4. Verify `/mnt/data/bundle.py` SHA-256 against `bundle_sha256`.
5. **First-invocation special case:** before any bundle payload exists, explicitly invoke `/mnt/data/bundle.py` and provide exactly one UTF-8 JSON object serialized on one stdin line. Two initialization forms are valid:

   Default verbatim intake uses exactly these three fields:

```json
{"schema":"execution-continuity-initialization-v1","type":"INITIALIZE","user_prompt":"<verbatim current user prompt>"}
```

   Optional semantic preprocessing uses exactly the same object plus the single field `"preprocessor": true`:

```json
{"schema":"execution-continuity-initialization-v1","type":"INITIALIZE","user_prompt":"<verbatim current user prompt>","preprocessor":true}
```

   `schema` must equal `execution-continuity-initialization-v1`; `type` must equal `INITIALIZE`; `user_prompt` must be the complete current user prompt verbatim as a non-empty JSON string. If `preprocessor` is present, its value must be the JSON boolean `true`; `false`, any non-boolean value, or any other additional field is invalid. Do not reinterpret, summarize, or pre-process `user_prompt` before this handoff. JSON escaping required to serialize the verbatim prompt does not count as modification.
6. Receipt of a valid initialization object is the bundle's invocation and the state-machine transition from inert to active. Before receipt, the bundle has no governed-turn state and exercises no control over the Worker. After receipt, the bundle owns control of the Worker for the governed turn.
7. On initialization the bundle preserves the exact `user_prompt` as `original_user_prompt` in bundle-owned state. When `preprocessor` is omitted, the bundle sets `task_prompt` to `original_user_prompt` verbatim. When `preprocessor` is `true`, the bundle enters its optional `prompt-preprocessor-v1` branch before issuing any `TASK_ACTION`.
8. In `prompt-preprocessor-v1`, the bundle emits a deterministic series of model-facing semantic question objects. Each object specifies one semantic function, its inputs, an instruction, constraints, and the required JSON response shape. The Worker acts only as the semantic engine: answer each object directly in the requested format and do not perform substantive task work. The bundle validates and stores the answers, constructs a typed Prompt IR, requests model-generated semantic fragments, mechanically recomposes those fragments into a candidate `task_prompt`, and requests a final semantic-equivalence audit. The bundle accepts the recomposed prompt only when its deterministic validation and semantic audit succeed. Material ambiguity, protocol failure, or failed semantic audit causes deterministic fallback to `original_user_prompt`; preprocessing failure does not itself fail the user's task.
9. Model-facing questionnaire choices must be self-describing at the point of presentation. Whenever an enumerated value or type/subtype choice is requested, present the enum token together with its natural-language meaning in the same question text or payload. The Worker must not be required to infer an answer domain from hidden validator state.
10. When prompt intake is complete, the bundle emits the first complete control payload. Every control payload must expose the governing `task_prompt` to the Worker. A `TASK_ACTION` payload pairs that `task_prompt` with one `command` authorizing exactly one material next action toward achieving it. When semantic preprocessing is accepted, the first command is the first dependency-valid action fragment from the preprocessed action graph. The Worker follows `task_prompt` for the turn and executes only the currently authorized `command`.
11. Treat the payload's `state` as opaque bundle-owned continuation state. Do not extract, rewrite, reconstruct, summarize, or separately persist it. The exposed `task_prompt` and `command` are model-facing control fields, not permission to modify opaque state.
12. After the authorized material action completes, fails, or reaches an attempted end-of-turn stop point, re-invoke the same `/mnt/data/bundle.py` and return the entire prior payload unchanged as the first JSON input line.
13. The running bundle then owns recorder/questioner/router processing. Answer each emitted protocol question directly on the process input using the requested answer format. Protocol answering does not authorize substantive task work.
14. Continue until the bundle emits another complete payload. `TASK_ACTION` authorizes exactly one next material action toward the same governing `task_prompt`. `FINAL_RESPONSE` authorizes only construction and delivery of the final user-facing response satisfying `task_prompt`, after which the turn ends without another bundle cycle.
15. Runtime execution records are written directly into `/mnt/data` using the canonical `execution-record_<timestamp>.json` filename. Do not create or use a recorder-specific subdirectory.

The default initialization state transition is:

`INERT -> receive valid INITIALIZE object -> preserve original_user_prompt -> set task_prompt = original_user_prompt -> emit first TASK_ACTION -> payload-return state-machine loop -> FINAL_RESPONSE`

The optional preprocessing transition is:

`INERT -> receive valid INITIALIZE object with preprocessor=true -> preserve original_user_prompt -> prompt-preprocessor-v1 semantic question sequence -> Prompt IR -> semantic fragment generation -> deterministic recomposition -> semantic audit -> accept recomposed task_prompt or fall back to original_user_prompt -> emit first TASK_ACTION -> payload-return state-machine loop -> FINAL_RESPONSE`

Before the first bundle invocation there is no payload; only canonical retrieval, artifact download, extraction, hash verification, and delivery of one valid initialization object are authorized bootstrap activity. After the initialization object is accepted:

`NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY.`

The canonical runtime implementation is one file: `execution-continuity-control/bundle.py`. Recorder, prompt-intake/preprocessor, action-questioner, and end-turn-router logic are ordinary functions inside that file. There are no model-facing child scripts, subprocess bridges, `sys.argv` shims, or textual main-guard stripping mechanisms.

Always acquire the artifact referenced by the current pointer before governed execution. Do not reconstruct the runtime from historical child scripts or stale local copies.
