#!/usr/bin/env python3
"""Build one ordinary Python bundle from the canonical plain-text procedures.

The build happens in GitHub Actions. Source modules are wrapped as ordinary
Python factory functions, so their definitions remain Python definitions in the
generated file. Their former subprocess bridges are rebound to an in-process
dispatcher. No runtime source decoding or dynamic code evaluation is used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import indent

CHILDREN = {
    "recorder": "scripts/action_event_recorder.py",
    "questioner": "scripts/action_questioner.py",
    "router": "scripts/end_turn_router.py",
}
CONTROLLER = "scripts/runtime_bundle.py"


def read_text(root: Path, relative: str) -> str:
    path = root / relative
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def strip_shebang_and_future(source: str) -> str:
    lines = source.splitlines()
    out: list[str] = []
    for index, line in enumerate(lines):
        if index == 0 and line.startswith("#!"):
            continue
        if line.strip() == "from __future__ import annotations":
            continue
        out.append(line)
    return "\n".join(out).rstrip() + "\n"


def strip_main_guard(source: str) -> str:
    marker = '\nif __name__ == "__main__":'
    if marker in source:
        source = source.split(marker, 1)[0]
    marker_single = "\nif __name__ == '__main__':"
    if marker_single in source:
        source = source.split(marker_single, 1)[0]
    return source.rstrip() + "\n"


def factory_source(name: str, source: str) -> str:
    cleaned = strip_main_guard(strip_shebang_and_future(source))
    body = indent(cleaned, "    ")
    factory = [
        f"def _build_{name}(_direct_child_dispatch):",
        body.rstrip(),
        "    # Replace the former child-process JSON bridge with a normal function call.",
        "    if 'run_json' in locals():",
        "        def run_json(command):",
        "            return _direct_child_dispatch(command)",
        "",
        "    import contextlib as _contextlib",
        "    import io as _io",
        "",
        "    def _invoke(argv):",
        "        _old_argv = list(sys.argv)",
        "        _buffer = _io.StringIO()",
        "        try:",
        f"            sys.argv = ['{name}.py', *list(argv)]",
        "            with _contextlib.redirect_stdout(_buffer):",
        "                try:",
        "                    _rc = main()",
        "                except SystemExit as _exit:",
        "                    _rc = _exit.code if isinstance(_exit.code, int) else 1",
        "        finally:",
        "            sys.argv = _old_argv",
        "        _lines = [line for line in _buffer.getvalue().splitlines() if line.strip()]",
        "        if not _lines:",
        f"            raise RuntimeError('{name} produced no JSON result')",
        "        try:",
        "            _data = json.loads(_lines[-1])",
        "        except Exception as _exc:",
        f"            raise RuntimeError('{name} returned non-JSON output: ' + _lines[-1]) from _exc",
        "        if _rc not in (0, None):",
        f"            raise RuntimeError('{name} failed: ' + repr(_data))",
        "        return _data",
        "",
        "    return _invoke",
        "",
    ]
    return "\n".join(factory)


def build(args: argparse.Namespace) -> None:
    root = Path(args.source_root)
    output = Path(args.output)

    child_text = {name: read_text(root, rel) for name, rel in CHILDREN.items()}
    controller = strip_shebang_and_future(read_text(root, CONTROLLER))

    provenance = {
        "repository": args.repository,
        "branch": args.branch,
        "commit_sha": args.commit_sha,
        "skill_tree_sha": args.skill_tree_sha,
    }

    parts: list[str] = [
        "#!/usr/bin/env python3",
        '"""Generated single-file Execution Continuity Control runtime.\n\nDo not edit this artifact directly; edit canonical source and rebuild it.\n"""',
        "from __future__ import annotations",
        "",
        "import json",
        "import sys",
        "from pathlib import Path",
        "",
        f"BUNDLE_SOURCE = {json.dumps(provenance, sort_keys=True)}",
        "",
    ]

    for name in ("recorder", "questioner", "router"):
        parts.append(factory_source(name, child_text[name]))

    parts.extend([
        "_PROCEDURES = {}",
        "",
        "def _direct_child_dispatch(command):",
        "    if not isinstance(command, list) or len(command) < 2:",
        "        raise ValueError('child command must contain an interpreter, target, and arguments')",
        "    target_name = Path(str(command[1])).name",
        "    aliases = {",
        "        'action_event_recorder.py': 'recorder',",
        "        'action_questioner.py': 'questioner',",
        "        'end_turn_router.py': 'router',",
        "        'recorder.py': 'recorder',",
        "        'questioner.py': 'questioner',",
        "        'router.py': 'router',",
        "    }",
        "    target = aliases.get(target_name)",
        "    if target is None or target not in _PROCEDURES:",
        "        raise ValueError(f'unknown in-process child target: {target_name!r}')",
        "    return _PROCEDURES[target](list(command[2:]))",
        "",
        "_PROCEDURES['recorder'] = _build_recorder(_direct_child_dispatch)",
        "_PROCEDURES['questioner'] = _build_questioner(_direct_child_dispatch)",
        "_PROCEDURES['router'] = _build_router(_direct_child_dispatch)",
        "BUNDLE_PROCEDURE_NAMES = tuple(sorted(_PROCEDURES))",
        "",
        "def call_procedure(target, argv):",
        "    if target not in _PROCEDURES:",
        "        raise ValueError(f'unknown procedure: {target!r}')",
        "    return _PROCEDURES[target](list(argv))",
        "",
        "# ---- controller source -------------------------------------------------",
        controller.rstrip(),
        "",
    ])

    generated = "\n".join(parts)

    forbidden = [
        "_CORE_GZIP_B64",
        "PAYLOAD_B64",
        "base64.b64decode",
        "gzip.decompress",
    ]
    present = [token for token in forbidden if token in generated]
    if present:
        raise RuntimeError(f"generated bundle contains forbidden encoding machinery: {present!r}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated, encoding="utf-8")
    output.chmod(0o755)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--repository", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--commit-sha", required=True)
    ap.add_argument("--skill-tree-sha", required=True)
    args = ap.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
