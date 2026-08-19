#!/usr/bin/env python3
"""Immutable execution-record appender and action-questioner bootstrapper.

External tracking enters through ``invoke``. The recorder does not know why it
was invoked and never classifies the tracked action. It appends only a
``recorder_invocation`` action with a recorder-generated timestamp, then starts
``action_questioner.py``.

Canonical child scripts return already-formatted action objects through
``append``. Appending a child object never starts another questionnaire.
The recorder validates the canonical structural contract and append-only
snapshot invariants; it does not judge the truth of questionnaire answers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RECORD_PREFIX = "execution-record_"
RECORD_SUFFIX = ".json"
STAMP_RE = re.compile(r"^execution-record_(\d{8}T\d{12}Z)\.json$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SCOPES = {"worker", "orchestrator"}
DIRECTIVES = {"CONTINUE", "COMPLETE", "IMPASSE"}

ACTION_QUESTIONS = [
    ("AQ1", "Is this action an end-of-turn attempt? Answer YES or NO."),
    ("AQ2", "State the user intent this action was intended to advance as one concise sentence describing the requested end state."),
    ("AQ3", "Decompose that user intent into a numbered list of independently testable requirements. Answer as a JSON array of {id,text} objects using UI1, UI2, ... in order."),
    ("AQ4", "Decompose the completed activity into the smallest meaningful ordered action units. Answer as a JSON array of {id,type,subtype,target} objects using A1, A2, ... in order and only the action ontology presented below."),
    ("AQ5", "Did an explicit plan for this activity exist before execution of the recorded activity began? Answer YES or NO."),
    ("AQ6", "Record the prior plan if one existed. Answer as a JSON array of {id,text} objects using P1, P2, ... in order; answer [] when AQ5 is NO. The actual executed path is the A# sequence from AQ4."),
    ("AQ7", "Map each atomic action to the decomposed user-intent items. Answer as a JSON array of {action_id,intent_ids,relation} objects using only existing A# and UI# IDs."),
    ("AQ8", "Catalog the observable evidence for this activity. Answer as a JSON array of {id,type,reference} objects using E1, E2, ... in order. Use [] only when no evidence is available."),
    ("AQ9", "Evaluate every decomposed user-intent item. Answer as a JSON array of {intent_id,result,action_ids,evidence_ids,remaining_gap} objects using only existing IDs; remaining_gap must be empty unless result is PARTIAL, FAILED, or UNADDRESSED."),
    ("AQ10", "Compare the prior plan with the actual action path. Answer as a JSON object with relationship and divergences. relationship must use the presented enum; divergences is an array of {plan_ids,action_ids,cause,note}. When AQ5 is NO use NO_PRIOR_PLAN and []."),
    ("AQ11", "For each material decision point, record why the next action was selected. Answer as a JSON array of {action_id,basis,note} objects; basis is an array of one or more presented enum values. Use [] only when no discretionary decision point occurred."),
    ("AQ12", "Classify the overall outcome of the recorded activity."),
    ("AQ13", "Record any decision-boundary counterfactuals that are actually supported by the observed state. Answer as a JSON array of {condition,alternate_action_type,alternate_action_subtype,note}. Use [] when none is supported; do not invent hypothetical alternatives merely to fill the field."),
    ("AQ14", "Provide the required NARRATIVE_MAPPING note. Use the exact section headings NARRATIVE_MAPPING, INTENT:, ACTION_PATH:, PLAN_RELATION:, OUTCOME_MAPPING:, and DECISION_CONTEXT:. Explain the structured decomposition as a coherent narrative; reference the UI#, A#, P#, and E# identifiers already created where applicable; introduce no new identifiers, actions, requirements, plans, or outcomes."),
]

ACTION_SUBTYPES = {
    "ACQUIRE": {"READ", "SEARCH", "RETRIEVE"},
    "TRANSFORM": {"CALCULATE", "DECOMPOSE", "SYNTHESIZE", "CONVERT", "EXTRACT"},
    "EVALUATE": {"COMPARE", "CLASSIFY", "VALIDATE", "SCORE"},
    "DECIDE": {"SELECT", "REJECT", "PRIORITIZE", "DEFER"},
    "ACT": {"CREATE", "MODIFY", "DELETE", "EXECUTE", "CALL"},
    "OBSERVE": {"INSPECT", "RECEIVE", "DETECT_ERROR", "DETECT_CHANGE"},
    "COMMUNICATE": {"ASK", "RETURN", "REPORT", "INSTRUCT", "SIGNAL"},
}
ACTION_TYPES = set(ACTION_SUBTYPES)
INTENT_RELATIONS = {"DIRECT", "SUPPORTING", "NONE", "OBSTRUCTED"}
EVIDENCE_TYPES = {"TOOL_RESULT", "ARTIFACT_STATE", "EXTERNAL_SOURCE", "COMPUTED_RESULT", "EXECUTION_RESULT", "USER_VISIBLE_OUTPUT", "MODEL_OBSERVATION", "NONE"}
INTENT_OUTCOMES = {"SUCCESS", "PARTIAL", "FAILED", "UNADDRESSED", "NOT_APPLICABLE"}
PLAN_RELATIONSHIPS = {"NO_PRIOR_PLAN", "MATCHED", "PARTIAL_DIVERGENCE", "MAJOR_DIVERGENCE"}
DIVERGENCE_CAUSES = {"TOOL_RESULT", "TOOL_FAILURE", "NEW_INFORMATION", "DEPENDENCY", "USER_CONSTRAINT", "SYSTEM_CONSTRAINT", "CANONICAL_RULE", "AVAILABILITY", "VALIDATION_FAILURE", "EFFICIENCY", "OTHER"}
DECISION_BASES = {"USER_EXPLICITLY_REQUIRED", "REQUIRED_SUBGOAL", "PRIOR_PLAN", "OBSERVED_STATE", "TOOL_AVAILABILITY", "DEPENDENCY_ORDER", "FAILURE_RECOVERY", "VALIDATION_REQUIREMENT", "CANONICAL_RULE", "EFFICIENCY", "ONLY_VIABLE_PATH", "OTHER"}
OVERALL_OUTCOMES = {"COMPLETE_SUCCESS", "PARTIAL_SUCCESS", "FAILED", "BLOCKED", "NO_EFFECT"}
NARRATIVE_HEADINGS = ["NARRATIVE_MAPPING", "INTENT:", "ACTION_PATH:", "PLAN_RELATION:", "OUTCOME_MAPPING:", "DECISION_CONTEXT:"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_text(value: Any, label: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{label} must be a {'string' if allow_empty else 'non-empty string'}")
    return value


def validate_iso(value: Any, label: str) -> None:
    text = require_text(value, label)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone information")


def exact_fields(obj: dict[str, Any], required: set[str], optional: set[str], label: str) -> None:
    missing = required - set(obj)
    extra = set(obj) - required - optional
    if missing or extra:
        raise ValueError(f"{label} fields invalid: missing={sorted(missing)!r}, extra={sorted(extra)!r}")


def parse_stamp(filename: str) -> str:
    match = STAMP_RE.fullmatch(filename)
    if not match:
        raise ValueError("record filename must match execution-record_YYYYMMDDTHHMMSSffffffZ.json")
    return match.group(1)


def validate_source(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    exact_fields(value, set(), {"chat_id", "chat_title"}, label)
    for key, item in value.items():
        if item is not None and not isinstance(item, str):
            raise ValueError(f"{label}.{key} must be a string or null")


def validate_router_pairs(pairs: Any, label: str) -> None:
    if not isinstance(pairs, list) or not pairs:
        raise ValueError(f"{label} must be a non-empty array")
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise ValueError(f"{label}[{index}] must be an object")
        exact_fields(pair, {"id", "question", "answer"}, set(), f"{label}[{index}]")
        require_text(pair["id"], f"{label}[{index}].id")
        require_text(pair["question"], f"{label}[{index}].question")
        require_text(pair["answer"], f"{label}[{index}].answer")


def validate_numbered_items(value: Any, prefix: str, label: str, require_nonempty: bool) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    if require_nonempty and not value:
        raise ValueError(f"{label} must be non-empty")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{label}[{index - 1}] must be an object")
        exact_fields(item, {"id", "text"}, set(), f"{label}[{index - 1}]")
        if item["id"] != f"{prefix}{index}":
            raise ValueError(f"{label}[{index - 1}].id must be {prefix}{index}")
        require_text(item["text"], f"{label}[{index - 1}].text")
    return value


def validate_atomic_actions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("AQ4 answer must be a non-empty array")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"AQ4[{index - 1}] must be an object")
        exact_fields(item, {"id", "type", "subtype", "target"}, set(), f"AQ4[{index - 1}]")
        if item["id"] != f"A{index}":
            raise ValueError(f"AQ4[{index - 1}].id must be A{index}")
        if item["type"] not in ACTION_TYPES or item["subtype"] not in ACTION_SUBTYPES[item["type"]]:
            raise ValueError(f"AQ4[{index - 1}] has invalid type/subtype")
        require_text(item["target"], f"AQ4[{index - 1}].target")
    return value


def id_set(items: list[dict[str, Any]]) -> set[str]:
    return {item["id"] for item in items}


def validate_questionnaire_pairs(pairs: Any, label: str) -> None:
    if not isinstance(pairs, list) or len(pairs) != len(ACTION_QUESTIONS):
        raise ValueError(f"{label} must contain exactly {len(ACTION_QUESTIONS)} pairs")
    answers: dict[str, Any] = {}
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise ValueError(f"{label}[{index}] must be an object")
        exact_fields(pair, {"id", "question", "answer"}, set(), f"{label}[{index}]")
        expected_id, expected_question = ACTION_QUESTIONS[index]
        if pair["id"] != expected_id or pair["question"] != expected_question:
            raise ValueError(f"{label}[{index}] does not match canonical {expected_id}")
        answers[expected_id] = pair["answer"]

    if answers["AQ1"] not in {"YES", "NO"}:
        raise ValueError("AQ1 answer must be YES or NO")
    require_text(answers["AQ2"], "AQ2")
    ui_items = validate_numbered_items(answers["AQ3"], "UI", "AQ3", True)
    actions = validate_atomic_actions(answers["AQ4"])
    if answers["AQ5"] not in {"YES", "NO"}:
        raise ValueError("AQ5 answer must be YES or NO")
    plan_items = validate_numbered_items(answers["AQ6"], "P", "AQ6", answers["AQ5"] == "YES")
    if answers["AQ5"] == "NO" and plan_items:
        raise ValueError("AQ6 must be [] when AQ5 is NO")

    ui_ids = id_set(ui_items)
    action_ids = id_set(actions)
    plan_ids = id_set(plan_items)

    mappings = answers["AQ7"]
    if not isinstance(mappings, list) or len(mappings) != len(action_ids):
        raise ValueError("AQ7 must contain one mapping for every A#")
    seen_actions: set[str] = set()
    for index, item in enumerate(mappings):
        if not isinstance(item, dict):
            raise ValueError(f"AQ7[{index}] must be an object")
        exact_fields(item, {"action_id", "intent_ids", "relation"}, set(), f"AQ7[{index}]")
        if item["action_id"] not in action_ids or item["action_id"] in seen_actions:
            raise ValueError(f"AQ7[{index}].action_id must be a unique existing A#")
        seen_actions.add(item["action_id"])
        if item["relation"] not in INTENT_RELATIONS:
            raise ValueError(f"AQ7[{index}].relation is invalid")
        ids = item["intent_ids"]
        if not isinstance(ids, list) or any(x not in ui_ids for x in ids) or len(ids) != len(set(ids)):
            raise ValueError(f"AQ7[{index}].intent_ids are invalid")
        if item["relation"] == "NONE" and ids:
            raise ValueError("AQ7 NONE requires empty intent_ids")
        if item["relation"] != "NONE" and not ids:
            raise ValueError("AQ7 non-NONE relation requires intent_ids")

    evidence = answers["AQ8"]
    if not isinstance(evidence, list):
        raise ValueError("AQ8 must be an array")
    evidence_ids: set[str] = set()
    for index, item in enumerate(evidence, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"AQ8[{index - 1}] must be an object")
        exact_fields(item, {"id", "type", "reference"}, set(), f"AQ8[{index - 1}]")
        if item["id"] != f"E{index}":
            raise ValueError(f"AQ8[{index - 1}].id must be E{index}")
        if item["type"] not in EVIDENCE_TYPES:
            raise ValueError(f"AQ8[{index - 1}].type is invalid")
        require_text(item["reference"], f"AQ8[{index - 1}].reference")
        evidence_ids.add(item["id"])

    outcomes = answers["AQ9"]
    if not isinstance(outcomes, list) or len(outcomes) != len(ui_ids):
        raise ValueError("AQ9 must contain one outcome for every UI#")
    seen_ui: set[str] = set()
    for index, item in enumerate(outcomes):
        if not isinstance(item, dict):
            raise ValueError(f"AQ9[{index}] must be an object")
        exact_fields(item, {"intent_id", "result", "action_ids", "evidence_ids", "remaining_gap"}, set(), f"AQ9[{index}]")
        if item["intent_id"] not in ui_ids or item["intent_id"] in seen_ui:
            raise ValueError(f"AQ9[{index}].intent_id must be unique existing UI#")
        seen_ui.add(item["intent_id"])
        if item["result"] not in INTENT_OUTCOMES:
            raise ValueError(f"AQ9[{index}].result is invalid")
        if not isinstance(item["action_ids"], list) or any(x not in action_ids for x in item["action_ids"]):
            raise ValueError(f"AQ9[{index}].action_ids are invalid")
        if not isinstance(item["evidence_ids"], list) or any(x not in evidence_ids for x in item["evidence_ids"]):
            raise ValueError(f"AQ9[{index}].evidence_ids are invalid")
        gap = require_text(item["remaining_gap"], f"AQ9[{index}].remaining_gap", allow_empty=True)
        if item["result"] in {"SUCCESS", "NOT_APPLICABLE"} and gap:
            raise ValueError(f"AQ9[{index}] remaining_gap must be empty")
        if item["result"] in {"PARTIAL", "FAILED", "UNADDRESSED"} and not gap.strip():
            raise ValueError(f"AQ9[{index}] remaining_gap is required")

    plan_path = answers["AQ10"]
    if not isinstance(plan_path, dict):
        raise ValueError("AQ10 must be an object")
    exact_fields(plan_path, {"relationship", "divergences"}, set(), "AQ10")
    relation = plan_path["relationship"]
    if relation not in PLAN_RELATIONSHIPS:
        raise ValueError("AQ10.relationship is invalid")
    if answers["AQ5"] == "NO" and relation != "NO_PRIOR_PLAN":
        raise ValueError("AQ10 must use NO_PRIOR_PLAN when AQ5 is NO")
    if answers["AQ5"] == "YES" and relation == "NO_PRIOR_PLAN":
        raise ValueError("AQ10 cannot use NO_PRIOR_PLAN when AQ5 is YES")
    divergences = plan_path["divergences"]
    if not isinstance(divergences, list):
        raise ValueError("AQ10.divergences must be an array")
    if relation in {"NO_PRIOR_PLAN", "MATCHED"} and divergences:
        raise ValueError("AQ10 divergences must be empty for NO_PRIOR_PLAN or MATCHED")
    for index, item in enumerate(divergences):
        if not isinstance(item, dict):
            raise ValueError(f"AQ10.divergences[{index}] must be an object")
        exact_fields(item, {"plan_ids", "action_ids", "cause", "note"}, set(), f"AQ10.divergences[{index}]")
        if not isinstance(item["plan_ids"], list) or any(x not in plan_ids for x in item["plan_ids"]):
            raise ValueError(f"AQ10.divergences[{index}].plan_ids are invalid")
        if not isinstance(item["action_ids"], list) or not item["action_ids"] or any(x not in action_ids for x in item["action_ids"]):
            raise ValueError(f"AQ10.divergences[{index}].action_ids are invalid")
        if item["cause"] not in DIVERGENCE_CAUSES:
            raise ValueError(f"AQ10.divergences[{index}].cause is invalid")
        note = require_text(item["note"], f"AQ10.divergences[{index}].note", allow_empty=True)
        if item["cause"] == "OTHER" and not note.strip():
            raise ValueError("AQ10 OTHER cause requires note")

    decisions = answers["AQ11"]
    if not isinstance(decisions, list):
        raise ValueError("AQ11 must be an array")
    seen_decisions: set[str] = set()
    for index, item in enumerate(decisions):
        if not isinstance(item, dict):
            raise ValueError(f"AQ11[{index}] must be an object")
        exact_fields(item, {"action_id", "basis", "note"}, set(), f"AQ11[{index}]")
        if item["action_id"] not in action_ids or item["action_id"] in seen_decisions:
            raise ValueError(f"AQ11[{index}].action_id must be a unique existing A#")
        seen_decisions.add(item["action_id"])
        if not isinstance(item["basis"], list) or not item["basis"] or any(x not in DECISION_BASES for x in item["basis"]):
            raise ValueError(f"AQ11[{index}].basis is invalid")
        note = require_text(item["note"], f"AQ11[{index}].note", allow_empty=True)
        if "OTHER" in item["basis"] and not note.strip():
            raise ValueError("AQ11 OTHER basis requires note")

    if answers["AQ12"] not in OVERALL_OUTCOMES:
        raise ValueError("AQ12 answer is invalid")

    counterfactuals = answers["AQ13"]
    if not isinstance(counterfactuals, list):
        raise ValueError("AQ13 must be an array")
    for index, item in enumerate(counterfactuals):
        if not isinstance(item, dict):
            raise ValueError(f"AQ13[{index}] must be an object")
        exact_fields(item, {"condition", "alternate_action_type", "alternate_action_subtype", "note"}, set(), f"AQ13[{index}]")
        require_text(item["condition"], f"AQ13[{index}].condition")
        if item["alternate_action_type"] not in ACTION_TYPES or item["alternate_action_subtype"] not in ACTION_SUBTYPES[item["alternate_action_type"]]:
            raise ValueError(f"AQ13[{index}] has invalid alternate action type/subtype")
        require_text(item["note"], f"AQ13[{index}].note", allow_empty=True)

    narrative = require_text(answers["AQ14"], "AQ14")
    positions = [narrative.find(heading) for heading in NARRATIVE_HEADINGS]
    if any(p < 0 for p in positions) or positions != sorted(positions) or not narrative.startswith("NARRATIVE_MAPPING"):
        raise ValueError("AQ14 required headings are missing or out of order")
    known = ui_ids | action_ids | plan_ids | evidence_ids
    refs = set(re.findall(r"\b(?:UI|A|P|E)[1-9][0-9]*\b", narrative))
    if refs - known:
        raise ValueError(f"AQ14 contains unknown IDs: {sorted(refs - known)!r}")
    if ui_ids - refs or action_ids - refs:
        raise ValueError("AQ14 must reference every UI# and A# identifier")
    if answers["AQ5"] == "YES" and plan_ids - refs:
        raise ValueError("AQ14 must reference every P# identifier when a prior plan exists")
    if answers["AQ5"] == "NO" and "NO_PRIOR_PLAN" not in narrative:
        raise ValueError("AQ14 must state NO_PRIOR_PLAN when AQ5 is NO")


def validate_router_cycle(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    required = {"cycle_id", "scope", "pairs", "directive"}
    optional = {"instruction", "impasse_evidence"}
    exact_fields(value, required, optional, label)
    require_text(value["cycle_id"], f"{label}.cycle_id")
    if value["scope"] not in SCOPES:
        raise ValueError(f"{label}.scope is invalid")
    validate_router_pairs(value["pairs"], f"{label}.pairs")
    if value["directive"] not in DIRECTIVES:
        raise ValueError(f"{label}.directive is invalid")
    if value["directive"] == "CONTINUE":
        require_text(value.get("instruction"), f"{label}.instruction")
    if value["directive"] == "IMPASSE":
        require_text(value.get("impasse_evidence"), f"{label}.impasse_evidence")


def validate_action(action: Any, persisted: bool) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ValueError("action must be a JSON object")
    common = {"action_type", "scope"}
    optional = {"source"}
    if persisted:
        common |= {"sequence", "recorded_at"}
    action_type = action.get("action_type")

    if action_type == "recorder_invocation":
        exact_fields(action, common, optional, "recorder_invocation")
    elif action_type == "action_questionnaire":
        exact_fields(action, common | {"pairs"}, optional, "action_questionnaire")
        validate_questionnaire_pairs(action["pairs"], "action_questionnaire.pairs")
    elif action_type == "end_turn_result":
        exact_fields(action, common | {"router_cycle"}, optional, "end_turn_result")
        validate_router_cycle(action["router_cycle"], "end_turn_result.router_cycle")
        if action["router_cycle"]["scope"] != action["scope"]:
            raise ValueError("end_turn_result scope must match router_cycle scope")
    else:
        raise ValueError(f"unsupported action_type: {action_type!r}")

    if action["scope"] not in SCOPES:
        raise ValueError("scope must be worker or orchestrator")
    if "source" in action:
        validate_source(action["source"], f"{action_type}.source")
    if persisted:
        if not isinstance(action["sequence"], int) or isinstance(action["sequence"], bool) or action["sequence"] < 1:
            raise ValueError("sequence must be a positive integer")
        validate_iso(action["recorded_at"], "recorded_at")
    return dict(action)


def validate_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")
    exact_fields(record, {"record_id", "snapshot_created_at", "predecessor", "actions"}, set(), "record")
    require_text(record["record_id"], "record_id")
    validate_iso(record["snapshot_created_at"], "snapshot_created_at")
    predecessor = record["predecessor"]
    if predecessor is not None:
        if not isinstance(predecessor, dict):
            raise ValueError("predecessor must be null or an object")
        exact_fields(predecessor, {"filename", "sha256"}, set(), "predecessor")
        parse_stamp(require_text(predecessor["filename"], "predecessor.filename"))
        digest = require_text(predecessor["sha256"], "predecessor.sha256")
        if not HASH_RE.fullmatch(digest):
            raise ValueError("predecessor.sha256 must be a lowercase SHA-256 digest")
    actions = record["actions"]
    if not isinstance(actions, list) or not actions:
        raise ValueError("actions must be a non-empty array")
    for expected, action in enumerate(actions, start=1):
        validated = validate_action(action, persisted=True)
        if validated["sequence"] != expected:
            raise ValueError(f"action sequence must be contiguous; expected {expected}")
    return dict(record)


def load_predecessor(path_text: str | None, persisted_name: str | None, record_id: str | None):
    if path_text is None:
        if persisted_name is not None:
            raise ValueError("--record-name requires --record")
        return None, None, None, None, require_text(record_id, "record_id")
    if not persisted_name:
        raise ValueError("--record-name is required with --record")
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(path)
    prior_stamp = parse_stamp(persisted_name)
    record = validate_record(read_json(path))
    if record_id and record["record_id"] != record_id:
        raise ValueError("record_id does not match predecessor")
    return record, persisted_name, file_sha256(path), prior_stamp, record["record_id"]


def make_stamp(prior_stamp: str | None) -> str:
    stamp = now_stamp()
    if prior_stamp is not None and stamp <= prior_stamp:
        raise ValueError("new snapshot timestamp is not later than predecessor")
    return stamp


def append_payload(payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    payload = validate_action(payload, persisted=False)
    prior, predecessor_name, predecessor_hash, prior_stamp, record_id = load_predecessor(
        args.record, args.record_name, args.record_id
    )
    actions = [] if prior is None else [dict(item) for item in prior["actions"]]
    action = {**payload, "sequence": len(actions) + 1, "recorded_at": now_iso()}
    validate_action(action, persisted=True)
    actions.append(action)
    stamp = make_stamp(prior_stamp)
    filename = f"{RECORD_PREFIX}{stamp}{RECORD_SUFFIX}"
    record = {
        "record_id": record_id,
        "snapshot_created_at": now_iso(),
        "predecessor": None if prior is None else {"filename": predecessor_name, "sha256": predecessor_hash},
        "actions": actions,
    }
    validate_record(record)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    write_json(output_path, record)
    return {
        "status": "RECORDED",
        "record": str(output_path),
        "record_filename": filename,
        "record_sha256": file_sha256(output_path),
        "record_id": record_id,
        "sequence": action["sequence"],
        "action_type": action["action_type"],
        "recorded_at": action["recorded_at"],
    }


def source_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    source: dict[str, Any] = {}
    if getattr(args, "chat_id", None) is not None:
        source["chat_id"] = args.chat_id
    if getattr(args, "chat_title", None) is not None:
        source["chat_title"] = args.chat_title
    return source or None


def run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True)
    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeError(f"child script produced no JSON; stderr={completed.stderr.strip()!r}")
    data = json.loads(stdout)
    if completed.returncode != 0:
        raise RuntimeError(f"child script failed: {data!r}")
    return data


def cmd_invoke(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {"action_type": "recorder_invocation", "scope": args.scope}
    source = source_from_args(args)
    if source:
        payload["source"] = source
    receipt = append_payload(payload, args)
    state_path = Path(args.state_dir) / f"action-questioner-{now_stamp()}.json"
    command = [
        sys.executable, args.questioner, "start",
        "--state", str(state_path),
        "--scope", args.scope,
        "--recorder", str(Path(__file__).resolve()),
        "--router", args.router,
        "--output-dir", args.output_dir,
        "--record", receipt["record"],
        "--record-name", receipt["record_filename"],
        "--record-id", receipt["record_id"],
    ]
    if args.chat_id is not None:
        command += ["--chat-id", args.chat_id]
    if args.chat_title is not None:
        command += ["--chat-title", args.chat_title]
    questioner = run_json(command)
    print(json.dumps({"status": "QUESTIONER_STARTED", "invocation": receipt, "questioner": questioner}, ensure_ascii=False))
    return 0


def cmd_append(args: argparse.Namespace) -> int:
    payload = read_json(Path(args.action_file))
    if not isinstance(payload, dict):
        raise ValueError("action-file must contain a JSON object")
    if payload.get("action_type") == "recorder_invocation":
        raise ValueError("recorder_invocation is created only by invoke")
    print(json.dumps(append_payload(payload, args), ensure_ascii=False))
    return 0


def add_record_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--record")
    parser.add_argument("--record-name")
    parser.add_argument("--record-id")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    invoke = sub.add_parser("invoke")
    add_record_args(invoke)
    invoke.add_argument("--scope", required=True, choices=sorted(SCOPES))
    invoke.add_argument("--state-dir", required=True)
    invoke.add_argument("--questioner", required=True)
    invoke.add_argument("--router", required=True)
    invoke.add_argument("--chat-id")
    invoke.add_argument("--chat-title")
    invoke.set_defaults(fn=cmd_invoke)
    append = sub.add_parser("append")
    add_record_args(append)
    append.add_argument("--action-file", required=True)
    append.set_defaults(fn=cmd_append)
    args = ap.parse_args()
    try:
        return args.fn(args)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "code": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
