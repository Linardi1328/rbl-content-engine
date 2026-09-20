"""Provider-neutral media production contracts for RBL Content Engine.

Phase 3A deliberately defines planning, readiness, and authorization primitives only.
It performs no network calls and exposes no generation submission method.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol


class PrototypeStage(str, Enum):
    PROVE_PIPELINE = "PROVE_PIPELINE"
    PROVE_REPEATABILITY = "PROVE_REPEATABILITY"
    STABILIZE_PROVIDER = "STABILIZE_PROVIDER"


class CostUnit(str, Enum):
    USD = "USD"
    CREDITS = "CREDITS"
    FREE_GENERATION = "FREE_GENERATION"
    LOCAL_COMPUTE = "LOCAL_COMPUTE"


class ProviderCapability(str, Enum):
    KEYFRAME_IMAGE = "keyframe_image"
    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_TO_VIDEO = "image_to_video"
    REFERENCE_IMAGE = "reference_image"
    START_FRAME = "start_frame"
    END_FRAME = "end_frame"
    VIDEO_EDIT = "video_edit"
    COST_ESTIMATE = "cost_estimate"
    TASK_MONITORING = "task_monitoring"


@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    channel: str
    capabilities: frozenset[ProviderCapability]
    recurring_commitment: bool = False
    owner_controlled_credentials_required: bool = True

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if not self.channel.strip():
            raise ValueError("channel must not be empty")


@dataclass(frozen=True)
class CostQuote:
    provider_id: str
    amount: Decimal
    unit: CostUnit
    source: str
    estimated_usd: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if self.amount < 0:
            raise ValueError("quote amount must be non-negative")
        if self.estimated_usd is not None and self.estimated_usd < 0:
            raise ValueError("estimated_usd must be non-negative")
        if not self.source.strip():
            raise ValueError("quote source must not be empty")

    def cash_cost_usd(self) -> Decimal:
        """Return a USD value only when it is explicit rather than inferred."""
        if self.unit is CostUnit.USD:
            return self.amount
        if self.estimated_usd is not None:
            return self.estimated_usd
        raise ValueError(
            f"quote for {self.provider_id} is denominated in {self.unit.value}; "
            "an explicit USD estimate is required before cash-budget comparison"
        )


@dataclass(frozen=True)
class GenerationNeed:
    required_capabilities: frozenset[ProviderCapability]

    def __post_init__(self) -> None:
        if not self.required_capabilities:
            raise ValueError("at least one provider capability is required")


def provider_can_satisfy(
    provider: ProviderDescriptor,
    need: GenerationNeed,
) -> bool:
    return need.required_capabilities.issubset(provider.capabilities)


@dataclass(frozen=True)
class ProductionRecord:
    video_id: str
    production_complete: bool
    published: bool
    retry_count: int | None
    qc_recorded: bool
    actual_cost_amount: Decimal | None
    actual_cost_unit: CostUnit | None
    social_observation_recorded: bool = False

    def __post_init__(self) -> None:
        if not self.video_id.strip():
            raise ValueError("video_id must not be empty")
        if self.retry_count is not None and self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")
        if (self.actual_cost_amount is None) != (self.actual_cost_unit is None):
            raise ValueError("actual cost amount and unit must be supplied together")
        if self.actual_cost_amount is not None and self.actual_cost_amount < 0:
            raise ValueError("actual cost must be non-negative")


@dataclass(frozen=True)
class StabilityPolicy:
    min_completed_published_videos: int = 5
    min_social_observations: int = 3

    def __post_init__(self) -> None:
        if self.min_completed_published_videos < 1:
            raise ValueError("minimum completed/published videos must be positive")
        if self.min_social_observations < 0:
            raise ValueError("minimum social observations must be non-negative")


@dataclass(frozen=True)
class StabilityEvaluation:
    stage: PrototypeStage
    ready_for_provider_stabilization: bool
    completed_published_videos: int
    social_observation_count: int
    blockers: tuple[str, ...]


def evaluate_stability(
    records: tuple[ProductionRecord, ...],
    *,
    human_confirmed: bool,
    policy: StabilityPolicy = StabilityPolicy(),
) -> StabilityEvaluation:
    completed = tuple(
        record for record in records if record.production_complete and record.published
    )
    completed_count = len(completed)
    social_count = sum(record.social_observation_recorded for record in completed)

    blockers: list[str] = []

    if completed_count < policy.min_completed_published_videos:
        blockers.append("MINIMUM_PUBLISHED_VIDEO_COUNT_NOT_MET")

    if any(record.retry_count is None for record in completed):
        blockers.append("RETRY_DATA_INCOMPLETE")

    if any(not record.qc_recorded for record in completed):
        blockers.append("QC_DATA_INCOMPLETE")

    if any(
        record.actual_cost_amount is None or record.actual_cost_unit is None
        for record in completed
    ):
        blockers.append("COST_DATA_INCOMPLETE")

    if social_count < policy.min_social_observations:
        blockers.append("MINIMUM_SOCIAL_OBSERVATION_COUNT_NOT_MET")

    if not human_confirmed:
        blockers.append("HUMAN_CONFIRMATION_REQUIRED")

    ready = not blockers

    if ready:
        stage = PrototypeStage.STABILIZE_PROVIDER
    elif completed_count < policy.min_completed_published_videos:
        stage = PrototypeStage.PROVE_PIPELINE
    else:
        stage = PrototypeStage.PROVE_REPEATABILITY

    return StabilityEvaluation(
        stage=stage,
        ready_for_provider_stabilization=ready,
        completed_published_videos=completed_count,
        social_observation_count=social_count,
        blockers=tuple(blockers),
    )


@dataclass(frozen=True)
class ProviderCommitmentRequest:
    provider_id: str
    recurring_subscription: bool
    human_authorized: bool

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")


def authorize_provider_commitment(
    evaluation: StabilityEvaluation,
    request: ProviderCommitmentRequest,
) -> ProviderCommitmentRequest:
    """Validate a provider migration/subscription decision without executing it."""
    if not evaluation.ready_for_provider_stabilization:
        raise ValueError("provider stabilization gate is not ready")
    if evaluation.stage is not PrototypeStage.STABILIZE_PROVIDER:
        raise ValueError("provider stabilization requires STABILIZE_PROVIDER stage")
    if not request.human_authorized:
        raise ValueError("explicit human authorization is required")
    return request


class MediaGenerationProvider(Protocol):
    """Read-only Phase 3A provider surface.

    Submission/execution is intentionally absent. A later phase may add a separate
    execution protocol after explicit human authorization.
    """

    @property
    def descriptor(self) -> ProviderDescriptor: ...

    def estimate_cost(self, need: GenerationNeed) -> CostQuote: ...
