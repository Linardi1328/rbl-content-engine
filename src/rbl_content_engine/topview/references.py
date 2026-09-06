"""Authoritative local reference registry for the Phase 1D Topview pilot.

This module performs local file hashing and state transitions only. It does not upload
assets, call MCP tools, approve creative work on the human's behalf, or generate media.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .validator import ValidationIssue, ValidationResult, validate_manifest, validate_state


REFERENCE_REGISTRY_VERSION = "0.1.0"


@dataclass(frozen=True)
class ReferenceRegistryResult:
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_workspace_file(workspace_root: str | Path, source_path: str) -> Path:
    root = Path(workspace_root).resolve()
    candidate = Path(source_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"reference source escapes workspace root: {source_path}") from exc

    if not resolved.is_file():
        raise ValueError(f"reference source is not a regular file: {source_path}")
    return resolved


def _manifest_reference_map(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    references = manifest.get("references", [])
    if not isinstance(references, list):
        return result
    for item in references:
        if isinstance(item, Mapping) and isinstance(item.get("id"), str):
            result[item["id"]] = item
    return result


def _derive_registry_status(registry: Mapping[str, Any]) -> str:
    ids = registry.get("pilot_reference_ids", [])
    records = registry.get("references", {})
    if not isinstance(ids, list) or not isinstance(records, Mapping) or not ids:
        return "BLOCKED"

    selected = [records.get(ref_id) for ref_id in ids]
    if any(not isinstance(item, Mapping) for item in selected):
        return "BLOCKED"
    if any(not item.get("remote_asset_id") for item in selected if isinstance(item, Mapping)):
        return "AWAITING_REMOTE_REGISTRATION"
    if any(
        item.get("approval_status") != "APPROVED"
        for item in selected
        if isinstance(item, Mapping)
    ):
        return "AWAITING_HUMAN_APPROVAL"
    if any(item.get("locked") is not True for item in selected if isinstance(item, Mapping)):
        return "AWAITING_REFERENCE_LOCK"
    return "COMPLETE"


def _state_reference_status(record: Mapping[str, Any]) -> str:
    if record.get("locked") is True:
        return "COMPLETE"
    if record.get("approval_status") == "APPROVED":
        return "APPROVED"
    if record.get("remote_asset_id"):
        return "APPROVAL_REQUIRED"
    return "IN_PROGRESS"


def sync_registry_to_state(
    state: Mapping[str, Any], registry: Mapping[str, Any]
) -> dict[str, Any]:
    updated = copy.deepcopy(dict(state))
    references = updated.setdefault("references", {})
    if not isinstance(references, dict):
        raise ValueError("state.references must be an object")

    registry_records = registry.get("references", {})
    ids = registry.get("pilot_reference_ids", [])
    if not isinstance(registry_records, Mapping) or not isinstance(ids, list):
        raise ValueError("reference registry is malformed")

    for ref_id in ids:
        record = registry_records.get(ref_id)
        if not isinstance(record, Mapping):
            continue
        references[ref_id] = {
            "status": _state_reference_status(record),
            "remote_asset_id": record.get("remote_asset_id"),
            "approved": record.get("approval_status") == "APPROVED",
            "locked": record.get("locked") is True,
        }

    updated["current_project"] = registry.get("project_id")
    updated["current_phase"] = "REFERENCES"
    status = _derive_registry_status(registry)
    if status == "AWAITING_HUMAN_APPROVAL":
        updated["approval_required"] = "REFERENCE_APPROVAL"
    else:
        updated["approval_required"] = None

    if status == "COMPLETE":
        updated["resume_hint"] = (
            "Phase 1D reference pilot complete. Stop before storyboard/keyframe or video "
            "generation until the next phase is explicitly authorized."
        )
    else:
        updated["resume_hint"] = f"Phase 1D reference pilot status: {status}."
    updated["last_updated_at"] = registry.get("last_updated_at")
    return updated


def initialize_reference_registry(
    manifest: Mapping[str, Any],
    state: Mapping[str, Any],
    workspace_root: str | Path,
    reference_ids: Sequence[str],
    *,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_result = validate_manifest(manifest)
    if not manifest_result.valid:
        raise ValueError("manifest must validate before references can be staged")

    state_result = validate_state(state)
    if not state_result.valid:
        raise ValueError("production state must validate before references can be staged")

    preflight = state.get("preflight")
    if not isinstance(preflight, Mapping) or preflight.get("status") != "READY":
        raise ValueError("Phase 1D reference staging requires preflight status READY")

    selected = list(reference_ids)
    if not 1 <= len(selected) <= 2:
        raise ValueError("Phase 1D stages exactly one or two references")
    if len(set(selected)) != len(selected):
        raise ValueError("Phase 1D reference IDs must be unique")

    by_id = _manifest_reference_map(manifest)
    records: dict[str, Any] = {}
    staged_at = timestamp or utc_now()

    for ref_id in selected:
        manifest_ref = by_id.get(ref_id)
        if manifest_ref is None:
            raise ValueError(f"reference {ref_id} is not present in the manifest")
        source = manifest_ref.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError(f"reference {ref_id} must have a local source path")
        source_file = resolve_workspace_file(workspace_root, source)
        records[ref_id] = {
            "reference_id": ref_id,
            "reference_type": manifest_ref.get("type", "other"),
            "source_path": source,
            "source_sha256": sha256_file(source_file),
            "remote_asset_id": None,
            "approval_status": "HUMAN_REQUIRED",
            "locked": False,
            "staged_at": staged_at,
            "registered_at": None,
            "approved_at": None,
            "locked_at": None,
        }

    project = manifest.get("project")
    project_id = project.get("id") if isinstance(project, Mapping) else None
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("manifest project.id is required")

    registry = {
        "schema_version": REFERENCE_REGISTRY_VERSION,
        "project_id": project_id,
        "pilot_reference_ids": selected,
        "status": "AWAITING_REMOTE_REGISTRATION",
        "references": records,
        "blocking_reason": None,
        "last_updated_at": staged_at,
    }
    updated_state = sync_registry_to_state(state, registry)
    return registry, updated_state


def record_remote_asset(
    registry: Mapping[str, Any],
    state: Mapping[str, Any],
    reference_id: str,
    remote_asset_id: str,
    *,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not remote_asset_id.strip():
        raise ValueError("remote asset ID must be a non-empty value observed from Topview")
    updated = copy.deepcopy(dict(registry))
    records = updated.get("references")
    if not isinstance(records, dict) or reference_id not in records:
        raise ValueError(f"reference {reference_id} is not staged in the pilot registry")
    record = records[reference_id]
    if not isinstance(record, dict):
        raise ValueError(f"reference {reference_id} registry record is malformed")
    if record.get("locked") is True:
        raise ValueError("locked references cannot be assigned a different remote asset ID")

    now = timestamp or utc_now()
    record["remote_asset_id"] = remote_asset_id.strip()
    record["registered_at"] = now
    updated["status"] = _derive_registry_status(updated)
    updated["last_updated_at"] = now
    return updated, sync_registry_to_state(state, updated)


def approve_reference(
    registry: Mapping[str, Any],
    state: Mapping[str, Any],
    reference_id: str,
    *,
    human_confirmed: bool,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if human_confirmed is not True:
        raise ValueError("reference approval requires explicit human confirmation")
    updated = copy.deepcopy(dict(registry))
    records = updated.get("references")
    if not isinstance(records, dict) or reference_id not in records:
        raise ValueError(f"reference {reference_id} is not staged in the pilot registry")
    record = records[reference_id]
    if not isinstance(record, dict):
        raise ValueError(f"reference {reference_id} registry record is malformed")
    if not record.get("remote_asset_id"):
        raise ValueError("reference must have an observed Topview remote asset ID before approval")
    if record.get("locked") is True:
        raise ValueError("locked references cannot be re-approved in place")

    now = timestamp or utc_now()
    record["approval_status"] = "APPROVED"
    record["approved_at"] = now
    updated["status"] = _derive_registry_status(updated)
    updated["last_updated_at"] = now
    return updated, sync_registry_to_state(state, updated)


def lock_reference(
    registry: Mapping[str, Any],
    state: Mapping[str, Any],
    workspace_root: str | Path,
    reference_id: str,
    *,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = copy.deepcopy(dict(registry))
    records = updated.get("references")
    if not isinstance(records, dict) or reference_id not in records:
        raise ValueError(f"reference {reference_id} is not staged in the pilot registry")
    record = records[reference_id]
    if not isinstance(record, dict):
        raise ValueError(f"reference {reference_id} registry record is malformed")
    if record.get("approval_status") != "APPROVED":
        raise ValueError("reference must be human-approved before locking")
    if not record.get("remote_asset_id"):
        raise ValueError("reference must have an observed Topview remote asset ID before locking")

    source = record.get("source_path")
    if not isinstance(source, str) or not source:
        raise ValueError("reference source path is missing")
    source_file = resolve_workspace_file(workspace_root, source)
    current_hash = sha256_file(source_file)
    if current_hash != record.get("source_sha256"):
        raise ValueError(
            "reference source changed after staging; stage and approve the replacement explicitly"
        )

    now = timestamp or utc_now()
    record["locked"] = True
    record["locked_at"] = now
    updated["status"] = _derive_registry_status(updated)
    updated["last_updated_at"] = now
    return updated, sync_registry_to_state(state, updated)


def validate_reference_registry(
    registry: Mapping[str, Any],
    workspace_root: str | Path,
    *,
    manifest: Mapping[str, Any] | None = None,
) -> ReferenceRegistryResult:
    issues: list[ValidationIssue] = []

    def add(code: str, path: str, message: str) -> None:
        issues.append(ValidationIssue(code=code, path=path, message=message))

    if registry.get("schema_version") != REFERENCE_REGISTRY_VERSION:
        add(
            "REFERENCE_REGISTRY_VERSION",
            "schema_version",
            f"expected {REFERENCE_REGISTRY_VERSION}",
        )

    ids = registry.get("pilot_reference_ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 2:
        add(
            "REFERENCE_PILOT_COUNT",
            "pilot_reference_ids",
            "Phase 1D must contain one or two pilot reference IDs",
        )
        ids = []
    elif len(ids) != len(set(ids)):
        add(
            "REFERENCE_PILOT_DUPLICATE",
            "pilot_reference_ids",
            "pilot reference IDs must be unique",
        )

    records = registry.get("references")
    if not isinstance(records, Mapping):
        add("REFERENCE_REGISTRY_SHAPE", "references", "references must be an object")
        records = {}

    manifest_refs = _manifest_reference_map(manifest) if manifest is not None else {}

    for ref_id in ids:
        record = records.get(ref_id)
        path = f"references.{ref_id}"
        if not isinstance(record, Mapping):
            add("REFERENCE_RECORD_MISSING", path, "selected reference record is missing")
            continue
        if record.get("reference_id") != ref_id:
            add("REFERENCE_ID_MISMATCH", f"{path}.reference_id", "record ID must match key")

        source = record.get("source_path")
        expected_hash = record.get("source_sha256")
        if not isinstance(source, str) or not source:
            add("REFERENCE_SOURCE_REQUIRED", f"{path}.source_path", "source path is required")
        else:
            try:
                source_file = resolve_workspace_file(workspace_root, source)
                actual_hash = sha256_file(source_file)
                if actual_hash != expected_hash:
                    code = (
                        "REFERENCE_SOURCE_DRIFT"
                        if record.get("locked") is True
                        else "REFERENCE_SOURCE_CHANGED"
                    )
                    add(code, f"{path}.source_sha256", "source bytes no longer match staged hash")
            except ValueError as exc:
                add("REFERENCE_SOURCE_INVALID", f"{path}.source_path", str(exc))

        if manifest is not None:
            manifest_ref = manifest_refs.get(ref_id)
            if manifest_ref is None:
                add("REFERENCE_NOT_IN_MANIFEST", path, "reference is not present in manifest")
            else:
                if manifest_ref.get("source") != source:
                    add(
                        "REFERENCE_SOURCE_MANIFEST_MISMATCH",
                        f"{path}.source_path",
                        "registry source must match manifest source",
                    )
                if manifest_ref.get("type") != record.get("reference_type"):
                    add(
                        "REFERENCE_TYPE_MANIFEST_MISMATCH",
                        f"{path}.reference_type",
                        "registry reference type must match manifest",
                    )

        remote_asset_id = record.get("remote_asset_id")
        approval_status = record.get("approval_status")
        locked = record.get("locked")
        if approval_status == "APPROVED" and not remote_asset_id:
            add(
                "REFERENCE_APPROVED_WITHOUT_REMOTE",
                path,
                "approved reference must have an observed remote asset ID",
            )
        if locked is True:
            if approval_status != "APPROVED":
                add(
                    "REFERENCE_LOCK_WITHOUT_APPROVAL",
                    path,
                    "locked reference must be human-approved",
                )
            if not remote_asset_id:
                add(
                    "REFERENCE_LOCK_WITHOUT_REMOTE",
                    path,
                    "locked reference must have an observed remote asset ID",
                )

    derived_status = _derive_registry_status(registry)
    if registry.get("status") != derived_status:
        add(
            "REFERENCE_REGISTRY_STATUS_MISMATCH",
            "status",
            f"expected derived status {derived_status}",
        )

    return ReferenceRegistryResult(tuple(issues))


def write_json_atomic(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    if ".example." in target.name:
        raise ValueError("refusing to mutate a tracked example file")
    if target.exists() and target.is_symlink():
        raise ValueError("refusing to replace a symlinked state/registry file")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
