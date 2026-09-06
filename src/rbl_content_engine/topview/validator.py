"""Dependency-free semantic validators for RBL Topview contracts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


MANIFEST_VERSION = "0.2.0"
STATE_VERSION = "0.1.0"
CAPABILITY_VERSION = "0.1.0"

CANONICAL_CAPABILITIES = {
    "mcp_connectivity",
    "authentication",
    "canvas_access",
    "canvas_ownership",
    "reference_access",
    "generation_config",
    "image_generation",
    "text_to_video",
    "image_to_video",
    "omni_reference",
    "motion_control",
    "task_monitoring",
    "targeted_video_edit",
    "timeline_edit",
    "timeline_export",
}

AI_GENERATION_METHODS = {
    "image_to_video",
    "text_to_video",
    "omni_reference",
    "motion_control",
}

SCENE_ID_RE = re.compile(r"^S[0-9]{2,}$")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class ValidationResult:
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class _Collector:
    def __init__(self) -> None:
        self.issues: list[ValidationIssue] = []

    def add(self, code: str, path: str, message: str) -> None:
        self.issues.append(ValidationIssue(code=code, path=path, message=message))

    def result(self) -> ValidationResult:
        return ValidationResult(tuple(self.issues))


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return value


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _check_lineage(value: Any, path: str, out: _Collector) -> None:
    lineage = _mapping(value)
    if lineage is None:
        out.add("LINEAGE_REQUIRED", path, "content_lineage must be an object")
        return

    status = lineage.get("verification_status")
    claim_ids = lineage.get("claim_ids")
    evidence_refs = lineage.get("evidence_refs")

    if not isinstance(claim_ids, list) or not isinstance(evidence_refs, list):
        out.add(
            "LINEAGE_SHAPE",
            path,
            "claim_ids and evidence_refs must both be arrays",
        )
        return

    if status == "VERIFIED":
        if not claim_ids:
            out.add("VERIFIED_CLAIMS_EMPTY", path, "VERIFIED lineage requires claim IDs")
        if not evidence_refs:
            out.add(
                "VERIFIED_EVIDENCE_EMPTY",
                path,
                "VERIFIED lineage requires evidence references",
            )
    elif status == "NOT_APPLICABLE":
        if claim_ids or evidence_refs:
            out.add(
                "NOT_APPLICABLE_HAS_LINEAGE",
                path,
                "NOT_APPLICABLE scenes must not carry claim/evidence lineage",
            )
    else:
        out.add(
            "LINEAGE_STATUS_BLOCKED",
            f"{path}.verification_status",
            "Only VERIFIED or NOT_APPLICABLE may enter a Topview production manifest",
        )


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _validate_budget(budget: Any, path: str, out: _Collector) -> None:
    obj = _mapping(budget)
    if obj is None:
        out.add("BUDGET_REQUIRED", path, "budget must be an object")
        return

    field_limits = {
        "target_monthly_usd": 60.0,
        "normal_monthly_cap_usd": 100.0,
        "absolute_monthly_ceiling_usd": 150.0,
    }
    values: dict[str, float] = {}
    for field, maximum in field_limits.items():
        number = _number(obj.get(field))
        if number is None or number < 0:
            out.add("BUDGET_VALUE", f"{path}.{field}", "must be a non-negative number")
            continue
        values[field] = number
        if number > maximum:
            out.add(
                "BUDGET_POLICY_EXCEEDED",
                f"{path}.{field}",
                f"must not exceed RBL policy limit US${maximum:g}",
            )

    if all(field in values for field in field_limits):
        if not (
            values["target_monthly_usd"]
            <= values["normal_monthly_cap_usd"]
            <= values["absolute_monthly_ceiling_usd"]
        ):
            out.add(
                "BUDGET_ORDER",
                path,
                "target must be <= normal cap <= absolute ceiling",
            )


def validate_manifest(manifest: Mapping[str, Any]) -> ValidationResult:
    out = _Collector()

    if manifest.get("schema_version") != MANIFEST_VERSION:
        out.add(
            "MANIFEST_VERSION",
            "schema_version",
            f"expected {MANIFEST_VERSION}",
        )

    boundary = _mapping(manifest.get("verification_boundary"))
    expected_boundary = {
        "source": "rbl_content_engine.prooflab",
        "gate": "require_verified_claims",
        "policy": "FAIL_CLOSED",
    }
    if boundary is None:
        out.add(
            "PROOFLAB_BOUNDARY_REQUIRED",
            "verification_boundary",
            "Topview production must be downstream of the local ProofLab gate",
        )
    else:
        for field, expected in expected_boundary.items():
            if boundary.get(field) != expected:
                out.add(
                    "PROOFLAB_BOUNDARY_MISMATCH",
                    f"verification_boundary.{field}",
                    f"expected {expected!r}",
                )
        verified_claim_ids = boundary.get("verified_claim_ids")
        if not isinstance(verified_claim_ids, list):
            out.add(
                "VERIFIED_CLAIM_IDS_SHAPE",
                "verification_boundary.verified_claim_ids",
                "must be an array",
            )

    _validate_budget(manifest.get("budget_policy"), "budget_policy", out)
    budget = _mapping(manifest.get("budget_policy")) or {}

    references = manifest.get("references")
    reference_ids: set[str] = set()
    if not isinstance(references, list):
        out.add("REFERENCES_SHAPE", "references", "must be an array")
        references = []
    for index, item in enumerate(references):
        ref = _mapping(item)
        path = f"references[{index}]"
        if ref is None:
            out.add("REFERENCE_SHAPE", path, "reference must be an object")
            continue
        ref_id = ref.get("id")
        if not isinstance(ref_id, str) or not ref_id:
            out.add("REFERENCE_ID", f"{path}.id", "reference ID is required")
        elif ref_id in reference_ids:
            out.add("REFERENCE_DUPLICATE", f"{path}.id", f"duplicate reference {ref_id}")
        else:
            reference_ids.add(ref_id)

    project = _mapping(manifest.get("project"))
    if project is None:
        out.add("PROJECT_REQUIRED", "project", "project must be an object")
    elif "content_lineage" in project:
        _check_lineage(project.get("content_lineage"), "project.content_lineage", out)

    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        out.add("SCENES_REQUIRED", "scenes", "at least one scene is required")
        return out.result()

    seen_scene_ids: list[str] = []
    estimated_total = 0.0
    for index, item in enumerate(scenes):
        scene = _mapping(item)
        path = f"scenes[{index}]"
        if scene is None:
            out.add("SCENE_SHAPE", path, "scene must be an object")
            continue

        scene_id = scene.get("id")
        if not isinstance(scene_id, str) or not SCENE_ID_RE.fullmatch(scene_id):
            out.add("SCENE_ID", f"{path}.id", "scene ID must match SNN or longer")
        elif scene_id in seen_scene_ids:
            out.add("SCENE_DUPLICATE", f"{path}.id", f"duplicate scene {scene_id}")
        else:
            seen_scene_ids.append(scene_id)

        _check_lineage(scene.get("content_lineage"), f"{path}.content_lineage", out)

        scene_refs = scene.get("references")
        if not isinstance(scene_refs, list):
            out.add("SCENE_REFERENCES_SHAPE", f"{path}.references", "must be an array")
        else:
            for ref_id in scene_refs:
                if ref_id not in reference_ids:
                    out.add(
                        "SCENE_REFERENCE_UNKNOWN",
                        f"{path}.references",
                        f"unknown reference {ref_id!r}",
                    )

        continuity = _mapping(scene.get("continuity"))
        if continuity is None:
            out.add("CONTINUITY_REQUIRED", f"{path}.continuity", "continuity is required")
        else:
            previous = continuity.get("continues_from_scene")
            if previous is not None:
                if previous == scene_id:
                    out.add(
                        "CONTINUITY_SELF_REFERENCE",
                        f"{path}.continuity.continues_from_scene",
                        "a scene cannot continue from itself",
                    )
                elif previous not in seen_scene_ids[:-1]:
                    out.add(
                        "CONTINUITY_FORWARD_OR_UNKNOWN",
                        f"{path}.continuity.continues_from_scene",
                        "continuity must refer to an earlier scene in the manifest",
                    )

        qc = _mapping(scene.get("qc"))
        checks = qc.get("required_checks") if qc else None
        if not isinstance(checks, list) or "factual_lineage" not in checks:
            out.add(
                "QC_FACTUAL_LINEAGE_REQUIRED",
                f"{path}.qc.required_checks",
                "factual_lineage must be a required QC check",
            )

        generation = _mapping(scene.get("generation"))
        if generation is None:
            out.add("GENERATION_REQUIRED", f"{path}.generation", "generation is required")
        else:
            method = generation.get("method")
            target_seconds = _number(generation.get("target_clip_seconds"))
            if method in AI_GENERATION_METHODS and target_seconds is not None:
                if target_seconds > 8 and not generation.get("long_clip_justification"):
                    out.add(
                        "LONG_CLIP_JUSTIFICATION_REQUIRED",
                        f"{path}.generation.long_clip_justification",
                        "AI clips over the 4–8 second default need explicit justification",
                    )
            estimated = _number(generation.get("estimated_cost_usd"))
            if estimated is not None:
                if estimated < 0:
                    out.add(
                        "NEGATIVE_ESTIMATED_COST",
                        f"{path}.generation.estimated_cost_usd",
                        "estimated cost cannot be negative",
                    )
                else:
                    estimated_total += estimated

        storyboard = _mapping(scene.get("storyboard"))
        if storyboard and storyboard.get("start_frame_required") is True:
            if storyboard.get("approval_status") == "APPROVED" and not storyboard.get(
                "approved_start_frame_id"
            ):
                out.add(
                    "APPROVED_START_FRAME_ID_REQUIRED",
                    f"{path}.storyboard.approved_start_frame_id",
                    "an approved required start frame must have an ID",
                )

    per_video_cap = _number(budget.get("per_video_cap_usd"))
    if per_video_cap is not None and estimated_total > per_video_cap:
        out.add(
            "PER_VIDEO_BUDGET_EXCEEDED",
            "budget_policy.per_video_cap_usd",
            f"estimated scene spend US${estimated_total:.2f} exceeds per-video cap",
        )

    absolute = _number(budget.get("absolute_monthly_ceiling_usd"))
    if absolute is not None and estimated_total > absolute:
        out.add(
            "ABSOLUTE_BUDGET_EXCEEDED",
            "budget_policy.absolute_monthly_ceiling_usd",
            f"estimated project spend US${estimated_total:.2f} exceeds absolute ceiling",
        )

    return out.result()


def validate_state(state: Mapping[str, Any]) -> ValidationResult:
    out = _Collector()

    if state.get("schema_version") != STATE_VERSION:
        out.add("STATE_VERSION", "schema_version", f"expected {STATE_VERSION}")

    budget = _mapping(state.get("budget"))
    if budget is None:
        out.add("STATE_BUDGET_REQUIRED", "budget", "budget must be an object")
    else:
        translated = {
            "target_monthly_usd": budget.get("target_monthly_usd"),
            "normal_monthly_cap_usd": budget.get("normal_cap_usd"),
            "absolute_monthly_ceiling_usd": budget.get("absolute_ceiling_usd"),
        }
        _validate_budget(translated, "budget", out)
        actual = _number(budget.get("actual_project_spend_usd"))
        absolute = _number(budget.get("absolute_ceiling_usd"))
        if actual is None or actual < 0:
            out.add(
                "STATE_ACTUAL_SPEND",
                "budget.actual_project_spend_usd",
                "must be a non-negative number",
            )
        elif absolute is not None and actual > absolute:
            out.add(
                "STATE_ABSOLUTE_BUDGET_EXCEEDED",
                "budget.actual_project_spend_usd",
                "actual project spend exceeds the absolute ceiling",
            )

    preflight = _mapping(state.get("preflight"))
    preflight_status = preflight.get("status") if preflight else None
    current_phase = state.get("current_phase")
    if current_phase not in {"PREFLIGHT", "BLOCKED"} and preflight_status != "READY":
        out.add(
            "PHASE_BEFORE_PREFLIGHT",
            "current_phase",
            "cannot advance beyond PREFLIGHT until preflight status is READY",
        )

    tasks = state.get("generated_tasks")
    if not isinstance(tasks, list):
        out.add("TASKS_SHAPE", "generated_tasks", "must be an array")
    else:
        if tasks and preflight_status != "READY":
            out.add(
                "TASKS_BEFORE_PREFLIGHT",
                "generated_tasks",
                "generated tasks cannot exist before preflight is READY",
            )
        seen: set[str] = set()
        for index, task in enumerate(tasks):
            obj = _mapping(task)
            if obj is None:
                out.add("TASK_SHAPE", f"generated_tasks[{index}]", "task must be an object")
                continue
            task_id = obj.get("task_id")
            if isinstance(task_id, str) and task_id:
                if task_id in seen:
                    out.add(
                        "TASK_DUPLICATE",
                        f"generated_tasks[{index}].task_id",
                        f"duplicate task ID {task_id}",
                    )
                seen.add(task_id)

    if preflight_status == "READY" and preflight is not None:
        for field in (
            "mcp_connected",
            "authenticated",
            "canvas_access",
            "ownership_permission",
            "generation_config_checked",
            "budget_checked",
        ):
            if preflight.get(field) is not True:
                out.add(
                    "READY_PREFLIGHT_INCOMPLETE",
                    f"preflight.{field}",
                    "READY preflight requires this check to be true",
                )

    return out.result()


def validate_capabilities(snapshot: Mapping[str, Any]) -> ValidationResult:
    out = _Collector()

    if snapshot.get("schema_version") != CAPABILITY_VERSION:
        out.add(
            "CAPABILITY_VERSION",
            "schema_version",
            f"expected {CAPABILITY_VERSION}",
        )

    session = _mapping(snapshot.get("session"))
    if session is None:
        out.add("SESSION_REQUIRED", "session", "session must be an object")
    elif session.get("status") == "READY":
        if session.get("connected") is not True:
            out.add("READY_NOT_CONNECTED", "session.connected", "READY requires connection")
        if session.get("authenticated") is not True:
            out.add(
                "READY_NOT_AUTHENTICATED",
                "session.authenticated",
                "READY requires authentication",
            )

    capabilities = snapshot.get("capabilities")
    if not isinstance(capabilities, list):
        out.add("CAPABILITIES_SHAPE", "capabilities", "must be an array")
        return out.result()

    by_id: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(capabilities):
        cap = _mapping(item)
        path = f"capabilities[{index}]"
        if cap is None:
            out.add("CAPABILITY_SHAPE", path, "capability must be an object")
            continue
        cap_id = cap.get("id")
        if cap_id not in CANONICAL_CAPABILITIES:
            out.add("CAPABILITY_ID", f"{path}.id", f"unknown capability ID {cap_id!r}")
            continue
        if cap_id in by_id:
            out.add("CAPABILITY_DUPLICATE", f"{path}.id", f"duplicate capability {cap_id}")
            continue
        by_id[str(cap_id)] = cap

        status = cap.get("status")
        if status == "VERIFIED_LIVE":
            if cap.get("source") != "LIVE_MCP":
                out.add(
                    "VERIFIED_LIVE_SOURCE",
                    f"{path}.source",
                    "VERIFIED_LIVE requires source LIVE_MCP",
                )
            if not isinstance(cap.get("tool_name"), str) or not cap.get("tool_name"):
                out.add(
                    "VERIFIED_LIVE_TOOL",
                    f"{path}.tool_name",
                    "VERIFIED_LIVE requires the exact observed tool name",
                )
            if not cap.get("verified_at"):
                out.add(
                    "VERIFIED_LIVE_TIME",
                    f"{path}.verified_at",
                    "VERIFIED_LIVE requires a verification timestamp",
                )

    missing = CANONICAL_CAPABILITIES.difference(by_id)
    for cap_id in sorted(missing):
        out.add(
            "CAPABILITY_MISSING",
            "capabilities",
            f"canonical capability {cap_id} is missing from the snapshot",
        )

    if session and session.get("status") == "READY":
        for cap_id in ("mcp_connectivity", "authentication"):
            cap = by_id.get(cap_id)
            if not cap or cap.get("status") != "VERIFIED_LIVE":
                out.add(
                    "READY_CORE_CAPABILITY",
                    f"capabilities.{cap_id}",
                    "READY session requires this capability to be VERIFIED_LIVE",
                )

    configs = snapshot.get("generation_configs")
    if not isinstance(configs, list):
        out.add("GENERATION_CONFIGS_SHAPE", "generation_configs", "must be an array")
    elif configs:
        config_cap = by_id.get("generation_config")
        if not config_cap or config_cap.get("status") != "VERIFIED_LIVE":
            out.add(
                "GENERATION_CONFIG_NOT_VERIFIED",
                "generation_configs",
                "model configuration cannot be trusted until generation_config is VERIFIED_LIVE",
            )
        seen_configs: set[tuple[str, str]] = set()
        for index, config in enumerate(configs):
            obj = _mapping(config)
            if obj is None:
                out.add(
                    "GENERATION_CONFIG_SHAPE",
                    f"generation_configs[{index}]",
                    "config must be an object",
                )
                continue
            key = (str(obj.get("task_type", "")), str(obj.get("submit_model", "")))
            if not all(key):
                out.add(
                    "GENERATION_CONFIG_ID",
                    f"generation_configs[{index}]",
                    "task_type and submit_model are required",
                )
            elif key in seen_configs:
                out.add(
                    "GENERATION_CONFIG_DUPLICATE",
                    f"generation_configs[{index}]",
                    f"duplicate live config {key[0]} / {key[1]}",
                )
            seen_configs.add(key)

    return out.result()
