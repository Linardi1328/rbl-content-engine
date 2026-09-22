"""Shared V1 job-scoped media-plan and runtime-path rules.

The live Higgsfield mutation path stays in the existing scripts. This module only
validates the tracked plan contract and keeps each weekly job's local runtime state
and outputs isolated from every other job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[3]
EXPECTED_MODEL = "bytedance/seedance-2.5/text-to-video"
LEGACY_PLAN_FILE = ROOT / "examples" / "production" / "rbl-launch-video-plan.json"
LEGACY_STATE_FILE = ROOT / ".production" / "rbl-launch-video.json"
LEGACY_OUTPUT_DIR = ROOT / ".production" / "launch-video-outputs"
JOB_ROOT = ROOT / ".production" / "jobs"
PUBLICATION_POLICY = "PENDING_HUMAN_REVIEW_BEFORE_ANY_PUBLICATION"


@dataclass(frozen=True)
class VideoRuntimePaths:
    state_file: Path
    output_dir: Path
    final_video: Path
    legacy_launch: bool


def plan_identity(plan: Mapping[str, Any]) -> tuple[str, str]:
    raw_job = plan.get("job_id")
    raw_launch = plan.get("launch_id")
    job_id = raw_job.strip() if isinstance(raw_job, str) else ""
    launch_id = raw_launch.strip() if isinstance(raw_launch, str) else ""

    if job_id and launch_id and job_id != launch_id:
        raise ValueError("video plan job_id and launch_id must match when both are present")
    value = job_id or launch_id
    if not value:
        raise ValueError("video plan requires job_id or legacy launch_id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise ValueError("video plan id must use only letters, numbers, dot, underscore, or hyphen")
    return ("job_id" if job_id else "launch_id", value)


def validate_video_plan(plan: Mapping[str, Any]) -> None:
    identity_key, _ = plan_identity(plan)

    if plan.get("publication_policy") != PUBLICATION_POLICY:
        raise ValueError("video plan must remain blocked pending human review")
    if plan.get("model") != EXPECTED_MODEL:
        raise ValueError("video plan must use the live-verified Seedance 2.5 path")
    if plan.get("aspect_ratio") != "9:16":
        raise ValueError("video plan must remain vertical 9:16")
    if plan.get("resolution") != "720p":
        raise ValueError("video plan must use the approved 720p draft resolution")
    if plan.get("output_format") != "mp4":
        raise ValueError("video plan output format must be mp4")
    if plan.get("generate_audio") is not False:
        raise ValueError("video draft must disable generated audio")

    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("video plan must contain shots")

    ids: set[str] = set()
    estimated_total = Decimal("0")
    planned_duration = 0
    for shot in shots:
        if not isinstance(shot, Mapping):
            raise ValueError("every video shot must be an object")
        shot_id = str(shot.get("shot_id", "")).strip()
        if not shot_id or shot_id in ids:
            raise ValueError("video shot IDs must be unique and non-empty")
        ids.add(shot_id)
        if shot.get("application") != EXPECTED_MODEL:
            raise ValueError(f"{shot_id}: application must use Seedance 2.5 text-to-video")

        duration = shot.get("duration_seconds")
        if not isinstance(duration, int) or isinstance(duration, bool):
            raise ValueError(f"{shot_id}: duration_seconds must be an integer")
        if duration < 4 or duration > 8:
            raise ValueError(f"{shot_id}: generated clip duration must remain 4-8 seconds")
        planned_duration += duration

        if not str(shot.get("prompt", "")).strip():
            raise ValueError(f"{shot_id}: prompt must not be empty")

        cost = Decimal(str(shot.get("estimated_cost_usd", "0")))
        if cost < 0:
            raise ValueError(f"{shot_id}: estimated cost must be non-negative")
        estimated_total += cost

    target_duration = plan.get("target_duration_seconds")
    if (
        not isinstance(target_duration, int)
        or isinstance(target_duration, bool)
        or target_duration != planned_duration
    ):
        raise ValueError(
            "target_duration_seconds must equal the sum of generated shot durations"
        )
    if identity_key == "job_id" and not 20 <= target_duration <= 30:
        raise ValueError("V1 weekly video duration must remain between 20 and 30 seconds")

    project_budget = Decimal(str(plan.get("project_budget_usd", "0")))
    if project_budget <= 0:
        raise ValueError("video project budget must be positive")
    if project_budget > Decimal("20"):
        raise ValueError("V1 video project budget may not exceed US$20")
    if estimated_total > project_budget:
        raise ValueError("planned video spend exceeds project budget")


def resolve_runtime_paths(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
) -> VideoRuntimePaths:
    identity_key, identity = plan_identity(plan)
    legacy = (
        identity_key == "launch_id"
        and plan_path.resolve() == LEGACY_PLAN_FILE.resolve()
    )

    if legacy:
        return VideoRuntimePaths(
            state_file=LEGACY_STATE_FILE,
            output_dir=LEGACY_OUTPUT_DIR,
            final_video=LEGACY_OUTPUT_DIR / "rbl-launch-review.mp4",
            legacy_launch=True,
        )

    job_dir = JOB_ROOT / identity
    return VideoRuntimePaths(
        state_file=job_dir / "higgsfield-state.json",
        output_dir=job_dir / "generation",
        final_video=job_dir / "review.mp4",
        legacy_launch=False,
    )


def state_path_string(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT.resolve()))
    except ValueError:
        return str(resolved)


def resolve_recorded_path(raw: str) -> Path:
    path = Path(raw)
    resolved = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("recorded media path escapes repository root") from exc
    return resolved
