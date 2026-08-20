#!/usr/bin/env python3
"""Single-file Execution Continuity Control runtime with discrete pre-action semantics."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CONTROL_VERSION = 6
PAYLOAD_SCHEMA = "execution-continuity-payload-v6"
INITIALIZATION_SCHEMA = "execution-continuity-initialization-v1"
SEMANTIC_PROTOCOL = "execution-semantic-engine-v2"
PREPROCESSOR_PROTOCOL = "prompt-preprocessor-v3"
RECORD_PREFIX = "execution-record_"
RECORD_SUFFIX = ".json"
STAMP_RE = re.compile(r"^execution-record_(\d{8}T\d{12}Z)\.json$")
DIRECTIVES = {"CONTINUE", "COMPLETE", "IMPASSE"}
MAX_PREACTION_RETRIES = 12

ATTENTION_LEVELS = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
INTENT_RELATIONSHIPS = {
    "DIRECT_EXECUTION",
    "NECESSARY_SUPPORT",
    "OPTIONAL_SUPPORT",
    "UNRELATED",
    "CONFLICTS_WITH_INTENT",
    "END_TURN_CANDIDATE",
}
SUBSTITUTE_RELATIONSHIPS = {"DIRECT_EXECUTION", "NECESSARY_SUPPORT", "NONE"}

BEHAVIORAL_INSTRUCTIONS = [
    "The generated bundle is the sole Orchestrator. Act as the Worker only under the current payload.",
    "NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY.",
    "The model-facing task_prompt is the governing task statement for this turn.",
    "TASK_ACTION authorizes exactly one material task action and only the command in that payload.",
    "No material action may begin from an ACTION_PROPOSAL request; ACTION_PROPOSAL authorizes only proposing the next action.",
    "Every proposed material action is evaluated before authorization against the current user-intent context, semantic attention, execution state, and the complete verbose failure-mode definitions.",
    "Semantic evaluation supplies only Boolean or closed-enum decision inputs; it does not supply scores, probabilities, confidence values, or thresholds.",
    "A blocked action and its contextual semantic equivalents are unavailable until materially new user input, governing constraints, or observed state changes the decision context.",
    "After an authorized action completes, fails, or reaches a stop point, return the complete TASK_ACTION payload unchanged to this same bundle before any further material task action.",
    "FINAL_RESPONSE authorizes only construction and delivery of the final user-facing response.",
    "Use observable execution evidence for completion, mutation, persistence, retrieval, validation, and failure claims.",
]

FAILURE_MODE_DEFINITIONS: dict[str, str] = {
    "FAILED_PATH_TREATED_AS_TASK_IMPASSE": """
A proposed action instantiates this failure mode when it stops, refuses, reports whole-task impossibility, or redirects toward termination because one attempted tool, method, command, source, operation, location, representation, dependency, or execution path failed or produced less than the requested result, even though the observed state does not establish that the requested result itself is impossible. Contextual equivalents include treating a local failure as a global limitation, reporting inability after only one failed route, or abandoning the requested objective without exhausting a materially different available route. It does not include a genuine impasse supported by observable evidence that the result cannot be produced through any legitimate available path.
""".strip(),
    "UNINSPECTED_FAILURE_CAUSE": """
A proposed action instantiates this failure mode when it treats an execution failure as a stopping condition, limitation, or reason to change the requested objective before the actual cause of the failure has been inspected or established where inspection is available and material. Contextual equivalents include assuming permission failure, tool incapability, malformed input, missing dependency, or environment limitation from an undiagnosed error. It does not require diagnostic work when the cause is already directly observable or when diagnosis cannot affect the next useful action.
""".strip(),
    "UNVERIFIED_LIMITATION_CLAIM": """
A proposed action instantiates this failure mode when it asserts or acts on a claim that a needed tool, capability, file, source, location, permission, operation, execution route, or environment is unavailable, inaccessible, unsupported, or impossible without direct observation or verification when verification is available. Contextual equivalents include declining to attempt an available connector, assuming write access is absent, or saying a format cannot be produced without testing the relevant mechanism. It does not include limitations directly established by governing instructions or observed tool results.
""".strip(),
    "ALTERNATIVE_PATH_OMISSION": """
A proposed action instantiates this failure mode when a path is blocked but the action stops, refuses, or remains on the blocked route instead of using or testing a materially available alternative that can preserve the requested result. Alternative paths include a different procedure or method, another suitable tool, another source, a usable representation conversion, another location or execution context, reordering independent work, decomposing the blocked operation, retrieving or reconstructing a dependency, or completing requested work that does not depend on the blocked path. It does not require speculative alternatives with no plausible connection to the requested result.
""".strip(),
    "UNSUPPORTED_OR_AVOIDABLE_PREREQUISITE": """
A proposed action instantiates this failure mode when, in context, it introduces or enforces a prerequisite, condition, verification activity, approval, inspection, test, formatting step, process step, certainty threshold, dependency, quality gate, or other obligation that is not required by the user's request or an applicable higher-priority instruction, and that obligation conditions, delays, narrows, redirects, or prevents progress toward a requested result. It also applies when a legitimate requirement exists but the proposed route satisfies it through avoidably burdensome work while a materially simpler legitimate route is available. The action need not call the new element a requirement; it is enough that the contextual relationship makes it function as a precondition. It does not include genuine technical dependencies without which the authorized action cannot be performed.
""".strip(),
    "REDUNDANT_AUTHORIZATION_GATE": """
A proposed action instantiates this failure mode when it asks for permission, approval, confirmation, authorization, or reconfirmation before continuing even though the user's current request already authorizes the action, valid authorization was already granted and not withdrawn, or only implementation wording, tool choice, subtask, command form, or execution context changed while the authorized objective remained the same. It does not include a genuinely new authorization boundary required by governing instructions or a materially new objective not previously authorized.
""".strip(),
    "AVOIDABLE_UNCERTAINTY_GATE": """
