---
name: execution-continuity-control
description: Enforces continuous task execution through a single generated runtime bundle that owns post-action recording, questioning, end-turn routing, and Worker authorization.
compatibility: Designed for ChatGPT Skills with GitHub artifact access, interactive Python 3 execution, and writable local execution-record storage.
---

# Execution Continuity Control

Canonical repository: `BestNameYet/Canonical-Skills-Location`  
Canonical branch: `main`  
Bundle pointer: repository-root `execution-continuity-bundle.json`

For every governed invocation:

1. Resolve current `main` and fetch the current repository-root `execution-continuity-bundle.json` from that revision.
2. Read its `artifact_id`, `bundle_filename`, `bundle_sha256`, and source provenance.
3. Download that GitHub Actions artifact and extract the single file named by `bundle_filename` into the local execution environment.
4. Verify the extracted file SHA-256 against `bundle_sha256`.
5. Execute the generated `bundle.py` directly with no bootstrap or other model-facing subcommand. With no input it emits the first complete control payload for the current governed turn.
6. Obey the payload's `command`. Treat the payload's `state` as opaque bundle-owned continuation state. Do not extract, rewrite, reconstruct, summarize, or separately persist it.
7. After the authorized material action completes, fails, or reaches an attempted end-of-turn stop point, re-invoke the same generated bundle and return the entire prior payload unchanged as the first JSON input line.
8. The running bundle then owns recorder/questioner/router processing. Answer each emitted protocol question directly on the process input using the requested answer format. Protocol answering does not authorize substantive task work.
9. Continue until the bundle emits another complete payload. `TASK_ACTION` authorizes exactly one next material action. `FINAL_RESPONSE` authorizes only construction and delivery of the final user-facing response, after which the turn ends without another bundle cycle.

`NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY.`

The canonical runtime implementation is one file: `execution-continuity-control/bundle.py`. Recorder, action-questioner, and end-turn-router logic are ordinary functions inside that file. There are no model-facing child scripts, subprocess bridges, `sys.argv` shims, or textual main-guard stripping mechanisms.

Always acquire the artifact referenced by the current pointer before governed execution. Do not reconstruct the runtime from historical child scripts or stale local copies.
