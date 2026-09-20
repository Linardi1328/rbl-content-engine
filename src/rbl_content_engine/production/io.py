"""JSON loading and deterministic reporting for Stage 3 fixtures."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .contracts import (
    KeyframeRecord,
    PublicationMethod,
    PublicationReceipt,
    QCStatus,
    SocialObservation,
    VideoPrototypeRecord,
)
from .providers import CostUnit
from .stage3 import Stage3Evaluation, evaluate_stage3, stage3_report_dict


def _decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{field} must be numeric") from exc


def load_stage3_evaluation(path: str | Path) -> Stage3Evaluation:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    keyframes = tuple(
        KeyframeRecord(
            keyframe_id=item["keyframe_id"],
            scene_id=item["scene_id"],
            provider_id=item["provider_id"],
            model_id=item["model_id"],
            job_id=item["job_id"],
            output_id=item["output_id"],
            created_at=item["created_at"],
            cost_amount=_decimal(item["cost_amount"], "keyframe cost_amount"),
            cost_unit=CostUnit(item["cost_unit"]),
            qc_status=QCStatus(item["qc_status"]),
            human_approved=bool(item["human_approved"]),
        )
        for item in payload.get("keyframes", [])
    )

    videos = tuple(
        VideoPrototypeRecord(
            video_id=item["video_id"],
            scene_id=item["scene_id"],
            provider_id=item["provider_id"],
            model_id=item["model_id"],
            job_ids=tuple(item["job_ids"]),
            output_id=item["output_id"],
            created_at=item["created_at"],
            start_keyframe_id=item.get("start_keyframe_id"),
            duration_seconds=_decimal(item["duration_seconds"], "video duration_seconds"),
            retry_count=int(item["retry_count"]),
            actual_cost_amount=_decimal(
                item["actual_cost_amount"],
                "video actual_cost_amount",
            ),
            actual_cost_unit=CostUnit(item["actual_cost_unit"]),
            qc_status=QCStatus(item["qc_status"]),
            human_approved=bool(item["human_approved"]),
        )
        for item in payload.get("videos", [])
    )

    publications = tuple(
        PublicationReceipt(
            video_id=item["video_id"],
            platform=item["platform"],
            content_id=item["content_id"],
            published_at=item["published_at"],
            method=PublicationMethod(item["method"]),
            human_confirmed=bool(item["human_confirmed"]),
        )
        for item in payload.get("publications", [])
    )

    observations = tuple(
        SocialObservation(
            content_id=item["content_id"],
            platform=item["platform"],
            observed_at=item["observed_at"],
            metrics={
                key: _decimal(value, f"observation metric {key}")
                for key, value in item["metrics"].items()
            },
        )
        for item in payload.get("observations", [])
    )

    return evaluate_stage3(
        keyframes,
        videos,
        publications,
        observations,
        human_confirmed_stability=bool(
            payload.get("human_confirmed_stability", False)
        ),
    )


def render_stage3_report(evaluation: Stage3Evaluation) -> str:
    return json.dumps(
        stage3_report_dict(evaluation),
        indent=2,
        sort_keys=True,
    ) + "\n"