A proposed action instantiates this failure mode when it asks the user a question, defers execution, or stops because information is missing, ambiguous, or uncertain even though the exact unknown is nonmaterial to the next useful action, is already resolvable from supplied context, can be retrieved or calculated with an available source or tool, or can be handled by a reasonable non-destructive bounded assumption while preserving useful progress. It does not include uncertainty where materially different values would change the correctness or safety of the next action and no legitimate resolution path exists without user input.
""".strip(),
    "DESCRIPTION_SUBSTITUTION": """
A proposed action instantiates this failure mode when it describes, plans, promises, recommends, or explains an action that can and should be performed now instead of performing the action, where the user requested execution rather than a description of execution. Contextual equivalents include saying what command would be run, what file would be changed, or what search would be performed while withholding the available operation. It does not include cases where the requested deliverable is itself an explanation, plan, specification, or description.
""".strip(),
    "STATUS_RESTATEMENT_SUBSTITUTION": """
A proposed action instantiates this failure mode when it mainly restates the user's request, summarizes instructions, reports status or progress, narrates intended steps, or produces response-shaped text while a requested substantive operation, retrieval, state change, artifact, calculation, or other observable result remains available and unperformed. It does not include concise status communication that accompanies rather than replaces ongoing substantive execution.
""".strip(),
    "INDEPENDENT_WORK_ABANDONMENT": """
A proposed action instantiates this failure mode when execution stops or defers because one requested portion is blocked, failed, or unresolved even though another requested portion remains independently executable and can materially advance the user's objective. Contextual equivalents include treating one missing dependency as a reason not to complete unrelated requested work. It does not require performing work that genuinely depends on the blocked portion.
""".strip(),
    "STALE_CONTEXT_EXECUTION": """
A proposed action instantiates this failure mode when it acts from an earlier request, prior assumption, obsolete state, superseded artifact, or previous task frame that conflicts with the latest applicable user request or already available state. Contextual equivalents include continuing an old plan after the user replaced it, or using stale file identity after a newer canonical state is available. It does not include stable prior context that remains compatible with the latest request.
""".strip(),
    "ASSISTANT_INTRODUCED_OR_OVERBROAD_CONSTRAINT": """
A proposed action instantiates this failure mode when it stops, detours, qualifies, narrows, or demands resolution because of a premise, concern, interpretation, scope element, objective, quality criterion, or constraint introduced by the assistant rather than grounded in the user's request or governing instructions. It also applies when a legitimate source constraint is interpreted more broadly than its actual scope requires and that expansion delays or prevents the requested work. It does not include genuinely applicable higher-priority constraints enforced only to their required scope.
""".strip(),
    "DIRECT_TOOL_SOURCE_BYPASS": """
A proposed action instantiates this failure mode when an unmet requested result depends on an available tool or source directly suited to that requirement, but the proposed action selects a less direct response path, unsupported workaround, speculation, or premature failure report instead of using the directly suited tool or source. It does not require use of a direct tool when the user forbids it, governing instructions prohibit it, or observable evidence establishes that the tool cannot satisfy the requirement.
""".strip(),
    "FALSE_FUTURE_DELEGATION": """
A proposed action instantiates this failure mode when it moves unfinished work into a later message, future turn, background process, promised follow-up, autonomous continuation, or monitoring process that has not actually been invoked and is not capable of carrying out that execution. Contextual equivalents include promising to return later with results or saying work will continue in the background when no real mechanism exists. It does not include an actually invoked scheduled or asynchronous mechanism that is authorized and capable of completing the future action.
""".strip(),
    "DISCUSSION_AS_EXECUTION": """
A proposed action instantiates this failure mode when a non-execution request about an action, design, example, possibility, or concept is misinterpreted as authorization or requirement to perform the discussed action, and the resulting execution delays, gates, or displaces the user's actual request. It does not include execution when the user explicitly requested that the discussed operation be performed.
""".strip(),
    "SUPPORT_PROCESS_INTERFERENCE": """
A proposed action instantiates this failure mode when planning, decomposition, logging, validation, formatting, approval handling, taxonomy construction, testing, inspection, procedural compliance work, or another support process becomes a prerequisite or detour that prevents substantive execution from continuing, unless that support process is explicitly required at that point by the user or a higher-priority instruction. When support work is required, this mode also applies if it is expanded beyond what is necessary and thereby unnecessarily interrupts substantive execution.
""".strip(),
    "UNGROUNDED_STOPPING_REASON": """
A proposed action instantiates this failure mode when it stops, refuses, defers, or materially redirects before the request has been carried as far as currently available information, authority, tools, and legitimate methods permit, and no concrete observable fact or governing constraint establishes that further progress is impossible or inappropriate. It is the residual class for refusal-to-execute behavior not captured more specifically elsewhere. A verified fact does not justify stopping under this definition when changing the execution path can avoid the condition while preserving the requested result.
""".strip(),
    "BLOCKED_ACTION_EQUIVALENCE": """
