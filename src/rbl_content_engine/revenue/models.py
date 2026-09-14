from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from typing import Any

MANIFEST_VERSION = "RBL_REVENUE_INTELLIGENCE_V1"
SCORING_VERSION = "RBL_OPPORTUNITY_V1"

POSITIVE_FACTORS = (
    "demand_signal",
    "creator_fit",
    "originality",
    "production_efficiency",
    "evergreen_value",
    "monetization_fit",
)
ALL_FACTORS = POSITIVE_FACTORS + ("risk",)

MONETIZATION_ROUTES = {
    "WATCH_PAGE_ADS",
    "SHORTS_ADS",
    "AFFILIATE",
    "SPONSORSHIP",
    "OWN_PRODUCT",
    "SERVICE_LEAD",
    "KHLIM_LEAD",
    "NONE",
}

NUMERIC_ANALYTICS_FIELDS = {
    "views",
    "impressions",
    "watch_time_minutes",
    "average_view_duration_seconds",
    "likes",
    "comments",
    "shares",
    "subscribers_gained",
    "revenue",
    "clicks",
    "leads",
    "sales",
}

DIRECTIONS = {"AT_LEAST", "AT_MOST"}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ResearchSnapshot:
    path: str
    research_date: str


@dataclass(frozen=True)
class Hypothesis:
    audience: str
    hook: str
    primary_metric: str
    target: float
    direction: str


@dataclass(frozen=True)
class Opportunity:
    id: str
    topic: str
    platform: str
    format: str
    factors: dict[str, int]
    factor_notes: dict[str, str]
    monetization_routes: tuple[str, ...]
    hypothesis: Hypothesis
    content_id: str | None = None
    input_index: int = 0


@dataclass(frozen=True)
class RevenueManifest:
    version: str
    research_snapshot: ResearchSnapshot
    opportunities: tuple[Opportunity, ...]


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{field} must be a non-empty string.")
    return value.strip()


