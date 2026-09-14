from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import Opportunity, SCORING_VERSION

WEIGHTS = {
    "demand_signal": 0.20,
    "creator_fit": 0.20,
    "originality": 0.15,
    "production_efficiency": 0.10,
    "evergreen_value": 0.10,
    "monetization_fit": 0.25,
}


@dataclass(frozen=True)
class RankedOpportunity:
    rank: int
    id: str
    topic: str
    platform: str
    format: str
    content_id: str | None
    factors: dict[str, int]
    factor_notes: dict[str, str]
    monetization_routes: tuple[str, ...]
    weighted_positive_score: float
    risk_penalty: float
    final_score: float
    scoring_version: str
    input_index: int

    def to_dict(self) -> dict:
        data = asdict(self)
        data["monetization_routes"] = list(self.monetization_routes)
        return data


def score_opportunity(opportunity: Opportunity) -> tuple[float, float, float]:
    weighted_positive = sum(
        opportunity.factors[name] * weight for name, weight in WEIGHTS.items()
    ) * 20.0
    risk_penalty = opportunity.factors["risk"] * 4.0
    final = max(0.0, min(100.0, weighted_positive - risk_penalty))
    return round(weighted_positive, 2), round(risk_penalty, 2), round(final, 2)


def rank_opportunities(opportunities: tuple[Opportunity, ...] | list[Opportunity]) -> list[RankedOpportunity]:
    scored = []
    for opportunity in opportunities:
        weighted_positive, risk_penalty, final = score_opportunity(opportunity)
        scored.append((opportunity, weighted_positive, risk_penalty, final))
    scored.sort(key=lambda item: (-item[3], item[0].input_index))
    return [
        RankedOpportunity(
            rank=index + 1,
            id=opportunity.id,
            topic=opportunity.topic,
            platform=opportunity.platform,
            format=opportunity.format,
            content_id=opportunity.content_id,
            factors=dict(opportunity.factors),
            factor_notes=dict(opportunity.factor_notes),
            monetization_routes=opportunity.monetization_routes,
            weighted_positive_score=weighted_positive,
            risk_penalty=risk_penalty,
            final_score=final,
            scoring_version=SCORING_VERSION,
            input_index=opportunity.input_index,
        )
        for index, (opportunity, weighted_positive, risk_penalty, final) in enumerate(scored)
    ]