A proposed action instantiates this failure mode when its contextual semantic function, objective, target, prerequisite role, sequencing effect, or material consequence is equivalent to an action already blocked in the current decision context, even if its wording, tool name, decomposition, or surface procedure differs. This prevents lexical reformulation from bypassing a block. The match should be false when materially new user input, governing constraints, or observed state changes the decision context enough that the previously blocked semantic function is no longer the same action choice.
""".strip(),
}

SEMANTIC_KINDS = {
    "GOAL": "A terminal result or state requested by the user.",
    "ACTION": "An action the user explicitly requests.",
    "OBJECT": "A target, artifact, entity, datum, or other object of meaning.",
    "CONSTRAINT": "A restriction on what may or must occur.",
    "DELIVERABLE": "Something the user expects to receive, observe, or have changed.",
    "CONDITION": "A condition, exception, branch trigger, or contingency.",
    "CONTROL_DIRECTIVE": "A directive about how task handling itself should operate.",
    "REFERENT": "A referring expression whose identity or attachment matters.",
    "MODIFIER": "A quantity, scope, degree, cardinality, or other modifier.",
}
RELATION_KINDS = {
    "OBJECT_OF": "One semantic item is the object or target of another.",
    "MODIFIES": "One item modifies another.",
    "GOVERNS": "One item constrains or governs another.",
    "REFERS_TO": "A referent identifies another item.",
    "CONJUNCT_WITH": "Items are jointly required or coordinated.",
    "ALTERNATIVE_TO": "Items are represented as alternatives.",
    "CONDITION_FOR": "One item supplies a condition for another.",
    "OUTPUT_OF": "A deliverable or result is the output of an action.",
    "SEQUENCED_WITH": "The source explicitly represents relative order.",
    "SCOPE_OVER": "One item defines the semantic scope of another.",
}
FEATURES = {
    "CARDINALITY": "Singular/plural or count semantics.",
    "QUANTITY": "Numeric or amount constraint.",
    "MODALITY": "Required, permitted, optional, hypothetical, or conditional force.",
    "POLARITY": "Positive or negative semantic force.",
    "SCOPE": "The set or proposition over which an expression operates.",
    "REFERENT": "The identity to which a phrase refers.",
    "CONDITION": "The condition under which a proposition applies.",
    "ORDER": "Required relative ordering.",
    "TEMPORAL": "Time or recency semantics.",
    "EXCLUSIVITY": "Only/exactly/exclusively semantics.",
    "COMPLETENESS": "All/every/complete/exhaustive semantics.",
    "DEGREE": "Strength or intensity expressed by the source.",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime | None = None) -> str:
    return (dt or utc_now()).isoformat().replace("+00:00", "Z")


def compact_stamp(dt: datetime | None = None) -> str:
    return (dt or utc_now()).strftime("%Y%m%dT%H%M%S%fZ")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()


def require_text(v: Any, name: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{name} must be non-empty text")
    return v.strip()


def require_bool(v: Any, name: str) -> bool:
    if not isinstance(v, bool):
        raise ValueError(f"{name} must be JSON true or false")
    return v


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def runtime_record_dir() -> Path:
    configured = os.environ.get("EXECUTION_CONTINUITY_RECORD_DIR")
    if configured:
        return Path(configured)
    base = Path("/mnt/data")
    if base.exists() and os.access(base, os.W_OK):
        return base
    return Path.cwd()


def list_records(directory: Path) -> list[tuple[datetime, Path]]:
    if not directory.exists():
        return []
    found = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        match = STAMP_RE.fullmatch(path.name)
        if not match:
            continue
        try:
            timestamp = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        found.append((timestamp, path))
    return sorted(found, key=lambda item: item[0])


def record_create(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{RECORD_PREFIX}{compact_stamp()}{RECORD_SUFFIX}"
    while path.exists():
        path = directory / f"{RECORD_PREFIX}{compact_stamp(utc_now() + timedelta(microseconds=1))}{RECORD_SUFFIX}"
    write_json_atomic(path, {
        "schema": "execution-continuity-record-v3",
        "created_at": iso_utc(),
        "updated_at": iso_utc(),
        "last_sequence": 0,
        "actions": [],
    })
    return path


def record_latest(directory: Path) -> dict[str, Any]:
    records = list_records(directory)
    path = records[-1][1] if records else record_create(directory)
    data = read_json(path)
    return {"record": str(path), "record_name": path.name, "action_count": int(data.get("last_sequence", 0))}


def record_append(record_state: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    path = Path(record_state["record"])
    data = read_json(path)
    sequence = int(data.get("last_sequence", 0)) + 1
    item = {"sequence": sequence, "timestamp": iso_utc(), **action}
    data.setdefault("actions", []).append(item)
    data["last_sequence"] = sequence
    data["updated_at"] = iso_utc()
    write_json_atomic(path, data)
    record_state["action_count"] = sequence
    return item


def semantic_question(question_id: str, semantic_function: str, instruction: str, inputs: dict[str, Any], response_schema: dict[str, Any], constraints: list[str], validator, protocol: str = SEMANTIC_PROTOCOL) -> Any:
    prompt = {"protocol": protocol, "question_id": question_id, "semantic_function": semantic_function, "instruction": instruction, "inputs": inputs, "response_schema": response_schema, "constraints": constraints}
    while True:
        print(json.dumps(prompt, ensure_ascii=False), flush=True)
        line = sys.stdin.readline()
        if line == "":
            raise EOFError(f"EOF waiting for {question_id}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            prompt = {**prompt, "validation_error": f"Response must be one JSON value: {exc}"}
            continue
        try:
            validator(value)
            return value
        except Exception as exc:
            prompt = {**prompt, "validation_error": str(exc)}


def _validate_context_map(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"semantic_items", "relations", "ambiguities"}:
        raise ValueError(f"{name} must contain semantic_items, relations, ambiguities")
    items = value["semantic_items"]
    if not isinstance(items, list) or not items:
        raise ValueError(f"{name}.semantic_items must be non-empty")
    ids = set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict) or set(item) != {"id", "kind", "meaning", "features"}:
            raise ValueError(f"{name}.semantic_items[{index}] invalid")
        if item["id"] != f"S{index}" or item["kind"] not in SEMANTIC_KINDS:
            raise ValueError(f"{name}.semantic_items IDs or kind invalid")
        require_text(item["meaning"], f"{name}.meaning")
        if not isinstance(item["features"], dict) or any(key not in FEATURES for key in item["features"]):
            raise ValueError(f"{name}.features invalid")
        ids.add(item["id"])
    relations = value["relations"]
    if not isinstance(relations, list):
        raise ValueError(f"{name}.relations must be an array")
    for index, rel in enumerate(relations, 1):
        if not isinstance(rel, dict) or set(rel) != {"id", "kind", "from_id", "to_id", "meaning"}:
            raise ValueError(f"{name}.relations[{index}] invalid")
        if rel["id"] != f"R{index}" or rel["kind"] not in RELATION_KINDS:
            raise ValueError(f"{name}.relation ID or kind invalid")
        if rel["from_id"] not in ids or rel["to_id"] not in ids:
            raise ValueError(f"{name}.relation references unknown semantic item")
        require_text(rel["meaning"], f"{name}.relation meaning")
    ambiguities = value["ambiguities"]
    if not isinstance(ambiguities, list):
        raise ValueError(f"{name}.ambiguities must be an array")
    for index, ambiguity in enumerate(ambiguities, 1):
        if not isinstance(ambiguity, dict) or set(ambiguity) != {"id", "subject", "interpretations", "material"}:
            raise ValueError(f"{name}.ambiguities[{index}] invalid")
        if ambiguity["id"] != f"U{index}" or not isinstance(ambiguity["material"], bool):
            raise ValueError(f"{name}.ambiguity invalid")
        require_text(ambiguity["subject"], f"{name}.ambiguity subject")
        if not isinstance(ambiguity["interpretations"], list) or len(ambiguity["interpretations"]) < 2:
            raise ValueError(f"{name}.ambiguity interpretations invalid")
    return value


def context_map(text: str, question_id: str, semantic_function: str) -> dict[str, Any]:
    return semantic_question(
        question_id,
        semantic_function,
        "Create a contextual semantic decomposition of prompt_text. Map meaning actually expressed or necessarily represented by the text. Preserve referents, scope, modality, polarity, ordering, conditions, cardinality, exclusions, and control directives. Do not invent execution strategy, quality criteria, prerequisites, or constraints.",
        {"prompt_text": text},
        {
            "semantic_items": [{"id": "S#", "kind": "SEMANTIC_KIND", "meaning": "string", "features": {"FEATURE": "value"}}],
            "relations": [{"id": "R#", "kind": "RELATION_KIND", "from_id": "S#", "to_id": "S#", "meaning": "string"}],
            "ambiguities": [{"id": "U#", "subject": "string", "interpretations": ["string", "string"], "material": False}],
        },
        ["Semantic kinds: " + " | ".join(f"{k} — {v}" for k, v in SEMANTIC_KINDS.items()), "Relation kinds: " + " | ".join(f"{k} — {v}" for k, v in RELATION_KINDS.items()), "Feature names: " + " | ".join(f"{k} — {v}" for k, v in FEATURES.items()), "Do not execute the user task."],
        lambda value: _validate_context_map(value, question_id),
    )


def intent_attention_map(task_prompt: str, intent_map: dict[str, Any]) -> dict[str, Any]:
    item_ids = {item["id"] for item in intent_map["semantic_items"]}
    relation_ids = {item["id"] for item in intent_map["relations"]}
    def validate(value: Any) -> None:
        if not isinstance(value, dict) or set(value) != {"item_attention", "relation_attention"}:
            raise ValueError("attention map invalid")
        items = value["item_attention"]
        if not isinstance(items, list) or {x.get("semantic_item_id") for x in items if isinstance(x, dict)} != item_ids:
            raise ValueError("item_attention must cover every semantic item")
        for item in items:
            if set(item) != {"semantic_item_id", "attention", "reason"} or item["attention"] not in ATTENTION_LEVELS:
                raise ValueError("item_attention entry invalid")
            require_text(item["reason"], "attention reason")
        relations = value["relation_attention"]
        if not isinstance(relations, list) or {x.get("relation_id") for x in relations if isinstance(x, dict)} != relation_ids:
            raise ValueError("relation_attention must cover every relation")
        for item in relations:
            if set(item) != {"relation_id", "attention", "reason"} or item["attention"] not in ATTENTION_LEVELS:
                raise ValueError("relation_attention entry invalid")
            require_text(item["reason"], "attention reason")
    return semantic_question(
        "PA2",
        "MAP_USER_INTENT_ATTENTION",
        "Assign one closed attention category to every user-intent semantic item and relation. Attention identifies semantic salience and fragility; it is not a score. Explicit requested end states, prohibitions, exclusions, ordering constraints, scope boundaries, and direct control directives normally receive high attention. Do not invent new requirements.",
        {"task_prompt": task_prompt, "intent_context_map": intent_map},
        {"item_attention": [{"semantic_item_id": "S#", "attention": "CRITICAL | HIGH | MEDIUM | LOW", "reason": "string"}], "relation_attention": [{"relation_id": "R#", "attention": "CRITICAL | HIGH | MEDIUM | LOW", "reason": "string"}]},
        ["Choose exactly one attention enum for each mapped item and relationship."],
        validate,
    )


def run_prompt_preprocessor(original_prompt: str) -> dict[str, Any]:
    source_map = context_map(original_prompt, "PP1", "MAP_SOURCE_CONTEXT")
    if any(item["material"] for item in source_map["ambiguities"]):
        return {"status": "FALLBACK", "reason": "MATERIAL_AMBIGUITY", "task_prompt": original_prompt}
    def validate_edit(value: Any) -> None:
        expected = {"candidate_task_prompt", "semantically_equivalent", "added_requirements", "note"}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("PP2 response invalid")
        require_text(value["candidate_task_prompt"], "candidate_task_prompt")
        require_bool(value["semantically_equivalent"], "semantically_equivalent")
        if not isinstance(value["added_requirements"], list):
            raise ValueError("added_requirements must be array")
        require_text(value["note"], "note")
    edited = semantic_question(
        "PP2",
        "SOURCE_RELATIVE_SEMANTIC_EDIT",
        "Produce a minimally edited candidate task prompt from original_user_prompt. Preserve all mapped semantics. Do not add execution strategy, methods, quality criteria, deliverables, assumptions, constraints, scope, or requirements. Return semantically_equivalent as JSON true or false, not a score. If no edit is needed, return the original text exactly.",
        {"original_user_prompt": original_prompt, "source_context_map": source_map},
        {"candidate_task_prompt": "string", "semantically_equivalent": True, "added_requirements": ["string"], "note": "string"},
        ["Semantic equivalence is a Boolean semantic judgment, not a degree or confidence value."],
        validate_edit,
        protocol=PREPROCESSOR_PROTOCOL,
    )
    if not edited["semantically_equivalent"] or edited["added_requirements"]:
        return {"status": "FALLBACK", "reason": "SEMANTIC_EDIT_REJECTED", "task_prompt": original_prompt}
    candidate = edited["candidate_task_prompt"]
    candidate_map = context_map(candidate, "PP3", "REMAP_CANDIDATE_CONTEXT")
    def validate_audit(value: Any) -> None:
        expected = {"equivalent", "missing_meaning", "added_meaning", "changed_relationships"}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("PP4 response invalid")
        require_bool(value["equivalent"], "equivalent")
        for key in ("missing_meaning", "added_meaning", "changed_relationships"):
            if not isinstance(value[key], list):
                raise ValueError(f"{key} must be array")
    audit = semantic_question(
        "PP4",
        "AUDIT_PROMPT_EQUIVALENCE",
        "Compare source and candidate context maps and answer equivalent using JSON true or false. Any added requirement, omitted meaning, changed referent, scope, modality, polarity, ordering, condition, cardinality, exclusion, or relationship makes equivalent false.",
        {"original_user_prompt": original_prompt, "source_context_map": source_map, "candidate_task_prompt": candidate, "candidate_context_map": candidate_map},
        {"equivalent": True, "missing_meaning": ["string"], "added_meaning": ["string"], "changed_relationships": ["string"]},
        ["Do not return a score or confidence value."],
        validate_audit,
        protocol=PREPROCESSOR_PROTOCOL,
    )
    if not audit["equivalent"] or audit["missing_meaning"] or audit["added_meaning"] or audit["changed_relationships"]:
        return {"status": "FALLBACK", "reason": "SEMANTIC_AUDIT_FAILED", "task_prompt": original_prompt, "audit": audit}
    return {"status": "ACCEPTED", "reason": None, "task_prompt": candidate, "source_context_map": source_map, "candidate_context_map": candidate_map, "audit": audit}


def ask_action_proposal(state: dict[str, Any], instruction: str, excluded: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    excluded = excluded or []
    prompt = {"protocol": "pre-action-control", "type": "PROPOSE_ACTION", "instruction": instruction, "task_prompt": state["task_prompt"], "execution_state": state.get("execution_summary", {}), "excluded_blocked_actions": excluded, "response_schema": {"action": "one concrete next material action clause, or END_TURN", "purpose": "concise contextual purpose", "expected_effect": "concise expected material effect"}, "constraints": ["Do not perform the action yet.", "Propose one action only.", "If excluded_blocked_actions is non-empty, do not propose the same action or a contextual semantic equivalent."]}
    while True:
        print(json.dumps(prompt, ensure_ascii=False), flush=True)
        line = sys.stdin.readline()
        if line == "":
            raise EOFError("EOF waiting for action proposal")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            prompt = {**prompt, "validation_error": f"Response must be one JSON object: {exc}"}
            continue
        try:
            if not isinstance(value, dict) or set(value) != {"action", "purpose", "expected_effect"}:
                raise ValueError("proposal must contain exactly action, purpose, expected_effect")
            require_text(value["action"], "proposal.action")
            require_text(value["purpose"], "proposal.purpose")
            require_text(value["expected_effect"], "proposal.expected_effect")
            return value
        except Exception as exc:
            prompt = {**prompt, "validation_error": str(exc)}


def _validate_failure_evaluation(value: Any) -> None:
    expected = {"intent_relationship", "failure_matches", "semantic_basis", "blocked_action_descriptor", "substitute_action", "substitute_relationship"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"evaluation must contain exactly {sorted(expected)}")
    if value["intent_relationship"] not in INTENT_RELATIONSHIPS:
        raise ValueError("intent_relationship invalid")
    matches = value["failure_matches"]
    if not isinstance(matches, dict) or set(matches) != set(FAILURE_MODE_DEFINITIONS):
        raise ValueError("failure_matches must contain exactly every supplied failure mode")
    for mode, matched in matches.items():
        require_bool(matched, f"failure_matches.{mode}")
    basis = value["semantic_basis"]
    if not isinstance(basis, dict) or set(basis) != {"intent_units", "action_units", "relationships", "attention_effect", "explanation"}:
        raise ValueError("semantic_basis invalid")
    for key in ("intent_units", "action_units", "relationships"):
        if not isinstance(basis[key], list):
            raise ValueError(f"semantic_basis.{key} must be array")
    require_text(basis["attention_effect"], "semantic_basis.attention_effect")
    require_text(basis["explanation"], "semantic_basis.explanation")
    descriptor = value["blocked_action_descriptor"]
    if not isinstance(descriptor, dict) or set(descriptor) != {"objective", "target", "operation", "contextual_function", "material_effect"}:
        raise ValueError("blocked_action_descriptor invalid")
    for key in descriptor:
        require_text(descriptor[key], f"blocked_action_descriptor.{key}")
    substitute = value["substitute_action"]
    if substitute is not None:
        require_text(substitute, "substitute_action")
    if value["substitute_relationship"] not in SUBSTITUTE_RELATIONSHIPS:
        raise ValueError("substitute_relationship invalid")
    if substitute is None and value["substitute_relationship"] != "NONE":
        raise ValueError("substitute_relationship must be NONE when substitute_action is null")
    if substitute is not None and value["substitute_relationship"] == "NONE":
        raise ValueError("substitute_relationship cannot be NONE when substitute_action is present")


def evaluate_proposed_action(state: dict[str, Any], proposal: dict[str, Any], origin: str) -> dict[str, Any]:
    return semantic_question(
        f"PAE-{uuid.uuid4().hex[:8]}",
        "CLASSIFY_ACTION_CONTEXT_AND_FAILURE_MODES",
        "Contextually decompose the proposed action and classify it using only the supplied Boolean and enumerated decision parameters. For EACH verbose failure-mode definition, answer whether the proposed action instantiates that mode or a contextual semantic equivalent: true means YES, false means NO. Also select exactly one intent_relationship enum. Do not score, rank, weight, estimate confidence, or return probabilities. Use blocked_action descriptors when classifying BLOCKED_ACTION_EQUIVALENCE. If a nearest materially direct prompt-supported substitute is apparent, return it and classify its relationship; otherwise return null and NONE.",
        {"task_prompt": state["task_prompt"], "user_intent_context_map": state["intent_context_map"], "user_intent_attention_map": state["intent_attention_map"], "current_execution_state": state.get("execution_summary", {}), "proposed_action": proposal, "proposal_origin": origin, "blocked_actions": state.get("blocked_actions", []), "failure_mode_definitions": FAILURE_MODE_DEFINITIONS},
        {"intent_relationship": "DIRECT_EXECUTION | NECESSARY_SUPPORT | OPTIONAL_SUPPORT | UNRELATED | CONFLICTS_WITH_INTENT | END_TURN_CANDIDATE", "failure_matches": {mode: False for mode in FAILURE_MODE_DEFINITIONS}, "semantic_basis": {"intent_units": ["string"], "action_units": ["string"], "relationships": ["string"], "attention_effect": "string", "explanation": "string"}, "blocked_action_descriptor": {"objective": "string", "target": "string", "operation": "string", "contextual_function": "string", "material_effect": "string"}, "substitute_action": None, "substitute_relationship": "DIRECT_EXECUTION | NECESSARY_SUPPORT | NONE"},
        ["Every failure mode definition is supplied in full and must receive exactly one Boolean answer.", "Evaluate semantic function and contextual effect, not lexical overlap.", "Attention categories identify which intent features dominate the classification; do not convert them to numbers.", "A matched failure mode is a categorical fact for the deterministic engine, not a degree of similarity.", "Do not perform the action.", "Do not convert prudence, preference, or an execution strategy into a user requirement."],
        _validate_failure_evaluation,
    )


def deterministic_action_decision(evaluation: dict[str, Any]) -> dict[str, Any]:
    matched = [mode for mode, value in evaluation["failure_matches"].items() if value]
    if matched:
        substitute = evaluation.get("substitute_action")
        substitute_relationship = evaluation.get("substitute_relationship")
        if substitute and substitute_relationship in {"DIRECT_EXECUTION", "NECESSARY_SUPPORT"}:
            return {"decision": "EVALUATE_SUBSTITUTE", "action": substitute, "reason": matched[0], "matched_failure_modes": matched}
        return {"decision": "MODEL_SELECT_EXCLUDING_BLOCKED", "reason": matched[0], "matched_failure_modes": matched}
    relationship = evaluation["intent_relationship"]
    if relationship in {"DIRECT_EXECUTION", "NECESSARY_SUPPORT", "END_TURN_CANDIDATE"}:
        return {"decision": "CONTINUE_CANDIDATE", "matched_failure_modes": []}
    return {"decision": "MODEL_SELECT_EXCLUDING_BLOCKED", "reason": f"INTENT_RELATIONSHIP_{relationship}", "matched_failure_modes": []}


def pre_action_control(state: dict[str, Any], initial_instruction: str) -> dict[str, Any]:
    proposal = ask_action_proposal(state, initial_instruction, state.get("blocked_actions", []))
    origin = "MODEL"
    for _ in range(MAX_PREACTION_RETRIES):
        evaluation = evaluate_proposed_action(state, proposal, origin)
        decision = deterministic_action_decision(evaluation)
        record_append(state["record_state"], {"action_type": "pre_action_evaluation", "scope": "worker", "proposal": proposal, "evaluation": evaluation, "deterministic_decision": decision})
        if proposal["action"].strip().upper() == "END_TURN":
            if decision["decision"] == "CONTINUE_CANDIDATE":
                return {"terminal_candidate": True, "proposal": proposal, "evaluation": evaluation}
            descriptor = evaluation["blocked_action_descriptor"]
            state.setdefault("blocked_actions", []).append({**descriptor, "blocked_reason": decision.get("reason"), "matched_failure_modes": decision.get("matched_failure_modes", []), "blocked_at_sequence": state["record_state"]["action_count"]})
            proposal = ask_action_proposal(state, "The end-turn action was blocked. Select the next useful material action toward task_prompt, excluding the blocked action and contextual semantic equivalents.", state["blocked_actions"])
            origin = "MODEL_RESELECT"
            continue
        if decision["decision"] == "CONTINUE_CANDIDATE":
            return {"terminal_candidate": False, "proposal": proposal, "evaluation": evaluation}
        descriptor = evaluation["blocked_action_descriptor"]
        state.setdefault("blocked_actions", []).append({**descriptor, "blocked_reason": decision.get("reason"), "matched_failure_modes": decision.get("matched_failure_modes", []), "blocked_at_sequence": state["record_state"]["action_count"]})
        if decision["decision"] == "EVALUATE_SUBSTITUTE":
            proposal = {"action": decision["action"], "purpose": "Semantic evaluator supplied the nearest prompt-supported substitute.", "expected_effect": "Advance the user intent while avoiding the blocked failure-mode behavior."}
            origin = "SEMANTIC_ENGINE_SUBSTITUTE"
            continue
        proposal = ask_action_proposal(state, "Select a different next material action toward task_prompt. The prior candidate is blocked; exclude it and all contextual semantic equivalents represented in excluded_blocked_actions.", state["blocked_actions"])
        origin = "MODEL_RESELECT"
    raise RuntimeError("pre-action control exceeded maximum candidate retries")


def run_terminal_check(state: dict[str, Any]) -> dict[str, Any]:
    completion_states = {"COMPLETE", "INCOMPLETE"}
    impasse_states = {"ESTABLISHED", "NOT_ESTABLISHED"}
    def validate(value: Any) -> None:
        expected = {"directive", "completion_state", "impasse_state", "remaining_gaps", "observable_basis"}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("terminal check response invalid")
        if value["directive"] not in DIRECTIVES or value["completion_state"] not in completion_states or value["impasse_state"] not in impasse_states:
            raise ValueError("terminal categorical response invalid")
        if not isinstance(value["remaining_gaps"], list):
            raise ValueError("remaining_gaps must be array")
        require_text(value["observable_basis"], "observable_basis")
    result = semantic_question(
        "TERMINAL",
        "TERMINAL_COMPLETION_OR_IMPASSE_CHECK",
        "Select closed categorical answers only. COMPLETE requires the requested result to be actually delivered or ready for final delivery with no material requested gap. IMPASSE requires an observable grounded condition preventing legitimate further progress through available paths. Otherwise select CONTINUE. Do not return scores or confidence values.",
        {"task_prompt": state["task_prompt"], "user_intent_context_map": state["intent_context_map"], "user_intent_attention_map": state["intent_attention_map"], "execution_state": state.get("execution_summary", {}), "blocked_actions": state.get("blocked_actions", [])},
        {"directive": "CONTINUE | COMPLETE | IMPASSE", "completion_state": "COMPLETE | INCOMPLETE", "impasse_state": "ESTABLISHED | NOT_ESTABLISHED", "remaining_gaps": ["string"], "observable_basis": "string"},
        ["Do not use a previously blocked failure-mode behavior as evidence of impasse.", "A failed path alone is not a task impasse.", "The deterministic engine will reject internally inconsistent categorical combinations."],
        validate,
    )
    if result["directive"] == "COMPLETE" and (result["completion_state"] != "COMPLETE" or result["remaining_gaps"]):
        result["directive"] = "CONTINUE"
    if result["directive"] == "IMPASSE" and result["impasse_state"] != "ESTABLISHED":
        result["directive"] = "CONTINUE"
    if result["directive"] == "CONTINUE" and result["completion_state"] == "COMPLETE" and not result["remaining_gaps"]:
        result["directive"] = "COMPLETE"
    return result


def seal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    base = {key: value for key, value in payload.items() if key != "payload_sha256"}
    payload["payload_sha256"] = sha256_json(base)
    return payload


def verify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema") != PAYLOAD_SCHEMA:
        raise ValueError("invalid payload schema")
    expected = payload.get("payload_sha256")
    base = {key: value for key, value in payload.items() if key != "payload_sha256"}
    if not isinstance(expected, str) or sha256_json(base) != expected:
        raise ValueError("payload integrity failure")
    if payload.get("authority") not in {"TASK_ACTION", "FINAL_RESPONSE"}:
        raise ValueError("invalid authority")
    if not isinstance(payload.get("state"), dict):
        raise ValueError("state missing")
    return payload


def new_state(user_prompt: str) -> dict[str, Any]:
    require_text(user_prompt, "initialization.user_prompt")
    record_state = record_latest(runtime_record_dir())
    return {"control_version": CONTROL_VERSION, "sequence": 1, "record_state": record_state, "turn_start_action_count": record_state["action_count"], "original_user_prompt": user_prompt, "task_prompt": user_prompt, "prompt_intake_mode": "VERBATIM", "preprocessor_requested": False, "preprocessor_status": "NOT_REQUESTED", "intent_context_map": None, "intent_attention_map": None, "blocked_actions": [], "execution_summary": {"authorized_actions": [], "observed_failures": [], "verified_limitations": [], "completed_results": []}}


def issue_task_payload(state: dict[str, Any], proposal: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    command = require_text(proposal["action"], "proposal.action")
    return seal_payload({"schema": PAYLOAD_SCHEMA, "authority": "TASK_ACTION", "task_prompt": state["task_prompt"], "command": command, "context": {"pre_action_decision": "CONTINUE_CANDIDATE", "proposal": proposal, "evaluation": evaluation, "blocked_actions": state.get("blocked_actions", [])}, "behavioral_instructions": BEHAVIORAL_INSTRUCTIONS, "state": state})


def issue_final_payload(state: dict[str, Any], terminal: dict[str, Any]) -> dict[str, Any]:
    record_path = Path(state["record_state"]["record"])
    record_content = read_json(record_path) if record_path.exists() else None
    return seal_payload({"schema": PAYLOAD_SCHEMA, "authority": "FINAL_RESPONSE", "task_prompt": state["task_prompt"], "command": "Construct and deliver the final user-facing response satisfying task_prompt from the current conversation and terminal context. Do not perform additional substantive task work.", "context": {"terminal_result": terminal, "execution_record_path": str(record_path), "execution_record_filename": record_path.name, "execution_record": record_content, "current_turn_action_range": {"start_sequence": state["turn_start_action_count"] + 1, "end_sequence": state["record_state"]["action_count"]}}, "behavioral_instructions": BEHAVIORAL_INSTRUCTIONS, "state": state})


def ask_post_action_report(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = {"protocol": "post-action-record", "instruction": "Report only the observable result of the single authorized action just attempted. This is evidence recording, not a behavioral questionnaire and grants no authority for another action.", "authorized_action": payload["command"], "response_schema": {"status": "COMPLETED | PARTIAL | FAILED", "observable_evidence": ["string"], "state_changes": ["string"], "remaining_gap": "string or NONE"}}
    while True:
        print(json.dumps(prompt, ensure_ascii=False), flush=True)
        line = sys.stdin.readline()
        if line == "":
            raise EOFError("EOF waiting for post-action report")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            prompt = {**prompt, "validation_error": f"Response must be one JSON object: {exc}"}
            continue
        try:
            if not isinstance(value, dict) or set(value) != {"status", "observable_evidence", "state_changes", "remaining_gap"}:
                raise ValueError("post-action report invalid")
            if value["status"] not in {"COMPLETED", "PARTIAL", "FAILED"}:
                raise ValueError("post-action status invalid")
            if not isinstance(value["observable_evidence"], list) or not isinstance(value["state_changes"], list):
                raise ValueError("evidence and state_changes must be arrays")
            require_text(value["remaining_gap"], "remaining_gap")
            return value
        except Exception as exc:
            prompt = {**prompt, "validation_error": str(exc)}


def process_returned_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = verify_payload(payload)
    if payload["authority"] != "TASK_ACTION":
        raise ValueError("only TASK_ACTION payloads may be returned to the bundle")
    state = payload["state"]
    report = ask_post_action_report(payload)
    record_append(state["record_state"], {"action_type": "authorized_action_result", "scope": "worker", "authorized_action": payload["command"], "report": report})
    state["execution_summary"]["authorized_actions"].append({"action": payload["command"], "status": report["status"], "evidence": report["observable_evidence"], "state_changes": report["state_changes"], "remaining_gap": report["remaining_gap"]})
    if report["status"] == "FAILED":
        state["execution_summary"]["observed_failures"].append({"action": payload["command"], "evidence": report["observable_evidence"], "remaining_gap": report["remaining_gap"]})
    if report["status"] == "COMPLETED":
        state["execution_summary"]["completed_results"].extend(report["observable_evidence"] or report["state_changes"])
    state["sequence"] += 1
    control = pre_action_control(state, "Propose the single next material action toward task_prompt, or END_TURN only if no further material action is needed.")
    if control["terminal_candidate"]:
        terminal = run_terminal_check(state)
        record_append(state["record_state"], {"action_type": "terminal_check", "scope": "worker", "result": terminal})
        if terminal["directive"] in {"COMPLETE", "IMPASSE"}:
            return issue_final_payload(state, terminal)
        control = pre_action_control(state, "Terminal check returned CONTINUE. Propose the next useful material action toward task_prompt; do not end the turn yet.")
    return issue_task_payload(state, control["proposal"], control["evaluation"])


def parse_initialization(value: Any) -> tuple[str, bool]:
    if not isinstance(value, dict):
        raise ValueError("initialization must be an object")
    required = {"schema", "type", "user_prompt"}
    allowed = required | {"preprocessor"}
    if not required.issubset(value) or not set(value).issubset(allowed):
        raise ValueError("initialization object must contain schema, type, and user_prompt, with only optional preprocessor")
    if value.get("schema") != INITIALIZATION_SCHEMA or value.get("type") != "INITIALIZE":
        raise ValueError("initialization schema or type invalid")
    requested = "preprocessor" in value
    if requested and value.get("preprocessor") is not True:
        raise ValueError("when present, initialization.preprocessor must be JSON true")
    return require_text(value["user_prompt"], "initialization.user_prompt"), requested


def process_initialization(value: Any) -> dict[str, Any]:
    user_prompt, preprocessor_requested = parse_initialization(value)
    state = new_state(user_prompt)
    state["preprocessor_requested"] = preprocessor_requested
    if preprocessor_requested:
        try:
            result = run_prompt_preprocessor(user_prompt)
            state["task_prompt"] = result["task_prompt"]
            state["preprocessor_status"] = result["status"]
            state["preprocessor_reason"] = result.get("reason")
            state["prompt_intake_mode"] = "SOURCE_ANCHORED_SEMANTIC_EDIT" if result["status"] == "ACCEPTED" else "VERBATIM_FALLBACK"
            state["preprocessor_result"] = result
        except Exception as exc:
            state["task_prompt"] = user_prompt
            state["prompt_intake_mode"] = "VERBATIM_FALLBACK"
            state["preprocessor_status"] = "FALLBACK"
            state["preprocessor_reason"] = "PROTOCOL_ERROR"
            state["preprocessor_error"] = {"type": type(exc).__name__, "detail": str(exc)}
    state["intent_context_map"] = context_map(state["task_prompt"], "PA1", "MAP_USER_INTENT_CONTEXT")
    state["intent_attention_map"] = intent_attention_map(state["task_prompt"], state["intent_context_map"])
    record_append(state["record_state"], {"action_type": "turn_intent_map", "scope": "worker", "task_prompt": state["task_prompt"], "intent_context_map": state["intent_context_map"], "intent_attention_map": state["intent_attention_map"]})
    control = pre_action_control(state, "Propose the single first material action toward task_prompt. Do not execute it yet.")
    if control["terminal_candidate"]:
        terminal = run_terminal_check(state)
        record_append(state["record_state"], {"action_type": "terminal_check", "scope": "worker", "result": terminal})
        if terminal["directive"] in {"COMPLETE", "IMPASSE"}:
            return issue_final_payload(state, terminal)
        control = pre_action_control(state, "Terminal check returned CONTINUE. Propose the first useful material action toward task_prompt.")
    return issue_task_payload(state, control["proposal"], control["evaluation"])


def emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    first = sys.stdin.readline()
    if first == "" or not first.strip():
        print(json.dumps({"schema": PAYLOAD_SCHEMA, "authority": "NONE", "execution_authority": False, "error": "InitializationRequired", "detail": f"Invoke with one JSON line using schema {INITIALIZATION_SCHEMA} and type INITIALIZE, or return a previously issued TASK_ACTION payload."}, ensure_ascii=False), flush=True)
        return 2
    try:
        value = json.loads(first)
        if isinstance(value, dict) and value.get("schema") == INITIALIZATION_SCHEMA:
            return emit(process_initialization(value))
        return emit(process_returned_payload(value))
    except Exception as exc:
        print(json.dumps({"schema": PAYLOAD_SCHEMA, "authority": "NONE", "execution_authority": False, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
