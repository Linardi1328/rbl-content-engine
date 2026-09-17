from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .baselines import MIN_BASELINE_SAMPLES, analyze_experiments
from .experiments import ExperimentRegistry
from .models import RevenueManifest
from .planning import build_planning_bridge
from .reporting import build_outputs

PHASE_2_VERSION = "RBL_PHASE_2_V1"


def _json_text(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _metric_relations(entry: dict[str, Any]) -> str:
    comparison = entry.get("prior_baseline_comparison") or {}
    if comparison.get("status") != "AVAILABLE":
        return "No mature prior baseline yet."
    relations = comparison.get("metrics", {})
    if not relations:
        return "Prior baseline exists, but no comparable optional metrics met the sample rule."
    selected = []
    for metric in ("views", "watch_time_minutes", "leads_per_1000_views", "clicks_per_1000_views"):
        item = relations.get(metric)
        if item:
            selected.append(f"{metric}: {item['relation']}")
    return "; ".join(selected) if selected else "Comparable metric relations are available in JSON."


def _ledger_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# RBL Experiment Ledger",
        "",
        f"Baseline policy: `{analysis['baseline_version']}` · minimum samples: {analysis['minimum_baseline_samples']}",
        "",
        analysis["disclaimer"],
        "",
        "| Experiment | Platform / format | Horizon | Status | Prior baseline |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for entry in analysis["ledger"]:
        prior = entry.get("prior_baseline")
        prior_status = prior["status"] if prior else "N/A"
        lines.append(
            f"| {entry['experiment_id']} | {entry['platform']} / {entry['format']} | "
            f"{entry['evaluation_after_days']}d | {entry['observation_status']} | {prior_status} |"
        )
    lines.extend(["", "## Historical observations", ""])
    for entry in analysis["ledger"]:
        lines.extend(
            [
                f"### {entry['experiment_id']}",
                "",
                f"- Content ID: `{entry['content_id']}`",
                f"- Cohort: `{entry['cohort_key']}`",
                f"- Design: {', '.join(entry['topic_tags'])} · {entry['archetype']} · {entry['hook_type']} · {entry['cta_type']}",
                f"- Primary variable: `{entry['primary_variable']}`",
                f"- Observation status: **{entry['observation_status']}**",
                f"- Prior-baseline context: {_metric_relations(entry)}",
                f"- Human note: {entry['note']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _baseline_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# RBL Creator Baseline Report",
        "",
        analysis["disclaimer"],
        "",
        f"Minimum mature samples per baseline metric: **{analysis['minimum_baseline_samples']}**",
        "",
        "| Cohort | Mature samples | Status | Metrics available |",
        "| --- | ---: | --- | ---: |",
    ]
    for baseline in analysis["cohort_baselines"]:
        lines.append(
            f"| `{baseline['cohort_key']}` | {baseline['sample_size']} | {baseline['status']} | {len(baseline['metrics'])} |"
        )
    lines.extend(["", "## Cohort detail", ""])
    for baseline in analysis["cohort_baselines"]:
        lines.extend(
            [
                f"### {baseline['cohort_key']}",
                "",
                f"Status: **{baseline['status']}** · mature samples: {baseline['sample_size']}",
                "",
            ]
        )
        for metric, stats in baseline["metrics"].items():
            lines.append(
                f"- `{metric}`: median {stats['median']} (n={stats['sample_size']}, range {stats['minimum']}–{stats['maximum']})"
            )
        for currency, values in baseline["revenue_by_currency"].items():
            stats = values["revenue"]
            lines.append(
                f"- `revenue` {currency}: median {stats['median']} (n={stats['sample_size']})"
            )
            if "revenue_per_1000_views" in values:
                rate = values["revenue_per_1000_views"]
                lines.append(
                    f"- `revenue_per_1000_views` {currency}: median {rate['median']} (n={rate['sample_size']})"
                )
        if not baseline["metrics"] and not baseline["revenue_by_currency"]:
            lines.append("- No metric has enough mature samples yet.")
        lines.append("")
    lines.extend(["## Declared comparison groups", ""])
    if not analysis["comparison_groups"]:
        lines.append("No controlled comparison groups are declared.")
    for group in analysis["comparison_groups"]:
        lines.extend(
            [
                f"### {group['comparison_group']}",
                "",
                f"- Primary variable: `{group['primary_variable']}`",
                f"- Mature members: {group['mature_member_count']}/{group['member_count']}",
                f"- Interpretation: {group['interpretation']}",
            ]
        )
        for member in group["members"]:
            lines.append(
                f"- {member['variant_label']}: {member['primary_variable_value']} · {member['observation_status']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _planning_markdown(planning: dict[str, Any]) -> str:
    lines = [
        "# RBL Phase 2 Planning Bridge",
        "",
        f"Decision status: **{planning['decision_status']}**",
        "",
        planning["disclaimer"],
        "",
        "| Rank | Opportunity | Score | Design | Baseline | References |",
        "| ---: | --- | ---: | --- | --- | ---: |",
    ]
    for item in planning["opportunities"]:
        lines.append(
            f"| {item['rank']} | {item['topic']} | {item['opportunity_score']:.2f} | "
            f"{item['design_status']} | {item['cohort_baseline']['status']} | {len(item['reference_candidates'])} |"
        )
    lines.extend(["", "## Human decision context", ""])
    for item in planning["opportunities"]:
        lines.extend(
            [
                f"### {item['rank']}. {item['topic']}",
                "",
                f"- Opportunity score: {item['opportunity_score']:.2f} (`{item['scoring_version']}`)",
                f"- Platform / format: {item['platform']} / {item['format']}",
                f"- Cohort baseline: **{item['cohort_baseline']['status']}** from {item['cohort_baseline']['sample_size']} mature item(s)",
                f"- Test readiness: **{item['test_readiness']}**",
                f"- Automatic score adjustment: `{item['automatic_score_adjustment']}`",
                f"- Decision status: **{item['decision_status']}**",
            ]
        )
        design = item["experiment_design"]
        if design:
            lines.extend(
                [
                    f"- Topic tags: {', '.join(design['topic_tags'])}",
                    f"- Archetype: {design['archetype']}",
                    f"- Hook type: {design['hook_type']}",
                    f"- CTA type: {design['cta_type']}",
                    f"- Primary variable: `{design['primary_variable']}`",
                ]
            )
        for note in item["learning_notes"]:
            lines.append(f"- Note: {note}")
        if item["reference_candidates"]:
            lines.append("- Historical reference candidates:")
            for reference in item["reference_candidates"]:
                lines.append(
                    f"  - `{reference['experiment_id']}`: {reference['historical_value']} → current {reference['current_value']}"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_phase2_outputs(
    manifest: RevenueManifest,
    current_analytics: dict[str, dict[str, Any]] | None,
    registry: ExperimentRegistry,
    history_analytics: dict[str, dict[str, Any]],
    *,
    input_paths: dict[str, str | None] | None = None,
) -> dict[str, str]:
    outputs = dict(build_outputs(manifest, current_analytics))
    analysis = analyze_experiments(
        registry,
        history_analytics,
        minimum_samples=MIN_BASELINE_SAMPLES,
    )
    planning = build_planning_bridge(manifest, registry, analysis)
    phase_run = {
        "phase_version": PHASE_2_VERSION,
        "baseline_version": analysis["baseline_version"],
        "planning_version": planning["planning_version"],
        "experiment_registry_version": registry.version,
        "opportunity_manifest_version": manifest.version,
        "minimum_baseline_samples": analysis["minimum_baseline_samples"],
        "inputs": input_paths or {},
        "counts": {
            "opportunities": len(manifest.opportunities),
            "experiments": len(registry.experiments),
            "evaluated_experiments": sum(
                1 for entry in analysis["ledger"] if entry["observation_status"] == "EVALUATED"
            ),
            "pending_experiments": sum(
                1 for entry in analysis["ledger"] if entry["observation_status"] == "WINDOW_PENDING"
            ),
            "experiments_without_data": sum(
                1 for entry in analysis["ledger"] if entry["observation_status"] == "NO_MATCHING_DATA"
            ),
            "available_cohort_baselines": sum(
                1 for baseline in analysis["cohort_baselines"] if baseline["status"] == "AVAILABLE"
            ),
            "comparison_groups": len(analysis["comparison_groups"]),
        },
        "decision_status": "PENDING_HUMAN",
        "disclaimer": (
            "Phase 2 produces descriptive decision context only. It does not establish causality, "
            "forecast performance, publish content, or authorize automatic strategy changes."
        ),
    }
    outputs.update(
        {
            "experiment-ledger.json": _json_text(
                {
                    "baseline_version": analysis["baseline_version"],
                    "experiment_registry_version": analysis["experiment_registry_version"],
                    "minimum_baseline_samples": analysis["minimum_baseline_samples"],
                    "disclaimer": analysis["disclaimer"],
                    "ledger": analysis["ledger"],
                    "comparison_groups": analysis["comparison_groups"],
                }
            ),
            "experiment-ledger.md": _ledger_markdown(analysis),
            "baseline-report.json": _json_text(
                {
                    "baseline_version": analysis["baseline_version"],
                    "minimum_baseline_samples": analysis["minimum_baseline_samples"],
                    "disclaimer": analysis["disclaimer"],
                    "cohort_baselines": analysis["cohort_baselines"],
                    "comparison_groups": analysis["comparison_groups"],
                }
            ),
            "baseline-report.md": _baseline_markdown(analysis),
            "planning-bridge.json": _json_text(planning),
            "planning-bridge.md": _planning_markdown(planning),
            "phase-2-run.json": _json_text(phase_run),
        }
    )
    return outputs


def write_phase2_outputs(
    output_dir: str | Path,
    manifest: RevenueManifest,
    current_analytics: dict[str, dict[str, Any]] | None,
    registry: ExperimentRegistry,
    history_analytics: dict[str, dict[str, Any]],
    *,
    input_paths: dict[str, str | None] | None = None,
) -> tuple[Path, ...]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    outputs = build_phase2_outputs(
        manifest,
        current_analytics,
        registry,
        history_analytics,
        input_paths=input_paths,
    )
    written: list[Path] = []
    for filename, content in outputs.items():
        path = destination / filename
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return tuple(written)
