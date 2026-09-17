from __future__ import annotations

from typing import Any

from .baselines import cohort_key
from .experiments import ExperimentRecord, ExperimentRegistry
from .models import ExperimentDesign, Opportunity, RevenueManifest
from .scoring import rank_opportunities

PLANNING_VERSION = "RBL_PLANNING_BRIDGE_V1"


def _tags_equal(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    return {tag.casefold() for tag in left} == {tag.casefold() for tag in right}


def _tags_overlap(left: tuple[str, ...], right: list[str] | tuple[str, ...]) -> bool:
    return bool({tag.casefold() for tag in left} & {tag.casefold() for tag in right})


def _design_dict(design: ExperimentDesign | None) -> dict[str, Any] | None:
    if design is None:
        return None
    return {
        "topic_tags": list(design.topic_tags),
        "archetype": design.archetype,
        "hook_type": design.hook_type,
        "cta_type": design.cta_type,
        "primary_variable": design.primary_variable,
    }


def _matches_except_primary(
    opportunity: Opportunity,
    design: ExperimentDesign,
    record: ExperimentRecord,
) -> bool:
    if record.platform.casefold() != opportunity.platform.casefold():
        return False
    if record.evaluation_after_days != opportunity.hypothesis.evaluation_after_days:
        return False

    dimensions = {
        "topic_tags": _tags_equal(design.topic_tags, record.topic_tags),
        "archetype": design.archetype.casefold() == record.archetype.casefold(),
        "hook_type": design.hook_type.casefold() == record.hook_type.casefold(),
        "format": opportunity.format.casefold() == record.format.casefold(),
        "cta_type": design.cta_type.casefold() == record.cta_type.casefold(),
    }
    for field, matches in dimensions.items():
        if field == design.primary_variable:
            continue
        if not matches:
            return False
    return not dimensions[design.primary_variable]


def _mature_records(
    registry: ExperimentRegistry, analysis: dict[str, Any]
) -> list[tuple[ExperimentRecord, dict[str, Any]]]:
    record_by_id = {record.id: record for record in registry.experiments}
    output: list[tuple[ExperimentRecord, dict[str, Any]]] = []
    for entry in analysis["ledger"]:
        if entry["observation_status"] != "EVALUATED":
            continue
        output.append((record_by_id[entry["experiment_id"]], entry))
    return output


def _cohort_baseline_map(analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        baseline["cohort_key"]: baseline
        for baseline in analysis["cohort_baselines"]
    }


def build_planning_bridge(
    manifest: RevenueManifest,
    registry: ExperimentRegistry,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    ranked = rank_opportunities(manifest.opportunities)
    ranked_by_id = {item.id: item for item in ranked}
    mature = _mature_records(registry, analysis)
    baseline_map = _cohort_baseline_map(analysis)
    opportunities: list[dict[str, Any]] = []

    for opportunity in manifest.opportunities:
        ranked_item = ranked_by_id[opportunity.id]
        design = opportunity.experiment_design
        key = cohort_key(
            opportunity.platform,
            opportunity.format,
            opportunity.hypothesis.evaluation_after_days,
        )
        cohort_history = [
            (record, entry)
            for record, entry in mature
            if entry["cohort_key"] == key
        ]
        baseline = baseline_map.get(
            key,
            {
                "cohort_key": key,
                "status": "INSUFFICIENT_HISTORY",
                "sample_size": len(cohort_history),
                "minimum_samples": analysis["minimum_baseline_samples"],
                "metrics": {},
                "revenue_by_currency": {},
            },
        )

        item: dict[str, Any] = {
            "opportunity_id": opportunity.id,
            "rank": ranked_item.rank,
            "topic": opportunity.topic,
            "platform": opportunity.platform,
            "format": opportunity.format,
            "opportunity_score": ranked_item.final_score,
            "scoring_version": ranked_item.scoring_version,
            "monetization_routes": list(opportunity.monetization_routes),
            "evaluation_after_days": opportunity.hypothesis.evaluation_after_days,
            "experiment_design": _design_dict(design),
            "design_status": "READY" if design is not None else "MISSING_DESIGN",
            "cohort_key": key,
            "cohort_baseline": baseline,
            "history_counts": {
                "mature_cohort": len(cohort_history),
                "same_topic_overlap": 0,
                "same_archetype": 0,
                "same_hook_type": 0,
                "same_cta_type": 0,
                "exact_signature": 0,
            },
            "reference_candidates": [],
            "test_readiness": "MISSING_DESIGN" if design is None else "NO_REFERENCE",
            "learning_notes": [],
            "automatic_score_adjustment": None,
            "decision_status": "PENDING_HUMAN",
        }

        if design is None:
            item["learning_notes"] = [
                "No experiment_design is declared. Phase 2 will not guess topic tags, archetype, hook type, CTA type, or the intended test variable.",
                "The Phase 2A opportunity score remains unchanged.",
            ]
            opportunities.append(item)
            continue

        same_topic = [
            record
            for record, _ in cohort_history
            if _tags_overlap(design.topic_tags, record.topic_tags)
        ]
        same_archetype = [
            record
            for record, _ in cohort_history
            if design.archetype.casefold() == record.archetype.casefold()
        ]
        same_hook = [
            record
            for record, _ in cohort_history
            if design.hook_type.casefold() == record.hook_type.casefold()
        ]
        same_cta = [
            record
            for record, _ in cohort_history
            if design.cta_type.casefold() == record.cta_type.casefold()
        ]
        exact = [
            record
            for record, _ in cohort_history
            if _tags_equal(design.topic_tags, record.topic_tags)
            and design.archetype.casefold() == record.archetype.casefold()
            and design.hook_type.casefold() == record.hook_type.casefold()
            and design.cta_type.casefold() == record.cta_type.casefold()
        ]
        item["history_counts"] = {
            "mature_cohort": len(cohort_history),
            "same_topic_overlap": len(same_topic),
            "same_archetype": len(same_archetype),
            "same_hook_type": len(same_hook),
            "same_cta_type": len(same_cta),
            "exact_signature": len(exact),
        }

        references = [
            {
                "experiment_id": record.id,
                "content_id": record.content_id,
                "published_at": entry["published_at"],
                "primary_variable": design.primary_variable,
                "historical_value": (
                    list(record.topic_tags)
                    if design.primary_variable == "topic_tags"
                    else getattr(record, design.primary_variable)
                ),
                "current_value": (
                    list(design.topic_tags)
                    if design.primary_variable == "topic_tags"
                    else (
                        opportunity.format
                        if design.primary_variable == "format"
                        else getattr(design, design.primary_variable)
                    )
                ),
            }
            for record, entry in mature
            if _matches_except_primary(opportunity, design, record)
        ]
        references.sort(key=lambda value: (value["published_at"] or "", value["experiment_id"]))
        item["reference_candidates"] = references
        item["test_readiness"] = (
            "REFERENCE_AVAILABLE" if references else "NO_REFERENCE"
        )

        baseline_status = baseline["status"]
        item["learning_notes"] = [
            (
                f"Cohort baseline is available from {baseline['sample_size']} mature historical item(s)."
                if baseline_status == "AVAILABLE"
                else f"Cohort baseline is not yet available: {baseline['sample_size']} mature item(s), "
                f"minimum {baseline['minimum_samples']}."
            ),
            f"Same-hook mature history: {len(same_hook)} item(s); same-archetype history: {len(same_archetype)} item(s).",
            (
                f"{len(references)} historical reference candidate(s) match every declared dimension except {design.primary_variable}."
                if references
                else f"No mature historical item matches every declared dimension except {design.primary_variable}."
            ),
            "Historical context does not change the Phase 2A score automatically. Any rescore requires a human edit and new rationale.",
        ]
        opportunities.append(item)

    opportunities.sort(key=lambda item: item["rank"])
    return {
        "planning_version": PLANNING_VERSION,
        "baseline_version": analysis["baseline_version"],
        "scoring_version": ranked[0].scoring_version if ranked else None,
        "research_snapshot": {
            "path": manifest.research_snapshot.path,
            "research_date": manifest.research_snapshot.research_date,
        },
        "disclaimer": (
            "Historical observations and baseline relations are descriptive decision context. "
            "They do not establish causality, forecast performance, or authorize automatic strategy changes."
        ),
        "opportunities": opportunities,
        "decision_status": "PENDING_HUMAN",
    }
