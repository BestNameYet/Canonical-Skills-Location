#!/usr/bin/env python3
"""Interactive execution-event recorder using timestamped project snapshots.

Persistent records follow ``execution-record.schema.json``. Each entry is an
incremental event delta: do not restate history already present in earlier
entries unless needed to identify the new event or its dependency. Runtime
session and receipt files are implementation bookkeeping and do not declare
independent format identities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RECORD_PREFIX = "execution-record_"
RECORD_SUFFIX = ".json"
FORMAT_VERSION = 1
UNAVAILABLE = "unavailable"

STAMP_RE = re.compile(r"^execution-record_(\d{8}T\d{12}Z)\.json$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ENTRY_ID_RE = re.compile(r"^[0-9a-f]{32}$")

ROOT_FIELDS = {"format_version", "created_at", "updated_at", "snapshot", "project", "entries"}
SNAPSHOT_FIELDS = {"timestamp", "filename", "predecessor_filename", "predecessor_sha256"}
PROJECT_FIELDS = {"project_id", "project_title"}
ENTRY_FIELDS = {"entry_id", "sequence", "recorded_at", "chat_id", "chat_title", "event", "outcome", "evidence"}

QUESTIONS = [
    ("event", "What new event occurred? Record only the delta from prior entries, including the relevant action or target."),
    ("outcome", "What new outcome or resulting state followed from that event?"),
    ("evidence", "What new observable evidence supports that outcome?"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_exposed(value: str | None) -> str:
    value = (value or "").strip()
    return value if value else UNAVAILABLE


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def require_exact_fields(obj: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(obj)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{label} fields invalid: missing={missing!r}, extra={extra!r}")


def validate_iso(value: Any, label: str) -> None:
    text = require_text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone information")


def parse_persisted_stamp(filename: str) -> str:
    match = STAMP_RE.fullmatch(filename)
    if not match:
        raise ValueError("record filename must match execution-record_YYYYMMDDTHHMMSSffffffZ.json")
    return match.group(1)


def compact_legacy_entry(entry: dict[str, Any]) -> dict[str, Any]:
    event_parts = [str(entry.get("occurred", "")).strip()]
    for key in ("type", "purpose", "operated_on"):
        value = str(entry.get(key, "")).strip()
        if value:
            event_parts.append(f"{key}={value}")

    outcome_parts = [str(entry.get("result", "")).strip()]
    for key in ("state_change", "status"):
        value = str(entry.get(key, "")).strip()
        if value:
            outcome_parts.append(f"{key}={value}")

    return {
        "entry_id": entry.get("entry_id"),
        "sequence": entry.get("sequence"),
        "recorded_at": entry.get("recorded_at"),
        "chat_id": normalize_exposed(entry.get("chat_id")),
        "chat_title": normalize_exposed(entry.get("chat_title")),
        "event": " | ".join(part for part in event_parts if part),
        "outcome": " | ".join(part for part in outcome_parts if part),
        "evidence": str(entry.get("evidence", "")).strip(),
    }


def normalize_record_format(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")

    if record.get("format_version") == FORMAT_VERSION:
        return dict(record)

    legacy_required = {"created_at", "updated_at", "snapshot", "project", "entries"}
    if legacy_required.issubset(record) and isinstance(record.get("entries"), list):
        return {
            "format_version": FORMAT_VERSION,
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "snapshot": record["snapshot"],
            "project": record["project"],
            "entries": [compact_legacy_entry(entry) for entry in record["entries"]],
        }

    raise ValueError("unsupported execution-record format")


def validate_record(record: Any) -> dict[str, Any]:
    record = normalize_record_format(record)
    require_exact_fields(record, ROOT_FIELDS, "record")
    if record["format_version"] != FORMAT_VERSION:
        raise ValueError("unsupported format_version")

    validate_iso(record["created_at"], "created_at")
    validate_iso(record["updated_at"], "updated_at")

    snapshot = record["snapshot"]
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    require_exact_fields(snapshot, SNAPSHOT_FIELDS, "snapshot")
    stamp = require_text(snapshot["timestamp"], "snapshot.timestamp")
    filename = require_text(snapshot["filename"], "snapshot.filename")
    if filename != f"{RECORD_PREFIX}{stamp}{RECORD_SUFFIX}" or parse_persisted_stamp(filename) != stamp:
        raise ValueError("snapshot filename and timestamp do not agree")

    predecessor_name = snapshot["predecessor_filename"]
    predecessor_hash = snapshot["predecessor_sha256"]
    if (predecessor_name is None) != (predecessor_hash is None):
        raise ValueError("predecessor filename/hash must both be null or both be present")
    if predecessor_name is not None:
        predecessor_stamp = parse_persisted_stamp(require_text(predecessor_name, "predecessor_filename"))
        if predecessor_stamp >= stamp:
            raise ValueError("predecessor timestamp must be earlier than snapshot timestamp")
        if not isinstance(predecessor_hash, str) or not HASH_RE.fullmatch(predecessor_hash):
            raise ValueError("predecessor_sha256 must be a lowercase SHA-256 digest")

    project = record["project"]
    if not isinstance(project, dict):
        raise ValueError("project must be an object")
    require_exact_fields(project, PROJECT_FIELDS, "project")
    require_text(project["project_id"], "project.project_id")
    require_text(project["project_title"], "project.project_title")

    entries = record["entries"]
    if not isinstance(entries, list):
        raise ValueError("entries must be a list")

    seen_ids: set[str] = set()
    for expected_sequence, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"entry {expected_sequence} must be an object")
        require_exact_fields(entry, ENTRY_FIELDS, f"entry {expected_sequence}")
        if entry["sequence"] != expected_sequence:
            raise ValueError(f"entry {expected_sequence} has non-contiguous sequence")
        if not isinstance(entry["entry_id"], str) or not ENTRY_ID_RE.fullmatch(entry["entry_id"]):
            raise ValueError(f"entry {expected_sequence} has invalid entry_id")
        if entry["entry_id"] in seen_ids:
            raise ValueError(f"duplicate entry_id: {entry['entry_id']}")
        seen_ids.add(entry["entry_id"])
        validate_iso(entry["recorded_at"], f"entry {expected_sequence}.recorded_at")
        for field in ("chat_id", "chat_title", "event", "outcome", "evidence"):
            require_text(entry[field], f"entry {expected_sequence}.{field}")

    return record


def new_record(project_id: str, project_title: str, stamp: str) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "snapshot": {
            "timestamp": stamp,
            "filename": f"{RECORD_PREFIX}{stamp}{RECORD_SUFFIX}",
            "predecessor_filename": None,
            "predecessor_sha256": None,
        },
        "project": {"project_id": project_id, "project_title": project_title},
        "entries": [],
    }


def reconcile_project_identity(record: dict[str, Any], project_id: str, project_title: str) -> None:
    project = record["project"]
    existing_id = normalize_exposed(project.get("project_id"))
    existing_title = normalize_exposed(project.get("project_title"))
    if existing_id != UNAVAILABLE and project_id != UNAVAILABLE and existing_id != project_id:
        raise ValueError(f"project_id mismatch: record={existing_id!r}, invocation={project_id!r}")
    if existing_id == UNAVAILABLE and project_id != UNAVAILABLE:
        project["project_id"] = project_id
    if existing_title == UNAVAILABLE and project_title != UNAVAILABLE:
        project["project_title"] = project_title


def load_source_record(source_path: str | None, source_name: str | None, project_id: str, project_title: str) -> tuple[dict[str, Any] | None, str | None, str | None, str | None]:
    if not source_path:
        if source_name:
            raise ValueError("--record-name requires --record")
        return None, None, None, None
    if not source_name:
        raise ValueError("--record-name is required when --record is supplied")

    prior_stamp = parse_persisted_stamp(source_name)
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"source record not found: {path}")

    record = validate_record(read_json(path))
    reconcile_project_identity(record, project_id, project_title)
    if record["snapshot"]["filename"] != source_name:
        raise ValueError("--record-name does not match source snapshot filename")
    return record, sha256(path), source_name, prior_stamp


def make_new_stamp(prior_stamp: str | None) -> str:
    stamp = now_stamp()
    if prior_stamp is not None and stamp <= prior_stamp:
        raise ValueError("new snapshot timestamp is not later than predecessor")
    return stamp


def append_entry(state: dict[str, Any]) -> tuple[Path, dict[str, Any], str | None]:
    output_dir = Path(state["output_dir"])
    project_id = normalize_exposed(state.get("project_id"))
    project_title = normalize_exposed(state.get("project_title"))
    chat_id = normalize_exposed(state.get("chat_id"))
    chat_title = normalize_exposed(state.get("chat_title"))

    prior, source_hash, source_name, prior_stamp = load_source_record(
        state.get("source_record_path"), state.get("source_persisted_name"), project_id, project_title
    )
    stamp = make_new_stamp(prior_stamp)
    output_path = output_dir / f"{RECORD_PREFIX}{stamp}{RECORD_SUFFIX}"

    record = prior if prior is not None else new_record(project_id, project_title, stamp)
    if prior is not None:
        record["format_version"] = FORMAT_VERSION
        record["updated_at"] = now_iso()
        record["snapshot"] = {
            "timestamp": stamp,
            "filename": output_path.name,
            "predecessor_filename": source_name,
            "predecessor_sha256": source_hash,
        }

    entry = {
        "entry_id": secrets.token_hex(16),
        "sequence": len(record["entries"]) + 1,
        "recorded_at": now_iso(),
        "chat_id": chat_id,
        "chat_title": chat_title,
        **state["answers"],
    }
    record["entries"].append(entry)
    write_json(output_path, validate_record(record))
    return output_path, entry, source_hash


def validate_session_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise ValueError("recorder session state must be an object")
    for key in ("session_id", "started_at", "question_index", "answers", "output_dir", "state_dir"):
        if key not in state:
            raise ValueError(f"recorder session state missing {key!r}")
    require_text(state["session_id"], "session_id")
    validate_iso(state["started_at"], "started_at")
    if not isinstance(state["question_index"], int) or isinstance(state["question_index"], bool):
        raise ValueError("question_index must be an integer")
    if not isinstance(state["answers"], dict):
        raise ValueError("answers must be an object")
    return state


def start(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    output_dir = Path(args.output_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.record:
        if not args.record_name:
            raise ValueError("--record-name is required when --record is supplied")
        source = Path(args.record)
        if not source.exists():
            raise FileNotFoundError(f"source record not found: {source}")
        record = validate_record(read_json(source))
        if record["snapshot"]["filename"] != args.record_name:
            raise ValueError("--record-name does not match source snapshot filename")
    elif args.record_name:
        raise ValueError("--record-name requires --record")

    session_id = secrets.token_hex(16)
    state_path = state_dir / f"recorder-session-{session_id}.json"
    state = {
        "session_id": session_id,
        "started_at": now_iso(),
        "question_index": 0,
        "answers": {},
        "source_record_path": args.record,
        "source_persisted_name": args.record_name,
        "output_dir": str(output_dir),
        "state_dir": str(state_dir),
        "project_id": normalize_exposed(args.project_id),
        "project_title": normalize_exposed(args.project_title),
        "chat_id": normalize_exposed(args.chat_id),
        "chat_title": normalize_exposed(args.chat_title),
    }
    write_json(state_path, state)

    field, question = QUESTIONS[0]
    print(json.dumps({"status": "QUESTION", "state": str(state_path), "question_number": 1, "field": field, "question": question}, ensure_ascii=False, sort_keys=True))
    return 0


def answer(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    state = validate_session_state(read_json(state_path))
    if state.get("completed_at"):
        raise ValueError("session already complete")

    idx = state["question_index"]
    if idx < 0 or idx >= len(QUESTIONS):
        raise ValueError("invalid recorder question index")

    text = args.text.strip()
    if not text:
        print(json.dumps({"status": "FAIL", "code": "EMPTY_ANSWER", "state": str(state_path), "question_number": idx + 1, "question": QUESTIONS[idx][1]}, ensure_ascii=False, sort_keys=True))
        return 2

    field, _ = QUESTIONS[idx]
    state["answers"][field] = text
    state["question_index"] = idx + 1
    write_json(state_path, state)

    if state["question_index"] < len(QUESTIONS):
        next_field, question = QUESTIONS[state["question_index"]]
        print(json.dumps({"status": "QUESTION", "state": str(state_path), "question_number": state["question_index"] + 1, "field": next_field, "question": question}, ensure_ascii=False, sort_keys=True))
        return 0

    output_path, entry, source_hash = append_entry(state)
    receipt = {
        "status": "RECORDED",
        "record": str(output_path),
        "record_filename": output_path.name,
        "entry_id": entry["entry_id"],
        "sequence": entry["sequence"],
        "source_record_filename": state.get("source_persisted_name"),
        "source_record_sha256": source_hash,
        "record_sha256": sha256(output_path),
        "recorded_at": entry["recorded_at"],
    }
    receipt_path = Path(state["state_dir"]) / f"recorder-receipt-{entry['entry_id']}.json"
    write_json(receipt_path, receipt)
    state.update({"completed_at": now_iso(), "entry_id": entry["entry_id"], "sequence": entry["sequence"], "receipt": str(receipt_path), "record": str(output_path)})
    write_json(state_path, state)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="mode", required=True)
    s = sp.add_parser("start")
    s.add_argument("--state-dir", required=True)
    s.add_argument("--output-dir", required=True)
    s.add_argument("--record")
    s.add_argument("--record-name")
    s.add_argument("--project-title", default=UNAVAILABLE)
    s.add_argument("--project-id", default=UNAVAILABLE)
    s.add_argument("--chat-title", default=UNAVAILABLE)
    s.add_argument("--chat-id", default=UNAVAILABLE)
    a = sp.add_parser("answer")
    a.add_argument("--state", required=True)
    a.add_argument("--text", required=True)
    args = ap.parse_args()
    try:
        return start(args) if args.mode == "start" else answer(args)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "code": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
