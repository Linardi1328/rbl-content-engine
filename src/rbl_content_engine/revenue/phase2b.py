from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
import sys
from typing import Any

from .analytics import load_analytics
from .models import ManifestError, MONETIZATION_ROUTES, NUMERIC_ANALYTICS_FIELDS

VERSION = "RBL_EXPERIMENT_BASELINE_V1"
MIN_BASELINE_SAMPLE = 3
TREATMENT_FIELDS = (
    "topic",
    "hook_type",
    "archetype",
    "title_variant",
    "thumbnail_concept",
    "cta",
)
BASELINE_METRICS = tuple(sorted(NUMERIC_ANALYTICS_FIELDS))


@dataclass(frozen=True)
class Experiment:
    id: str
    content_id: str
    platform: str
    format: str
    evaluation_after_days: int
    treatment: dict[str, Any]
    metrics: tuple[str, ...]


@dataclass(frozen=True)
class ExperimentManifest:
    version: str
    experiments: tuple[Experiment, ...]


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{field} must be a non-empty string.")
    return value.strip()


def _integer(value: Any, field: str, minimum: int = 0, maximum: int = 365) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ManifestError(f"{field} must be an integer from {minimum} to {maximum}.")
    return value


def load_experiments(path: str | Path) -> ExperimentManifest:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Unable to read experiment manifest: {exc}") from exc
    if data.get("version") != VERSION:
        raise ManifestError(f"version must be {VERSION}.")
    raw = data.get("experiments")
    if not isinstance(raw, list) or not raw:
        raise ManifestError("experiments must be a non-empty array.")
    seen_ids: set[str] = set()
    seen_content: set[str] = set()
    experiments: list[Experiment] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ManifestError(f"experiments[{index}] must be an object.")
        experiment_id = _nonempty(item.get("id"), f"experiments[{index}].id")
        content_id = _nonempty(item.get("content_id"), f"{experiment_id}.content_id")
        if experiment_id in seen_ids:
            raise ManifestError(f"Duplicate experiment id: {experiment_id}")
        if content_id in seen_content:
            raise ManifestError(f"Duplicate experiment content_id: {content_id}")
        seen_ids.add(experiment_id)
        seen_content.add(content_id)
        treatment = item.get("treatment")
        if not isinstance(treatment, dict):
            raise ManifestError(f"{experiment_id}.treatment is required.")
        normalized_treatment = {
            field: _nonempty(treatment.get(field), f"{experiment_id}.treatment.{field}")
            for field in TREATMENT_FIELDS
        }
        routes = treatment.get("monetization_routes")
        if not isinstance(routes, list) or not routes:
            raise ManifestError(f"{experiment_id}.treatment.monetization_routes is required.")
        normalized_routes = tuple(_nonempty(route, f"{experiment_id}.treatment.monetization_routes") for route in routes)
        unknown = [route for route in normalized_routes if route not in MONETIZATION_ROUTES]
        if unknown:
            raise ManifestError(f"{experiment_id} has unknown monetization route(s): {', '.join(unknown)}")
        normalized_treatment["monetization_routes"] = list(normalized_routes)
        metrics = item.get("metrics")
        if not isinstance(metrics, list) or not metrics:
            raise ManifestError(f"{experiment_id}.metrics is required.")
        normalized_metrics = tuple(_nonempty(metric, f"{experiment_id}.metrics") for metric in metrics)
        unsupported = [metric for metric in normalized_metrics if metric not in NUMERIC_ANALYTICS_FIELDS]
        if unsupported:
            raise ManifestError(f"{experiment_id} has unsupported metric(s): {', '.join(unsupported)}")
        if len(set(normalized_metrics)) != len(normalized_metrics):
            raise ManifestError(f"{experiment_id}.metrics must be unique.")
        experiments.append(
            Experiment(
                id=experiment_id,
                content_id=content_id,
                platform=_nonempty(item.get("platform"), f"{experiment_id}.platform"),
                format=_nonempty(item.get("format"), f"{experiment_id}.format"),
                evaluation_after_days=_integer(item.get("evaluation_after_days"), f"{experiment_id}.evaluation_after_days"),
                treatment=normalized_treatment,
                metrics=normalized_metrics,
            )
        )
    return ExperimentManifest(version=VERSION, experiments=tuple(experiments))


