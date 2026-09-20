"""Stage 3 provider-neutral production records and authorization contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Mapping

from .providers import CostQuote, CostUnit, ProviderCapability


def _aware_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")


class GenerationScope(str, Enum):
    KEYFRAME = "KEYFRAME"
    VIDEO_DRAFT = "VIDEO_DRAFT"


class QCStatus(str, Enum):
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"


class PublicationMethod(str, Enum):
    MANUAL_EXTERNAL = "MANUAL_EXTERNAL"


@dataclass(frozen=True)
class ProviderSnapshot:
    provider_id: str
    channel: str
    observed_at: str
    capabilities: frozenset[ProviderCapability]
    model_ids: tuple[str, ...] = ()
    source: str = "LIVE_READ_ONLY"

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if not self.channel.strip():
            raise ValueError("channel must not be empty")
        if not self.capabilities:
            raise ValueError("provider snapshot must include capabilities")
        _aware_timestamp(self.observed_at, "observed_at")
        if len(set(self.model_ids)) != len(self.model_ids):
            raise ValueError("model_ids must be unique")


@dataclass(frozen=True)
class LockedReference:
    reference_id: str
    human_approved: bool
    locked: bool
    source_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.reference_id.strip():
            raise ValueError("reference_id must not be empty")
        if self.locked and not self.human_approved:
            raise ValueError("a locked reference must be human approved")


@dataclass(frozen=True)
class SceneCard:
    scene_id: str
    purpose: str
    platform: str
    aspect_ratio: str
    duration_seconds: Decimal
    reference_ids: tuple[str, ...]
    prompt: str
    required_capabilities: frozenset[ProviderCapability]
    long_clip_justification: str | None = None

    def __post_init__(self) -> None:
        if not self.scene_id.strip() or not self.scene_id.startswith("S"):
            raise ValueError("scene_id must be a non-empty SceneCard id")
        if not self.purpose.strip():
            raise ValueError("purpose must not be empty")
        if ":" not in self.aspect_ratio:
            raise ValueError("aspect_ratio must use W:H form")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if len(set(self.reference_ids)) != len(self.reference_ids):
            raise ValueError("reference_ids must be unique")
        if not self.required_capabilities:
            raise ValueError("required_capabilities must not be empty")


@dataclass(frozen=True)
class GenerationAuthorization:
    authorization_id: str
    provider_id: str
    scope: GenerationScope
    human_authorized: bool
    authorized_at: str
    max_usd: Decimal | None = None
    max_credits: Decimal | None = None
    allow_free_generation: bool = True
    allow_local_compute: bool = True

    def __post_init__(self) -> None:
        if not self.authorization_id.strip():
            raise ValueError("authorization_id must not be empty")
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        _aware_timestamp(self.authorized_at, "authorized_at")
        for value, name in (
            (self.max_usd, "max_usd"),
            (self.max_credits, "max_credits"),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")


def require_authorized_quote(
    quote: CostQuote,
    authorization: GenerationAuthorization,
    *,
    scope: GenerationScope,
) -> None:
    if not authorization.human_authorized:
        raise ValueError("generation requires explicit human authorization")
    if authorization.provider_id != quote.provider_id:
        raise ValueError("authorization provider does not match quote provider")
    if authorization.scope is not scope:
        raise ValueError("authorization scope does not match generation scope")

    if quote.unit is CostUnit.USD:
        if authorization.max_usd is None or quote.amount > authorization.max_usd:
            raise ValueError("USD quote exceeds authorized spend")
    elif quote.unit is CostUnit.CREDITS:
        if authorization.max_credits is None or quote.amount > authorization.max_credits:
            raise ValueError("credit quote exceeds authorized spend")
    elif quote.unit is CostUnit.FREE_GENERATION:
        if not authorization.allow_free_generation:
            raise ValueError("free-generation allowance is not authorized")
    elif quote.unit is CostUnit.LOCAL_COMPUTE:
        if not authorization.allow_local_compute:
            raise ValueError("local compute is not authorized")


@dataclass(frozen=True)
class KeyframeRecord:
    keyframe_id: str
    scene_id: str
    provider_id: str
    model_id: str
    job_id: str
    output_id: str
    created_at: str
    cost_amount: Decimal
    cost_unit: CostUnit
    qc_status: QCStatus
    human_approved: bool

    def __post_init__(self) -> None:
        for value, name in (
            (self.keyframe_id, "keyframe_id"),
            (self.scene_id, "scene_id"),
            (self.provider_id, "provider_id"),
            (self.model_id, "model_id"),
            (self.job_id, "job_id"),
            (self.output_id, "output_id"),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        _aware_timestamp(self.created_at, "created_at")
        if self.cost_amount < 0:
            raise ValueError("cost_amount must be non-negative")


@dataclass(frozen=True)
class VideoPrototypeRecord:
    video_id: str
    scene_id: str
    provider_id: str
    model_id: str
    job_ids: tuple[str, ...]
    output_id: str
    created_at: str
    start_keyframe_id: str | None
    duration_seconds: Decimal
    retry_count: int
    actual_cost_amount: Decimal
    actual_cost_unit: CostUnit
    qc_status: QCStatus
    human_approved: bool

    def __post_init__(self) -> None:
        for value, name in (
            (self.video_id, "video_id"),
            (self.scene_id, "scene_id"),
            (self.provider_id, "provider_id"),
            (self.model_id, "model_id"),
            (self.output_id, "output_id"),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not self.job_ids or any(not value.strip() for value in self.job_ids):
            raise ValueError("job_ids must contain observed job identifiers")
        if len(set(self.job_ids)) != len(self.job_ids):
            raise ValueError("job_ids must be unique")
        _aware_timestamp(self.created_at, "created_at")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")
        if self.actual_cost_amount < 0:
            raise ValueError("actual_cost_amount must be non-negative")


@dataclass(frozen=True)
class PublicationReceipt:
    video_id: str
    platform: str
    content_id: str
    published_at: str
    method: PublicationMethod
    human_confirmed: bool

    def __post_init__(self) -> None:
        if not self.video_id.strip() or not self.content_id.strip():
            raise ValueError("publication receipt ids must not be empty")
        if not self.platform.strip():
            raise ValueError("platform must not be empty")
        _aware_timestamp(self.published_at, "published_at")
        if self.method is not PublicationMethod.MANUAL_EXTERNAL:
            raise ValueError("RBL does not support automatic publication receipts")
        if not self.human_confirmed:
            raise ValueError("publication receipt requires human confirmation")


@dataclass(frozen=True)
class SocialObservation:
    content_id: str
    platform: str
    observed_at: str
    metrics: Mapping[str, Decimal]

    def __post_init__(self) -> None:
        if not self.content_id.strip() or not self.platform.strip():
            raise ValueError("social observation ids must not be empty")
        _aware_timestamp(self.observed_at, "observed_at")
        if not self.metrics:
            raise ValueError("metrics must not be empty")
        if any(value < 0 for value in self.metrics.values()):
            raise ValueError("social metrics must be non-negative")
