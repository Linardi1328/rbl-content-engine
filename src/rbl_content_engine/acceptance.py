"""Offline Customer Zero acceptance evaluator for the RBL Content Engine V1.

The evaluator performs no provider calls and no paid mutations. It verifies the
recorded artifacts from one real end-to-end content item:

weekly package -> storyboard -> media plan -> generated review cut ->
human-approved Phase 5 manifest -> completed publication receipt.

A PASS requires explicit human confirmation that the inputs describe a real RBL
content item rather than the checked-in synthetic fixtures.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .production.video_job import (
    EXPECTED_MODEL,
    plan_identity,
    resolve_recorded_path,
    validate_video_plan,
)
from .publishing.core import load_post_manifest


PASS = "PASS"
FAIL = "FAIL"


@dataclass(frozen=True)
class AcceptanceCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
        }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required acceptance artifact is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _record(
    checks: list[AcceptanceCheck],
    name: str,
    ok: bool,
    success: str,
    failure: str,
) -> None:
    checks.append(
        AcceptanceCheck(
            name=name,
            status=PASS if ok else FAIL,
            detail=success if ok else failure,
        )
    )


def evaluate_customer_zero(
    *,
    content_package_path: Path,
    storyboard_path: Path,
    media_plan_path: Path,
    generation_state_path: Path,
    post_manifest_path: Path,
    publication_receipt_path: Path,
    human_confirmed_real_content: bool,
) -> dict[str, Any]:
    checks: list[AcceptanceCheck] = []

    content = _read_json(content_package_path)
    storyboard = _read_json(storyboard_path)
    media_plan = _read_json(media_plan_path)
    generation = _read_json(generation_state_path)
    receipt = _read_json(publication_receipt_path)

    job_id = content.get("job_id")
    _record(
        checks,
        "real_content_confirmation",
        human_confirmed_real_content,
        "operator confirmed this is a real RBL Customer Zero item",
        "explicit --human-confirmed-real-content is required; synthetic fixtures cannot pass",
    )

    _record(
        checks,
        "content_package_ready",
        (
            isinstance(job_id, str)
            and bool(job_id)
            and content.get("status") == "READY_FOR_HUMAN_REVIEW"
            and content.get("verification_status") == "PASS"
            and content.get("approval_status") == "PENDING_HUMAN"
        ),
        "weekly package is evidence-verified and ready for human review",
        "weekly package must be READY_FOR_HUMAN_REVIEW / PASS / PENDING_HUMAN",
    )

    planned_duration = content.get("planned_duration_seconds")
    _record(
        checks,
        "content_duration",
        isinstance(planned_duration, int)
        and not isinstance(planned_duration, bool)
        and 20 <= planned_duration <= 30,
        "weekly content duration is within the V1 20-30 second window",
        "weekly content duration must be an integer between 20 and 30 seconds",
    )

    content_beats = content.get("script_beats")
    _record(
        checks,
        "content_has_script_beats",
        isinstance(content_beats, list) and len(content_beats) > 0,
        "weekly package contains script beats",
        "weekly package must contain at least one script beat",
    )

    storyboard_shots = storyboard.get("shots")
    storyboard_ok = (
        storyboard.get("job_id") == job_id
        and storyboard.get("approval_status") == "PENDING_HUMAN"
        and storyboard.get("planned_duration_seconds") == planned_duration
        and isinstance(storyboard_shots, list)
        and isinstance(content_beats, list)
        and len(storyboard_shots) == len(content_beats)
    )
    _record(
        checks,
        "storyboard_lineage",
        storyboard_ok,
        "storyboard matches the weekly job, duration, review gate, and beat count",
        "storyboard must match the weekly job, duration, PENDING_HUMAN gate, and beat count",
    )

    if storyboard_ok:
        beat_lineage_ok = all(
            isinstance(beat, Mapping)
            and isinstance(shot, Mapping)
            and beat.get("shot_id") == shot.get("shot_id")
            and beat.get("duration_seconds") == shot.get("duration_seconds")
            and beat.get("source_claim_ids") == shot.get("source_claim_ids")
            for beat, shot in zip(content_beats, storyboard_shots)
        )
    else:
        beat_lineage_ok = False
    _record(
        checks,
        "storyboard_beat_lineage",
        beat_lineage_ok,
        "every storyboard shot preserves beat ID, duration, and claim lineage",
        "storyboard shot lineage does not exactly match the weekly content package",
    )

    media_plan_error: str | None = None
    try:
        validate_video_plan(media_plan)
    except (ValueError, TypeError) as exc:
        media_plan_error = str(exc)

    media_identity_ok = False
    media_shots_ok = False
    if media_plan_error is None and isinstance(job_id, str):
        identity_key, identity = plan_identity(media_plan)
        media_identity_ok = identity_key == "job_id" and identity == job_id
        raw_media_shots = media_plan.get("shots")
        if isinstance(raw_media_shots, list) and isinstance(storyboard_shots, list):
            media_shots_ok = (
                len(raw_media_shots) == len(storyboard_shots)
                and media_plan.get("target_duration_seconds") == planned_duration
                and all(
                    isinstance(media_shot, Mapping)
                    and isinstance(story_shot, Mapping)
                    and media_shot.get("shot_id") == story_shot.get("shot_id")
                    and media_shot.get("duration_seconds")
                    == story_shot.get("duration_seconds")
                    for media_shot, story_shot in zip(
                        raw_media_shots, storyboard_shots
                    )
                )
            )

    _record(
        checks,
        "media_plan_valid",
        media_plan_error is None,
        "media plan satisfies the V1 Seedance production contract",
        "media plan validation failed"
        + (f": {media_plan_error}" if media_plan_error else ""),
    )
    _record(
        checks,
        "media_plan_job_lineage",
        media_identity_ok,
        "media plan job_id matches the weekly content package",
        "media plan must use the exact weekly job_id",
    )
    _record(
        checks,
        "media_plan_storyboard_alignment",
        media_shots_ok,
        "media plan shot IDs and durations exactly match the storyboard",
        "media plan must preserve storyboard shot IDs, durations, and total duration",
    )

    generation_shots = generation.get("shots")
    generation_base_ok = (
        generation.get("job_id") == job_id
        and generation.get("model") == EXPECTED_MODEL
        and generation.get("status") == "PENDING_HUMAN_REVIEW"
        and generation.get("publication_status") == "BLOCKED_PENDING_HUMAN_REVIEW"
        and isinstance(generation_shots, Mapping)
    )
    _record(
        checks,
        "generation_state",
        generation_base_ok,
        "generated media job is complete and stopped at PENDING_HUMAN_REVIEW",
        "generation state must match job_id/model and stop at PENDING_HUMAN_REVIEW",
    )

    plan_shots = media_plan.get("shots")
    generation_shots_ok = (
        generation_base_ok
        and isinstance(plan_shots, list)
        and all(
            isinstance(shot, Mapping)
            and isinstance(generation_shots.get(str(shot.get("shot_id"))), Mapping)
            and generation_shots[str(shot.get("shot_id"))].get("status") == "COMPLETED"
            for shot in plan_shots
        )
    )
    _record(
        checks,
        "generation_shot_completion",
        generation_shots_ok,
        "every planned generated shot has a COMPLETED runtime record",
        "every planned media shot must have a COMPLETED generation record",
    )

    final_video = generation.get("final_video")
    final_video_ok = False
    final_video_detail = "final generated review cut metadata is missing"
    if isinstance(final_video, Mapping):
        raw_path = final_video.get("local_path")
        try:
            actual_path = (
                resolve_recorded_path(str(raw_path))
                if isinstance(raw_path, str) and raw_path
                else None
            )
        except ValueError as exc:
            actual_path = None
            final_video_detail = str(exc)
        duration = final_video.get("duration_seconds")
        expected = (
            float(media_plan.get("target_duration_seconds"))
            if isinstance(media_plan.get("target_duration_seconds"), int)
            else None
        )
        final_video_ok = (
            actual_path is not None
            and actual_path.is_file()
            and final_video.get("technical_qc") == "PASS"
            and int(final_video.get("width", 0)) == 720
            and int(final_video.get("height", 0)) == 1280
            and isinstance(duration, (int, float))
            and not isinstance(duration, bool)
            and expected is not None
            and expected - 2.5 <= float(duration) <= expected + 2.5
        )
        if final_video_ok:
            final_video_detail = (
                "final review cut exists, passed technical QC, is 720x1280, "
                "and matches the planned duration"
            )
        elif actual_path is not None and not actual_path.is_file():
            final_video_detail = f"final review cut file is missing: {actual_path}"
        elif final_video.get("technical_qc") != "PASS":
            final_video_detail = "final review cut technical_qc must be PASS"
        elif (
            int(final_video.get("width", 0)),
            int(final_video.get("height", 0)),
        ) != (720, 1280):
            final_video_detail = "final review cut must be 720x1280"
        elif expected is not None and isinstance(duration, (int, float)):
            final_video_detail = (
                f"final review cut duration {duration} does not match planned "
                f"{expected} seconds"
            )
    _record(
        checks,
        "final_review_cut",
        final_video_ok,
        final_video_detail if final_video_ok else "",
        final_video_detail,
    )

    manifest: dict[str, Any] | None = None
    manifest_error: str | None = None
    try:
        manifest = load_post_manifest(post_manifest_path)
    except (ValueError, OSError) as exc:
        manifest_error = str(exc)

    enabled_platforms: list[str] = []
    if manifest is not None:
        raw_platforms = manifest.get("platforms")
        if isinstance(raw_platforms, Mapping):
            enabled_platforms = sorted(
                str(name)
                for name, config in raw_platforms.items()
                if isinstance(config, Mapping) and config.get("enabled", True)
            )

    manifest_ok = (
        manifest is not None
        and manifest.get("post_id") == job_id
        and len(enabled_platforms) > 0
        and isinstance(manifest.get("approval"), Mapping)
        and manifest["approval"].get("human_confirmed") is True
    )
    _record(
        checks,
        "publication_manifest",
        manifest_ok,
        "Phase 5 manifest matches the job, has enabled targets, and binds exact human-approved assets",
        "Phase 5 manifest must validate, match job_id, enable at least one platform, and have exact-asset human approval"
        + (f": {manifest_error}" if manifest_error else ""),
    )

    receipt_platforms = receipt.get("platforms")
    receipt_base_ok = (
        receipt.get("post_id") == job_id
        and receipt.get("job_status") == "COMPLETE"
        and isinstance(receipt_platforms, Mapping)
        and manifest is not None
        and receipt.get("scheduled_at") == manifest.get("scheduled_at")
    )
    _record(
        checks,
        "publication_receipt_complete",
        receipt_base_ok,
        "publication receipt is COMPLETE and matches the approved post",
        "publication receipt must be COMPLETE and match post_id/scheduled_at",
    )

    platform_states_ok = False
    at_least_one_published = False
    if receipt_base_ok and isinstance(receipt_platforms, Mapping):
        platform_states_ok = all(
            isinstance(receipt_platforms.get(platform), Mapping)
            and receipt_platforms[platform].get("status")
            in {"PUBLISHED", "NATIVE_SCHEDULED"}
            and not receipt_platforms[platform].get("error")
            for platform in enabled_platforms
        )
        at_least_one_published = any(
            isinstance(receipt_platforms.get(platform), Mapping)
            and receipt_platforms[platform].get("status") == "PUBLISHED"
            for platform in enabled_platforms
        )

    _record(
        checks,
        "enabled_platforms_complete",
        platform_states_ok,
        "every platform enabled for the acceptance post completed successfully",
        "every enabled platform must finish as PUBLISHED or NATIVE_SCHEDULED with no error",
    )
    _record(
        checks,
        "live_publication_observed",
        at_least_one_published,
        "at least one enabled platform reached an actual PUBLISHED state",
        "Customer Zero acceptance requires at least one actual PUBLISHED platform",
    )

    overall = PASS if checks and all(item.status == PASS for item in checks) else FAIL
    failed = [item.name for item in checks if item.status == FAIL]

    return {
        "schema_version": "1.0.0",
        "acceptance": "RBL_CONTENT_ENGINE_V1_CUSTOMER_ZERO",
        "status": overall,
        "job_id": job_id,
        "enabled_platforms": enabled_platforms,
        "failed_checks": failed,
        "checks": [item.to_dict() for item in checks],
        "network_calls": 0,
        "paid_mutations": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate one real RBL V1 Customer Zero end-to-end acceptance run"
    )
    parser.add_argument("--content-package", type=Path, required=True)
    parser.add_argument("--storyboard", type=Path, required=True)
    parser.add_argument("--media-plan", type=Path, required=True)
    parser.add_argument("--generation-state", type=Path, required=True)
    parser.add_argument("--post-manifest", type=Path, required=True)
    parser.add_argument("--publication-receipt", type=Path, required=True)
    parser.add_argument(
        "--human-confirmed-real-content",
        action="store_true",
        help="Confirm these artifacts belong to a real RBL content item, not a synthetic fixture",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = evaluate_customer_zero(
        content_package_path=args.content_package,
        storyboard_path=args.storyboard,
        media_plan_path=args.media_plan,
        generation_state_path=args.generation_state,
        post_manifest_path=args.post_manifest,
        publication_receipt_path=args.publication_receipt,
        human_confirmed_real_content=args.human_confirmed_real_content,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
