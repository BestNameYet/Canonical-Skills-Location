#!/usr/bin/env python3
"""Plain-text Execution Continuity Control lease controller.

This source is combined at build time with the recorder, action questioner, and
end-turn router into one generated ``bundle.py``. The generated bundle invokes
those procedures through ordinary in-process Python function calls. There is no
runtime source decoding, compression, ``exec()``, or ``compile()``.

The generated bundle is the sole Orchestrator. The model acts only under the
current bundle-issued payload. Every emitted control payload carries the
behavioral instructions applicable to the model at that point in execution.
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ``call_procedure(target, argv)`` is supplied by the generated bundle before
# this controller source is evaluated. target is recorder, questioner, or router.

CONTROL_VERSION = 1
DEFAULT_CONTROL_STATE = Path("/mnt/data/execution-continuity-control-control-state.json")
DEFAULT_OUTPUT_DIR = Path("/mnt/data/execution-continuity-control-records")
DEFAULT_STATE_DIR = Path("/mnt/data/execution-continuity-control-protocol-state")

FINAL_NARRATIVE_HEURISTIC = (
    "Map the captured user prompt to the newest execution-record evidence. "
    "Treat current-turn actions as primary evidence and earlier actions only as "
    "relevant prior state, dependencies, or constraints. Prefer newer supported "
    "state over stale conflicts. Do not turn plans, intentions, questionnaire "
    "self-report, or unsupported claims into accomplishments. State meaningful "
    "remaining gaps or impasse causes. Compress low-level continuity bookkeeping. "
    "Expose user-relevant deliverables when appropriate and suppress internal "
    "continuity artifacts unless requested or necessary as evidence."
)

BEHAVIORAL_INSTRUCTIONS = [
    "The generated bundle is the sole Orchestrator. Act as the Worker only under the current payload.",
    "NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY.",
    "Obey only the authority carried by the current unconsumed lease; never infer permission to perform another material action.",
    "TASK_ACTION authorizes exactly one material task action. After it completes or fails, invoke this same bundle with after-action and the matching action_id before any further material task action.",
    "CONTINUITY_RESPONSE authorizes only an answer to the supplied recorder/questioner/router protocol question. It authorizes no substantive task work.",
    "FINAL_RESPONSE authorizes only construction and delivery of the final user-facing response from the supplied terminal context. It authorizes no remediation or additional task execution.",
    "Planning, status reporting, procedural compliance, or statements of intention do not substitute for requested execution when execution is available.",
    "Use observable execution evidence for claims about completion, mutation, persistence, retrieval, validation, or failure.",
    "Treat every proposed stop or completion as a material action that must pass through after-action, questionnaire, and router processing.",
    "A router CONTINUE directive must be executed through the next TASK_ACTION lease; do not end the user-facing turn instead.",
    "Do not ask for permission already granted by the user's request unless a higher-priority rule actually requires new authorization.",
    "Do not promise uninvoked background or future execution. Perform currently executable work in the current turn.",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def count_record_actions(path_text: str | None) -> int:
    if not path_text:
        return 0
    path = Path(path_text)
    if not path.exists():
        return 0
    try:
        value = read_json(path)
    except Exception:
        return 0
    actions = value.get("actions") if isinstance(value, dict) else None
    return len(actions) if isinstance(actions, list) else 0


def initial_state() -> dict[str, Any]:
    return {
        "control_version": CONTROL_VERSION,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "phase": "awaiting_user_prompt",
        "user_prompt": None,
        "lease_sequence": 0,
        "current_lease": None,
        "record_config": None,
        "current_record": None,
        "current_record_name": None,
        "current_record_id": None,
        "questioner_state": None,
        "turn_start_action_count": 0,
        "terminal_directive": None,
    }


def load_state(path: Path, create: bool = False) -> dict[str, Any]:
    if not path.exists():
        if not create:
            raise ValueError("control state does not exist; invoke bootstrap first")
        state = initial_state()
        write_json(path, state)
        return state
    state = read_json(path)
    if not isinstance(state, dict) or state.get("control_version") != CONTROL_VERSION:
        raise ValueError("control state is malformed or has an unsupported version")
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(path, state)


def base_payload(status: str, execution_authority: bool, **extra: Any) -> dict[str, Any]:
    return {
        "status": status,
        "execution_authority": execution_authority,
        "behavioral_instructions": BEHAVIORAL_INSTRUCTIONS,
        **extra,
    }


def emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def control_error(detail: str, code: str = "CONTROL_ERROR") -> int:
    return emit(base_payload(code, False, detail=detail))


def lease_payload(state: dict[str, Any]) -> dict[str, Any]:
    lease = state.get("current_lease")
    if not isinstance(lease, dict):
        raise ValueError("no current lease exists")
    authority = lease["authority"]
    return base_payload(
        "WORKER_PAYLOAD",
        authority == "TASK_ACTION",
        lease=lease,
        user_prompt=state.get("user_prompt"),
    )


def issue_lease(
    state_path: Path,
    state: dict[str, Any],
    authority: str,
    next_instruction: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if state.get("current_lease") is not None:
        raise ValueError("cannot issue a second lease while another lease is outstanding")
    state["lease_sequence"] += 1
    lease = {
        "sequence": state["lease_sequence"],
        "action_id": uuid.uuid4().hex,
        "authority": authority,
        "issued_at": now_iso(),
        "next_instruction": next_instruction,
        "context": context or {},
        "return_contract": (
            "After exactly one material task action invoke after-action with this action_id."
            if authority == "TASK_ACTION"
            else "Return only the requested protocol answer through continuity-answer with this action_id."
            if authority == "CONTINUITY_RESPONSE"
            else "Construct and deliver only the final user-facing response. Do not perform more task work."
        ),
    }
    state["current_lease"] = lease
    state["phase"] = {
        "TASK_ACTION": "task_action",
        "CONTINUITY_RESPONSE": "continuity_response",
        "FINAL_RESPONSE": "final",
    }[authority]
    save_state(state_path, state)
    return lease_payload(state)


def consume_lease(state_path: Path, state: dict[str, Any], action_id: str, authority: str) -> dict[str, Any]:
    lease = state.get("current_lease")
    if not isinstance(lease, dict):
        raise ValueError("there is no outstanding lease")
    if lease.get("action_id") != action_id:
        raise ValueError("action_id does not match the current lease")
    if lease.get("authority") != authority:
        raise ValueError(f"current lease authority is {lease.get('authority')}, not {authority}")
    state["current_lease"] = None
    save_state(state_path, state)
    return lease


def update_record_from_receipt(state: dict[str, Any], receipt: Any) -> None:
    if not isinstance(receipt, dict):
        return
    record = receipt.get("record")
    record_name = receipt.get("record_filename")
    record_id = receipt.get("record_id")
    if isinstance(record, str):
        state["current_record"] = record
    if isinstance(record_name, str):
        state["current_record_name"] = record_name
    if isinstance(record_id, str):
        state["current_record_id"] = record_id
    config = state.get("record_config")
    if isinstance(config, dict):
        if isinstance(record, str):
            config["record"] = record
        if isinstance(record_name, str):
            config["record_name"] = record_name
        if isinstance(record_id, str):
            config["record_id"] = record_id


def configure_recording(state: dict[str, Any], args: argparse.Namespace) -> None:
    if state.get("record_config") is not None:
        return
    output_dir = args.output_dir or str(DEFAULT_OUTPUT_DIR)
    state_dir = args.state_dir or str(DEFAULT_STATE_DIR)
    record_id = args.record_id
    if not record_id:
        raise ValueError("first after-action requires --record-id")
    if bool(args.record) != bool(args.record_name):
        raise ValueError("--record and --record-name must be supplied together")
    state["turn_start_action_count"] = count_record_actions(args.record)
    state["record_config"] = {
        "output_dir": output_dir,
        "state_dir": state_dir,
        "record_id": record_id,
        "record": args.record,
        "record_name": args.record_name,
        "chat_id": args.chat_id,
        "chat_title": args.chat_title,
    }


def recorder_invoke_argv(state: dict[str, Any]) -> list[str]:
    config = state["record_config"]
    argv = [
        "invoke",
        "--output-dir", config["output_dir"],
        "--scope", "worker",
        "--state-dir", config["state_dir"],
        "--questioner", "action_questioner.py",
        "--router", "end_turn_router.py",
        "--record-id", config["record_id"],
    ]
    if config.get("record"):
        argv += ["--record", config["record"], "--record-name", config["record_name"]]
    if config.get("chat_id") is not None:
        argv += ["--chat-id", config["chat_id"]]
    if config.get("chat_title") is not None:
        argv += ["--chat-title", config["chat_title"]]
    return argv


def make_continuity_context(questioner_output: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol": questioner_output,
        "instruction": "Answer only the supplied protocol question using observable execution state and return that answer through continuity-answer.",
    }


def terminal_context(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    record_path = state.get("current_record")
    record_content = None
    total_actions = 0
    if isinstance(record_path, str) and Path(record_path).exists():
        try:
            record_content = read_json(Path(record_path))
            actions = record_content.get("actions") if isinstance(record_content, dict) else None
            total_actions = len(actions) if isinstance(actions, list) else 0
        except Exception:
            record_content = None
    start = int(state.get("turn_start_action_count") or 0) + 1
    return {
        "terminal_directive": state.get("terminal_directive"),
        "terminal_result": result,
        "execution_record_path": record_path,
        "execution_record_filename": state.get("current_record_name"),
        "record_id": state.get("current_record_id"),
        "execution_record": record_content,
        "current_turn_action_range": {
            "start_sequence": start,
            "end_sequence": total_actions,
        },
        "final_narrative_heuristic": FINAL_NARRATIVE_HEURISTIC,
        "file_exposure_guidance": (
            "Expose user-created or user-relevant deliverables when appropriate. "
            "Do not expose internal continuity state, questionnaires, router state, or execution records by default."
        ),
    }


def cmd_bootstrap(args: argparse.Namespace) -> int:
    state_path = Path(args.control_state)
    if state_path.exists():
        state = load_state(state_path)
        if state.get("phase") == "final":
            state = initial_state()
            write_json(state_path, state)
        elif state.get("current_lease") is not None:
            return emit(lease_payload(state))
    else:
        state = initial_state()
        write_json(state_path, state)

    if state.get("phase") != "awaiting_user_prompt":
        return control_error(f"bootstrap cannot resume phase {state.get('phase')!r} without an outstanding lease")
    return emit(base_payload(
        "REQUEST_USER_PROMPT",
        False,
        request="Supply the complete current user prompt unchanged.",
        next_command=f"provide-prompt --control-state {state_path} --user-prompt <complete user prompt>",
    ))


def cmd_provide_prompt(args: argparse.Namespace) -> int:
    state_path = Path(args.control_state)
    state = load_state(state_path)
    if state.get("phase") != "awaiting_user_prompt" or state.get("current_lease") is not None:
        return control_error("provide-prompt is legal only while awaiting the initial user prompt")
    if not args.user_prompt:
        return control_error("user prompt must not be empty")
    state["user_prompt"] = args.user_prompt
    payload = issue_lease(
        state_path,
        state,
        "TASK_ACTION",
        "Perform exactly one next material action toward the captured user prompt. After that action completes or fails, invoke after-action with this lease's action_id before any further material task action.",
    )
    return emit(payload)


def cmd_after_action(args: argparse.Namespace) -> int:
    state_path = Path(args.control_state)
    state = load_state(state_path)
    try:
        consume_lease(state_path, state, args.action_id, "TASK_ACTION")
        configure_recording(state, args)
        save_state(state_path, state)
        result = call_procedure("recorder", recorder_invoke_argv(state))
        if result.get("status") != "QUESTIONER_STARTED":
            raise RuntimeError(f"recorder returned unexpected result: {result!r}")
        update_record_from_receipt(state, result.get("invocation"))
        questioner = result.get("questioner")
        if not isinstance(questioner, dict) or questioner.get("status") != "QUESTION":
            raise RuntimeError(f"questioner did not return its first question: {questioner!r}")
        state["questioner_state"] = questioner.get("state")
        save_state(state_path, state)
        payload = issue_lease(
            state_path,
            state,
            "CONTINUITY_RESPONSE",
            "Answer only the supplied continuity protocol question, then return the answer with continuity-answer and this lease's action_id.",
            make_continuity_context(questioner),
        )
        return emit(payload)
    except Exception as exc:
        save_state(state_path, state)
        return control_error(str(exc), type(exc).__name__)


def cmd_continuity_answer(args: argparse.Namespace) -> int:
    state_path = Path(args.control_state)
    state = load_state(state_path)
    try:
        consume_lease(state_path, state, args.action_id, "CONTINUITY_RESPONSE")
        questioner_state = state.get("questioner_state")
        if not isinstance(questioner_state, str) or not questioner_state:
            raise ValueError("questioner state is unavailable")
        result = call_procedure("questioner", ["answer", "--state", questioner_state, "--answer", args.answer])

        if result.get("status") == "QUESTION":
            if isinstance(result.get("record"), dict):
                update_record_from_receipt(state, result["record"])
            save_state(state_path, state)
            payload = issue_lease(
                state_path,
                state,
                "CONTINUITY_RESPONSE",
                "Answer only the supplied continuity protocol question, then return the answer with continuity-answer and this lease's action_id.",
                make_continuity_context(result),
            )
            return emit(payload)

        if result.get("status") == "QUESTIONER_ACTION_OVER":
            update_record_from_receipt(state, result.get("record"))
            state["questioner_state"] = None
            save_state(state_path, state)
            payload = issue_lease(
                state_path,
                state,
                "TASK_ACTION",
                "The prior material action was not an end-of-turn attempt. Perform exactly one next material action toward the captured user prompt, then invoke after-action with this lease's action_id.",
                {"questionnaire_result": result},
            )
            return emit(payload)

        if result.get("status") == "DIRECTIVE":
            update_record_from_receipt(state, result.get("record"))
            state["questioner_state"] = None
            directive = result.get("directive")
            state["terminal_directive"] = directive
            save_state(state_path, state)

            if directive == "CONTINUE":
                instruction = result.get("instruction") or "Continue execution toward the requested result."
                payload = issue_lease(
                    state_path,
                    state,
                    "TASK_ACTION",
                    instruction,
                    {"router_result": result},
                )
                return emit(payload)

            if directive in {"COMPLETE", "IMPASSE"}:
                payload = issue_lease(
                    state_path,
                    state,
                    "FINAL_RESPONSE",
                    (
                        "Construct and deliver the final response from the supplied terminal context. Do not perform additional remediation or task execution."
                    ),
                    terminal_context(state, result),
                )
                return emit(payload)

            raise RuntimeError(f"unsupported router directive: {directive!r}")

        raise RuntimeError(f"questioner returned unexpected result: {result!r}")
    except Exception as exc:
        save_state(state_path, state)
        return control_error(str(exc), type(exc).__name__)


def cmd_self_test(args: argparse.Namespace) -> int:
    required = {"recorder", "questioner", "router"}
    registered = set(globals().get("BUNDLE_PROCEDURE_NAMES", []))
    if registered != required:
        print(json.dumps({"status": "SELF_TEST_FAIL", "detail": f"procedure registry mismatch: {sorted(registered)!r}"}))
        return 2
    if any(token in Path(__file__).read_text(encoding="utf-8") for token in ("_CORE_GZIP_B64", "PAYLOAD_B64", "base64.b64decode", "gzip.decompress")):
        print(json.dumps({"status": "SELF_TEST_FAIL", "detail": "forbidden encoding machinery present"}))
        return 2
    print(json.dumps({"status": "SELF_TEST_PASS", "procedures": sorted(required)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Execution Continuity Control single-file runtime")
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="command")

    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("--control-state", default=str(DEFAULT_CONTROL_STATE))
    bootstrap.set_defaults(fn=cmd_bootstrap)

    prompt = sub.add_parser("provide-prompt")
    prompt.add_argument("--control-state", default=str(DEFAULT_CONTROL_STATE))
    prompt.add_argument("--user-prompt", required=True)
    prompt.set_defaults(fn=cmd_provide_prompt)

    after = sub.add_parser("after-action")
    after.add_argument("--control-state", default=str(DEFAULT_CONTROL_STATE))
    after.add_argument("--action-id", required=True)
    after.add_argument("--output-dir")
    after.add_argument("--state-dir")
    after.add_argument("--record-id")
    after.add_argument("--record")
    after.add_argument("--record-name")
    after.add_argument("--chat-id")
    after.add_argument("--chat-title")
    after.set_defaults(fn=cmd_after_action)

    answer = sub.add_parser("continuity-answer")
    answer.add_argument("--control-state", default=str(DEFAULT_CONTROL_STATE))
    answer.add_argument("--action-id", required=True)
    answer.add_argument("--answer", required=True)
    answer.set_defaults(fn=cmd_continuity_answer)
    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()
    if args.self_test:
        return cmd_self_test(args)
    if not getattr(args, "command", None):
        ap.error("a command is required unless --self-test is used")
    try:
        return args.fn(args)
    except Exception as exc:
        return control_error(str(exc), type(exc).__name__)


if __name__ == "__main__":
    raise SystemExit(main())
