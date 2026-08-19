#!/usr/bin/env python3
"""Structured post-action questionnaire and end-turn-router proxy.

The recorder starts this script after persisting a ``recorder_invocation``.
The questioner owns a structured post-action interrogation that decomposes user
intent, atomic execution units, plan/path relations, evidence, outcomes,
decision bases, counterfactuals, and one constrained narrative mapping note.

For every question that uses enumerated values, the question payload co-presents
canonical definition tables. The questioner validates only answer shape,
enumerated legality, ordering, and internal references. It does not judge the
truth of the model's answers or derive conclusions from them.

AQ1 is the sole end-turn discriminator and accepts YES/NO with Y/N aliases.
After the questionnaire is complete, the questioner emits the
``QUESTIONER_ACTION_OVER`` signal together with the formatted questionnaire
object. The object is appended through the recorder. If AQ1 is YES, the
questioner then invokes and proxies ``end_turn_router.py``. The router never
writes the execution record directly.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCOPES = {"worker", "orchestrator"}

YES_NO = [
    {"value": "YES", "definition": "The stated condition is true for the recorded activity."},
    {"value": "NO", "definition": "The stated condition is not true for the recorded activity."},
]

ACTION_TYPES = [
    {"value": "ACQUIRE", "definition": "Obtain information, content, state, or evidence not already available in the active execution state."},
    {"value": "TRANSFORM", "definition": "Derive a new representation, structure, computation, or synthesis from existing information without deciding whether it is acceptable or preferable."},
    {"value": "EVALUATE", "definition": "Judge an object, result, proposition, or state against criteria."},
    {"value": "DECIDE", "definition": "Select, reject, prioritize, defer, or otherwise choose among available execution paths."},
    {"value": "ACT", "definition": "Cause or request an external or persistent state change, or execute an operation capable of producing one."},
    {"value": "OBSERVE", "definition": "Receive or inspect the result or state produced by an earlier operation."},
    {"value": "COMMUNICATE", "definition": "Send information, a question, instruction, result, or control signal to another actor or execution layer."},
]

ACTION_SUBTYPES = {
    "ACQUIRE": [
        ("READ", "Obtain content from a known source."),
        ("SEARCH", "Discover candidate information or resources when the exact source is not already known."),
        ("RETRIEVE", "Fetch a specifically identified resource or previously stored state."),
    ],
    "TRANSFORM": [
        ("CALCULATE", "Produce a value by mathematical or algorithmic computation."),
        ("DECOMPOSE", "Break an object, requirement, plan, or problem into constituent elements."),
        ("SYNTHESIZE", "Combine multiple inputs into a new integrated representation."),
        ("CONVERT", "Change representation or format while substantially preserving meaning."),
        ("EXTRACT", "Select and structure relevant portions from a larger input."),
    ],
    "EVALUATE": [
        ("COMPARE", "Determine similarities, differences, or relative properties between alternatives or states."),
        ("CLASSIFY", "Assign an item to a defined category without selecting an execution path."),
        ("VALIDATE", "Test whether something satisfies explicit requirements or invariants."),
        ("SCORE", "Assign an ordinal or quantitative evaluation according to criteria."),
    ],
    "DECIDE": [
        ("SELECT", "Choose one available alternative or next action."),
        ("REJECT", "Explicitly eliminate an alternative from further execution."),
        ("PRIORITIZE", "Establish execution order or preference among multiple alternatives."),
        ("DEFER", "Intentionally postpone a choice or action because its prerequisite state is not yet satisfied."),
    ],
    "ACT": [
        ("CREATE", "Cause a new persistent artifact or state object to exist."),
        ("MODIFY", "Change an existing persistent artifact or state."),
        ("DELETE", "Remove an existing persistent artifact or state."),
        ("EXECUTE", "Run code, a script, command, or other executable procedure."),
        ("CALL", "Invoke an external tool, API, service, or executable interface to perform an operation."),
    ],
    "OBSERVE": [
        ("INSPECT", "Examine resulting state or output after an operation."),
        ("RECEIVE", "Accept a result, return value, message, or callback from another actor or tool."),
        ("DETECT_ERROR", "Observe an explicit failure, exception, contradiction, or invalid result."),
        ("DETECT_CHANGE", "Observe that relevant state changed from an earlier state."),
    ],
    "COMMUNICATE": [
        ("ASK", "Request information or a decision from another actor."),
        ("RETURN", "Return control, data, or a result to the invoking actor."),
        ("REPORT", "Communicate execution state or findings without transferring control."),
        ("INSTRUCT", "Supply an instruction that another actor is expected to execute."),
        ("SIGNAL", "Emit a defined machine-interpretable control signal."),
    ],
}
ACTION_SUBTYPE_ROWS = [
    {"value": subtype, "parent": parent, "definition": definition}
    for parent, rows in ACTION_SUBTYPES.items()
    for subtype, definition in rows
]
ACTION_TYPE_VALUES = {row["value"] for row in ACTION_TYPES}
ACTION_SUBTYPE_VALUES = {parent: {value for value, _ in rows} for parent, rows in ACTION_SUBTYPES.items()}

INTENT_RELATIONS = [
    {"value": "DIRECT", "definition": "The action itself directly produced or attempted to produce the state required by the mapped intent item or items."},
    {"value": "SUPPORTING", "definition": "The action enabled, informed, validated, or prepared another action that directly advanced the mapped intent item or items."},
    {"value": "NONE", "definition": "No material relationship between this action and a user-intent item is identified."},
    {"value": "OBSTRUCTED", "definition": "The action or its outcome materially impeded achievement of the mapped intent item or items."},
]
INTENT_RELATION_VALUES = {row["value"] for row in INTENT_RELATIONS}

EVIDENCE_TYPES = [
    {"value": "TOOL_RESULT", "definition": "Direct structured or textual result returned by a tool invocation."},
    {"value": "ARTIFACT_STATE", "definition": "Observable content, metadata, existence, or mutation state of a persistent artifact."},
    {"value": "EXTERNAL_SOURCE", "definition": "Evidence contained in an external authoritative or informational source."},
    {"value": "COMPUTED_RESULT", "definition": "Result produced through calculation or deterministic transformation."},
    {"value": "EXECUTION_RESULT", "definition": "Return value, exit status, test output, or other result of executing a procedure."},
    {"value": "USER_VISIBLE_OUTPUT", "definition": "Result directly exposed to the user."},
    {"value": "MODEL_OBSERVATION", "definition": "State observed by the model but not represented by a stronger evidence category."},
    {"value": "NONE", "definition": "No supporting evidence is available."},
]
EVIDENCE_TYPE_VALUES = {row["value"] for row in EVIDENCE_TYPES}

INTENT_OUTCOMES = [
    {"value": "SUCCESS", "definition": "Available evidence shows that this intent item was fully satisfied."},
    {"value": "PARTIAL", "definition": "Some but not all of the intent item was satisfied."},
    {"value": "FAILED", "definition": "The action path attempted to satisfy the item but did not achieve the required result."},
    {"value": "UNADDRESSED", "definition": "The recorded activity did not attempt to satisfy this item."},
    {"value": "NOT_APPLICABLE", "definition": "Subsequent information established that the item did not apply to the execution state being handled."},
]
INTENT_OUTCOME_VALUES = {row["value"] for row in INTENT_OUTCOMES}

PLAN_RELATIONSHIPS = [
    {"value": "NO_PRIOR_PLAN", "definition": "No identifiable plan existed before the recorded activity began."},
    {"value": "MATCHED", "definition": "The actual action path materially followed the prior plan."},
    {"value": "PARTIAL_DIVERGENCE", "definition": "The prior plan remained substantially operative, but one or more material steps changed."},
    {"value": "MAJOR_DIVERGENCE", "definition": "The actual path replaced or abandoned a substantial portion of the prior plan."},
]
PLAN_RELATIONSHIP_VALUES = {row["value"] for row in PLAN_RELATIONSHIPS}

DIVERGENCE_CAUSES = [
    {"value": "TOOL_RESULT", "definition": "A successful tool result changed what should happen next."},
    {"value": "TOOL_FAILURE", "definition": "Tool failure made the planned path unavailable or inappropriate."},
    {"value": "NEW_INFORMATION", "definition": "Newly acquired information changed the preferred path."},
    {"value": "DEPENDENCY", "definition": "An unsatisfied or newly discovered prerequisite changed execution order or method."},
    {"value": "USER_CONSTRAINT", "definition": "An explicit user requirement constrained the available path."},
    {"value": "SYSTEM_CONSTRAINT", "definition": "Environment, permission, policy, capability, or system behavior constrained the path."},
    {"value": "CANONICAL_RULE", "definition": "An applicable governing rule required or prohibited the path."},
    {"value": "AVAILABILITY", "definition": "A required resource, service, artifact, or actor was or was not available."},
    {"value": "VALIDATION_FAILURE", "definition": "Evaluation showed that a preceding result did not satisfy its requirements."},
    {"value": "EFFICIENCY", "definition": "Multiple viable paths existed and one was chosen because it reduced expected work, latency, or resource use."},
    {"value": "OTHER", "definition": "A material cause exists that cannot be represented by another canonical category; a short note is required."},
]
DIVERGENCE_CAUSE_VALUES = {row["value"] for row in DIVERGENCE_CAUSES}

DECISION_BASES = [
    {"value": "USER_EXPLICITLY_REQUIRED", "definition": "The user directly specified this action or method."},
    {"value": "REQUIRED_SUBGOAL", "definition": "The action was necessary to satisfy a decomposed user-intent item."},
    {"value": "PRIOR_PLAN", "definition": "The action was the next applicable step in an already established plan."},
    {"value": "OBSERVED_STATE", "definition": "Current execution state made the action appropriate."},
    {"value": "TOOL_AVAILABILITY", "definition": "Tool capabilities or availability determined the path."},
    {"value": "DEPENDENCY_ORDER", "definition": "The action had to occur before another action because of a prerequisite relationship."},
    {"value": "FAILURE_RECOVERY", "definition": "The action was selected in response to a preceding failure."},
    {"value": "VALIDATION_REQUIREMENT", "definition": "The action was necessary to establish whether a prior result met its requirements."},
    {"value": "CANONICAL_RULE", "definition": "A governing execution rule required the action."},
    {"value": "EFFICIENCY", "definition": "The action was preferred among otherwise viable alternatives because of expected execution efficiency."},
    {"value": "ONLY_VIABLE_PATH", "definition": "All known alternatives were unavailable, invalid, or incapable of satisfying the requirement."},
    {"value": "OTHER", "definition": "No canonical category accurately represents the selection basis; a short note is required."},
]
DECISION_BASIS_VALUES = {row["value"] for row in DECISION_BASES}

OVERALL_OUTCOMES = [
    {"value": "COMPLETE_SUCCESS", "definition": "All intent items addressed by this activity were fully achieved."},
    {"value": "PARTIAL_SUCCESS", "definition": "The activity achieved useful progress but at least one addressed intent item remains incomplete."},
    {"value": "FAILED", "definition": "The activity attempted to advance its mapped intent but achieved no required result."},
    {"value": "BLOCKED", "definition": "Execution could not proceed because a required dependency or capability remained unavailable. This does not itself authorize end-of-turn."},
    {"value": "NO_EFFECT", "definition": "The activity completed but produced no material change to progress toward the mapped intent."},
]
OVERALL_OUTCOME_VALUES = {row["value"] for row in OVERALL_OUTCOMES}

QUESTIONS = [
    {
        "id": "AQ1",
        "question": "Is this action an end-of-turn attempt? Answer YES or NO.",
        "format": "ENUM: YES | NO. Y/N are accepted aliases and normalized.",
        "tables": [{"name": "yes_no", "rows": YES_NO}],
    },
    {
        "id": "AQ2",
        "question": "State the user intent this action was intended to advance as one concise sentence describing the requested end state.",
        "format": "SHORT_TEXT",
        "tables": [],
    },
    {
        "id": "AQ3",
        "question": "Decompose that user intent into a numbered list of independently testable requirements. Answer as a JSON array of {id,text} objects using UI1, UI2, ... in order.",
        "format": 'JSON_ARRAY: [{"id":"UI1","text":"..."}, ...]',
        "tables": [],
    },
    {
        "id": "AQ4",
        "question": "Decompose the completed activity into the smallest meaningful ordered action units. Answer as a JSON array of {id,type,subtype,target} objects using A1, A2, ... in order and only the action ontology presented below.",
        "format": 'JSON_ARRAY: [{"id":"A1","type":"ACQUIRE","subtype":"READ","target":"..."}, ...]',
        "tables": [
            {"name": "action_types", "rows": ACTION_TYPES},
            {"name": "action_subtypes", "rows": ACTION_SUBTYPE_ROWS},
        ],
    },
    {
        "id": "AQ5",
        "question": "Did an explicit plan for this activity exist before execution of the recorded activity began? Answer YES or NO.",
        "format": "ENUM: YES | NO. Y/N are accepted aliases and normalized.",
        "tables": [{"name": "yes_no", "rows": YES_NO}],
    },
    {
        "id": "AQ6",
        "question": "Record the prior plan if one existed. Answer as a JSON array of {id,text} objects using P1, P2, ... in order; answer [] when AQ5 is NO. The actual executed path is the A# sequence from AQ4.",
        "format": 'JSON_ARRAY: [{"id":"P1","text":"..."}, ...] or []',
        "tables": [],
    },
    {
        "id": "AQ7",
        "question": "Map each atomic action to the decomposed user-intent items. Answer as a JSON array of {action_id,intent_ids,relation} objects using only existing A# and UI# IDs.",
        "format": 'JSON_ARRAY: [{"action_id":"A1","intent_ids":["UI1"],"relation":"DIRECT"}, ...]',
        "tables": [{"name": "action_intent_relation", "rows": INTENT_RELATIONS}],
    },
    {
        "id": "AQ8",
        "question": "Catalog the observable evidence for this activity. Answer as a JSON array of {id,type,reference} objects using E1, E2, ... in order. Use [] only when no evidence is available.",
        "format": 'JSON_ARRAY: [{"id":"E1","type":"TOOL_RESULT","reference":"..."}, ...] or []',
        "tables": [{"name": "evidence_type", "rows": EVIDENCE_TYPES}],
    },
    {
        "id": "AQ9",
        "question": "Evaluate every decomposed user-intent item. Answer as a JSON array of {intent_id,result,action_ids,evidence_ids,remaining_gap} objects using only existing IDs; remaining_gap must be empty unless result is PARTIAL, FAILED, or UNADDRESSED.",
        "format": 'JSON_ARRAY: [{"intent_id":"UI1","result":"SUCCESS","action_ids":["A1"],"evidence_ids":["E1"],"remaining_gap":""}, ...]',
        "tables": [{"name": "intent_outcome", "rows": INTENT_OUTCOMES}],
    },
    {
        "id": "AQ10",
        "question": "Compare the prior plan with the actual action path. Answer as a JSON object with relationship and divergences. relationship must use the presented enum; divergences is an array of {plan_ids,action_ids,cause,note}. When AQ5 is NO use NO_PRIOR_PLAN and [].",
        "format": 'JSON_OBJECT: {"relationship":"MATCHED","divergences":[{"plan_ids":["P1"],"action_ids":["A2"],"cause":"NEW_INFORMATION","note":"..."}]}',
        "tables": [
            {"name": "plan_path_relationship", "rows": PLAN_RELATIONSHIPS},
            {"name": "divergence_cause", "rows": DIVERGENCE_CAUSES},
        ],
    },
    {
        "id": "AQ11",
        "question": "For each material decision point, record why the next action was selected. Answer as a JSON array of {action_id,basis,note} objects; basis is an array of one or more presented enum values. Use [] only when no discretionary decision point occurred.",
        "format": 'JSON_ARRAY: [{"action_id":"A2","basis":["OBSERVED_STATE","REQUIRED_SUBGOAL"],"note":""}, ...] or []',
        "tables": [{"name": "decision_basis", "rows": DECISION_BASES}],
    },
    {
        "id": "AQ12",
        "question": "Classify the overall outcome of the recorded activity.",
        "format": "ENUM: COMPLETE_SUCCESS | PARTIAL_SUCCESS | FAILED | BLOCKED | NO_EFFECT",
        "tables": [{"name": "overall_activity_outcome", "rows": OVERALL_OUTCOMES}],
    },
    {
        "id": "AQ13",
        "question": "Record any decision-boundary counterfactuals that are actually supported by the observed state. Answer as a JSON array of {condition,alternate_action_type,alternate_action_subtype,note}. Use [] when none is supported; do not invent hypothetical alternatives merely to fill the field.",
        "format": 'JSON_ARRAY: [{"condition":"...","alternate_action_type":"ACT","alternate_action_subtype":"MODIFY","note":"..."}, ...] or []',
        "tables": [
            {"name": "action_types", "rows": ACTION_TYPES},
            {"name": "action_subtypes", "rows": ACTION_SUBTYPE_ROWS},
        ],
    },
    {
        "id": "AQ14",
        "question": "Provide the required NARRATIVE_MAPPING note. Use the exact section headings NARRATIVE_MAPPING, INTENT:, ACTION_PATH:, PLAN_RELATION:, OUTCOME_MAPPING:, and DECISION_CONTEXT:. Explain the structured decomposition as a coherent narrative; reference the UI#, A#, P#, and E# identifiers already created where applicable; introduce no new identifiers, actions, requirements, plans, or outcomes.",
        "format": "FORMATTED_TEXT with the six required headings in order",
        "tables": [],
    },
]
QUESTION_BY_ID = {q["id"]: q for q in QUESTIONS}

ID_PATTERNS = {
    "UI": re.compile(r"^UI([1-9][0-9]*)$"),
    "A": re.compile(r"^A([1-9][0-9]*)$"),
    "P": re.compile(r"^P([1-9][0-9]*)$"),
    "E": re.compile(r"^E([1-9][0-9]*)$"),
}
NARRATIVE_HEADINGS = [
    "NARRATIVE_MAPPING",
    "INTENT:",
    "ACTION_PATH:",
    "PLAN_RELATION:",
    "OUTCOME_MAPPING:",
    "DECISION_CONTEXT:",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(obj, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("questioner state must be an object")
    return value


def run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True)
    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeError(f"child script produced no JSON; stderr={completed.stderr.strip()!r}")
    data = json.loads(stdout)
    if completed.returncode != 0:
        raise RuntimeError(f"child script failed: {data!r}")
    return data


def normalize_yes_no(raw: str, qid: str) -> str:
    value = raw.strip().upper()
    value = {"Y": "YES", "N": "NO"}.get(value, value)
    if value not in {"YES", "NO"}:
        raise ValueError(f"{qid} requires YES/NO or Y/N")
    return value


def parse_json(raw: str, qid: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{qid} requires valid JSON: {exc.msg}") from exc


def require_text(value: Any, label: str, allow_empty: bool = False, max_length: int = 4000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{label} must not be empty")
    if len(value) > max_length:
        raise ValueError(f"{label} exceeds {max_length} characters")
    return value


def require_exact_fields(obj: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError(f"{label} must be an object")
    if set(obj) != fields:
        raise ValueError(f"{label} fields must be exactly {sorted(fields)!r}")
    return obj


def validate_numbered_items(value: Any, prefix: str, label: str, require_nonempty: bool = True) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    if require_nonempty and not value:
        raise ValueError(f"{label} must contain at least one item")
    for index, item in enumerate(value, start=1):
        require_exact_fields(item, {"id", "text"}, f"{label}[{index - 1}]")
        expected = f"{prefix}{index}"
        if item["id"] != expected:
            raise ValueError(f"{label}[{index - 1}].id must be {expected}")
        require_text(item["text"], f"{label}[{index - 1}].text", max_length=1000)
    return value


def known_ids(state: dict[str, Any], qid: str) -> set[str]:
    answers = state["answers"]
    if qid == "UI":
        return {item["id"] for item in answers.get("AQ3", [])}
    if qid == "A":
        return {item["id"] for item in answers.get("AQ4", [])}
    if qid == "P":
        return {item["id"] for item in answers.get("AQ6", [])}
    if qid == "E":
        return {item["id"] for item in answers.get("AQ8", [])}
    raise ValueError(qid)


def validate_atomic_actions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("AQ4 must be a non-empty JSON array")
    for index, item in enumerate(value, start=1):
        require_exact_fields(item, {"id", "type", "subtype", "target"}, f"AQ4[{index - 1}]")
        if item["id"] != f"A{index}":
            raise ValueError(f"AQ4[{index - 1}].id must be A{index}")
        action_type = item["type"]
        subtype = item["subtype"]
        if action_type not in ACTION_TYPE_VALUES:
            raise ValueError(f"AQ4[{index - 1}].type is not canonical")
        if subtype not in ACTION_SUBTYPE_VALUES[action_type]:
            raise ValueError(f"AQ4[{index - 1}].subtype is invalid for {action_type}")
        require_text(item["target"], f"AQ4[{index - 1}].target", max_length=1000)
    return value


def validate_action_intent_map(value: Any, state: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("AQ7 must be a JSON array")
    action_ids = known_ids(state, "A")
    intent_ids = known_ids(state, "UI")
    if len(value) != len(action_ids):
        raise ValueError("AQ7 must contain exactly one mapping for every A# action")
    seen: set[str] = set()
    for index, item in enumerate(value):
        require_exact_fields(item, {"action_id", "intent_ids", "relation"}, f"AQ7[{index}]")
        action_id = item["action_id"]
        if action_id not in action_ids or action_id in seen:
            raise ValueError(f"AQ7[{index}].action_id must be a unique existing A#")
        seen.add(action_id)
        relation = item["relation"]
        if relation not in INTENT_RELATION_VALUES:
            raise ValueError(f"AQ7[{index}].relation is invalid")
        ids = item["intent_ids"]
        if not isinstance(ids, list) or any(x not in intent_ids for x in ids) or len(ids) != len(set(ids)):
            raise ValueError(f"AQ7[{index}].intent_ids must contain unique existing UI# IDs")
        if relation == "NONE" and ids:
            raise ValueError("AQ7 relation NONE requires an empty intent_ids array")
        if relation != "NONE" and not ids:
            raise ValueError(f"AQ7 relation {relation} requires at least one intent_id")
    return value


def validate_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("AQ8 must be a JSON array")
    for index, item in enumerate(value, start=1):
        require_exact_fields(item, {"id", "type", "reference"}, f"AQ8[{index - 1}]")
        if item["id"] != f"E{index}":
            raise ValueError(f"AQ8[{index - 1}].id must be E{index}")
        if item["type"] not in EVIDENCE_TYPE_VALUES:
            raise ValueError(f"AQ8[{index - 1}].type is invalid")
        require_text(item["reference"], f"AQ8[{index - 1}].reference", max_length=1500)
    return value


def validate_intent_outcomes(value: Any, state: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("AQ9 must be a JSON array")
    intent_ids = known_ids(state, "UI")
    action_ids = known_ids(state, "A")
    evidence_ids = known_ids(state, "E")
    if len(value) != len(intent_ids):
        raise ValueError("AQ9 must contain exactly one result for every UI# item")
    seen: set[str] = set()
    for index, item in enumerate(value):
        require_exact_fields(item, {"intent_id", "result", "action_ids", "evidence_ids", "remaining_gap"}, f"AQ9[{index}]")
        intent_id = item["intent_id"]
        if intent_id not in intent_ids or intent_id in seen:
            raise ValueError(f"AQ9[{index}].intent_id must be a unique existing UI#")
        seen.add(intent_id)
        result = item["result"]
        if result not in INTENT_OUTCOME_VALUES:
            raise ValueError(f"AQ9[{index}].result is invalid")
        a_ids = item["action_ids"]
        e_ids = item["evidence_ids"]
        if not isinstance(a_ids, list) or any(x not in action_ids for x in a_ids) or len(a_ids) != len(set(a_ids)):
            raise ValueError(f"AQ9[{index}].action_ids must contain unique existing A# IDs")
        if not isinstance(e_ids, list) or any(x not in evidence_ids for x in e_ids) or len(e_ids) != len(set(e_ids)):
            raise ValueError(f"AQ9[{index}].evidence_ids must contain unique existing E# IDs")
        gap = require_text(item["remaining_gap"], f"AQ9[{index}].remaining_gap", allow_empty=True, max_length=1500)
        if result in {"SUCCESS", "NOT_APPLICABLE"} and gap:
            raise ValueError(f"AQ9[{index}].remaining_gap must be empty for {result}")
        if result in {"PARTIAL", "FAILED", "UNADDRESSED"} and not gap.strip():
            raise ValueError(f"AQ9[{index}].remaining_gap is required for {result}")
    return value


def validate_plan_path(value: Any, state: dict[str, Any]) -> dict[str, Any]:
    require_exact_fields(value, {"relationship", "divergences"}, "AQ10")
    relationship = value["relationship"]
    if relationship not in PLAN_RELATIONSHIP_VALUES:
        raise ValueError("AQ10.relationship is invalid")
    plan_exists = state["answers"].get("AQ5") == "YES"
    if plan_exists and relationship == "NO_PRIOR_PLAN":
        raise ValueError("AQ10 cannot use NO_PRIOR_PLAN when AQ5 is YES")
    if not plan_exists and relationship != "NO_PRIOR_PLAN":
        raise ValueError("AQ10 must use NO_PRIOR_PLAN when AQ5 is NO")
    divergences = value["divergences"]
    if not isinstance(divergences, list):
        raise ValueError("AQ10.divergences must be an array")
    if relationship in {"NO_PRIOR_PLAN", "MATCHED"} and divergences:
        raise ValueError(f"AQ10.divergences must be empty for {relationship}")
    plan_ids = known_ids(state, "P")
    action_ids = known_ids(state, "A")
    for index, item in enumerate(divergences):
        require_exact_fields(item, {"plan_ids", "action_ids", "cause", "note"}, f"AQ10.divergences[{index}]")
        p_ids = item["plan_ids"]
        a_ids = item["action_ids"]
        if not isinstance(p_ids, list) or any(x not in plan_ids for x in p_ids) or len(p_ids) != len(set(p_ids)):
            raise ValueError(f"AQ10.divergences[{index}].plan_ids must contain unique existing P# IDs")
        if not isinstance(a_ids, list) or any(x not in action_ids for x in a_ids) or len(a_ids) != len(set(a_ids)) or not a_ids:
            raise ValueError(f"AQ10.divergences[{index}].action_ids must contain at least one unique existing A#")
        cause = item["cause"]
        if cause not in DIVERGENCE_CAUSE_VALUES:
            raise ValueError(f"AQ10.divergences[{index}].cause is invalid")
        note = require_text(item["note"], f"AQ10.divergences[{index}].note", allow_empty=True, max_length=1000)
        if cause == "OTHER" and not note.strip():
            raise ValueError("AQ10 divergence cause OTHER requires a note")
    return value


def validate_decision_points(value: Any, state: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("AQ11 must be a JSON array")
    action_ids = known_ids(state, "A")
    seen: set[str] = set()
    for index, item in enumerate(value):
        require_exact_fields(item, {"action_id", "basis", "note"}, f"AQ11[{index}]")
        action_id = item["action_id"]
        if action_id not in action_ids or action_id in seen:
            raise ValueError(f"AQ11[{index}].action_id must be a unique existing A#")
        seen.add(action_id)
        basis = item["basis"]
        if not isinstance(basis, list) or not basis or len(basis) != len(set(basis)) or any(x not in DECISION_BASIS_VALUES for x in basis):
            raise ValueError(f"AQ11[{index}].basis must contain one or more unique canonical values")
        note = require_text(item["note"], f"AQ11[{index}].note", allow_empty=True, max_length=1000)
        if "OTHER" in basis and not note.strip():
            raise ValueError("AQ11 basis OTHER requires a note")
    return value


def validate_counterfactuals(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("AQ13 must be a JSON array")
    for index, item in enumerate(value):
        require_exact_fields(item, {"condition", "alternate_action_type", "alternate_action_subtype", "note"}, f"AQ13[{index}]")
        require_text(item["condition"], f"AQ13[{index}].condition", max_length=1000)
        action_type = item["alternate_action_type"]
        subtype = item["alternate_action_subtype"]
        if action_type not in ACTION_TYPE_VALUES:
            raise ValueError(f"AQ13[{index}].alternate_action_type is invalid")
        if subtype not in ACTION_SUBTYPE_VALUES[action_type]:
            raise ValueError(f"AQ13[{index}].alternate_action_subtype is invalid for {action_type}")
        require_text(item["note"], f"AQ13[{index}].note", allow_empty=True, max_length=1000)
    return value


def validate_narrative(text: str, state: dict[str, Any]) -> str:
    text = require_text(text, "AQ14", max_length=12000)
    positions = []
    for heading in NARRATIVE_HEADINGS:
        position = text.find(heading)
        if position < 0:
            raise ValueError(f"AQ14 is missing required heading {heading}")
        positions.append(position)
    if positions != sorted(positions) or not text.startswith("NARRATIVE_MAPPING"):
        raise ValueError("AQ14 headings must appear in the required order and start with NARRATIVE_MAPPING")

    known = known_ids(state, "UI") | known_ids(state, "A") | known_ids(state, "P") | known_ids(state, "E")
    referenced = set(re.findall(r"\b(?:UI|A|P|E)[1-9][0-9]*\b", text))
    unknown = referenced - known
    if unknown:
        raise ValueError(f"AQ14 introduces unknown identifiers: {sorted(unknown)!r}")
    missing_ui = known_ids(state, "UI") - referenced
    missing_actions = known_ids(state, "A") - referenced
    missing_plan = known_ids(state, "P") - referenced
    if missing_ui:
        raise ValueError(f"AQ14 must reference every UI# item; missing {sorted(missing_ui)!r}")
    if missing_actions:
        raise ValueError(f"AQ14 must reference every A# item; missing {sorted(missing_actions)!r}")
    if state["answers"].get("AQ5") == "YES" and missing_plan:
        raise ValueError(f"AQ14 must reference every P# item; missing {sorted(missing_plan)!r}")
    if state["answers"].get("AQ5") == "NO" and "NO_PRIOR_PLAN" not in text:
        raise ValueError("AQ14 PLAN_RELATION must state NO_PRIOR_PLAN when AQ5 is NO")
    return text


def validate_answer(qid: str, raw: str, state: dict[str, Any]) -> Any:
    if qid in {"AQ1", "AQ5"}:
        return normalize_yes_no(raw, qid)
    if qid == "AQ2":
        return require_text(raw.strip(), "AQ2", max_length=1000)
    if qid == "AQ3":
        return validate_numbered_items(parse_json(raw, qid), "UI", "AQ3")
    if qid == "AQ4":
        return validate_atomic_actions(parse_json(raw, qid))
    if qid == "AQ6":
        value = parse_json(raw, qid)
        require_nonempty = state["answers"].get("AQ5") == "YES"
        value = validate_numbered_items(value, "P", "AQ6", require_nonempty=require_nonempty)
        if not require_nonempty and value:
            raise ValueError("AQ6 must be [] when AQ5 is NO")
        return value
    if qid == "AQ7":
        return validate_action_intent_map(parse_json(raw, qid), state)
    if qid == "AQ8":
        return validate_evidence(parse_json(raw, qid))
    if qid == "AQ9":
        return validate_intent_outcomes(parse_json(raw, qid), state)
    if qid == "AQ10":
        return validate_plan_path(parse_json(raw, qid), state)
    if qid == "AQ11":
        return validate_decision_points(parse_json(raw, qid), state)
    if qid == "AQ12":
        value = raw.strip().upper()
        if value not in OVERALL_OUTCOME_VALUES:
            raise ValueError("AQ12 answer is not a canonical overall outcome")
        return value
    if qid == "AQ13":
        return validate_counterfactuals(parse_json(raw, qid))
    if qid == "AQ14":
        return validate_narrative(raw, state)
    raise ValueError(f"unknown question id: {qid}")


def source_from_state(state: dict[str, Any]) -> dict[str, Any] | None:
    value = state.get("source") or {}
    return value or None


def action_question_payload(state: dict[str, Any]) -> dict[str, Any]:
    index = state["question_index"]
    spec = QUESTIONS[index]
    out: dict[str, Any] = {
        "status": "QUESTION",
        "phase": "action_questionnaire",
        "state": state["state_path"],
        "question_number": index + 1,
        "question_count": len(QUESTIONS),
        "question_id": spec["id"],
        "question": spec["question"],
        "answer_format": spec["format"],
    }
    if spec["tables"]:
        out["definition_tables"] = spec["tables"]
    if spec["id"] in {"AQ1", "AQ5"}:
        out["allowed_answers"] = ["YES", "NO"]
    elif spec["id"] == "AQ12":
        out["allowed_answers"] = [row["value"] for row in OVERALL_OUTCOMES]
    return out


def router_question_payload(state: dict[str, Any], router_output: dict[str, Any], questionnaire_result: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": "QUESTION",
        "phase": "end_turn_router",
        "state": state["state_path"],
        "question_id": router_output["question_id"],
        "question": router_output["question"],
        "allowed_answers": router_output["allowed_answers"],
        "cycle_id": router_output["cycle_id"],
    }
    if questionnaire_result is not None:
        out["questioner_signal"] = "QUESTIONER_ACTION_OVER"
        out["questioner_data_object"] = questionnaire_result["data_object"]
        out["record"] = questionnaire_result["record"]
    return out


def recorder_append(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    payload_path = Path(state["state_path"]).with_name(f"questioner-return-{uuid.uuid4().hex}.json")
    write_json(payload_path, payload)
    receipt = run_json([
        sys.executable, state["recorder"], "append",
        "--output-dir", state["output_dir"],
        "--record", state["record"],
        "--record-name", state["record_name"],
        "--record-id", state["record_id"],
        "--action-file", str(payload_path),
    ])
    state["record"] = receipt["record"]
    state["record_name"] = receipt["record_filename"]
    state["record_id"] = receipt["record_id"]
    state["updated_at"] = now()
    write_json(Path(state["state_path"]), state)
    return receipt


def build_action_questionnaire(state: dict[str, Any]) -> dict[str, Any]:
    pairs = [
        {"id": spec["id"], "question": spec["question"], "answer": state["answers"][spec["id"]]}
        for spec in QUESTIONS
    ]
    payload: dict[str, Any] = {
        "action_type": "action_questionnaire",
        "scope": state["scope"],
        "pairs": pairs,
    }
    source = source_from_state(state)
    if source:
        payload["source"] = source
    return payload


def finish_action_questionnaire(state: dict[str, Any]) -> dict[str, Any]:
    payload = build_action_questionnaire(state)
    receipt = recorder_append(state, payload)
    return {
        "status": "QUESTIONER_ACTION_OVER",
        "signal": "QUESTIONER_ACTION_OVER",
        "phase": "action_questionnaire_complete",
        "state": state["state_path"],
        "data_object": payload,
        "record": receipt,
    }


def start_router(state: dict[str, Any]) -> dict[str, Any]:
    router_state = Path(state["state_path"]).with_name(f"end-turn-router-{uuid.uuid4().hex}.json")
    router_output = run_json([
        sys.executable, state["router"], "start",
        "--state", str(router_state),
        "--scope", state["scope"],
    ])
    state["phase"] = "end_turn_router"
    state["router_state"] = str(router_state)
    state["router_cycle_id"] = router_output["cycle_id"]
    state["updated_at"] = now()
    write_json(Path(state["state_path"]), state)
    return router_output


def append_end_turn_result(state: dict[str, Any], router_data: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action_type": "end_turn_result",
        "scope": state["scope"],
        "router_cycle": router_data,
    }
    source = source_from_state(state)
    if source:
        payload["source"] = source
    return recorder_append(state, payload)


def cmd_start(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    source: dict[str, Any] = {}
    if args.chat_id is not None:
        source["chat_id"] = args.chat_id
    if args.chat_title is not None:
        source["chat_title"] = args.chat_title
    state = {
        "session_id": uuid.uuid4().hex,
        "started_at": now(),
        "updated_at": now(),
        "state_path": str(state_path),
        "phase": "action_questionnaire",
        "question_index": 0,
        "answers": {},
        "scope": args.scope,
        "recorder": args.recorder,
        "router": args.router,
        "output_dir": args.output_dir,
        "record": args.record,
        "record_name": args.record_name,
        "record_id": args.record_id,
        "source": source,
    }
    write_json(state_path, state)
    print(json.dumps(action_question_payload(state), ensure_ascii=False))
    return 0


def answer_action_question(state: dict[str, Any], raw: str) -> dict[str, Any]:
    index = state["question_index"]
    if index < 0 or index >= len(QUESTIONS):
        raise ValueError("action questionnaire is not waiting for an answer")
    qid = QUESTIONS[index]["id"]
    value = validate_answer(qid, raw, state)
    state["answers"][qid] = value
    state["question_index"] = index + 1
    state["updated_at"] = now()
    write_json(Path(state["state_path"]), state)

    if state["question_index"] < len(QUESTIONS):
        return action_question_payload(state)

    questionnaire_result = finish_action_questionnaire(state)
    state["questionnaire_receipt"] = questionnaire_result["record"]
    state["questionnaire_data_object"] = questionnaire_result["data_object"]
    write_json(Path(state["state_path"]), state)

    if state["answers"]["AQ1"] == "NO":
        state["phase"] = "complete"
        state["completed_at"] = now()
        write_json(Path(state["state_path"]), state)
        questionnaire_result["phase"] = "complete"
        return questionnaire_result

    router_output = start_router(state)
    return router_question_payload(state, router_output, questionnaire_result)


def answer_router(state: dict[str, Any], raw: str) -> dict[str, Any]:
    router_output = run_json([
        sys.executable, state["router"], "answer",
        "--state", state["router_state"],
        "--answer", raw,
    ])
    if router_output.get("status") == "QUESTION":
        return router_question_payload(state, router_output)
    if router_output.get("status") != "DIRECTIVE" or not isinstance(router_output.get("data_object"), dict):
        raise RuntimeError(f"router returned unexpected terminal payload: {router_output!r}")

    router_data = router_output["data_object"]
    receipt = append_end_turn_result(state, router_data)
    state["phase"] = "complete"
    state["completed_at"] = now()
    state["end_turn_receipt"] = receipt
    state["directive"] = router_data["directive"]
    write_json(Path(state["state_path"]), state)
    out = {
        "status": "DIRECTIVE",
        "phase": "complete",
        "state": state["state_path"],
        "cycle_id": router_data["cycle_id"],
        "directive": router_data["directive"],
        "record": receipt,
        "end_turn": router_data,
    }
    if "instruction" in router_data:
        out["instruction"] = router_data["instruction"]
    if "impasse_evidence" in router_data:
        out["impasse_evidence"] = router_data["impasse_evidence"]
    return out


def cmd_answer(args: argparse.Namespace) -> int:
    state = load(Path(args.state))
    phase = state.get("phase")
    if phase == "action_questionnaire":
        result = answer_action_question(state, args.answer)
    elif phase == "end_turn_router":
        result = answer_router(state, args.answer)
    else:
        raise ValueError("questioner session is already complete")
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    start = sub.add_parser("start")
    start.add_argument("--state", required=True)
    start.add_argument("--scope", required=True, choices=sorted(SCOPES))
    start.add_argument("--recorder", required=True)
    start.add_argument("--router", required=True)
    start.add_argument("--output-dir", required=True)
    start.add_argument("--record", required=True)
    start.add_argument("--record-name", required=True)
    start.add_argument("--record-id", required=True)
    start.add_argument("--chat-id")
    start.add_argument("--chat-title")
    start.set_defaults(fn=cmd_start)
    answer = sub.add_parser("answer")
    answer.add_argument("--state", required=True)
    answer.add_argument("--answer", required=True)
    answer.set_defaults(fn=cmd_answer)
    args = ap.parse_args()
    try:
        return args.fn(args)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "code": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
