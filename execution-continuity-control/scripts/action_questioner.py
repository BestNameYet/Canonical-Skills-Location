#!/usr/bin/env python3
"""Eight-question action classifier and end-turn dispatcher.

The recorder starts this script after recording an invocation. This script asks
exactly eight canonical questions. AQ2 is a strict YES/NO end-turn question so
routing never depends on interpreting free-form action-type prose.

After AQ8 it sends the complete ordered question/answer data object to the
recorder. If AQ2 was YES, it then invokes the canonical end-turn router using
the newly appended snapshot as that cycle's predecessor.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

QUESTIONS = [
    ("AQ1", "What just occurred?", None),
    ("AQ2", "Is this action an end-of-turn attempt? Answer YES or NO.", ["YES", "NO"]),
    ("AQ3", "Why did it occur?", None),
    ("AQ4", "What did it operate on?", None),
    ("AQ5", "What actually happened?", None),
    ("AQ6", "What artifacts or state changed?", None),
    ("AQ7", "What is its status?", None),
    ("AQ8", "What evidence supports that status or result?", None),
]
SCOPES = {"worker", "orchestrator"}


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


def normalize_yes_no(raw: str) -> str:
    value = raw.strip().upper()
    aliases = {"Y": "YES", "N": "NO"}
    value = aliases.get(value, value)
    if value not in {"YES", "NO"}:
        raise ValueError("AQ2 requires YES/NO or Y/N")
    return value


def current_payload(state: dict[str, Any]) -> dict[str, Any]:
    index = state["question_index"]
    qid, question, allowed = QUESTIONS[index]
    result = {
        "status": "QUESTION",
        "state": state["state_path"],
        "question_number": index + 1,
        "question_id": qid,
        "question": question,
    }
    if allowed:
        result["allowed_answers"] = allowed
    return result


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


def append_questionnaire(state: dict[str, Any]) -> dict[str, Any]:
    pairs = []
    for qid, question, _ in QUESTIONS:
        pairs.append({"id": qid, "question": question, "answer": state["answers"][qid]})
    payload = {
        "action_type": "action_questionnaire",
        "scope": state["scope"],
        "pairs": pairs,
    }
    if state.get("source"):
        payload["source"] = state["source"]
    payload_path = Path(state["state_path"]).with_suffix(".action.json")
    write_json(payload_path, payload)
    command = [
        sys.executable,
        state["recorder"],
        "append",
        "--output-dir",
        state["output_dir"],
        "--record",
        state["record"],
        "--record-name",
        state["record_name"],
        "--record-id",
        state["record_id"],
        "--action-file",
        str(payload_path),
    ]
    return run_json(command)


def start_router(state: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    router_state = Path(state["state_path"]).with_name(f"end-turn-router-{uuid.uuid4().hex}.json")
    command = [
        sys.executable,
        state["router"],
        "start",
        "--state",
        str(router_state),
        "--scope",
        state["scope"],
        "--recorder",
        state["recorder"],
        "--output-dir",
        state["output_dir"],
        "--record",
        receipt["record"],
        "--record-name",
        receipt["record_filename"],
        "--record-id",
        receipt["record_id"],
    ]
    if state.get("source", {}).get("chat_id") is not None:
        command += ["--chat-id", state["source"]["chat_id"]]
    if state.get("source", {}).get("chat_title") is not None:
        command += ["--chat-title", state["source"]["chat_title"]]
    return run_json(command)


def cmd_start(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    source = {}
    if args.chat_id is not None:
        source["chat_id"] = args.chat_id
    if args.chat_title is not None:
        source["chat_title"] = args.chat_title
    state = {
        "session_id": uuid.uuid4().hex,
        "started_at": now(),
        "state_path": str(state_path),
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
    print(json.dumps(current_payload(state), ensure_ascii=False))
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    state = load(state_path)
    index = state["question_index"]
    if index < 0 or index >= len(QUESTIONS):
        raise ValueError("questioner is not waiting for an answer")
    qid, _, allowed = QUESTIONS[index]
    text = args.answer.strip()
    if not text:
        raise ValueError("answer must not be empty")
    if allowed:
        text = normalize_yes_no(text)
    state["answers"][qid] = text
    state["question_index"] = index + 1
    state["updated_at"] = now()
    write_json(state_path, state)

    if state["question_index"] < len(QUESTIONS):
        print(json.dumps(current_payload(state), ensure_ascii=False))
        return 0

    receipt = append_questionnaire(state)
    state["completed_at"] = now()
    state["questionnaire_record"] = receipt
    write_json(state_path, state)

    if state["answers"]["AQ2"] == "YES":
        router = start_router(state, receipt)
        state["router_started_at"] = now()
        state["router_state"] = router.get("state")
        write_json(state_path, state)
        print(json.dumps({"status": "ROUTER_STARTED", "questionnaire_record": receipt, "router": router}, ensure_ascii=False))
        return 0

    print(json.dumps({"status": "QUESTIONNAIRE_COMPLETE", "questionnaire_record": receipt}, ensure_ascii=False))
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
