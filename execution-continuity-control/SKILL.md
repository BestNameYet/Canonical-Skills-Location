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
5. **First-invocation special case:** before any bundle payload exists, explicitly invoke `/mnt/data/bundle.py` and provide exactly one UTF-8 JSON object, serialized on one stdin line, with exactly these three fields:

```json
{"schema":"execution-continuity-initialization-v1","type":"INITIALIZE","user_prompt":"<verbatim current user prompt>"}
```

   `schema` must equal `execution-continuity-initialization-v1`; `type` must equal `INITIALIZE`; `user_prompt` must be the complete current user prompt verbatim as a non-empty JSON string. Do not add, omit, rename, reinterpret, summarize, or pre-process fields before this handoff. JSON escaping required to serialize the verbatim prompt does not count as modification.
6. Receipt of that valid initialization object is the bundle's invocation and the state-machine transition from inert to active. Before receipt, the bundle has no governed-turn state and exercises no control over the Worker. After receipt, the bundle owns control of the Worker for the governed turn.
7. On initialization the bundle must preserve the exact `user_prompt` as `original_user_prompt` in bundle-owned state. The bundle then establishes an executable `task_prompt`. It may either use `original_user_prompt` verbatim as `task_prompt`, or conduct a model-facing preprocessing questionnaire using the Worker as the semantic engine and store the resulting prompt separately as `task_prompt`. Preprocessing questions are protocol work only and do not authorize substantive task execution.
8. Model-facing questionnaire choices must be self-describing at the point of presentation. Whenever an enumerated value or type/subtype choice is requested, present the enum token together with its natural-language meaning in the same question text or payload. The Worker must not be required to infer an answer domain from hidden validator state.
9. When prompt intake is complete, the bundle emits the first complete control payload. Every control payload must expose the governing `task_prompt` to the Worker. A `TASK_ACTION` payload pairs that `task_prompt` with one `command` authorizing exactly one material next action toward achieving it. The Worker follows `task_prompt` for the turn and executes only the currently authorized `command`.
10. Treat the payload's `state` as opaque bundle-owned continuation state. Do not extract, rewrite, reconstruct, summarize, or separately persist it. The exposed `task_prompt` and `command` are model-facing control fields, not permission to modify opaque state.
11. After the authorized material action completes, fails, or reaches an attempted end-of-turn stop point, re-invoke the same `/mnt/data/bundle.py` and return the entire prior payload unchanged as the first JSON input line.
12. The running bundle then owns recorder/questioner/router processing. Answer each emitted protocol question directly on the process input using the requested answer format. Protocol answering does not authorize substantive task work.
13. Continue until the bundle emits another complete payload. `TASK_ACTION` authorizes exactly one next material action toward the same governing `task_prompt`. `FINAL_RESPONSE` authorizes only construction and delivery of the final user-facing response satisfying `task_prompt`, after which the turn ends without another bundle cycle.
14. Runtime execution records are written directly into `/mnt/data` using the canonical `execution-record_<timestamp>.json` filename. Do not create or use a recorder-specific subdirectory.

The initialization state transition is:

`INERT -> receive valid INITIALIZE object -> preserve original_user_prompt -> establish task_prompt -> emit first TASK_ACTION -> payload-return state-machine loop -> FINAL_RESPONSE`

Before the first bundle invocation there is no payload; only canonical retrieval, artifact download, extraction, hash verification, and delivery of the exact initialization object are authorized bootstrap activity. After the initialization object is accepted:

`NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY.`

The canonical runtime implementation is one file: `execution-continuity-control/bundle.py`. Recorder, prompt-intake/questioner, action-questioner, and end-turn-router logic are ordinary functions inside that file. There are no model-facing child scripts, subprocess bridges, `sys.argv` shims, or textual main-guard stripping mechanisms.

Always acquire the artifact referenced by the current pointer before governed execution. Do not reconstruct the runtime from historical child scripts or stale local copies.