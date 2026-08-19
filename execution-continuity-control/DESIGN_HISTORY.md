# Execution Continuity Control — Design History

## Identity

- Canonical repository: `BestNameYet/Canonical-Skills-Location`
- Canonical branch: `main`
- Canonical path: `execution-continuity-control/`
- Version identity: Git commit SHA
- Runtime authority: the Actions artifact referenced by repository-root `execution-continuity-bundle.json`

## Protected design history

The system exists to force completion-oriented execution rather than allow planning, status reporting, one failed path, or unsupported completion claims to substitute for doing the requested work.

Recording moved from history-first bookkeeping to prospective post-action recording. One logical project execution record is represented by immutable timestamped snapshots. The recorder is the sole writer, the action questionnaire owns structured post-action representation, and the end-turn router alone classifies `CONTINUE`, `COMPLETE`, or `IMPASSE`.

A self-invoked end-turn gate was bypassable because the same model controlled both work and the actual turn boundary. Control therefore moved into a runtime bundle. The bundle is the Orchestrator; the model is a Worker operating only under current bundle-issued authorization.

## 2026-08-19 — child-script and CLI architecture removed

An intermediate bundle implementation embedded `action_event_recorder.py`, `action_questioner.py`, and `end_turn_router.py` as pseudo-scripts. The builder wrapped complete CLI programs in factories, rewrote `sys.argv`, captured stdout JSON, and tried to remove `__main__` blocks by exact textual matching. `end_turn_router.py` used a compact `if __name__=="__main__":` form that escaped stripping, so its CLI executed while the generated bundle loaded and intercepted the intended controller entrypoint.

The resolution is structural, not another guard-pattern patch:

- the canonical runtime source is now exactly one file: `execution-continuity-control/bundle.py`;
- recorder, questioner, router, payload, and controller behavior are ordinary functions in that file;
- the former child scripts are deleted from canon;
- the former build wrapper is deleted;
- there is no subprocess bridge, child CLI, `sys.argv` rewriting, stdout JSON proxy, source encoding, dynamic source evaluation, or main-guard stripping;
- GitHub Actions validates and publishes the canonical single-file bundle rather than reconstructing it from child scripts.

## 2026-08-19 — opaque payload round trip

The earlier controller exposed model-facing commands such as `bootstrap`, `provide-prompt`, `after-action`, and `continuity-answer`, plus a separate hidden controller-state file. That made the model parse identifiers and reconstruct controller calls.

The current interface uses the entire payload as the continuation object:

1. execute `bundle.py` directly with no input;
2. receive a complete `TASK_ACTION` payload containing command, context, behavioral instructions, and bundle-owned state;
3. perform exactly that one material action;
4. on completion, failure, or attempted end-turn, return the complete prior payload unchanged as the first JSON input line to the same bundle;
5. the running bundle asks the post-action questionnaire and, when applicable, the end-turn router interactively;
6. the bundle persists recorder/questionnaire/router actions and emits the next complete payload;
7. router `CONTINUE` yields another `TASK_ACTION`; router `COMPLETE` or `IMPASSE` yields `FINAL_RESPONSE` authority only.

Payload state is opaque to the Worker. A SHA-256 over canonicalized payload content detects mutation. Separate controller-state and questionnaire/router state files are no longer part of the control protocol. Execution-record snapshots remain persisted because audit persistence is distinct from continuation state.

## 2026-08-19 — source-anchored semantic preprocessor v2

The first semantic preprocessor decomposed the user prompt into requirements, then derived an execution action graph and model-rendered fragments, and finally used `_recompose()` to turn the action graph back into a new `task_prompt`. This created a category error: an operational method chosen to satisfy the request could become a new user-level requirement merely because it appeared in the plan. In the observed failure, source-reading was a reasonable execution strategy, but recompilation converted it into a new source-grounding requirement. A separate requirement mapping also broadened singular `recurring issue` to plural `recurring issues`. The final semantic audit correctly rejected the candidate, but only after the contaminated prompt had already been generated.

The correction changes the computational model rather than adding another downstream guard:

