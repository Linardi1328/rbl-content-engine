"""CLI for local RBL Topview contracts, Phase 1D preflight, and reference state."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .pilot import (
    apply_phase_1d_preflight,
    confirm_phase_1d_preflight,
    evaluate_phase_1d_preflight,
    evaluate_reference_pilot_status,
)
from .preflight import evaluate_preflight
from .references import (
    approve_reference,
    initialize_reference_registry,
    lock_reference,
    record_remote_asset,
    utc_now,
    validate_reference_registry,
    write_json_atomic,
)
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


def _load_or_block(*paths: Path) -> tuple[list[dict[str, Any]] | None, int | None]:
    loaded: list[dict[str, Any]] = []
    try:
        for path in paths:
            loaded.append(load_json(path))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        _emit({"status": "BLOCKED", "blockers": [str(exc)]})
        return None, 2
    return loaded, None


def _validate_mutation(
    state: dict[str, Any],
    registry: dict[str, Any],
    workspace_root: Path,
) -> tuple[bool, dict[str, Any]]:
    state_result = validate_state(state)
    registry_result = validate_reference_registry(registry, workspace_root)
    payload = {
        "state": state_result.to_dict(),
        "registry": registry_result.to_dict(),
    }
    return state_result.valid and registry_result.valid, payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rbl_content_engine.topview",
        description="Validate and manage local Topview production contracts without media generation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("validate-manifest", "validate a Topview Production Manifest"),
        ("validate-state", "validate local Topview production state"),
        ("validate-capabilities", "validate a live Topview capability snapshot"),
    ):
        sub = subparsers.add_parser(command, help=help_text)
        sub.add_argument("path", type=Path)

    validate_refs = subparsers.add_parser(
        "validate-references", help="validate a Phase 1D reference registry and source fingerprints"
    )
    validate_refs.add_argument("path", type=Path)
    validate_refs.add_argument("--workspace-root", required=True, type=Path)
    validate_refs.add_argument("--manifest", type=Path)

    preflight = subparsers.add_parser(
        "preflight",
        help="evaluate local future-production readiness; paid generation remains blocked",
    )
    preflight.add_argument("--manifest", required=True, type=Path)
    preflight.add_argument("--state", required=True, type=Path)
    preflight.add_argument("--capabilities", required=True, type=Path)

    pilot_preflight = subparsers.add_parser(
        "phase1d-preflight",
        help="evaluate non-chargeable Phase 1D technical preflight",
    )
    pilot_preflight.add_argument("--manifest", required=True, type=Path)
    pilot_preflight.add_argument("--state", required=True, type=Path)
    pilot_preflight.add_argument("--capabilities", required=True, type=Path)
    pilot_preflight.add_argument(
        "--apply",
        action="store_true",
        help="persist a successful technical preflight as APPROVAL_REQUIRED",
    )

    confirm = subparsers.add_parser(
        "phase1d-confirm-preflight",
        help="explicitly confirm a successful non-chargeable preflight",
    )
    confirm.add_argument("--state", required=True, type=Path)
    confirm.add_argument("--human-confirmed", action="store_true")

    ref_init = subparsers.add_parser(
        "reference-init",
        help="stage one or two manifest references locally after confirmed preflight",
    )
    ref_init.add_argument("--manifest", required=True, type=Path)
    ref_init.add_argument("--state", required=True, type=Path)
    ref_init.add_argument("--registry", required=True, type=Path)
    ref_init.add_argument("--workspace-root", required=True, type=Path)
    ref_init.add_argument("--reference", action="append", required=True)

    ref_remote = subparsers.add_parser(
        "reference-record-remote",
        help="record a remote asset ID observed from the live Topview session",
    )
    ref_remote.add_argument("--state", required=True, type=Path)
    ref_remote.add_argument("--registry", required=True, type=Path)
    ref_remote.add_argument("--workspace-root", required=True, type=Path)
    ref_remote.add_argument("--reference", required=True)
    ref_remote.add_argument("--remote-asset-id", required=True)

    ref_approve = subparsers.add_parser(
        "reference-approve",
        help="record explicit human approval for a remotely registered reference",
    )
    ref_approve.add_argument("--state", required=True, type=Path)
    ref_approve.add_argument("--registry", required=True, type=Path)
    ref_approve.add_argument("--workspace-root", required=True, type=Path)
    ref_approve.add_argument("--reference", required=True)
    ref_approve.add_argument("--human-confirmed", action="store_true")

    ref_lock = subparsers.add_parser(
        "reference-lock",
        help="cryptographically lock an approved reference to its current local source bytes",
    )
    ref_lock.add_argument("--state", required=True, type=Path)
    ref_lock.add_argument("--registry", required=True, type=Path)
    ref_lock.add_argument("--workspace-root", required=True, type=Path)
    ref_lock.add_argument("--reference", required=True)

    ref_status = subparsers.add_parser(
        "reference-pilot-status",
        help="evaluate end-to-end Phase 1D preflight/reference pilot status",
    )
    ref_status.add_argument("--manifest", required=True, type=Path)
    ref_status.add_argument("--state", required=True, type=Path)
    ref_status.add_argument("--capabilities", required=True, type=Path)
    ref_status.add_argument("--registry", required=True, type=Path)
    ref_status.add_argument("--workspace-root", required=True, type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "validate-manifest":
        return _validate(str(args.path), validate_manifest)
    if args.command == "validate-state":
        return _validate(str(args.path), validate_state)
    if args.command == "validate-capabilities":
        return _validate(str(args.path), validate_capabilities)

    if args.command == "validate-references":
        loaded, error = _load_or_block(args.path, *( [args.manifest] if args.manifest else [] ))
        if error is not None or loaded is None:
            return 2
        registry = loaded[0]
        manifest = loaded[1] if len(loaded) > 1 else None
        result = validate_reference_registry(
            registry, args.workspace_root, manifest=manifest
        )
        _emit(result.to_dict())
        return 0 if result.valid else 2

    if args.command == "preflight":
        loaded, error = _load_or_block(args.manifest, args.state, args.capabilities)
        if error is not None or loaded is None:
            return 2
        manifest, state, capabilities = loaded
        result = evaluate_preflight(manifest, state, capabilities)
        _emit(result.to_dict())
        return 0 if result.ready else 2

    if args.command == "phase1d-preflight":
        loaded, error = _load_or_block(args.manifest, args.state, args.capabilities)
        if error is not None or loaded is None:
            return 2
        manifest, state, capabilities = loaded
        result = evaluate_phase_1d_preflight(manifest, state, capabilities)
        payload = result.to_dict()
        if args.apply and result.ready_for_confirmation:
            updated_state = apply_phase_1d_preflight(
                state, capabilities, result, checked_at=utc_now()
            )
            state_validation = validate_state(updated_state)
            if not state_validation.valid:
                payload["state_validation"] = state_validation.to_dict()
                payload["status"] = "BLOCKED"
                _emit(payload)
                return 2
            write_json_atomic(args.state, updated_state)
            payload["state_updated"] = True
        else:
            payload["state_updated"] = False
        _emit(payload)
        return 0 if result.ready_for_confirmation else 2

    if args.command == "phase1d-confirm-preflight":
        loaded, error = _load_or_block(args.state)
        if error is not None or loaded is None:
            return 2
        try:
            updated_state = confirm_phase_1d_preflight(
                loaded[0], human_confirmed=args.human_confirmed, confirmed_at=utc_now()
            )
            validation = validate_state(updated_state)
            if not validation.valid:
                _emit({"status": "BLOCKED", "state_validation": validation.to_dict()})
                return 2
            write_json_atomic(args.state, updated_state)
        except ValueError as exc:
            _emit({"status": "BLOCKED", "blockers": [str(exc)]})
            return 2
        _emit({"status": "READY", "reference_staging_allowed": True, "paid_generation_authorized": False})
        return 0

    if args.command == "reference-init":
        if args.registry.exists():
            _emit({"status": "BLOCKED", "blockers": ["reference registry already exists; do not overwrite it implicitly"]})
            return 2
        loaded, error = _load_or_block(args.manifest, args.state)
        if error is not None or loaded is None:
            return 2
        manifest, state = loaded
        try:
            registry, updated_state = initialize_reference_registry(
                manifest,
                state,
                args.workspace_root,
                args.reference,
                timestamp=utc_now(),
            )
            registry_validation = validate_reference_registry(
                registry, args.workspace_root, manifest=manifest
            )
            state_validation = validate_state(updated_state)
            if not registry_validation.valid or not state_validation.valid:
                _emit({
                    "status": "BLOCKED",
                    "registry_validation": registry_validation.to_dict(),
                    "state_validation": state_validation.to_dict(),
                })
                return 2
            write_json_atomic(args.registry, registry)
            write_json_atomic(args.state, updated_state)
        except ValueError as exc:
            _emit({"status": "BLOCKED", "blockers": [str(exc)]})
            return 2
        _emit({"status": registry["status"], "reference_ids": registry["pilot_reference_ids"]})
        return 0

    if args.command in {"reference-record-remote", "reference-approve", "reference-lock"}:
        loaded, error = _load_or_block(args.registry, args.state)
        if error is not None or loaded is None:
            return 2
        registry, state = loaded
        try:
            now = utc_now()
            if args.command == "reference-record-remote":
                updated_registry, updated_state = record_remote_asset(
                    registry,
                    state,
                    args.reference,
                    args.remote_asset_id,
                    timestamp=now,
                )
            elif args.command == "reference-approve":
                updated_registry, updated_state = approve_reference(
                    registry,
                    state,
                    args.reference,
                    human_confirmed=args.human_confirmed,
                    timestamp=now,
                )
            else:
                updated_registry, updated_state = lock_reference(
                    registry,
                    state,
                    args.workspace_root,
                    args.reference,
                    timestamp=now,
                )

            valid, validation_payload = _validate_mutation(
                updated_state, updated_registry, args.workspace_root
            )
            if not valid:
                _emit({"status": "BLOCKED", **validation_payload})
                return 2
            write_json_atomic(args.registry, updated_registry)
            write_json_atomic(args.state, updated_state)
        except ValueError as exc:
            _emit({"status": "BLOCKED", "blockers": [str(exc)]})
            return 2
        _emit({
            "status": updated_registry["status"],
            "reference": args.reference,
            "paid_generation_authorized": False,
        })
        return 0

    if args.command == "reference-pilot-status":
        loaded, error = _load_or_block(
            args.manifest, args.state, args.capabilities, args.registry
        )
        if error is not None or loaded is None:
            return 2
        manifest, state, capabilities, registry = loaded
        result = evaluate_reference_pilot_status(
            manifest,
            state,
            capabilities,
            registry,
            str(args.workspace_root),
        )
        _emit(result.to_dict())
        return 0 if result.complete else 2

    raise AssertionError(f"Unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
