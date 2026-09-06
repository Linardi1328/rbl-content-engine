"""Fail-closed local preflight evaluation for future Topview production."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

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
class PreflightResult:
    status: str
    required_capabilities: tuple[str, ...]
    blockers: tuple[str, ...]
    manual_steps: tuple[str, ...]
    validation_issues: tuple[ValidationIssue, ...]
    chargeable_operations_required: bool

    @property
    def ready(self) -> bool:
        return self.status in {"READY", "READY_NON_CHARGEABLE"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.ready,
            "required_capabilities": list(self.required_capabilities),
            "blockers": list(self.blockers),
            "manual_steps": list(self.manual_steps),
            "chargeable_operations_required": self.chargeable_operations_required,
            "validation_issues": [issue.to_dict() for issue in self.validation_issues],
        }


def _capability_map(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in snapshot.get("capabilities", []):
        if isinstance(item, Mapping) and isinstance(item.get("id"), str):
            result[item["id"]] = item
    return result


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


def _required_capabilities(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    required = {"mcp_connectivity", "authentication"}
    scenes = manifest.get("scenes", [])

    generation_methods = _generation_methods(manifest)
    uses_references = False
    needs_image_generation = False

    if isinstance(manifest.get("references"), list) and manifest.get("references"):
        uses_references = True

    for scene in scenes if isinstance(scenes, list) else []:
        if not isinstance(scene, Mapping):
            continue
        refs = scene.get("references")
        if isinstance(refs, list) and refs:
            uses_references = True

        storyboard = scene.get("storyboard")
        if isinstance(storyboard, Mapping):
            if (
                storyboard.get("start_frame_required") is True
                and not storyboard.get("approved_start_frame_id")
            ):
                needs_image_generation = True

    for method in generation_methods:
        required.add(METHOD_CAPABILITY[method])

    if uses_references:
        required.add("reference_access")
    if needs_image_generation:
        required.add("image_generation")
    if generation_methods:
        required.update(
            {
                "canvas_access",
                "canvas_ownership",
                "generation_config",
                "task_monitoring",
            }
        )

    return tuple(sorted(required))


def _chargeable_required(manifest: Mapping[str, Any]) -> bool:
    if _generation_methods(manifest):
        return True

    scenes = manifest.get("scenes", [])
    if not isinstance(scenes, list):
        return False
    for scene in scenes:
        if not isinstance(scene, Mapping):
            continue
        storyboard = scene.get("storyboard")
        if isinstance(storyboard, Mapping):
            if (
                storyboard.get("start_frame_required") is True
                and not storyboard.get("approved_start_frame_id")
            ):
                return True
    return False


def _references_ready(manifest: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    references = manifest.get("references", [])
    if not isinstance(references, list):
        return blockers

    used: set[str] = set()
    scenes = manifest.get("scenes", [])
    if isinstance(scenes, list):
        for scene in scenes:
            if isinstance(scene, Mapping) and isinstance(scene.get("references"), list):
                used.update(str(item) for item in scene["references"])

    for item in references:
        if not isinstance(item, Mapping):
            continue
        ref_id = item.get("id")
        if ref_id not in used:
            continue
        if item.get("approval_status") != "APPROVED":
            blockers.append(f"reference {ref_id} is not human-approved")
        if item.get("locked") is not True:
            blockers.append(f"reference {ref_id} is not locked")
    return blockers


def _live_config_blockers(
    manifest: Mapping[str, Any], capabilities: Mapping[str, Any]
) -> list[str]:
    methods = _generation_methods(manifest)
    if not methods:
        return []

    configs = capabilities.get("generation_configs", [])
    if not isinstance(configs, list):
        return ["live generation_configs is not an array"]

    configured_methods = {
        str(item.get("task_type"))
        for item in configs
        if isinstance(item, Mapping) and item.get("task_type")
    }
    return [
        f"no live generation configuration recorded for required task type {method}"
        for method in sorted(methods.difference(configured_methods))
    ]


def evaluate_preflight(
    manifest: Mapping[str, Any],
    state: Mapping[str, Any],
    capabilities: Mapping[str, Any],
    *,
    chargeable_operations_authorized: bool = False,
) -> PreflightResult:
    """Evaluate local readiness without calling Topview or any other external service.

    Phase 1 callers should use the default `chargeable_operations_authorized=False`.
    A later phase must add an explicit human-controlled authorization boundary before
    invoking this function with chargeable operations enabled.
    """

    manifest_result = validate_manifest(manifest)
    state_result = validate_state(state)
    capability_result = validate_capabilities(capabilities)
    validation_issues = (
        manifest_result.issues + state_result.issues + capability_result.issues
    )

    required = _required_capabilities(manifest)
    chargeable_required = _chargeable_required(manifest)
    blockers: list[str] = []
    manual_steps: list[str] = []

    if validation_issues:
        blockers.append("one or more local contracts failed validation")

    session = capabilities.get("session")
    if not isinstance(session, Mapping) or session.get("status") != "READY":
        blockers.append("Topview live discovery session is not READY")

    by_id = _capability_map(capabilities)
    for cap_id in required:
        cap = by_id.get(cap_id)
        if not cap:
            blockers.append(f"required capability {cap_id} is missing")
            continue
        status = cap.get("status")
        if status == "MANUAL_REQUIRED":
            manual_steps.append(cap_id)
            if cap_id in {
                "mcp_connectivity",
                "authentication",
                "canvas_access",
                "canvas_ownership",
                "reference_access",
                "generation_config",
                "task_monitoring",
            }:
                blockers.append(f"required capability {cap_id} cannot be automated safely")
        elif status != "VERIFIED_LIVE":
            blockers.append(f"required capability {cap_id} is {status or 'UNKNOWN'}")

    account = capabilities.get("account")
    if "canvas_access" in required:
        if not isinstance(account, Mapping) or account.get("canvas_access") is not True:
            blockers.append("live account/Canvas access has not been positively verified")
    if "canvas_ownership" in required:
        if not isinstance(account, Mapping) or account.get("ownership_permission") is not True:
            blockers.append("live Canvas ownership/mutation permission has not been positively verified")

    blockers.extend(_live_config_blockers(manifest, capabilities))
    blockers.extend(_references_ready(manifest))

    if chargeable_required and not chargeable_operations_authorized:
        blockers.append(
            "chargeable Topview generation is not authorized in the current Phase 1 scope"
        )

    for optional_capability in ("targeted_video_edit", "timeline_edit", "timeline_export"):
        cap = by_id.get(optional_capability)
        if cap and cap.get("status") == "MANUAL_REQUIRED":
            manual_steps.append(optional_capability)

    if blockers:
        status = "BLOCKED"
    elif chargeable_required:
        status = "READY"
    else:
        status = "READY_NON_CHARGEABLE"

    return PreflightResult(
        status=status,
        required_capabilities=required,
        blockers=tuple(dict.fromkeys(blockers)),
        manual_steps=tuple(dict.fromkeys(manual_steps)),
        validation_issues=validation_issues,
        chargeable_operations_required=chargeable_required,
    )
