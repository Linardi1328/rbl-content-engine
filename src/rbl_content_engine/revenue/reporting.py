from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import RevenueManifest, SCORING_VERSION
from .scoring import RankedOpportunity, rank_opportunities

DISCLAIMER = (
    "These scores and observations are decision aids, not forecasts. "
    "Observed performance does not establish causality or guarantee future results."
)


def _json_text(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _observation(
    ranked: RankedOpportunity,
    manifest: RevenueManifest,
    analytics: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    opportunity = next(o for o in manifest.opportunities if o.id == ranked.id)
    hypothesis = opportunity.hypothesis
    result: dict[str, Any] = {
        "opportunity_id": opportunity.id,
        "content_id": opportunity.content_id,
        "topic": opportunity.topic,
        "platform": opportunity.platform,
        "format": opportunity.format,
        "audience": hypothesis.audience,
        "hook": hypothesis.hook,
        "monetization_routes": list(opportunity.monetization_routes),
        "primary_metric": hypothesis.primary_metric,
        "target": hypothesis.target,
        "direction": hypothesis.direction,
        "opportunity_score": ranked.final_score,
        "scoring_version": SCORING_VERSION,
        "research_snapshot": {
            "path": manifest.research_snapshot.path,
            "research_date": manifest.research_snapshot.research_date,
        },
        "observation_status": "UNOBSERVED",
        "observed_value": None,
        "observed_metrics": None,
    }
    if not opportunity.content_id:
        return result
    if analytics is None or opportunity.content_id not in analytics:
        result["observation_status"] = "NO_MATCHING_DATA"
        return result
    metrics = analytics[opportunity.content_id]
    observed = metrics.get(hypothesis.primary_metric)
    result["observed_metrics"] = metrics
    if observed is None:
        result["observation_status"] = "NO_MATCHING_DATA"
        return result
    result["observed_value"] = observed
    if hypothesis.direction == "AT_LEAST":
        met = float(observed) >= hypothesis.target
    else:
        met = float(observed) <= hypothesis.target
    result["observation_status"] = "TARGET_MET" if met else "TARGET_MISSED"
    return result


def _ranking_payload(
    manifest: RevenueManifest, ranked: list[RankedOpportunity]
) -> dict[str, Any]:
    return {
        "version": manifest.version,
        "scoring_version": SCORING_VERSION,
        "research_snapshot": {
            "path": manifest.research_snapshot.path,
            "research_date": manifest.research_snapshot.research_date,
        },
        "disclaimer": DISCLAIMER,
        "opportunities": [item.to_dict() for item in ranked],
    }


def _ranking_markdown(
    manifest: RevenueManifest, ranked: list[RankedOpportunity]
) -> str:
    lines = [
        "# RBL Opportunity Ranking",
        "",
        f"Research snapshot: `{manifest.research_snapshot.path}` ({manifest.research_snapshot.research_date})",
        f"Scoring policy: `{SCORING_VERSION}`",
        "",
        DISCLAIMER,
        "",
        "| Rank | Opportunity | Platform / format | Score | Risk penalty | Monetization routes |",
        "| ---: | --- | --- | ---: | ---: | --- |",
    ]
    for item in ranked:
        lines.append(
            f"| {item.rank} | {item.topic} | {item.platform} / {item.format} | "
            f"{item.final_score:.2f} | {item.risk_penalty:.2f} | {', '.join(item.monetization_routes)} |"
        )
    lines.extend(["", "## Factor details", ""])
    for item in ranked:
        lines.extend(
            [
                f"### {item.rank}. {item.topic}",
                "",
                f"Weighted positive score: **{item.weighted_positive_score:.2f}**",
                f"Risk penalty: **{item.risk_penalty:.2f}**",
                f"Final score: **{item.final_score:.2f}**",
                "",
            ]
        )
        for factor, value in item.factors.items():
            note = item.factor_notes.get(factor, "No note supplied.")
            lines.append(f"- `{factor}`: {value}/5 — {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _learning_markdown(
    manifest: RevenueManifest, observations: list[dict[str, Any]]
) -> str:
    lines = [
        "# RBL Revenue & Audience Learning Report",
        "",
        f"Research snapshot: `{manifest.research_snapshot.path}` ({manifest.research_snapshot.research_date})",
        "",
        DISCLAIMER,
        "",
    ]
    for observation in observations:
        lines.extend(
            [
                f"## {observation['opportunity_id']} — {observation['topic']}",
                "",
                f"- Platform / format: {observation['platform']} / {observation['format']}",
                f"- Opportunity score: {observation['opportunity_score']:.2f}",
                f"- Monetization routes: {', '.join(observation['monetization_routes'])}",
                f"- Hypothesis metric: `{observation['primary_metric']}` {observation['direction']} {observation['target']}",
                f"- Observation status: **{observation['observation_status']}**",
            ]
        )
        if observation["observed_value"] is not None:
            lines.append(f"- Observed value: {observation['observed_value']}")
        if observation["content_id"]:
            lines.append(f"- Content ID: `{observation['content_id']}`")
        else:
            lines.append("- Content ID: not assigned; publication remains a human/manual step.")
        lines.extend(
            [
                "",
                "Interpretation: compare the observation with the pre-declared hypothesis only. "
                "Do not infer that the hook, format, platform, or monetization route caused the result.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_outputs(
    manifest: RevenueManifest,
    analytics: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    ranked = rank_opportunities(manifest.opportunities)
    observations = [_observation(item, manifest, analytics) for item in ranked]
    hypotheses = {
        "version": manifest.version,
        "research_snapshot": {
            "path": manifest.research_snapshot.path,
            "research_date": manifest.research_snapshot.research_date,
        },
        "disclaimer": DISCLAIMER,
        "hypotheses": observations,
    }
    learning = {
        "version": manifest.version,
        "research_snapshot": {
            "path": manifest.research_snapshot.path,
            "research_date": manifest.research_snapshot.research_date,
        },
        "disclaimer": DISCLAIMER,
        "observations": observations,
    }
    return {
        "opportunity-ranking.json": _json_text(_ranking_payload(manifest, ranked)),
        "opportunity-ranking.md": _ranking_markdown(manifest, ranked),
        "hypotheses.json": _json_text(hypotheses),
        "learning-report.json": _json_text(learning),
        "learning-report.md": _learning_markdown(manifest, observations),
    }


def write_outputs(
    output_dir: str | Path,
    manifest: RevenueManifest,
    analytics: dict[str, dict[str, Any]] | None = None,
) -> tuple[Path, ...]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    outputs = build_outputs(manifest, analytics)
    written: list[Path] = []
    for filename, content in outputs.items():
        path = destination / filename
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return tuple(written)