def _score(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 5:
        raise ManifestError(f"{field} must be an integer from 0 to 5.")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(f"{field} must be numeric.")
    result = float(value)
    if result < 0:
        raise ManifestError(f"{field} must be non-negative.")
    return result


def _resolve_inside(workspace: Path, relative: str, field: str) -> Path:
    candidate = (workspace / relative).resolve()
    root = workspace.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ManifestError(f"{field} must stay inside the workspace.") from exc
    if not candidate.is_file():
        raise ManifestError(f"{field} does not exist: {relative}")
    return candidate


def load_manifest(path: str | Path, *, workspace: str | Path | None = None) -> RevenueManifest:
    manifest_path = Path(path)
    root = Path(workspace) if workspace is not None else Path.cwd()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Unable to read opportunity manifest: {exc}") from exc

    if data.get("version") != MANIFEST_VERSION:
        raise ManifestError(f"version must be {MANIFEST_VERSION}.")

    research = data.get("research_snapshot")
    if not isinstance(research, dict):
        raise ManifestError("research_snapshot is required.")
    research_path = _nonempty(research.get("path"), "research_snapshot.path")
    research_date = _nonempty(
        research.get("research_date"), "research_snapshot.research_date"
    )
    try:
        date.fromisoformat(research_date)
    except ValueError as exc:
        raise ManifestError("research_snapshot.research_date must be an ISO date.") from exc
    _resolve_inside(root, research_path, "research_snapshot.path")

    raw_opportunities = data.get("opportunities")
    if not isinstance(raw_opportunities, list) or not raw_opportunities:
        raise ManifestError("opportunities must be a non-empty array.")

    seen_ids: set[str] = set()
    opportunities: list[Opportunity] = []
    for index, raw in enumerate(raw_opportunities):
        if not isinstance(raw, dict):
            raise ManifestError(f"opportunities[{index}] must be an object.")
        opportunity_id = _nonempty(raw.get("id"), f"opportunities[{index}].id")
        if opportunity_id in seen_ids:
            raise ManifestError(f"Duplicate opportunity id: {opportunity_id}")
        seen_ids.add(opportunity_id)

        raw_factors = raw.get("factors")
        if not isinstance(raw_factors, dict):
            raise ManifestError(f"{opportunity_id}.factors is required.")
        missing = [factor for factor in ALL_FACTORS if factor not in raw_factors]
        extra = [factor for factor in raw_factors if factor not in ALL_FACTORS]
        if missing or extra:
            detail = []
            if missing:
                detail.append(f"missing {', '.join(missing)}")
            if extra:
                detail.append(f"unknown {', '.join(extra)}")
            raise ManifestError(f"{opportunity_id}.factors: {'; '.join(detail)}.")
        factors = {
            factor: _score(raw_factors[factor], f"{opportunity_id}.factors.{factor}")
            for factor in ALL_FACTORS
        }

        raw_notes = raw.get("factor_notes", {})
        if not isinstance(raw_notes, dict):
            raise ManifestError(f"{opportunity_id}.factor_notes must be an object.")
        factor_notes: dict[str, str] = {}
        for factor, note in raw_notes.items():
            if factor not in ALL_FACTORS:
                raise ManifestError(f"{opportunity_id}.factor_notes has unknown factor {factor}.")
            factor_notes[factor] = _nonempty(
                note, f"{opportunity_id}.factor_notes.{factor}"
            )

        raw_routes = raw.get("monetization_routes")
        if not isinstance(raw_routes, list) or not raw_routes:
            raise ManifestError(f"{opportunity_id}.monetization_routes is required.")
        routes = tuple(_nonempty(route, f"{opportunity_id}.monetization_routes") for route in raw_routes)
        unknown_routes = [route for route in routes if route not in MONETIZATION_ROUTES]
        if unknown_routes:
            raise ManifestError(
                f"{opportunity_id} has unknown monetization route(s): {', '.join(unknown_routes)}"
            )
        if "NONE" in routes and len(routes) > 1:
            raise ManifestError(f"{opportunity_id}: NONE cannot be combined with other routes.")
        if len(set(routes)) != len(routes):
            raise ManifestError(f"{opportunity_id}: monetization routes must be unique.")

        raw_hypothesis = raw.get("hypothesis")
        if not isinstance(raw_hypothesis, dict):
            raise ManifestError(f"{opportunity_id}.hypothesis is required.")
        metric = _nonempty(
            raw_hypothesis.get("primary_metric"),
            f"{opportunity_id}.hypothesis.primary_metric",
        )
        if metric not in NUMERIC_ANALYTICS_FIELDS:
            raise ManifestError(
                f"{opportunity_id}.hypothesis.primary_metric must be a supported numeric analytics field."
            )
        direction = _nonempty(
            raw_hypothesis.get("direction"), f"{opportunity_id}.hypothesis.direction"
        )
        if direction not in DIRECTIONS:
            raise ManifestError(
                f"{opportunity_id}.hypothesis.direction must be AT_LEAST or AT_MOST."
            )
        hypothesis = Hypothesis(
            audience=_nonempty(
                raw_hypothesis.get("audience"), f"{opportunity_id}.hypothesis.audience"
            ),
            hook=_nonempty(
                raw_hypothesis.get("hook"), f"{opportunity_id}.hypothesis.hook"
            ),
            primary_metric=metric,
            target=_number(
                raw_hypothesis.get("target"), f"{opportunity_id}.hypothesis.target"
            ),
            direction=direction,
        )

        content_id = raw.get("content_id")
        if content_id is not None:
            content_id = _nonempty(content_id, f"{opportunity_id}.content_id")

        opportunities.append(
            Opportunity(
                id=opportunity_id,
                topic=_nonempty(raw.get("topic"), f"{opportunity_id}.topic"),
                platform=_nonempty(raw.get("platform"), f"{opportunity_id}.platform"),
                format=_nonempty(raw.get("format"), f"{opportunity_id}.format"),
                factors=factors,
                factor_notes=factor_notes,
                monetization_routes=routes,
                hypothesis=hypothesis,
                content_id=content_id,
                input_index=index,
            )
        )

    return RevenueManifest(
        version=MANIFEST_VERSION,
        research_snapshot=ResearchSnapshot(
            path=research_path, research_date=research_date
        ),
        opportunities=tuple(opportunities),
    )
