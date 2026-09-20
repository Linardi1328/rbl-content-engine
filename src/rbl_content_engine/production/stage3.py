"""Deterministic Stage 3 readiness, repeatability, and stabilization logic."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .contracts import (
    GenerationAuthorization,
    GenerationScope,
    KeyframeRecord,
    LockedReference,
    ProviderSnapshot,
    PublicationReceipt,
    QCStatus,
    SceneCard,
    SocialObservation,
    VideoPrototypeRecord,
    require_authorized_quote,
)
from .providers import (
    CostQuote,
    CostUnit,
    ProductionRecord,
    ProviderCapability,
    StabilityEvaluation,
    StabilityPolicy,
    evaluate_stability,
)


class Stage3Phase(str, Enum):
    PHASE_3B_KEYFRAME = "PHASE_3B_KEYFRAME"
    PHASE_3C_VIDEO = "PHASE_3C_VIDEO"
    PHASE_3D_REPEATABILITY = "PHASE_3D_REPEATABILITY"
    PHASE_3E_STABILIZATION = "PHASE_3E_STABILIZATION"


@dataclass(frozen=True)
class PreflightResult:
    ready: bool
    blockers: tuple[str, ...]


def _provider_supports(
    snapshot: ProviderSnapshot,
    capabilities: frozenset[ProviderCapability],
) -> bool:
    return capabilities.issubset(snapshot.capabilities)


def evaluate_keyframe_preflight(
    scene: SceneCard,
    references: tuple[LockedReference, ...],
    snapshot: ProviderSnapshot,
    quote: CostQuote,
    authorization: GenerationAuthorization,
    *,
    model_id: str,
) -> PreflightResult:
    blockers: list[str] = []
    if quote.provider_id != snapshot.provider_id:
        blockers.append("QUOTE_PROVIDER_MISMATCH")

    required = frozenset({ProviderCapability.KEYFRAME_IMAGE})
    if not _provider_supports(snapshot, required):
        blockers.append("KEYFRAME_CAPABILITY_UNAVAILABLE")
    if model_id not in snapshot.model_ids:
        blockers.append("MODEL_NOT_DISCOVERED")
    elif not snapshot.model_is_executable(model_id):
        blockers.append("MODEL_NOT_EXECUTABLE")

    refs = {reference.reference_id: reference for reference in references}
    for reference_id in scene.reference_ids:
        ref = refs.get(reference_id)
        if ref is None:
            blockers.append(f"REFERENCE_MISSING:{reference_id}")
        elif not ref.human_approved or not ref.locked:
            blockers.append(f"REFERENCE_NOT_LOCKED:{reference_id}")

    try:
        require_authorized_quote(
            quote,
            authorization,
            scope=GenerationScope.KEYFRAME,
        )
    except ValueError as exc:
        blockers.append(str(exc))

    return PreflightResult(ready=not blockers, blockers=tuple(blockers))


def keyframe_is_complete(record: KeyframeRecord) -> bool:
    return record.qc_status is QCStatus.PASS and record.human_approved


def evaluate_video_preflight(
    scene: SceneCard,
    keyframe: KeyframeRecord,
    snapshot: ProviderSnapshot,
    quote: CostQuote,
    authorization: GenerationAuthorization,
    *,
    model_id: str,
) -> PreflightResult:
    blockers: list[str] = []
    if quote.provider_id != snapshot.provider_id:
        blockers.append("QUOTE_PROVIDER_MISMATCH")
    if not keyframe_is_complete(keyframe):
        blockers.append("START_KEYFRAME_NOT_APPROVED")
    if keyframe.scene_id != scene.scene_id:
        blockers.append("START_KEYFRAME_SCENE_MISMATCH")

    required = frozenset({ProviderCapability.IMAGE_TO_VIDEO, ProviderCapability.START_FRAME})
    if not _provider_supports(snapshot, required):
        blockers.append("IMAGE_TO_VIDEO_CAPABILITY_UNAVAILABLE")
    if model_id not in snapshot.model_ids:
        blockers.append("MODEL_NOT_DISCOVERED")
    elif not snapshot.model_is_executable(model_id):
        blockers.append("MODEL_NOT_EXECUTABLE")

    if scene.duration_seconds > Decimal("8") and not scene.long_clip_justification:
        blockers.append("LONG_CLIP_JUSTIFICATION_REQUIRED")

    try:
        require_authorized_quote(
            quote,
            authorization,
            scope=GenerationScope.VIDEO_DRAFT,
        )
    except ValueError as exc:
        blockers.append(str(exc))

    return PreflightResult(ready=not blockers, blockers=tuple(blockers))


def video_is_complete(record: VideoPrototypeRecord) -> bool:
    return record.qc_status is QCStatus.PASS and record.human_approved


@dataclass(frozen=True)
class CostBucket:
    provider_id: str
    unit: CostUnit
    amount: Decimal


def summarize_costs(
    videos: tuple[VideoPrototypeRecord, ...],
) -> tuple[CostBucket, ...]:
    totals: dict[tuple[str, CostUnit], Decimal] = {}
    for video in videos:
        key = (video.provider_id, video.actual_cost_unit)
        totals[key] = totals.get(key, Decimal("0")) + video.actual_cost_amount
    return tuple(
        CostBucket(provider_id=provider_id, unit=unit, amount=totals[(provider_id, unit)])
        for provider_id, unit in sorted(
            totals,
            key=lambda item: (item[0], item[1].value),
        )
    )


def build_repeatability_records(
    videos: tuple[VideoPrototypeRecord, ...],
    publications: tuple[PublicationReceipt, ...],
    observations: tuple[SocialObservation, ...],
) -> tuple[ProductionRecord, ...]:
    video_ids = [video.video_id for video in videos]
    if len(video_ids) != len(set(video_ids)):
        raise ValueError("duplicate video_id in video records")

    receipt_by_video: dict[str, PublicationReceipt] = {}
    content_to_video: dict[str, str] = {}
    for receipt in publications:
        if receipt.video_id in receipt_by_video:
            raise ValueError("duplicate publication receipt for video")
        if receipt.content_id in content_to_video:
            raise ValueError("duplicate published content_id")
        receipt_by_video[receipt.video_id] = receipt
        content_to_video[receipt.content_id] = receipt.video_id

    observation_ids: set[str] = set()
    observed_content: set[str] = set()
    for observation in observations:
        key = f"{observation.platform}:{observation.content_id}:{observation.observed_at}"
        if key in observation_ids:
            raise ValueError("duplicate social observation")
        observation_ids.add(key)
        if observation.content_id not in content_to_video:
            raise ValueError("social observation has no matching publication receipt")
        receipt = receipt_by_video[content_to_video[observation.content_id]]
        if receipt.platform != observation.platform:
            raise ValueError("social observation platform mismatches publication receipt")
        observed_content.add(observation.content_id)

    result: list[ProductionRecord] = []
    for video in sorted(videos, key=lambda item: item.video_id):
        receipt = receipt_by_video.get(video.video_id)
        published = receipt is not None
        social_observed = bool(receipt and receipt.content_id in observed_content)
        result.append(
            ProductionRecord(
                video_id=video.video_id,
                production_complete=video_is_complete(video),
                published=published,
                retry_count=video.retry_count,
                qc_recorded=video.qc_status is not QCStatus.PENDING,
                actual_cost_amount=video.actual_cost_amount,
                actual_cost_unit=video.actual_cost_unit,
                social_observation_recorded=social_observed,
            )
        )
    return tuple(result)


@dataclass(frozen=True)
class ProviderSummary:
    provider_id: str
    completed_videos: int
    total_retries: int
    qc_passed_videos: int
    costs: tuple[CostBucket, ...]


@dataclass(frozen=True)
class Stage3Evaluation:
    phase: Stage3Phase
    ready_for_provider_stabilization: bool
    blockers: tuple[str, ...]
    stability: StabilityEvaluation
    provider_summaries: tuple[ProviderSummary, ...]


def build_provider_summaries(
    videos: tuple[VideoPrototypeRecord, ...],
) -> tuple[ProviderSummary, ...]:
    provider_ids = sorted({video.provider_id for video in videos})
    summaries: list[ProviderSummary] = []
    for provider_id in provider_ids:
        provider_videos = tuple(video for video in videos if video.provider_id == provider_id)
        summaries.append(
            ProviderSummary(
                provider_id=provider_id,
                completed_videos=sum(video_is_complete(video) for video in provider_videos),
                total_retries=sum(video.retry_count for video in provider_videos),
                qc_passed_videos=sum(video.qc_status is QCStatus.PASS for video in provider_videos),
                costs=summarize_costs(provider_videos),
            )
        )
    return tuple(summaries)


def evaluate_stage3(
    keyframes: tuple[KeyframeRecord, ...],
    videos: tuple[VideoPrototypeRecord, ...],
    publications: tuple[PublicationReceipt, ...],
    observations: tuple[SocialObservation, ...],
    *,
    human_confirmed_stability: bool,
    policy: StabilityPolicy = StabilityPolicy(),
) -> Stage3Evaluation:
    if not any(keyframe_is_complete(keyframe) for keyframe in keyframes):
        production_records = build_repeatability_records(videos, publications, observations)
        stability = evaluate_stability(
            production_records,
            human_confirmed=human_confirmed_stability,
            policy=policy,
        )
        return Stage3Evaluation(
            phase=Stage3Phase.PHASE_3B_KEYFRAME,
            ready_for_provider_stabilization=False,
            blockers=("APPROVED_KEYFRAME_REQUIRED",),
            stability=stability,
            provider_summaries=build_provider_summaries(videos),
        )

    if not any(video_is_complete(video) for video in videos):
        production_records = build_repeatability_records(videos, publications, observations)
        stability = evaluate_stability(
            production_records,
            human_confirmed=human_confirmed_stability,
            policy=policy,
        )
        return Stage3Evaluation(
            phase=Stage3Phase.PHASE_3C_VIDEO,
            ready_for_provider_stabilization=False,
            blockers=("COMPLETE_VIDEO_PROTOTYPE_REQUIRED",),
            stability=stability,
            provider_summaries=build_provider_summaries(videos),
        )

    production_records = build_repeatability_records(videos, publications, observations)
    stability = evaluate_stability(
        production_records,
        human_confirmed=human_confirmed_stability,
        policy=policy,
    )

    if not stability.ready_for_provider_stabilization:
        return Stage3Evaluation(
            phase=Stage3Phase.PHASE_3D_REPEATABILITY,
            ready_for_provider_stabilization=False,
            blockers=stability.blockers,
            stability=stability,
            provider_summaries=build_provider_summaries(videos),
        )

    return Stage3Evaluation(
        phase=Stage3Phase.PHASE_3E_STABILIZATION,
        ready_for_provider_stabilization=True,
        blockers=(),
        stability=stability,
        provider_summaries=build_provider_summaries(videos),
    )


def stage3_report_dict(evaluation: Stage3Evaluation) -> dict[str, object]:
    return {
        "phase": evaluation.phase.value,
        "ready_for_provider_stabilization": evaluation.ready_for_provider_stabilization,
        "blockers": list(evaluation.blockers),
        "stability": {
            "stage": evaluation.stability.stage.value,
            "ready_for_provider_stabilization": (
                evaluation.stability.ready_for_provider_stabilization
            ),
            "completed_published_videos": evaluation.stability.completed_published_videos,
            "social_observation_count": evaluation.stability.social_observation_count,
            "blockers": list(evaluation.stability.blockers),
        },
        "providers": [
            {
                "provider_id": summary.provider_id,
                "completed_videos": summary.completed_videos,
                "total_retries": summary.total_retries,
                "qc_passed_videos": summary.qc_passed_videos,
                "costs": [
                    {
                        "unit": bucket.unit.value,
                        "amount": str(bucket.amount),
                    }
                    for bucket in summary.costs
                ],
            }
            for summary in evaluation.provider_summaries
        ],
        "provider_selection": "HUMAN_DECISION_REQUIRED",
    }
