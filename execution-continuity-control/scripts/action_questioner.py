#!/usr/bin/env python3
"""Eight-question action interview and end-turn-router proxy.

The recorder starts this script after persisting a ``recorder_invocation``.
This script owns the eight action questions. AQ2 is the sole routing test and
accepts only YES/NO (with Y/N aliases).

After the eight-question interview, the questioner returns its formatted action
object to the recorder. If AQ2 is YES, the questioner then invokes and proxies
all interaction with ``end_turn_router.py``. The router never talks to the
recorder. When the router returns its completed data object, this script wraps
that object as ``end_turn_result`` and returns the wrapper to the recorder.
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


def run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True)
    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeError(f"child script produced no JSON; stderr={completed.stderr.strip()!r}")
    data = json.loads(stdout)
    if completed.returncode != 0:
        raise RuntimeError(f"child script failed: {data!r}")
    return data


def normalize_yes_no(raw: str) -> str:
    value = raw.strip().upper()
    value = {"Y": "YES", "N": "NO"}.get(value, value)
    if value not in {"YES", "NO"}:
        raise ValueError("AQ2 requires YES/NO or Y/N")
    return value


def source_from_state(state: dict[str, Any]) -> dict[str, Any] | None:
    value = state.get("source") or {}
    return value or None


def action_question_payload(state: dict[str, Any]) -> dict[str, Any]:
    index = state["question_index"]
    qid, question, allowed = QUESTIONS[index]
    out = {
        "status": "QUESTION",
        "phase": "action_questionnaire",
        "state": state["state_path"],
        "question_number": index + 1,
        "question_id": qid,
        "question": question,
    }
    if allowed:
        out["allowed_answers"] = allowed
    return out


def router_question_payload(state: dict[str, Any], router_output: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "QUESTION",
        "phase": "end_turn_router",
        "state": state["state_path"],
        "question_id": router_output["question_id"],
        "question": router_output["question"],
        "allowed_answers": router_output["allowed_answers"],
        "cycle_id": router_output["cycle_id"],
    }


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


def finish_action_questionnaire(state: dict[str, Any]) -> dict[str, Any]:
    pairs = [
        {"id": qid, "question": question, "answer": state["answers"][qid]}
        for qid, question, _ in QUESTIONS
    ]
    payload: dict[str, Any] = {
        "action_type": "action_questionnaire",
        "scope": state["scope"],
        "pairs": pairs,
    }
    source = source_from_state(state)
    if source:
        payload["source"] = source
    return recorder_append(state, payload)


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
    qid, _, allowed = QUESTIONS[index]
    text = raw.strip()
    if not text:
        raise ValueError("answer must not be empty")
    if allowed:
        text = normalize_yes_no(text)
    state["answers"][qid] = text
    state["question_index"] = index + 1
    state["updated_at"] = now()
    write_json(Path(state["state_path"]), state)

    if state["question_index"] < len(QUESTIONS):
        return action_question_payload(state)

    questionnaire_receipt = finish_action_questionnaire(state)
    state["questionnaire_receipt"] = questionnaire_receipt
    write_json(Path(state["state_path"]), state)

    if state["answers"]["AQ2"] == "NO":
        state["phase"] = "complete"
        state["completed_at"] = now()
        write_json(Path(state["state_path"]), state)
        return {
            "status": "QUESTIONNAIRE_COMPLETE",
            "phase": "complete",
            "state": state["state_path"],
            "record": questionnaire_receipt,
        }

    router_output = start_router(state)
    return router_question_payload(state, router_output)


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
