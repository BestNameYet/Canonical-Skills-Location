#!/usr/bin/env python3
"""Executable runtime-bundle template for Execution Continuity Control.

At bootstrap, the caller replaces the single payload sentinel in PAYLOAD_B64
with base64-encoded UTF-8 JSON conforming to schemas/runtime-bundle.schema.json.
The resulting timestamped script is the only model-facing continuity runtime
entrypoint for the governed turn.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PAYLOAD_B64 = "__EXECUTION_CONTINUITY_BUNDLE_PAYLOAD_B64__"

BUNDLE_NAME_RE = re.compile(
    r"^execution-continuity-control_bundle_(\d{8}T\d{12}Z)\.py$"
)
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


def fail(detail: str, code: str = "BUNDLE_ERROR") -> int:
    print(json.dumps({"status": "FAIL", "code": code, "detail": detail}, ensure_ascii=False))
    return 2


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
        actual = git_blob_sha(item["content"])
        if actual != item["git_blob_sha"]:
            raise ValueError(f"{path}: embedded content does not match git_blob_sha")
        seen[path] = item
    if set(seen) != set(EXPECTED_PATHS):
        raise ValueError("embedded canonical path set is incomplete")


def bundle_stamp() -> str:
    match = BUNDLE_NAME_RE.fullmatch(Path(__file__).name)
    if not match:
        raise ValueError(
            "bundle filename must match execution-continuity-control_bundle_YYYYMMDDTHHMMSSffffffZ.py"
        )
    return match.group(1)


def runtime_root() -> Path:
    return Path("/mnt/data") / f"execution-continuity-control_run_{bundle_stamp()}"


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
            actual = destination.read_bytes()
            if actual != expected:
                raise ValueError(f"runtime derivative differs from embedded canonical content: {relative}")
        else:
            destination.write_bytes(expected)
        if relative.startswith("scripts/") and relative.endswith(".py"):
            destination.chmod(0o700)
    return root


def bootstrap_receipt(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    return {
        "status": "BUNDLE_READY",
        "bundle": str(Path(__file__).resolve()),
        "bundle_timestamp": bundle_stamp(),
        "runtime_root": str(root),
        "source": manifest["source"],
        "root": manifest["root"],
        "files": EXPECTED_PATHS,
        "model_entrypoints": ["recorder", "questioner", "router"],
    }


def run_child(manifest: dict[str, Any], target: str, child_args: list[str]) -> int:
    root = materialize(manifest)
    relative = SCRIPT_TARGETS[target]
    command = [sys.executable, str(root / relative), *child_args]
    completed = subprocess.run(command)
    return completed.returncode


def run_recorder(manifest: dict[str, Any], child_args: list[str]) -> int:
    if not child_args:
        raise ValueError("recorder requires its recorder mode and arguments")
    if child_args[0] == "invoke":
        if "--questioner" in child_args or "--router" in child_args:
            raise ValueError("recorder child paths are bundle-controlled and must not be supplied by the caller")
        root = materialize(manifest)
        child_args = [
            *child_args,
            "--questioner", str(root / SCRIPT_TARGETS["questioner"]),
            "--router", str(root / SCRIPT_TARGETS["router"]),
        ]
    return run_child(manifest, "recorder", child_args)


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
    parser.add_argument(
        "command",
        choices=["bootstrap", "recorder", "questioner", "router", "show"],
    )
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args()

    try:
        manifest = decode_manifest()
        if ns.command == "bootstrap":
            if ns.args:
                raise ValueError("bootstrap takes no additional arguments")
            root = materialize(manifest)
            print(json.dumps(bootstrap_receipt(manifest, root), ensure_ascii=False))
            return 0
        if ns.command == "show":
            if len(ns.args) != 1:
                raise ValueError("show requires exactly one canonical root-relative path")
            return show_embedded(manifest, ns.args[0])
        if ns.command == "recorder":
            return run_recorder(manifest, ns.args)
        return run_child(manifest, ns.command, ns.args)
    except Exception as exc:
        return fail(str(exc), type(exc).__name__)


if __name__ == "__main__":
    raise SystemExit(main())
