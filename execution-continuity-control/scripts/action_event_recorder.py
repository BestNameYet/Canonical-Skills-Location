#!/usr/bin/env python3
"""Interactive execution-event recorder using timestamped project snapshots.

The persistent record format is controlled by the canonical
``execution-record.schema.json`` shipped beside this skill. The recorder uses
only the Python standard library and enforces the same structural contract plus
cross-field invariants that are not expressed by the JSON Schema.

The caller supplies the latest persisted project record, if one exists, with
``--record`` and its persisted filename with ``--record-name``. After the eighth
answer, the recorder appends exactly one entry and writes a new complete
snapshot named:

    execution-record_YYYYMMDDTHHMMSSffffffZ.json

Persistence of the returned record is owned by the calling environment.
Runtime session and receipt objects are implementation bookkeeping and do not
declare independent format identities.
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

ROOT_FIELDS = {
    "format_version", "created_at", "updated_at", "snapshot", "project", "entry_count", "entries",
}
SNAPSHOT_FIELDS = {"timestamp", "filename", "predecessor_filename", "predecessor_sha256"}
PROJECT_FIELDS = {"project_id", "project_title"}
ENTRY_FIELDS = {
    "entry_id", "sequence", "recorded_at", "project_id", "project_title", "chat_id", "chat_title",
    "source_record_filename", "source_record_sha256", "occurred", "type", "purpose", "operated_on",
    "result", "state_change", "status", "evidence",
}
NARRATIVE_FIELDS = (
    "occurred", "type", "purpose", "operated_on", "result", "state_change", "status", "evidence",
)

QUESTIONS = [
    ("occurred", "What just occurred?"),
    ("type", "What type was it?"),
    ("purpose", "Why did it occur?"),
    ("operated_on", "What did it operate on?"),
    ("result", "What actually happened?"),
    ("state_change", "What artifacts or state changed?"),
    ("status", "What is its status?"),
    ("evidence", "What evidence supports that status or result?"),
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


def require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def require_exact_fields(obj: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(obj)
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f"missing={sorted(missing)!r}")
        if extra:
            parts.append(f"extra={sorted(extra)!r}")
        raise ValueError(f"{label} fields invalid: " + ", ".join(parts))


def validate_iso_datetime(value: Any, label: str) -> None:
    text = require_nonempty_string(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone information")


def parse_persisted_stamp(filename: str) -> str:
    match = STAMP_RE.fullmatch(filename)
    if not match:
        raise ValueError(
            "source record metadata must identify a persisted filename matching "
            "'execution-record_YYYYMMDDTHHMMSSffffffZ.json'"
        )
    return match.group(1)


def normalize_record_format(record: Any) -> dict[str, Any]:
    """Return the current record representation without mutating the source.

    Current records declare ``format_version``. Historical predecessor snapshots
    may predate that field. A structurally compatible historical snapshot is
    converted in memory by selecting only the persistent fields that remain part
    of the current contract. The historical file itself is never rewritten.
    """
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")

    if record.get("format_version") == FORMAT_VERSION:
        return dict(record)

    legacy_fields = {"created_at", "updated_at", "snapshot", "project", "entry_count", "entries"}
    if legacy_fields.issubset(record):
        return {
            "format_version": FORMAT_VERSION,
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "snapshot": record["snapshot"],
            "project": record["project"],
            "entry_count": record["entry_count"],
            "entries": record["entries"],
        }

    raise ValueError("unsupported execution-record format")


def validate_record(record: Any) -> dict[str, Any]:
    record = normalize_record_format(record)
    require_exact_fields(record, ROOT_FIELDS, "record")

    if record.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"unsupported format_version: {record.get('format_version')!r}")

    validate_iso_datetime(record.get("created_at"), "created_at")
    validate_iso_datetime(record.get("updated_at"), "updated_at")

    snapshot = record.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("record 'snapshot' must be an object")
    require_exact_fields(snapshot, SNAPSHOT_FIELDS, "snapshot")

    stamp = require_nonempty_string(snapshot.get("timestamp"), "snapshot.timestamp")
    filename = require_nonempty_string(snapshot.get("filename"), "snapshot.filename")
    if filename != f"{RECORD_PREFIX}{stamp}{RECORD_SUFFIX}":
        raise ValueError("snapshot filename does not match snapshot timestamp")
    if parse_persisted_stamp(filename) != stamp:
        raise ValueError("invalid snapshot timestamp format")

    predecessor_filename = snapshot.get("predecessor_filename")
    predecessor_hash = snapshot.get("predecessor_sha256")
    if predecessor_filename is None or predecessor_hash is None:
        if predecessor_filename is not None or predecessor_hash is not None:
            raise ValueError("snapshot predecessor filename/hash must both be null or both be present")
    else:
        predecessor_stamp = parse_persisted_stamp(
            require_nonempty_string(predecessor_filename, "snapshot.predecessor_filename")
        )
        if predecessor_stamp >= stamp:
            raise ValueError("snapshot predecessor timestamp must be earlier than snapshot timestamp")
        if not isinstance(predecessor_hash, str) or not HASH_RE.fullmatch(predecessor_hash):
            raise ValueError("snapshot.predecessor_sha256 must be a lowercase SHA-256 hex digest")

    project = record.get("project")
    if not isinstance(project, dict):
        raise ValueError("record 'project' must be an object")
    require_exact_fields(project, PROJECT_FIELDS, "project")
    require_nonempty_string(project.get("project_id"), "project.project_id")
    require_nonempty_string(project.get("project_title"), "project.project_title")

    entries = record.get("entries")
    if not isinstance(entries, list):
        raise ValueError("record 'entries' must be a list")
    entry_count = record.get("entry_count")
    if not isinstance(entry_count, int) or isinstance(entry_count, bool) or entry_count < 0:
        raise ValueError("entry_count must be a non-negative integer")
    if entry_count != len(entries):
        raise ValueError("entry_count does not equal the number of entries")

    seen_ids: set[str] = set()
    for expected_sequence, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"entry {expected_sequence} is not an object")
        require_exact_fields(entry, ENTRY_FIELDS, f"entry {expected_sequence}")

        if entry.get("sequence") != expected_sequence:
            raise ValueError(
                f"non-contiguous sequence at entry {expected_sequence}: found {entry.get('sequence')!r}"
            )

        entry_id = entry.get("entry_id")
        if not isinstance(entry_id, str) or not ENTRY_ID_RE.fullmatch(entry_id):
            raise ValueError(f"entry {expected_sequence} has invalid entry_id")
        if entry_id in seen_ids:
            raise ValueError(f"duplicate entry_id: {entry_id}")
        seen_ids.add(entry_id)

        validate_iso_datetime(entry.get("recorded_at"), f"entry {expected_sequence}.recorded_at")
        for provenance_field in ("project_id", "project_title", "chat_id", "chat_title"):
            require_nonempty_string(entry.get(provenance_field), f"entry {expected_sequence}.{provenance_field}")

        source_name = entry.get("source_record_filename")
        source_hash = entry.get("source_record_sha256")
        if source_name is None or source_hash is None:
            if source_name is not None or source_hash is not None:
                raise ValueError(
                    f"entry {expected_sequence} source filename/hash must both be null or both be present"
                )
        else:
            parse_persisted_stamp(
                require_nonempty_string(source_name, f"entry {expected_sequence}.source_record_filename")
            )
            if not isinstance(source_hash, str) or not HASH_RE.fullmatch(source_hash):
                raise ValueError(
                    f"entry {expected_sequence}.source_record_sha256 must be a lowercase SHA-256 digest"
                )

        for field in NARRATIVE_FIELDS:
            require_nonempty_string(entry.get(field), f"entry {expected_sequence}.{field}")

    return record


def new_record(project_id: str, project_title: str, stamp: str) -> dict[str, Any]:
    filename = f"{RECORD_PREFIX}{stamp}{RECORD_SUFFIX}"
    return {
        "format_version": FORMAT_VERSION,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "snapshot": {
            "timestamp": stamp,
            "filename": filename,
            "predecessor_filename": None,
            "predecessor_sha256": None,
        },
        "project": {"project_id": project_id, "project_title": project_title},
        "entry_count": 0,
        "entries": [],
    }


def reconcile_project_identity(record: dict[str, Any], project_id: str, project_title: str) -> None:
    project = record.get("project")
    if not isinstance(project, dict):
        raise ValueError("record 'project' must be an object")

    existing_id = normalize_exposed(project.get("project_id"))
    existing_title = normalize_exposed(project.get("project_title"))

    if existing_id != UNAVAILABLE and project_id != UNAVAILABLE and existing_id != project_id:
        raise ValueError(f"project_id mismatch: record={existing_id!r}, invocation={project_id!r}")

    if existing_id == UNAVAILABLE and project_id != UNAVAILABLE:
        project["project_id"] = project_id
    if existing_title == UNAVAILABLE and project_title != UNAVAILABLE:
        project["project_title"] = project_title


def load_source_record(source_path: str | None, source_persisted_name: str | None, project_id: str, project_title: str) -> tuple[dict[str, Any] | None, str | None, str | None, str | None]:
    if not source_path:
        if source_persisted_name:
            raise ValueError("--record-name requires --record")
        return None, None, None, None

    if not source_persisted_name:
        raise ValueError("--record-name is required when --record is supplied")

    prior_stamp = parse_persisted_stamp(source_persisted_name)
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"source record not found: {path}")

    record = validate_record(read_json(path))
    reconcile_project_identity(record, project_id, project_title)

    if record["snapshot"]["filename"] != source_persisted_name:
        raise ValueError(
            "supplied persisted source filename does not match the filename recorded inside the source snapshot"
        )

    return record, sha256(path), source_persisted_name, prior_stamp


def make_new_stamp(prior_stamp: str | None) -> str:
    stamp = now_stamp()
    if prior_stamp is not None and stamp <= prior_stamp:
        raise ValueError(f"new snapshot timestamp {stamp} is not later than predecessor {prior_stamp}")
    return stamp


def append_entry(state: dict[str, Any]) -> tuple[Path, dict[str, Any], str | None]:
    output_dir = Path(state["output_dir"])
    project_id = normalize_exposed(state.get("project_id"))
    project_title = normalize_exposed(state.get("project_title"))
    chat_id = normalize_exposed(state.get("chat_id"))
    chat_title = normalize_exposed(state.get("chat_title"))

    prior_record, source_hash, source_name, prior_stamp = load_source_record(
        state.get("source_record_path"), state.get("source_persisted_name"), project_id, project_title
    )

    stamp = make_new_stamp(prior_stamp)
    output_filename = f"{RECORD_PREFIX}{stamp}{RECORD_SUFFIX}"
    output_path = output_dir / output_filename

    if prior_record is None:
        record = new_record(project_id, project_title, stamp)
    else:
        record = prior_record
        record["format_version"] = FORMAT_VERSION
        record["snapshot"] = {
            "timestamp": stamp,
            "filename": output_filename,
            "predecessor_filename": source_name,
            "predecessor_sha256": source_hash,
        }
        record["updated_at"] = now_iso()

    entries = record["entries"]
    sequence = len(entries) + 1
    entry = {
        "entry_id": secrets.token_hex(16),
        "sequence": sequence,
        "recorded_at": now_iso(),
        "project_id": project_id,
        "project_title": project_title,
        "chat_id": chat_id,
        "chat_title": chat_title,
        "source_record_filename": source_name,
        "source_record_sha256": source_hash,
        **state["answers"],
    }
    entries.append(entry)
    record["entry_count"] = len(entries)
    record = validate_record(record)
    write_json(output_path, record)
    return output_path, entry, source_hash


def validate_session_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise ValueError("recorder session state must be a JSON object")
    for key in (
        "session_id", "started_at", "question_index", "answers", "output_dir", "state_dir",
        "project_id", "project_title", "chat_id", "chat_title",
    ):
        if key not in state:
            raise ValueError(f"recorder session state missing {key!r}")
    require_nonempty_string(state.get("session_id"), "session_id")
    validate_iso_datetime(state.get("started_at"), "started_at")
    idx = state.get("question_index")
    if not isinstance(idx, int) or isinstance(idx, bool):
        raise ValueError("question_index must be an integer")
    if not isinstance(state.get("answers"), dict):
        raise ValueError("answers must be an object")
    return state


def start(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    output_dir = Path(args.output_dir)
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
        parse_persisted_stamp(args.record_name)
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

    key, question = QUESTIONS[0]
    print(json.dumps({
        "status": "QUESTION", "state": str(state_path), "source_record": args.record or "none",
        "source_persisted_name": args.record_name or "none", "question_number": 1,
        "field": key, "question": question,
    }, ensure_ascii=False, sort_keys=True))
    return 0


def answer(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    state = validate_session_state(read_json(state_path))
    if state.get("completed_at"):
        raise ValueError("session already complete")

    idx = int(state["question_index"])
    if idx < 0 or idx >= len(QUESTIONS):
        raise ValueError("invalid recorder question index")

    text = args.text.strip()
    if not text:
        print(json.dumps({
            "status": "FAIL", "code": "EMPTY_ANSWER", "state": str(state_path),
            "question_number": idx + 1, "question": QUESTIONS[idx][1],
        }, ensure_ascii=False, sort_keys=True))
        return 2

    key, _ = QUESTIONS[idx]
    state["answers"][key] = text
    idx += 1
    state["question_index"] = idx
    write_json(state_path, state)

    if idx < len(QUESTIONS):
        next_key, question = QUESTIONS[idx]
        print(json.dumps({
            "status": "QUESTION", "state": str(state_path), "question_number": idx + 1,
            "field": next_key, "question": question,
        }, ensure_ascii=False, sort_keys=True))
        return 0

    output_path, entry, source_hash = append_entry(state)
    record_hash = sha256(output_path)
    receipt = {
        "status": "RECORDED",
        "record": str(output_path),
        "record_filename": output_path.name,
        "entry_id": entry["entry_id"],
        "sequence": entry["sequence"],
        "source_record_filename": entry["source_record_filename"],
        "source_record_sha256": source_hash,
        "record_sha256": record_hash,
        "recorded_at": entry["recorded_at"],
    }

    receipt_path = Path(state["state_dir"]) / f"recorder-receipt-{entry['entry_id']}.json"
    write_json(receipt_path, receipt)
    state["completed_at"] = now_iso()
    state["entry_id"] = entry["entry_id"]
    state["sequence"] = entry["sequence"]
    state["receipt"] = str(receipt_path)
    state["record"] = str(output_path)
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
