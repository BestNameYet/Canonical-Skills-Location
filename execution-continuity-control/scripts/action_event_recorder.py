#!/usr/bin/env python3
"""Immutable execution-record appender and questionnaire bootstrapper.

External action tracking always enters through ``invoke``. The recorder does
not know why it was invoked and does not classify the action. It appends only a
``recorder_invocation`` action with the current timestamp, then starts the
action questioner.

Canonical child scripts send already-formatted data objects back through
``append``. ``append`` stores those objects without starting another questioner,
which prevents recursive audit machinery.
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

QUESTIONNAIRE = [
    ("AQ1", "What just occurred?"),
    ("AQ2", "Is this action an end-of-turn attempt? Answer YES or NO."),
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


def validate_pairs(pairs: Any, label: str, questionnaire: bool = False) -> None:
    if not isinstance(pairs, list) or not pairs:
        raise ValueError(f"{label} must be a non-empty array")
    if questionnaire and len(pairs) != 8:
        raise ValueError(f"{label} must contain exactly eight pairs")
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise ValueError(f"{label}[{index}] must be an object")
        exact_fields(pair, {"id", "question", "answer"}, set(), f"{label}[{index}]")
        require_text(pair["id"], f"{label}[{index}].id")
        require_text(pair["question"], f"{label}[{index}].question")
        require_text(pair["answer"], f"{label}[{index}].answer")
        if questionnaire:
            expected_id, expected_question = QUESTIONNAIRE[index]
            if pair["id"] != expected_id or pair["question"] != expected_question:
                raise ValueError(f"{label}[{index}] does not match {expected_id}")
            if expected_id == "AQ2" and pair["answer"] not in {"YES", "NO"}:
                raise ValueError("AQ2 answer must be YES or NO")


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
        validate_pairs(action["pairs"], "action_questionnaire.pairs", questionnaire=True)
    elif action_type == "router_cycle":
        exact_fields(
            action,
            common | {"pairs", "directive"},
            optional | {"instruction", "impasse_evidence"},
            "router_cycle",
        )
        validate_pairs(action["pairs"], "router_cycle.pairs")
        if action["directive"] not in DIRECTIVES:
            raise ValueError("router_cycle.directive is invalid")
        if action["directive"] == "CONTINUE":
            require_text(action.get("instruction"), "router_cycle.instruction")
        if action["directive"] == "IMPASSE":
            require_text(action.get("impasse_evidence"), "router_cycle.impasse_evidence")
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
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"child script produced invalid JSON: {stdout!r}") from exc
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
        sys.executable,
        args.questioner,
        "start",
        "--state",
        str(state_path),
        "--scope",
        args.scope,
        "--recorder",
        str(Path(__file__).resolve()),
        "--router",
        args.router,
        "--output-dir",
        args.output_dir,
        "--record",
        receipt["record"],
        "--record-name",
        receipt["record_filename"],
        "--record-id",
        receipt["record_id"],
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
    if payload.get("action_type") == "recorder_invocation":
        raise ValueError("recorder_invocation is created only by invoke")
    receipt = append_payload(payload, args)
    print(json.dumps(receipt, ensure_ascii=False))
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
