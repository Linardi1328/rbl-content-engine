from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
from typing import Any

from .analytics import parse_timestamp
from .models import ManifestError, MetricTarget, RevenueManifest, SCORING_VERSION
from .scoring import RankedOpportunity, rank_opportunities

DISCLAIMER = (
    "These scores and observations are decision aids, not forecasts. "
    "Observed performance does not establish causality or guarantee future results."
)


def _json_text(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _target_shell(target: MetricTarget | None) -> dict[str, Any] | None:
    if target is None:
        return None
    return {
        "metric": target.metric,
        "target": target.target,
        "direction": target.direction,
        "currency": target.currency,
        "status": "UNOBSERVED",
        "observed_value": None,
    }


def _evaluate_target(
    target: MetricTarget | None,
    metrics: dict[str, Any],
    *,
    window_status: str,
) -> dict[str, Any] | None:
    result = _target_shell(target)
    if target is None or result is None:
        return None
    observed = metrics.get(target.metric)
    result["observed_value"] = observed
    if window_status == "WINDOW_PENDING":
        result["status"] = "WINDOW_PENDING"
        return result
    if observed is None:
        result["status"] = "NO_MATCHING_DATA"
        return result
    if target.metric == "revenue":
        observed_currency = metrics.get("currency")
        if not observed_currency:
            raise ManifestError(
                "Revenue analytics require currency when evaluating a revenue target."
            )
        if observed_currency.casefold() != (target.currency or "").casefold():
            raise ManifestError(
                f"Revenue currency mismatch: target uses {target.currency}, analytics use {observed_currency}."
            )
    if target.direction == "AT_LEAST":
        met = float(observed) >= target.target
    else:
        met = float(observed) <= target.target
    result["status"] = "TARGET_MET" if met else "TARGET_MISSED"
    return result


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
        "evaluation_after_days": hypothesis.evaluation_after_days,
        "opportunity_score": ranked.final_score,
        "scoring_version": SCORING_VERSION,
        "research_snapshot": {
            "path": manifest.research_snapshot.path,
            "research_date": manifest.research_snapshot.research_date,
        },
        "observation_status": "UNOBSERVED",
        "published_at": None,
        "observed_at": None,
        "evaluation_due_at": None,
        "audience_target": _target_shell(hypothesis.audience_target),
        "commercial_target": _target_shell(hypothesis.commercial_target),
        "observed_metrics": None,
    }
    if not opportunity.content_id:
        return result
    if analytics is None or opportunity.content_id not in analytics:
        result["observation_status"] = "NO_MATCHING_DATA"
        if result["audience_target"]:
            result["audience_target"]["status"] = "NO_MATCHING_DATA"
        if result["commercial_target"]:
            result["commercial_target"]["status"] = "NO_MATCHING_DATA"
        return result

    metrics = analytics[opportunity.content_id]
    if str(metrics.get("platform", "")).casefold() != opportunity.platform.casefold():
        raise ManifestError(
            f"Platform mismatch for content_id {opportunity.content_id}: opportunity is {opportunity.platform}, analytics are {metrics.get('platform')}."
        )

    published_at = parse_timestamp(
        str(metrics["published_at"]), f"{opportunity.content_id}.published_at"
    )
    observed_at = parse_timestamp(
        str(metrics["observed_at"]), f"{opportunity.content_id}.observed_at"
    )
    evaluation_due = published_at + timedelta(days=hypothesis.evaluation_after_days)
    window_status = "WINDOW_PENDING" if observed_at < evaluation_due else "EVALUATED"

    result.update(
        {
            "observation_status": window_status,
            "published_at": published_at.isoformat(),
            "observed_at": observed_at.isoformat(),
            "evaluation_due_at": evaluation_due.isoformat(),
            "observed_metrics": metrics,
            "audience_target": _evaluate_target(
                hypothesis.audience_target, metrics, window_status=window_status
            ),
            "commercial_target": _evaluate_target(
                hypothesis.commercial_target, metrics, window_status=window_status
            ),
        }
    )
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
            lines.append(f"- `{factor}`: {value}/5 — {item.factor_notes[factor]}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _target_line(label: str, target: dict[str, Any] | None) -> str:
    if target is None:
        return f"- {label}: not declared"
    currency = f" {target['currency']}" if target.get("currency") else ""
    observed = (
        f"; observed {target['observed_value']}{currency}"
        if target.get("observed_value") is not None
        else ""
    )
    return (
        f"- {label}: `{target['metric']}` {target['direction']} "
        f"{target['target']}{currency} → **{target['status']}**{observed}"
    )


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
                f"- Evaluation horizon: {observation['evaluation_after_days']} day(s)",
                f"- Observation status: **{observation['observation_status']}**",
                _target_line("Audience target", observation["audience_target"]),
                _target_line("Commercial target", observation["commercial_target"]),
            ]
        )
        if observation["content_id"]:
            lines.append(f"- Content ID: `{observation['content_id']}`")
        else:
            lines.append("- Content ID: not assigned; publication remains a human/manual step.")
        if observation["published_at"]:
            lines.append(f"- Published at: {observation['published_at']}")
        if observation["observed_at"]:
            lines.append(f"- Observed at: {observation['observed_at']}")
        if observation["evaluation_due_at"]:
            lines.append(f"- Evaluation due at: {observation['evaluation_due_at']}")
        lines.extend(
            [
                "",
                "Interpretation: compare each observation with its pre-declared target only. "
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
