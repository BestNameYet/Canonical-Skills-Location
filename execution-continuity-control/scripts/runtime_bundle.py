#!/usr/bin/env python3
"""Executable runtime bundle and orchestration controller.

Bootstrap replaces PAYLOAD_B64's sentinel with a base64-encoded UTF-8 JSON
manifest conforming to schemas/runtime-bundle.schema.json. The resulting
one-per-turn timestamped script is the only model-facing continuity runtime
entrypoint. It owns child materialization/dispatch and the Orchestrator↔Worker
control handshake.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PAYLOAD_B64 = "__EXECUTION_CONTINUITY_BUNDLE_PAYLOAD_B64__"

BUNDLE_NAME_RE = re.compile(r"^execution-continuity-control_bundle_(\d{8}T\d{12}Z)\.py$")
EXPECTED_REPOSITORY = "BestNameYet/Canonical-Skills-Location"
EXPECTED_BRANCH = "main"
EXPECTED_ROOT = "execution-continuity-control/"
EXPECTED_FORMAT = "execution-continuity-runtime-bundle/v2"
EXPECTED_PATHS = [
    "SKILL.md",
    "DESIGN_HISTORY.md",
    "schemas/execution-record.schema.json",
    "schemas/runtime-bundle.schema.json",
    "scripts/runtime_bundle.py",
    "scripts/action_event_recorder.py",
    "scripts/action_questioner.py",
    "scripts/end_turn_router.py",
]
SCRIPT_TARGETS = {
    "recorder": "scripts/action_event_recorder.py",
    "questioner": "scripts/action_questioner.py",
    "router": "scripts/end_turn_router.py",
}
SCOPES = {"worker", "orchestrator"}

ORCHESTRATOR_DEFINITION = (
    "The Orchestrator is the highest-scope, task-domain-neutral controller. "
    "It does not independently solve, critique, reinterpret, or form opinions about the user's task. "
    "It preserves the captured user prompt as Worker payload; directs a Worker to perform one material action at a time; "
    "invokes this executable bundle immediately after every completed material action; routes recorder, questioner, and router protocol questions using observable execution state; "
    "intercepts every Worker stop attempt; and owns the actual user-facing turn boundary. "
    "Worker COMPLETE or IMPASSE ends only the Worker lifecycle. Only an Orchestrator-scoped end-turn cycle returning COMPLETE after its end_turn_result is recorded authorizes the user-facing turn to end."
)

WORKER_RULES = [
    "Operate as the Orchestrator defined by the bundle; do not perform the user's substantive task yourself.",
    "Give the captured user prompt to the Worker as the operative task without silently replacing its requested end state.",
    "Direct the Worker to perform exactly one next material action at a time. A material action is a completed action, event, failure, decision, tool use, artifact effect, or evaluation that matters to execution understanding.",
    "Immediately after that material action completes, regain control and invoke this same bundle with `after-action --scope worker`; do not allow the Worker to begin another material action first.",
    "Complete every recorder/questioner/router interaction returned by the bundle before issuing another Worker action command.",
    "Answer continuity questions from observable Worker or Orchestrator execution state; do not invent evidence, actions, results, or hidden reasoning.",
    "When the bundle returns ORCHESTRATE_WORKER, direct the Worker to perform the next required material action, honoring any returned continuation instruction.",
    "Treat every Worker stop or completion attempt as a material action and route it through the same bundle cycle; the action questionnaire must explicitly classify the end-turn attempt.",
    "Worker COMPLETE or IMPASSE returns lifecycle control to the Orchestrator and never directly ends the user-facing turn.",
    "If the Orchestrator proposes to end the user-facing turn, route that proposal through `after-action --scope orchestrator`; only an outer COMPLETE returned after persistence authorizes final turn termination.",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def fail(detail: str, code: str = "BUNDLE_ERROR") -> int:
    print(json.dumps({"status": "FAIL", "code": code, "detail": detail}, ensure_ascii=False))
    return 2


def emit(obj: dict[str, Any]) -> int:
    print(json.dumps(obj, ensure_ascii=False))
    return 0


def git_blob_sha(content: str) -> str:
    raw = content.encode("utf-8")
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def decode_manifest() -> dict[str, Any]:
    try:
        raw = base64.b64decode(PAYLOAD_B64.encode("ascii"), validate=True)
        manifest = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"embedded payload is not valid base64 UTF-8 JSON: {exc}") from exc
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: Any) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    required = {"bundle_format", "created_at", "source", "root", "files"}
    if set(manifest) != required:
        raise ValueError(f"manifest fields must be exactly {sorted(required)!r}")
    if manifest["bundle_format"] != EXPECTED_FORMAT:
        raise ValueError("unsupported bundle_format")
    if manifest["root"] != EXPECTED_ROOT:
        raise ValueError("canonical root mismatch")
    source = manifest["source"]
    if not isinstance(source, dict) or set(source) != {"repository", "branch", "commit_sha"}:
        raise ValueError("source fields are invalid")
    if source["repository"] != EXPECTED_REPOSITORY or source["branch"] != EXPECTED_BRANCH:
        raise ValueError("canonical repository or branch mismatch")
    if not isinstance(source["commit_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", source["commit_sha"]):
        raise ValueError("commit_sha must be a 40-character lowercase hex SHA")
    files = manifest["files"]
    if not isinstance(files, list) or len(files) != len(EXPECTED_PATHS):
        raise ValueError(f"files must contain exactly {len(EXPECTED_PATHS)} entries")
    seen: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(files):
        if not isinstance(item, dict) or set(item) != {"path", "git_blob_sha", "encoding", "content"}:
            raise ValueError(f"files[{index}] has invalid fields")
        path = item["path"]
        if path not in EXPECTED_PATHS or path in seen:
            raise ValueError(f"files[{index}].path is unexpected or duplicated")
        if item["encoding"] != "utf-8":
            raise ValueError(f"{path}: encoding must be utf-8")
        if not isinstance(item["content"], str):
            raise ValueError(f"{path}: content must be a string")
        if not isinstance(item["git_blob_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", item["git_blob_sha"]):
            raise ValueError(f"{path}: git_blob_sha is invalid")
        if git_blob_sha(item["content"]) != item["git_blob_sha"]:
            raise ValueError(f"{path}: embedded content does not match git_blob_sha")
        seen[path] = item
    if set(seen) != set(EXPECTED_PATHS):
        raise ValueError("embedded canonical path set is incomplete")


def bundle_stamp() -> str:
    match = BUNDLE_NAME_RE.fullmatch(Path(__file__).name)
    if not match:
        raise ValueError("bundle filename must match execution-continuity-control_bundle_YYYYMMDDTHHMMSSffffffZ.py")
    return match.group(1)


def runtime_root() -> Path:
    return Path("/mnt/data") / f"execution-continuity-control_run_{bundle_stamp()}"


def control_state_path() -> Path:
    return runtime_root() / "orchestration" / "control-state.json"


def file_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["path"]: item for item in manifest["files"]}


def materialize(manifest: dict[str, Any]) -> Path:
    root = runtime_root()
    entries = file_map(manifest)
    for relative in EXPECTED_PATHS:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        expected = entries[relative]["content"].encode("utf-8")
        if destination.exists():
            if destination.read_bytes() != expected:
                raise ValueError(f"runtime derivative differs from embedded canonical content: {relative}")
        else:
            destination.write_bytes(expected)
        if relative.startswith("scripts/") and relative.endswith(".py"):
            destination.chmod(0o700)
    return root


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def initial_control_state(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "control_version": 1,
        "bundle_timestamp": bundle_stamp(),
        "source": manifest["source"],
        "phase": "awaiting_user_prompt",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "user_prompt": None,
        "orchestrator_confirmed": False,
        "worker_action_count": 0,
        "current_scope": None,
        "questioner_state": None,
        "record": None,
    }


def load_control(manifest: dict[str, Any], create: bool = False) -> dict[str, Any]:
    materialize(manifest)
    path = control_state_path()
    if not path.exists():
        if not create:
            raise ValueError("orchestration control state does not exist; invoke bootstrap first")
        state = initial_control_state(manifest)
        write_json(path, state)
        return state
    state = read_json(path)
    if not isinstance(state, dict) or state.get("bundle_timestamp") != bundle_stamp():
        raise ValueError("orchestration control state does not belong to this bundle")
    if state.get("source") != manifest["source"]:
        raise ValueError("orchestration control state source does not match embedded snapshot")
    return state


def save_control(state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(control_state_path(), state)


def request_user_prompt(manifest: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "REQUEST_USER_PROMPT",
        "phase": state["phase"],
        "bundle": str(Path(__file__).resolve()),
        "bundle_timestamp": bundle_stamp(),
        "runtime_root": str(runtime_root()),
        "source": manifest["source"],
        "bundle_ready": True,
        "control_state": str(control_state_path()),
        "request": "Supply the complete current user prompt unchanged to this bundle.",
        "next_command": "provide-prompt --user-prompt <complete user prompt>",
    }


def identity_check(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ORCHESTRATOR_IDENTITY_CHECK",
        "phase": state["phase"],
        "control_state": str(control_state_path()),
        "definition": ORCHESTRATOR_DEFINITION,
        "question": f"Is the model operating as the Orchestrator defined as: {ORCHESTRATOR_DEFINITION} Answer YES or NO.",
        "instruction_to_caller": "Adopt the Orchestrator role exactly as defined above, then answer the identity check through this bundle.",
        "allowed_answers": ["YES", "NO"],
        "next_command": "orchestrator-confirm --answer YES|NO",
    }


def worker_command(state: dict[str, Any], continuation: str | None = None, subscript_output: Any = None) -> dict[str, Any]:
    instruction = (
        "Orchestrate a Worker to perform the next required material action toward the captured user prompt. "
        "Do not perform the task yourself. After exactly one material action completes, immediately regain control and invoke this bundle with `after-action --scope worker` before any further Worker action."
    )
    if continuation:
        instruction += f" Router continuation to honor: {continuation}"
    out: dict[str, Any] = {
        "status": "ORCHESTRATE_WORKER",
        "phase": "worker_ready",
        "control_state": str(control_state_path()),
        "user_prompt": state["user_prompt"],
        "instruction": instruction,
        "rules": WORKER_RULES,
        "completed_worker_actions": state["worker_action_count"],
        "next_bundle_command_after_action": "after-action --scope worker",
    }
    if state.get("record") is None:
        out["first_after_action_requires"] = ["--output-dir", "--state-dir", "--record-id"]
        out["optional_predecessor_args"] = ["--record", "--record-name"]
    if subscript_output is not None:
        out["subscript_output"] = subscript_output
    return out


def parse_named_args(args: list[str], specs: list[tuple[str, dict[str, Any]]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=False)
    for name, kwargs in specs:
        p.add_argument(name, **kwargs)
    return p.parse_args(args)


def run_child_capture(manifest: dict[str, Any], target: str, child_args: list[str]) -> tuple[int, str, str, Any]:
    root = materialize(manifest)
    command = [sys.executable, str(root / SCRIPT_TARGETS[target]), *child_args]
    completed = subprocess.run(command, capture_output=True, text=True)
    stdout = completed.stdout.strip()
    stderr = completed.stderr
    parsed: Any = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except Exception:
            parsed = None
    return completed.returncode, stdout, stderr, parsed


def relay_child(manifest: dict[str, Any], target: str, child_args: list[str]) -> int:
    root = materialize(manifest)
    completed = subprocess.run([sys.executable, str(root / SCRIPT_TARGETS[target]), *child_args])
    return completed.returncode


def recorder_args_from_state(state: dict[str, Any], ns: argparse.Namespace) -> list[str]:
    record = state.get("record")
    if record is None:
        if not ns.output_dir or not ns.state_dir or not ns.record_id:
            raise ValueError("first after-action requires --output-dir, --state-dir, and --record-id")
        record = {
            "output_dir": ns.output_dir,
            "state_dir": ns.state_dir,
            "record_id": ns.record_id,
            "record": ns.record,
            "record_name": ns.record_name,
            "chat_id": ns.chat_id,
            "chat_title": ns.chat_title,
        }
        if bool(ns.record) != bool(ns.record_name):
            raise ValueError("--record and --record-name must be supplied together")
        state["record"] = record
        save_control(state)
    else:
        for field in ("output_dir", "state_dir", "record_id"):
            supplied = getattr(ns, field)
            if supplied is not None and supplied != record[field]:
                raise ValueError(f"{field} conflicts with established orchestration record configuration")
    args = [
        "invoke",
        "--scope", ns.scope,
        "--output-dir", record["output_dir"],
        "--state-dir", record["state_dir"],
        "--record-id", record["record_id"],
    ]
    if record.get("record"):
        args += ["--record", record["record"], "--record-name", record["record_name"]]
    if record.get("chat_id") is not None:
        args += ["--chat-id", record["chat_id"]]
    if record.get("chat_title") is not None:
        args += ["--chat-title", record["chat_title"]]
    return args


def update_record_from_receipt(state: dict[str, Any], receipt: Any) -> None:
    if not isinstance(receipt, dict) or state.get("record") is None:
        return
    candidate = receipt
    if "invocation" in receipt and isinstance(receipt["invocation"], dict):
        candidate = receipt["invocation"]
    if "record" in candidate and isinstance(candidate["record"], dict):
        candidate = candidate["record"]
    if isinstance(candidate, dict):
        path = candidate.get("record")
        name = candidate.get("record_filename")
        rid = candidate.get("record_id")
        if isinstance(path, str) and isinstance(name, str):
            state["record"]["record"] = path
            state["record"]["record_name"] = name
        if isinstance(rid, str):
            state["record"]["record_id"] = rid


def continuity_question(state: dict[str, Any], output: Any, stderr: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": "CONTINUITY_QUESTION",
        "phase": "continuity_interview",
        "control_state": str(control_state_path()),
        "subscript_output": output,
        "instruction_to_orchestrator": "Answer the returned continuity question from observable execution state, then send that answer back through this bundle.",
        "next_command": "continuity-answer --answer <answer>",
    }
    if stderr:
        out["subscript_stderr"] = stderr
    return out


def cmd_bootstrap(manifest: dict[str, Any], args: list[str]) -> int:
    if args:
        raise ValueError("bootstrap takes no additional arguments")
    state = load_control(manifest, create=True)
    if state["phase"] == "awaiting_user_prompt":
        return emit(request_user_prompt(manifest, state))
    if state["phase"] == "awaiting_orchestrator_confirmation":
        return emit(identity_check(state))
    if state["orchestrator_confirmed"] and state.get("user_prompt"):
        return emit(worker_command(state))
    raise ValueError(f"unsupported orchestration phase: {state['phase']}")


def cmd_provide_prompt(manifest: dict[str, Any], args: list[str]) -> int:
    ns = parse_named_args(args, [("--user-prompt", {"required": True})])
    state = load_control(manifest)
    if state["phase"] != "awaiting_user_prompt":
        raise ValueError("bundle is not awaiting the user prompt")
    if not ns.user_prompt.strip():
        raise ValueError("user prompt must be non-empty")
    state["user_prompt"] = ns.user_prompt
    state["phase"] = "awaiting_orchestrator_confirmation"
    save_control(state)
    return emit(identity_check(state))


def cmd_orchestrator_confirm(manifest: dict[str, Any], args: list[str]) -> int:
    ns = parse_named_args(args, [("--answer", {"required": True})])
    state = load_control(manifest)
    if state["phase"] != "awaiting_orchestrator_confirmation":
        raise ValueError("bundle is not awaiting Orchestrator identity confirmation")
    answer = ns.answer.strip().upper()
    if answer not in {"YES", "NO", "Y", "N"}:
        raise ValueError("Orchestrator identity answer must be YES or NO")
    if answer in {"NO", "N"}:
        return emit({
            "status": "ORCHESTRATOR_REQUIRED",
            "phase": state["phase"],
            "definition": ORCHESTRATOR_DEFINITION,
            "instruction": "Switch to the Orchestrator role exactly as defined, then invoke this bundle again with `orchestrator-confirm --answer YES`.",
            "next_command": "orchestrator-confirm --answer YES",
        })
    state["orchestrator_confirmed"] = True
    state["phase"] = "worker_ready"
    save_control(state)
    return emit(worker_command(state))


def cmd_after_action(manifest: dict[str, Any], args: list[str]) -> int:
    specs = [
        ("--scope", {"required": True, "choices": sorted(SCOPES)}),
        ("--output-dir", {}), ("--state-dir", {}), ("--record-id", {}),
        ("--record", {}), ("--record-name", {}), ("--chat-id", {}), ("--chat-title", {}),
    ]
    ns = parse_named_args(args, specs)
    state = load_control(manifest)
    if not state.get("orchestrator_confirmed"):
        raise ValueError("Orchestrator identity has not been confirmed")
    if state["phase"] not in {"worker_ready", "worker_terminal", "orchestrator_continue"}:
        raise ValueError(f"after-action is not valid during phase {state['phase']!r}")
    if ns.scope == "orchestrator" and state["phase"] == "worker_ready":
        raise ValueError("Orchestrator-scoped end control is valid only after lifecycle control has returned to the Orchestrator")
    child_args = recorder_args_from_state(state, ns)
    root = materialize(manifest)
    child_args += [
        "--questioner", str(root / SCRIPT_TARGETS["questioner"]),
        "--router", str(root / SCRIPT_TARGETS["router"]),
    ]
    rc, stdout, stderr, parsed = run_child_capture(manifest, "recorder", child_args)
    if rc != 0:
        return emit({"status": "SUBSCRIPT_FAIL", "subscript": SCRIPT_TARGETS["recorder"], "exit_status": rc, "stdout": stdout, "stderr": stderr})
    if not isinstance(parsed, dict) or parsed.get("status") != "QUESTIONER_STARTED":
        raise RuntimeError(f"recorder returned unexpected output: {stdout!r}")
    update_record_from_receipt(state, parsed)
    questioner = parsed.get("questioner")
    if not isinstance(questioner, dict) or not isinstance(questioner.get("state"), str):
        raise RuntimeError("recorder did not return a valid questioner state")
    state["current_scope"] = ns.scope
    state["questioner_state"] = questioner["state"]
    state["phase"] = "continuity_interview"
    save_control(state)
    return emit(continuity_question(state, questioner, stderr))


def cmd_continuity_answer(manifest: dict[str, Any], args: list[str]) -> int:
    ns = parse_named_args(args, [("--answer", {"required": True})])
    state = load_control(manifest)
    if state["phase"] != "continuity_interview" or not state.get("questioner_state"):
        raise ValueError("bundle is not awaiting a continuity answer")
    rc, stdout, stderr, parsed = run_child_capture(manifest, "questioner", [
        "answer", "--state", state["questioner_state"], "--answer", ns.answer
    ])
    if rc != 0:
        return emit({"status": "SUBSCRIPT_FAIL", "subscript": SCRIPT_TARGETS["questioner"], "exit_status": rc, "stdout": stdout, "stderr": stderr})
    if not isinstance(parsed, dict):
        raise RuntimeError(f"questioner returned non-JSON output: {stdout!r}")
    if parsed.get("status") == "QUESTION":
        return emit(continuity_question(state, parsed, stderr))

    update_record_from_receipt(state, parsed)
    scope = state.get("current_scope")
    state["questioner_state"] = None
    state["current_scope"] = None

    if parsed.get("status") == "QUESTIONER_ACTION_OVER":
        if scope == "worker":
            state["worker_action_count"] += 1
        state["phase"] = "worker_ready" if scope == "worker" else "orchestrator_continue"
        save_control(state)
        if scope == "worker":
            return emit(worker_command(state, subscript_output=parsed))
        return emit({
            "status": "ORCHESTRATOR_CONTINUE",
            "phase": state["phase"],
            "subscript_output": parsed,
            "instruction": "The Orchestrator action was not an end-turn attempt. Continue lifecycle control; resume the Worker if substantive work remains.",
        })

    if parsed.get("status") != "DIRECTIVE":
        raise RuntimeError(f"unexpected terminal questioner output: {parsed!r}")
    directive = parsed.get("directive")
    continuation = parsed.get("instruction") if isinstance(parsed.get("instruction"), str) else None
    if scope == "worker":
        state["worker_action_count"] += 1
        if directive == "CONTINUE":
            state["phase"] = "worker_ready"
            save_control(state)
            return emit(worker_command(state, continuation=continuation, subscript_output=parsed))
        state["phase"] = "worker_terminal"
        save_control(state)
        return emit({
            "status": "WORKER_TERMINAL_TO_ORCHESTRATOR",
            "phase": state["phase"],
            "directive": directive,
            "subscript_output": parsed,
            "instruction": "Worker lifecycle control has returned to the Orchestrator. Do not end the user-facing turn from this Worker result. If substantive work remains, invoke `resume-worker`; if proposing actual turn termination, perform the Orchestrator stop action and invoke `after-action --scope orchestrator`.",
            "next_commands": ["resume-worker", "after-action --scope orchestrator"],
        })

    if scope == "orchestrator":
        if directive == "COMPLETE":
            state["phase"] = "turn_end_authorized"
            save_control(state)
            return emit({
                "status": "TURN_END_AUTHORIZED",
                "phase": state["phase"],
                "directive": directive,
                "subscript_output": parsed,
                "instruction": "Outer Orchestrator COMPLETE is persisted. User-facing turn termination is authorized.",
            })
        if directive == "CONTINUE":
            state["phase"] = "worker_ready"
            save_control(state)
            return emit(worker_command(state, continuation=continuation, subscript_output=parsed))
        state["phase"] = "orchestrator_continue"
        save_control(state)
        return emit({
            "status": "TURN_END_PROHIBITED",
            "phase": state["phase"],
            "directive": directive,
            "subscript_output": parsed,
            "instruction": "Outer IMPASSE does not authorize user-facing END_TURN. Continue or remediate according to observable state, using `resume-worker` when Worker execution should continue.",
            "next_command": "resume-worker",
        })
    raise RuntimeError("terminal directive had no valid scope")


def cmd_resume_worker(manifest: dict[str, Any], args: list[str]) -> int:
    if args:
        raise ValueError("resume-worker takes no additional arguments")
    state = load_control(manifest)
    if not state.get("orchestrator_confirmed") or not state.get("user_prompt"):
        raise ValueError("orchestration has not been initialized")
    if state["phase"] not in {"worker_terminal", "orchestrator_continue"}:
        raise ValueError(f"resume-worker is not valid during phase {state['phase']!r}")
    state["phase"] = "worker_ready"
    save_control(state)
    return emit(worker_command(state))


def cmd_status(manifest: dict[str, Any], args: list[str]) -> int:
    if args:
        raise ValueError("status takes no additional arguments")
    state = load_control(manifest)
    return emit({"status": "CONTROL_STATUS", "control_state": str(control_state_path()), "state": state})


def show_embedded(manifest: dict[str, Any], relative: str) -> int:
    entries = file_map(manifest)
    if relative not in entries:
        raise ValueError(f"unknown embedded path: {relative}")
    sys.stdout.write(entries[relative]["content"])
    if entries[relative]["content"] and not entries[relative]["content"].endswith("\n"):
        sys.stdout.write("\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=[
        "bootstrap", "provide-prompt", "orchestrator-confirm", "after-action", "continuity-answer", "resume-worker", "status", "show",
    ])
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args()
    try:
        manifest = decode_manifest()
        if ns.command == "bootstrap":
            return cmd_bootstrap(manifest, ns.args)
        if ns.command == "provide-prompt":
            return cmd_provide_prompt(manifest, ns.args)
        if ns.command == "orchestrator-confirm":
            return cmd_orchestrator_confirm(manifest, ns.args)
        if ns.command == "after-action":
            return cmd_after_action(manifest, ns.args)
        if ns.command == "continuity-answer":
            return cmd_continuity_answer(manifest, ns.args)
        if ns.command == "resume-worker":
            return cmd_resume_worker(manifest, ns.args)
        if ns.command == "status":
            return cmd_status(manifest, ns.args)
        if ns.command == "show":
            if len(ns.args) != 1:
                raise ValueError("show requires exactly one canonical root-relative path")
            return show_embedded(manifest, ns.args[0])
        raise ValueError(f"unsupported command: {ns.command}")
    except Exception as exc:
        return fail(str(exc), type(exc).__name__)


if __name__ == "__main__":
    raise SystemExit(main())
