"""CLI for local RBL Topview contract validation and preflight."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .preflight import evaluate_preflight
from .validator import (
    ValidationResult,
    load_json,
    validate_capabilities,
    validate_manifest,
    validate_state,
)


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _validate(path: str, validator: Callable[[dict[str, Any]], ValidationResult]) -> int:
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        _emit({"valid": False, "issues": [{"code": "LOAD_ERROR", "path": path, "message": str(exc)}]})
        return 2

    result = validator(data)
    _emit(result.to_dict())
    return 0 if result.valid else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rbl_content_engine.topview",
        description="Validate local Topview production contracts without external calls.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("validate-manifest", "validate a Topview Production Manifest"),
        ("validate-state", "validate local Topview production state"),
        ("validate-capabilities", "validate a live Topview capability snapshot"),
    ):
        sub = subparsers.add_parser(command, help=help_text)
        sub.add_argument("path", type=Path)

    preflight = subparsers.add_parser(
        "preflight",
        help="evaluate local readiness from manifest, state, and live capability snapshot",
    )
    preflight.add_argument("--manifest", required=True, type=Path)
    preflight.add_argument("--state", required=True, type=Path)
    preflight.add_argument("--capabilities", required=True, type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "validate-manifest":
        return _validate(str(args.path), validate_manifest)
    if args.command == "validate-state":
        return _validate(str(args.path), validate_state)
    if args.command == "validate-capabilities":
        return _validate(str(args.path), validate_capabilities)

    if args.command == "preflight":
        try:
            manifest = load_json(args.manifest)
            state = load_json(args.state)
            capabilities = load_json(args.capabilities)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            _emit({"status": "BLOCKED", "ready": False, "blockers": [str(exc)]})
            return 2

        result = evaluate_preflight(manifest, state, capabilities)
        _emit(result.to_dict())
        return 0 if result.ready else 2

    raise AssertionError(f"Unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
