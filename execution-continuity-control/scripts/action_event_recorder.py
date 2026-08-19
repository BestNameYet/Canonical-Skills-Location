#!/usr/bin/env python3
"""Append one completed action to an immutable execution-record snapshot.

This recorder is deliberately non-interactive. It never asks the eight-action
questions. Ordinary actions are supplied directly with ``record``. Structured
actions produced by other canonical scripts, such as ``action_questioner.py``
or ``end_turn_router.py``, are supplied with ``append``.

Every successful invocation writes a new complete snapshot. The predecessor is
never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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
    ("AQ1", "What just occurred?"),
    ("AQ2", "What type was it?"),
    ("AQ3", "Why did it occur?"),
    ("AQ4", "What did it operate on?"),
    ("AQ5", "What actually happened?"),
    ("AQ6", "What artifacts or state changed?"),
    ("AQ7", "What is its status?"),
    ("AQ8", "What evidence supports that status or result?"),
]


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


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def require_exact_fields(obj: dict[str, Any], required: set[str], optional: set[str], label: str) -> None:
    actual = set(obj)
    missing = required - actual
    extra = actual - required - optional
    if missing or extra:
        raise ValueError(f"{label} fields invalid: missing={sorted(missing)!r}, extra={sorted(extra)!r}")


def validate_iso(value: Any, label: str) -> None:
    text = require_text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone information")


def parse_stamp(filename: str) -> str:
    match = STAMP_RE.fullmatch(filename)
    if not match:
        raise ValueError("record filename must match execution-record_YYYYMMDDTHHMMSSffffffZ.json")
    return match.group(1)


def validate_source(source: Any, label: str) -> None:
    if not isinstance(source, dict):
        raise ValueError(f"{label} must be an object")
    require_exact_fields(source, set(), {"chat_id", "chat_title"}, label)
    for key, value in source.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{label}.{key} must be a string or null")


def validate_pairs(pairs: Any, label: str, exact_questions: list[tuple[str, str]] | None = None) -> None:
    if not isinstance(pairs, list) or not pairs:
        raise ValueError(f"{label} must be a non-empty array")
    if exact_questions is not None and len(pairs) != len(exact_questions):
        raise ValueError(f"{label} must contain exactly {len(exact_questions)} pairs")
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise ValueError(f"{label}[{index}] must be an object")
        require_exact_fields(pair, {"id", "question", "answer"}, set(), f"{label}[{index}]")
        require_text(pair["id"], f"{label}[{index}].id")
        require_text(pair["question"], f"{label}[{index}].question")
        require_text(pair["answer"], f"{label}[{index}].answer")
        if exact_questions is not None:
            expected_id, expected_question = exact_questions[index]
            if pair["id"] != expected_id or pair["question"] != expected_question:
                raise ValueError(f"{label}[{index}] does not match canonical question {expected_id}")


def validate_action(action: Any, persisted: bool) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ValueError("action must be a JSON object")

    common_required = {"action_type", "scope"}
    common_optional = {"source"}
    if persisted:
        common_required |= {"sequence", "recorded_at"}

    action_type = action.get("action_type")
    if action_type == "recorded_action":
        required = common_required | {"action", "result"}
        optional = common_optional | {"evidence"}
        require_exact_fields(action, required, optional, "recorded_action")
        require_text(action["action"], "recorded_action.action")
        require_text(action["result"], "recorded_action.result")
        if "evidence" in action:
            if not isinstance(action["evidence"], list):
                raise ValueError("recorded_action.evidence must be an array")
            for i, item in enumerate(action["evidence"]):
                require_text(item, f"recorded_action.evidence[{i}]")
    elif action_type == "action_questionnaire":
        required = common_required | {"subject_sequence", "pairs"}
        optional = common_optional
        require_exact_fields(action, required, optional, "action_questionnaire")
        if not isinstance(action["subject_sequence"], int) or isinstance(action["subject_sequence"], bool) or action["subject_sequence"] < 1:
            raise ValueError("action_questionnaire.subject_sequence must be a positive integer")
        validate_pairs(action["pairs"], "action_questionnaire.pairs", ACTION_QUESTIONS)
    elif action_type == "router_cycle":
        required = common_required | {"pairs", "directive"}
        optional = common_optional | {"cycle_id", "instruction", "impasse_evidence"}
        require_exact_fields(action, required, optional, "router_cycle")
        validate_pairs(action["pairs"], "router_cycle.pairs")
        if action["directive"] not in DIRECTIVES:
            raise ValueError("router_cycle.directive is invalid")
        if "cycle_id" in action:
            require_text(action["cycle_id"], "router_cycle.cycle_id")
        if action["directive"] == "CONTINUE":
            require_text(action.get("instruction"), "router_cycle.instruction")
        if action["directive"] == "IMPASSE":
            require_text(action.get("impasse_evidence"), "router_cycle.impasse_evidence")
    else:
        raise ValueError(f"unsupported action_type: {action_type!r}")

    if action["scope"] not in SCOPES:
        raise ValueError("scope must be 'worker' or 'orchestrator'")
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
    require_exact_fields(
        record,
        {"record_id", "snapshot_created_at", "predecessor", "actions"},
        set(),
        "record",
    )
    require_text(record["record_id"], "record_id")
    validate_iso(record["snapshot_created_at"], "snapshot_created_at")

    predecessor = record["predecessor"]
    if predecessor is not None:
        if not isinstance(predecessor, dict):
            raise ValueError("predecessor must be null or an object")
        require_exact_fields(predecessor, {"filename", "sha256"}, set(), "predecessor")
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
        if not record_id:
            raise ValueError("--record-id is required for the first snapshot")
        return None, None, None, None

    if not persisted_name:
        raise ValueError("--record-name is required with --record")
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(path)
    parse_stamp(persisted_name)
    record = validate_record(read_json(path))
    if record_id and record["record_id"] != record_id:
        raise ValueError("record_id does not match predecessor")
    return record, persisted_name, file_sha256(path), parse_stamp(persisted_name)


def make_stamp(prior_stamp: str | None) -> str:
    stamp = now_stamp()
    if prior_stamp is not None and stamp <= prior_stamp:
        raise ValueError("new snapshot timestamp is not later than predecessor")
    return stamp


def append_payload(
    payload: dict[str, Any],
    output_dir: Path,
    record_path: str | None,
    record_name: str | None,
    record_id: str | None,
) -> dict[str, Any]:
    payload = validate_action(payload, persisted=False)
    prior, predecessor_name, predecessor_hash, prior_stamp = load_predecessor(
        record_path, record_name, record_id
    )
    stamp = make_stamp(prior_stamp)
    filename = f"{RECORD_PREFIX}{stamp}{RECORD_SUFFIX}"

    if prior is None:
        actions: list[dict[str, Any]] = []
        resolved_record_id = require_text(record_id, "record_id")
        predecessor = None
    else:
        actions = [dict(item) for item in prior["actions"]]
        resolved_record_id = prior["record_id"]
        predecessor = {"filename": predecessor_name, "sha256": predecessor_hash}

    action = {
        **payload,
        "sequence": len(actions) + 1,
        "recorded_at": now_iso(),
    }
    validate_action(action, persisted=True)
    actions.append(action)

    record = {
        "record_id": resolved_record_id,
        "snapshot_created_at": now_iso(),
        "predecessor": predecessor,
        "actions": actions,
    }
    validate_record(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    write_json(output_path, record)
    return {
        "status": "RECORDED",
        "record": str(output_path),
        "record_filename": filename,
        "record_sha256": file_sha256(output_path),
        "sequence": action["sequence"],
        "action_type": action["action_type"],
        "recorded_at": action["recorded_at"],
        "predecessor_filename": predecessor_name,
        "predecessor_sha256": predecessor_hash,
    }


def source_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    source: dict[str, Any] = {}
    if args.chat_id is not None:
        source["chat_id"] = args.chat_id
    if args.chat_title is not None:
        source["chat_title"] = args.chat_title
    return source or None


def cmd_record(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "action_type": "recorded_action",
        "scope": args.scope,
        "action": args.action,
        "result": args.result,
    }
    if args.evidence:
        payload["evidence"] = args.evidence
    source = source_from_args(args)
    if source:
        payload["source"] = source
    receipt = append_payload(
        payload,
        Path(args.output_dir),
        args.record,
        args.record_name,
        args.record_id,
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_append(args: argparse.Namespace) -> int:
    payload = read_json(Path(args.action_file))
    receipt = append_payload(
        payload,
        Path(args.output_dir),
        args.record,
        args.record_name,
        args.record_id,
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


def add_record_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--record")
    parser.add_argument("--record-name")
    parser.add_argument("--record-id")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)

    record = sub.add_parser("record", help="append a lightweight ordinary action without an interview")
    add_record_args(record)
    record.add_argument("--scope", required=True, choices=sorted(SCOPES))
    record.add_argument("--action", required=True)
    record.add_argument("--result", required=True)
    record.add_argument("--evidence", action="append", default=[])
    record.add_argument("--chat-id")
    record.add_argument("--chat-title")
    record.set_defaults(fn=cmd_record)

    append = sub.add_parser("append", help="append a structured action payload produced by another script")
    add_record_args(append)
    append.add_argument("--action-file", required=True)
    append.set_defaults(fn=cmd_append)

    args = ap.parse_args()
    try:
        return args.fn(args)
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAIL", "code": type(exc).__name__, "detail": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