def _parse_datetime(value: str, field: str) -> datetime:
    text = value.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ManifestError(f"{field} must be an ISO datetime.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManifestError(f"{field} must include a timezone offset.")
    return parsed


def _parse_metric(value: str, field: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        result = float(text)
    except ValueError as exc:
        raise ManifestError(f"{field} must be numeric.") from exc
    if result < 0:
        raise ManifestError(f"{field} must be non-negative.")
    return result


def load_history(path: str | Path) -> list[dict[str, Any]]:
    required = {
        "content_id",
        "platform",
        "format",
        "published_at",
        "observed_at",
        "evaluation_after_days",
        "views",
        "hook_type",
        "archetype",
        "cta",
    }
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ManifestError("History CSV has no header row.")
            missing = sorted(required - set(reader.fieldnames))
            if missing:
                raise ManifestError(f"History CSV missing required field(s): {', '.join(missing)}")
            rows = list(reader)
    except OSError as exc:
        raise ManifestError(f"Unable to read history CSV: {exc}") from exc
    if not rows:
        raise ManifestError("History CSV contains no data rows.")
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for line, row in enumerate(rows, start=2):
        content_id = _nonempty(row.get("content_id"), f"history line {line} content_id")
        if content_id in seen:
            raise ManifestError(f"History CSV has duplicate content_id: {content_id}")
        seen.add(content_id)
        published = _parse_datetime(row["published_at"], f"history line {line} published_at")
        observed = _parse_datetime(row["observed_at"], f"history line {line} observed_at")
        if observed < published:
            raise ManifestError(f"history line {line} observed_at cannot precede published_at.")
        try:
            window = int(row["evaluation_after_days"])
        except ValueError as exc:
            raise ManifestError(f"history line {line} evaluation_after_days must be an integer.") from exc
        _integer(window, f"history line {line} evaluation_after_days")
        if observed < published + timedelta(days=window):
            raise ManifestError(f"history line {line} is not mature for its declared evaluation window.")
        record: dict[str, Any] = {
            "content_id": content_id,
            "platform": _nonempty(row.get("platform"), f"history line {line} platform"),
            "format": _nonempty(row.get("format"), f"history line {line} format"),
            "published_at": row["published_at"].strip(),
            "observed_at": row["observed_at"].strip(),
            "evaluation_after_days": window,
            "hook_type": _nonempty(row.get("hook_type"), f"history line {line} hook_type"),
            "archetype": _nonempty(row.get("archetype"), f"history line {line} archetype"),
            "cta": _nonempty(row.get("cta"), f"history line {line} cta"),
        }
        for metric in BASELINE_METRICS:
            if metric in row:
                record[metric] = _parse_metric(row.get(metric, ""), f"history line {line} {metric}")
        output.append(record)
    return output


def _metric_baseline(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    values = [float(row[metric]) for row in rows if row.get(metric) is not None]
    if len(values) < MIN_BASELINE_SAMPLE:
        return {"status": "INSUFFICIENT_BASELINE", "sample_size": len(values), "median": None}
    return {"status": "READY", "sample_size": len(values), "median": round(float(median(values)), 6)}


def _comparison(observed: float | int | None, baseline: dict[str, Any]) -> dict[str, Any]:
    if observed is None:
        return {**baseline, "observed": None, "comparison": "NO_OBSERVATION", "delta": None, "ratio": None}
    if baseline["status"] != "READY":
        return {**baseline, "observed": observed, "comparison": "INSUFFICIENT_BASELINE", "delta": None, "ratio": None}
    base = float(baseline["median"])
    value = float(observed)
    delta = value - base
    comparison = "ABOVE_BASELINE" if delta > 0 else "BELOW_BASELINE" if delta < 0 else "AT_BASELINE"
    ratio = None if base == 0 else round(value / base, 6)
    return {**baseline, "observed": observed, "comparison": comparison, "delta": round(delta, 6), "ratio": ratio}


def analyze(manifest: ExperimentManifest, analytics: dict[str, dict[str, Any]], history: list[dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for experiment in manifest.experiments:
        observed = analytics.get(experiment.content_id)
        if observed is None:
            results.append({
                "experiment": asdict(experiment),
                "status": "NO_MATCHING_DATA",
                "baseline_cohort": None,
                "metric_comparisons": {},
                "treatment_context": {},
            })
            continue
        if str(observed.get("platform", "")).lower() != experiment.platform.lower():
            raise ManifestError(f"{experiment.id}: analytics platform does not match experiment platform.")
        published = _parse_datetime(str(observed["published_at"]), f"{experiment.id} published_at")
        observed_at = _parse_datetime(str(observed["observed_at"]), f"{experiment.id} observed_at")
        due = published + timedelta(days=experiment.evaluation_after_days)
        if observed_at < due:
            status = "WINDOW_PENDING"
        else:
            status = "EVALUATED"
        cohort = [
            row for row in history
            if row["content_id"] != experiment.content_id
            and row["platform"].lower() == experiment.platform.lower()
            and row["format"].lower() == experiment.format.lower()
            and row["evaluation_after_days"] == experiment.evaluation_after_days
        ]
        metric_comparisons = {
            metric: _comparison(observed.get(metric) if status == "EVALUATED" else None, _metric_baseline(cohort, metric))
            for metric in experiment.metrics
        }
        context: dict[str, Any] = {}
        for dimension in ("hook_type", "archetype", "cta"):
            value = experiment.treatment[dimension]
            matched = [row for row in cohort if row[dimension].lower() == str(value).lower()]
            context[dimension] = {
                "value": value,
                "sample_size": len(matched),
                "metric_medians": {
                    metric: _metric_baseline(matched, metric) for metric in experiment.metrics
                },
            }
        results.append({
            "experiment": asdict(experiment),
            "status": status,
            "published_at": observed["published_at"],
            "observed_at": observed["observed_at"],
            "evaluation_due_at": due.isoformat(),
            "baseline_cohort": {
                "platform": experiment.platform,
                "format": experiment.format,
                "evaluation_after_days": experiment.evaluation_after_days,
                "sample_size": len(cohort),
            },
            "metric_comparisons": metric_comparisons,
            "treatment_context": context,
        })
    return {
        "version": VERSION,
        "baseline_policy": {
            "method": "median",
            "minimum_sample": MIN_BASELINE_SAMPLE,
            "cohort_keys": ["platform", "format", "evaluation_after_days"],
        },
        "disclaimer": "Historical comparisons are descriptive observations, not causal attribution, forecasts, or guarantees.",
        "experiments": results,
    }


def markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# RBL Phase 2B Experiment & Baseline Report",
        "",
        payload["disclaimer"],
        "",
        f"Baseline policy: median; minimum sample {payload['baseline_policy']['minimum_sample']}; matched by platform / format / evaluation window.",
        "",
    ]
    for item in payload["experiments"]:
        exp = item["experiment"]
        lines.extend([
            f"## {exp['id']} — {exp['treatment']['topic']}",
            "",
            f"- Content ID: `{exp['content_id']}`",
            f"- Platform / format: {exp['platform']} / {exp['format']}",
            f"- Status: **{item['status']}**",
            f"- Hook type: {exp['treatment']['hook_type']}",
            f"- Archetype: {exp['treatment']['archetype']}",
            f"- CTA: {exp['treatment']['cta']}",
            f"- Monetization routes: {', '.join(exp['treatment']['monetization_routes'])}",
        ])
        cohort = item.get("baseline_cohort")
        if cohort:
            lines.append(f"- Baseline cohort: n={cohort['sample_size']} at {cohort['evaluation_after_days']}-day window")
        lines.extend(["", "### Metric comparisons", ""])
        if not item["metric_comparisons"]:
            lines.append("No mature matching analytics are available.")
        else:
            lines.append("| Metric | Observed | Median baseline | n | Comparison |")
            lines.append("| --- | ---: | ---: | ---: | --- |")
            for metric, result in item["metric_comparisons"].items():
                lines.append(
                    f"| {metric} | {result['observed'] if result['observed'] is not None else '—'} | "
                    f"{result['median'] if result['median'] is not None else '—'} | {result['sample_size']} | {result['comparison']} |"
                )
        lines.extend([
            "",
            "Interpretation: use these comparisons to form the next human hypothesis. Do not claim that any hook, archetype, CTA, platform, or route caused the observed result.",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(output_dir: str | Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "experiment-baselines.json"
    md_path = destination / "experiment-baselines.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(markdown_report(payload), encoding="utf-8")
    return json_path, md_path


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Offline RBL Phase 2B experiment and baseline intelligence.")
    p.add_argument("manifest", help="Experiment manifest JSON path")
    p.add_argument("--analytics", required=True, help="Current manually exported first-party analytics CSV")
    p.add_argument("--history", required=True, help="Historical first-party baseline CSV")
    p.add_argument("--output", required=True, help="Output directory")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        manifest = load_experiments(args.manifest)
        analytics = load_analytics(args.analytics)
        history = load_history(args.history)
        payload = analyze(manifest, analytics, history)
        written = write_outputs(args.output, payload)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