- `original_user_prompt` remains the authoritative text object;
- the semantic engine first produces a source-anchored contextual map of semantic items, semantic relations, material ambiguities, and preservation-sensitive features;
- source anchors use exact substrings plus occurrence counts rather than model-generated character offsets;
- a separate semantic-attention map identifies fragility, rewrite freedom, protected features, and protected relations; higher attention means lower rewrite freedom;
- candidate revision uses bounded source-relative replacement edits only; the model does not regenerate the whole prompt from an abstract representation;
- deterministic validation checks edit anchors, overlap, semantic intersections, relation intersections, and `LOCKED` spans before patch application;
- the candidate is independently remapped without receiving the original map;
- an explicit item/relation alignment audit compares the independently generated source and candidate maps and rejects omissions, additions, changed features, changed relations, or other semantic drift;
- execution planning runs only after semantic equivalence passes and is stored separately from `task_prompt`;
- the execution plan may select methods or information-acquisition steps, but it is never eligible input for rewriting `task_prompt`;
- the previously observed singular-to-plural mutation is covered by a local regression test in which a `LOCKED` `recurring issue` anchor cannot be edited to `recurring issues` before semantic audit;
- fallback remains fail-safe: material ambiguity, candidate ambiguity, protocol failure, or failed semantic equivalence restores the verbatim original prompt without failing the user's task.

## Protected invariants

1. Requested-task completion outranks procedural ceremony.
2. Planning, explanation, or status does not substitute for available requested execution.
3. Completion, mutation, persistence, retrieval, validation, and failure claims require observable support.
4. Do not reconstruct unrecorded history as contemporaneous evidence.
5. Record a completed material action before another material action is authorized.
6. Maintain one logical append-only project execution record; corrections append.
7. Recorder is the sole execution-record writer.
8. Action-questionnaire capture and router classification remain logically separate responsibilities even though they are functions in one file.
9. Router alone classifies `CONTINUE`, `COMPLETE`, or `IMPASSE` and never directly writes the execution record.
10. Router cycles are persisted as `end_turn_result` actions before their directive is acted on.
11. The runtime bundle is the sole Orchestrator; the model acts as Worker.
12. `NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY` for substantive task work.
13. `TASK_ACTION` authorizes exactly one material action.
14. The complete prior payload must be returned before another material action can be authorized.
15. Payload continuation state is bundle-owned and opaque to the Worker.
16. Protocol-question answering grants no substantive task authority.
17. Router `CONTINUE` produces exactly one new `TASK_ACTION` payload.
18. Router `COMPLETE` or `IMPASSE` produces `FINAL_RESPONSE` authority only.
19. `FINAL_RESPONSE` authorizes final user-facing delivery only and is not routed through another continuity cycle.
20. Runtime derivatives never acquire canonical source authority.
21. The canonical runtime is one plain-text Python file; no encoded source container or dynamic decoding mechanism is permitted.
22. There are no recorder/questioner/router child scripts in the canonical runtime architecture.
23. There is no pseudo-subprocess/CLI compatibility layer among continuity components.
24. GitHub Actions must compile-check and directly execute the canonical bundle before publishing its artifact pointer.
25. Related source changes are staged together and `main` is moved only after the complete source set has been validated.
26. Prompt preprocessing must treat `original_user_prompt` as the authoritative semantic source; an execution plan is never an authoritative source for governing prompt semantics.
27. Any accepted preprocessor revision must be source-relative, mechanically patched, independently remapped, and semantically equivalent at both item and relation levels.
28. Semantic-attention metadata controls rewrite freedom: preservation-sensitive features and relations may not be broadened, weakened, strengthened, reassigned, or silently dropped.

## Superseded mechanisms

Do not restore these merely because historical revisions contain them:

- history-first/per-turn logging gates;
- model-owned end-turn gating;
- direct model invocation of recorder/questioner/router paths;
- child-process bridges among continuity components;
- wrapping child CLI programs in factories;
- rewriting `sys.argv` to emulate script calls;
- source encoding/decoding or dynamic source evaluation;
- textual `__main__`-guard stripping;
- model-facing `bootstrap`, `provide-prompt`, `after-action`, or `continuity-answer` subcommands;
- a separate hidden controller-state file;
- requiring the Worker to extract an action ID or state fragment from a payload;
- reconstructing the runtime from stale or historical child scripts;
- recompiling execution-plan actions into `task_prompt`;
- treating exact supporting-text provenance as proof that a paraphrased semantic claim is equivalent.

## Revision rule

Resolve current `main`, inspect the current single-file bundle, skill bootstrap, workflow, and this history, preserve or explicitly supersede affected invariants, validate the complete replacement source set before publication, then update canonical `main` atomically. Validate the resulting Actions artifact after publication.
