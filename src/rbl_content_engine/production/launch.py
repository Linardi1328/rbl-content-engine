"""Launch-video orchestration records and human publication gate."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .contracts import QCStatus


class LaunchStatus(str, Enum):
    PLANNED = "PLANNED"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    APPROVED_FOR_PUBLICATION = "APPROVED_FOR_PUBLICATION"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class LaunchShot:
    shot_id: str
    purpose: str
    duration_seconds: Decimal
    application: str
    estimated_cost_usd: Decimal
    prompt: str

    def __post_init__(self) -> None:
        if not self.shot_id.strip():
            raise ValueError("shot_id must not be empty")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if not self.application.strip():
            raise ValueError("application must not be empty")
        if self.estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd must be non-negative")
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")


@dataclass(frozen=True)
class LaunchShotResult:
    shot_id: str
    request_id: str
    output_url: str
    actual_cost_usd: Decimal
    qc_status: QCStatus

    def __post_init__(self) -> None:
        if not self.shot_id.strip() or not self.request_id.strip():
            raise ValueError("shot result ids must not be empty")
        if not self.output_url.strip():
            raise ValueError("output_url must not be empty")
        if self.actual_cost_usd < 0:
            raise ValueError("actual_cost_usd must be non-negative")


@dataclass(frozen=True)
class LaunchProject:
    launch_id: str
    title: str
    platform_targets: tuple[str, ...]
    shots: tuple[LaunchShot, ...]
    project_budget_usd: Decimal
    status: LaunchStatus = LaunchStatus.PLANNED

    def __post_init__(self) -> None:
        if not self.launch_id.strip() or not self.title.strip():
            raise ValueError("launch project identifiers must not be empty")
        if not self.platform_targets:
            raise ValueError("platform_targets must not be empty")
        if len(set(self.platform_targets)) != len(self.platform_targets):
            raise ValueError("platform_targets must be unique")
        if not self.shots:
            raise ValueError("launch project must contain at least one shot")
        if len({shot.shot_id for shot in self.shots}) != len(self.shots):
            raise ValueError("shot IDs must be unique")
        if self.project_budget_usd <= 0:
            raise ValueError("project_budget_usd must be positive")
        if sum((shot.estimated_cost_usd for shot in self.shots), Decimal("0")) > self.project_budget_usd:
            raise ValueError("estimated shot spend exceeds launch project budget")


@dataclass(frozen=True)
class LaunchReview:
    launch_id: str
    status: LaunchStatus
    final_video_url: str | None
    actual_spend_usd: Decimal
    qc_status: QCStatus
    human_approved_for_publication: bool = False

    def __post_init__(self) -> None:
        if not self.launch_id.strip():
            raise ValueError("launch_id must not be empty")
        if self.actual_spend_usd < 0:
            raise ValueError("actual_spend_usd must be non-negative")
        if self.human_approved_for_publication and self.status is not LaunchStatus.APPROVED_FOR_PUBLICATION:
            raise ValueError("publication approval requires APPROVED_FOR_PUBLICATION state")


def prepare_human_review(
    project: LaunchProject,
    results: tuple[LaunchShotResult, ...],
    *,
    final_video_url: str,
    actual_editing_cost_usd: Decimal = Decimal("0"),
) -> LaunchReview:
    if not final_video_url.strip():
        raise ValueError("final_video_url must not be empty")
    if actual_editing_cost_usd < 0:
        raise ValueError("actual_editing_cost_usd must be non-negative")

    expected = {shot.shot_id for shot in project.shots}
    observed = {result.shot_id for result in results}
    if expected != observed:
        raise ValueError("launch results must cover every planned shot exactly once")
    if any(result.qc_status is not QCStatus.PASS for result in results):
        raise ValueError("all launch shots must pass QC before human review")

    total = sum((result.actual_cost_usd for result in results), Decimal("0")) + actual_editing_cost_usd
    if total > project.project_budget_usd:
        raise ValueError("actual launch spend exceeds project budget")

    return LaunchReview(
        launch_id=project.launch_id,
        status=LaunchStatus.PENDING_HUMAN_REVIEW,
        final_video_url=final_video_url,
        actual_spend_usd=total,
        qc_status=QCStatus.PASS,
        human_approved_for_publication=False,
    )


def approve_for_publication(
    review: LaunchReview,
    *,
    human_confirmed: bool,
) -> LaunchReview:
    if review.status is not LaunchStatus.PENDING_HUMAN_REVIEW:
        raise ValueError("launch must be pending human review")
    if review.qc_status is not QCStatus.PASS:
        raise ValueError("launch QC must pass before publication approval")
    if not human_confirmed:
        raise ValueError("explicit human publication approval is required")

    return LaunchReview(
        launch_id=review.launch_id,
        status=LaunchStatus.APPROVED_FOR_PUBLICATION,
        final_video_url=review.final_video_url,
        actual_spend_usd=review.actual_spend_usd,
        qc_status=review.qc_status,
        human_approved_for_publication=True,
    )
