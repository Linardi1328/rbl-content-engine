"""Controlled, non-chargeable Phase 1D Topview preflight and reference pilot."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from .references import ReferenceRegistryResult, validate_reference_registry
from .validator import (
    AI_GENERATION_METHODS,
    ValidationIssue,
    validate_capabilities,
    validate_manifest,
    validate_state,
)


METHOD_CAPABILITY = {
    "text_to_video": "text_to_video",
    "image_to_video": "image_to_video",
    "omni_reference": "omni_reference",
    "motion_control": "motion_control",
}


@dataclass(frozen=True)
class Phase1DPreflightResult:
    status: str
    required_capabilities: tuple[str, ...]
    blockers: tuple[str, ...]
    validation_issues: tuple[ValidationIssue, ...]

    @property
    def ready_for_confirmation(self) -> bool:
        return self.status == "READY_FOR_CONFIRMATION"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready_for_confirmation": self.ready_for_confirmation,
            "required_capabilities": list(self.required_capabilities),
            "blockers": list(self.blockers),
            "validation_issues": [issue.to_dict() for issue in self.validation_issues],
            "paid_generation_authorized": False,
        }


@dataclass(frozen=True)
class ReferencePilotStatus:
    status: str
    blockers: tuple[str, ...]
    validation_issues: tuple[ValidationIssue, ...]

    @property
    def complete(self) -> bool:
        return self.status == "COMPLETE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "complete": self.complete,
            "blockers": list(self.blockers),
            "validation_issues": [issue.to_dict() for issue in self.validation_issues],
            "generated_tasks_allowed": False,
            "paid_generation_authorized": False,
        }


def _generation_methods(manifest: Mapping[str, Any]) -> set[str]:
    methods: set[str] = set()
    scenes = manifest.get("scenes", [])
    if not isinstance(scenes, list):
        return methods
    for scene in scenes:
        if not isinstance(scene, Mapping):
            continue
        generation = scene.get("generation")
        if isinstance(generation, Mapping):
            method = generation.get("method")
            if method in AI_GENERATION_METHODS:
                methods.add(str(method))
    return methods


def _capability_map(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    capabilities = snapshot.get("capabilities", [])
    if not isinstance(capabilities, list):
        return result
    for item in capabilities:
        if isinstance(item, Mapping) and isinstance(item.get("id"), str):
            result[item["id"]] = item
    return result


def _required_capabilities(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    required = {
        "mcp_connectivity",
        "authentication",
        "canvas_access",
        "canvas_ownership",
        "reference_access",
        "generation_config",
        "task_monitoring",
    }
    for method in _generation_methods(manifest):
        required.add(METHOD_CAPABILITY[method])
    return tuple(sorted(required))


def _generation_config_blockers(
    manifest: Mapping[str, Any], capabilities: Mapping[str, Any]
) -> list[str]:
    methods = _generation_methods(manifest)
    if not methods:
        return []
    configs = capabilities.get("generation_configs", [])
    if not isinstance(configs, list):
        return ["live generation_configs is not an array"]
    configured = {
        str(item.get("task_type"))
        for item in configs
        if isinstance(item, Mapping) and item.get("task_type")
    }
    return [
        f"no live generation configuration recorded for required task type {method}"
        for method in sorted(methods.difference(configured))
    ]


def _zero_spend_and_no_tasks_blockers(state: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    tasks = state.get("generated_tasks")
    if isinstance(tasks, list) and tasks:
        blockers.append("Phase 1D requires generated_tasks to remain empty")
    budget = state.get("budget")
    if isinstance(budget, Mapping):
        actual = budget.get("actual_project_spend_usd")
        if actual != 0:
            blockers.append("Phase 1D requires actual project spend to remain US$0")
    else:
        blockers.append("production state budget is missing")
    return blockers


def evaluate_phase_1d_preflight(
    manifest: Mapping[str, Any],
    state: Mapping[str, Any],
    capabilities: Mapping[str, Any],
) -> Phase1DPreflightResult:
    """Evaluate technical readiness for the non-chargeable Phase 1D pilot.

    This checks live discovery metadata and configuration only. It never invokes Topview
    and never authorizes a generation task.
    """

    manifest_result = validate_manifest(manifest)
    state_result = validate_state(state)
    capability_result = validate_capabilities(capabilities)
    issues = manifest_result.issues + state_result.issues + capability_result.issues
    blockers: list[str] = []

    if issues:
        blockers.append("one or more local contracts failed validation")

    session = capabilities.get("session")
    if not isinstance(session, Mapping) or session.get("status") != "READY":
        blockers.append("Topview live discovery session is not READY")

    required = _required_capabilities(manifest)
    by_id = _capability_map(capabilities)
    for capability_id in required:
        item = by_id.get(capability_id)
        if not item:
            blockers.append(f"required capability {capability_id} is missing")
            continue
        status = item.get("status")
        if status != "VERIFIED_LIVE":
            blockers.append(
                f"required capability {capability_id} is {status or 'UNKNOWN'}, not VERIFIED_LIVE"
            )

    account = capabilities.get("account")
    if not isinstance(account, Mapping):
        blockers.append("live Topview account/Canvas metadata is missing")
    else:
        if account.get("canvas_access") is not True:
            blockers.append("Canvas access has not been positively verified")
        if account.get("ownership_permission") is not True:
            blockers.append("Canvas ownership/mutation permission has not been positively verified")
        if not account.get("canvas_id"):
            blockers.append("the intended live Canvas/project ID has not been recorded")

    blockers.extend(_generation_config_blockers(manifest, capabilities))
    blockers.extend(_zero_spend_and_no_tasks_blockers(state))

    status = "BLOCKED" if blockers else "READY_FOR_CONFIRMATION"
    return Phase1DPreflightResult(
        status=status,
        required_capabilities=required,
        blockers=tuple(dict.fromkeys(blockers)),
        validation_issues=issues,
    )


def apply_phase_1d_preflight(
    state: Mapping[str, Any],
    capabilities: Mapping[str, Any],
    result: Phase1DPreflightResult,
    *,
    checked_at: str,
) -> dict[str, Any]:
    """Persist a successful technical preflight as awaiting human confirmation."""

    if not result.ready_for_confirmation:
        raise ValueError("cannot apply a blocked Phase 1D preflight")

    updated = copy.deepcopy(dict(state))
    session = capabilities.get("session")
    account = capabilities.get("account")
    if not isinstance(session, Mapping) or not isinstance(account, Mapping):
        raise ValueError("capability snapshot is missing live session/account metadata")

    capability_map = _capability_map(capabilities)
    preflight = updated.setdefault("preflight", {})
    if not isinstance(preflight, dict):
        raise ValueError("state.preflight must be an object")
    preflight.update(
        {
            "status": "APPROVAL_REQUIRED",
            "mcp_connected": True,
            "authenticated": True,
            "account_hint": account.get("account_hint"),
            "canvas_access": True,
            "ownership_permission": True,
            "generation_config_checked": True,
            "budget_checked": True,
            "required_capabilities": {
                capability_id: capability_map[capability_id]["status"]
                for capability_id in result.required_capabilities
                if capability_id in capability_map
            },
            "mcp_version": session.get("mcp_version"),
            "checked_at": checked_at,
            "blocking_reason": None,
        }
    )

    canvas = updated.setdefault("canvas", {})
    if not isinstance(canvas, dict):
        raise ValueError("state.canvas must be an object")
    canvas["id"] = account.get("canvas_id")
    canvas["status"] = "READY"
    updated["current_phase"] = "PREFLIGHT"
    updated["approval_required"] = "PREFLIGHT_CONFIRMATION"
    updated["resume_hint"] = (
        "Technical Phase 1D preflight passed. Human confirmation is required before "
        "staging references. No generation is authorized."
    )
    updated["last_updated_at"] = checked_at
    return updated


def confirm_phase_1d_preflight(
    state: Mapping[str, Any],
    *,
    human_confirmed: bool,
    confirmed_at: str,
) -> dict[str, Any]:
    if human_confirmed is not True:
        raise ValueError("Phase 1D preflight confirmation requires an explicit human action")
    updated = copy.deepcopy(dict(state))
    preflight = updated.get("preflight")
    if not isinstance(preflight, dict) or preflight.get("status") != "APPROVAL_REQUIRED":
        raise ValueError("technical preflight must be APPROVAL_REQUIRED before confirmation")

    for field in (
        "mcp_connected",
        "authenticated",
        "canvas_access",
        "ownership_permission",
        "generation_config_checked",
        "budget_checked",
    ):
        if preflight.get(field) is not True:
            raise ValueError(f"cannot confirm incomplete preflight: {field} is not true")

    preflight["status"] = "READY"
    preflight["checked_at"] = confirmed_at
    updated["approval_required"] = None
    updated["resume_hint"] = (
        "Phase 1D preflight confirmed. Stage one or two references; do not generate media."
    )
    updated["last_updated_at"] = confirmed_at
    return updated


def evaluate_reference_pilot_status(
    manifest: Mapping[str, Any],
    state: Mapping[str, Any],
    capabilities: Mapping[str, Any],
    registry: Mapping[str, Any],
    workspace_root: str,
) -> ReferencePilotStatus:
    preflight_result = evaluate_phase_1d_preflight(manifest, state, capabilities)
    registry_result: ReferenceRegistryResult = validate_reference_registry(
        registry, workspace_root, manifest=manifest
    )
    issues = preflight_result.validation_issues + registry_result.issues
    blockers: list[str] = []

    # Once references are staged, the state preflight must already be explicitly READY.
    state_preflight = state.get("preflight")
    if not isinstance(state_preflight, Mapping) or state_preflight.get("status") != "READY":
        blockers.append("Phase 1D human-confirmed preflight is not READY")

    # Ignore the expected validate_state phase-vs-preflight issue only by requiring READY above;
    # all other technical blockers remain relevant.
    blockers.extend(preflight_result.blockers)
    if registry_result.issues:
        blockers.append("reference registry failed validation")
    blockers.extend(_zero_spend_and_no_tasks_blockers(state))

    records = registry.get("references")
    ids = registry.get("pilot_reference_ids")
    state_records = state.get("references")
    if isinstance(records, Mapping) and isinstance(ids, list):
        if not isinstance(state_records, Mapping):
            blockers.append("state.references is missing")
        else:
            for ref_id in ids:
                record = records.get(ref_id)
                state_record = state_records.get(ref_id)
                if not isinstance(record, Mapping) or not isinstance(state_record, Mapping):
                    blockers.append(f"state/registry reference {ref_id} is missing")
                    continue
                if state_record.get("remote_asset_id") != record.get("remote_asset_id"):
                    blockers.append(f"state/registry remote asset mismatch for {ref_id}")
                if state_record.get("approved") != (record.get("approval_status") == "APPROVED"):
                    blockers.append(f"state/registry approval mismatch for {ref_id}")
                if state_record.get("locked") != (record.get("locked") is True):
                    blockers.append(f"state/registry lock mismatch for {ref_id}")

    if blockers:
        status = "BLOCKED"
    else:
        registry_status = registry.get("status")
        status = str(registry_status) if registry_status else "BLOCKED"

    return ReferencePilotStatus(
        status=status,
        blockers=tuple(dict.fromkeys(blockers)),
        validation_issues=issues,
    )
