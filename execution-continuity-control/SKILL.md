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
3. Download that GitHub Actions artifact and extract the single file named by `bundle_filename` directly into `/mnt/data` as `/mnt/data/bundle.py`. Do not create a bundle-specific directory.
4. Verify `/mnt/data/bundle.py` SHA-256 against `bundle_sha256`.
5. **First-invocation special case:** before any bundle payload exists, invoke `/mnt/data/bundle.py` once and provide the current user's prompt verbatim as the first protocol input. This retrieval/verification/initial-input handoff is the only pre-payload bootstrap activity authorized by this skill.
6. The bundle owns semantic intake. It must preserve the original user prompt in bundle-owned state. It may either adopt the prompt verbatim as the executable task prompt or conduct a model-facing preprocessing questionnaire, using the Worker as the semantic engine, to derive a more explicit executable prompt. If preprocessing is used, the original prompt remains preserved and the derived prompt is separately stored in bundle-owned state.
7. Model-facing questionnaire choices must be self-describing at the point of presentation. Whenever an enumerated value or type/subtype choice is requested, present the enum token together with its natural-language meaning in the same question text or payload. The Worker must not be required to infer an answer domain from hidden validator state.
8. Once prompt intake is complete, the bundle emits the first complete control payload. `TASK_ACTION` authorizes exactly one material action toward the stored executable prompt. From that point onward the bundle controls substantive execution.
9. Obey the payload's `command`. Treat the payload's `state` as opaque bundle-owned continuation state. Do not extract, rewrite, reconstruct, summarize, or separately persist it.
10. After the authorized material action completes, fails, or reaches an attempted end-of-turn stop point, re-invoke the same `/mnt/data/bundle.py` and return the entire prior payload unchanged as the first JSON input line.
11. The running bundle then owns recorder/questioner/router processing. Answer each emitted protocol question directly on the process input using the requested answer format. Protocol answering does not authorize substantive task work.
12. Continue until the bundle emits another complete payload. `TASK_ACTION` authorizes exactly one next material action. `FINAL_RESPONSE` authorizes only construction and delivery of the final user-facing response, after which the turn ends without another bundle cycle.
13. Runtime execution records are written directly into `/mnt/data` using the canonical `execution-record_<timestamp>.json` filename. Do not create or use a recorder-specific subdirectory.

Before the first bundle invocation, there is no payload; only retrieval, verification, and verbatim handoff of the current user prompt are authorized. After that handoff:

`NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY.`

The canonical runtime implementation is one file: `execution-continuity-control/bundle.py`. Recorder, prompt-intake/questioner, action-questioner, and end-turn-router logic are ordinary functions inside that file. There are no model-facing child scripts, subprocess bridges, `sys.argv` shims, or textual main-guard stripping mechanisms.

Always acquire the artifact referenced by the current pointer before governed execution. Do not reconstruct the runtime from historical child scripts or stale local copies.