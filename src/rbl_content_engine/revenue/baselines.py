from __future__ import annotations

from datetime import timedelta
from statistics import median
from typing import Any

from .analytics import parse_timestamp
from .experiments import ExperimentRecord, ExperimentRegistry
from .models import ManifestError, NUMERIC_ANALYTICS_FIELDS

BASELINE_VERSION = "RBL_CREATOR_BASELINE_V1"
MIN_BASELINE_SAMPLES = 3

DERIVED_METRICS = (
    "watch_minutes_per_1000_views",
    "engagements_per_1000_views",
    "subscribers_per_1000_views",
    "clicks_per_1000_views",
    "leads_per_1000_views",
    "sales_per_1000_views",
)


def cohort_key(platform: str, format_name: str, evaluation_after_days: int) -> str:
    return f"{platform.casefold()}|{format_name.casefold()}|{evaluation_after_days}d"


def _safe_rate(numerator: Any, views: Any) -> float | None:
    if not isinstance(numerator, (int, float)) or not isinstance(views, (int, float)):
        return None
    if views <= 0:
        return None
    return round(float(numerator) / float(views) * 1000.0, 6)


def metric_snapshot(metrics: dict[str, Any]) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for field in sorted(NUMERIC_ANALYTICS_FIELDS - {"revenue"}):
        value = metrics.get(field)
        if isinstance(value, (int, float)):
            snapshot[field] = float(value)

    views = metrics.get("views")
    derived = {
        "watch_minutes_per_1000_views": _safe_rate(
            metrics.get("watch_time_minutes"), views
        ),
        "engagements_per_1000_views": _safe_rate(
            sum(
                float(metrics.get(field) or 0)
                for field in ("likes", "comments", "shares")
            )
            if any(metrics.get(field) is not None for field in ("likes", "comments", "shares"))
            else None,
            views,
        ),
        "subscribers_per_1000_views": _safe_rate(
            metrics.get("subscribers_gained"), views
        ),
        "clicks_per_1000_views": _safe_rate(metrics.get("clicks"), views),
        "leads_per_1000_views": _safe_rate(metrics.get("leads"), views),
        "sales_per_1000_views": _safe_rate(metrics.get("sales"), views),
    }
    for field, value in derived.items():
        if value is not None:
            snapshot[field] = value
    return snapshot


def _stat(values: list[float]) -> dict[str, float | int]:
    return {
        "sample_size": len(values),
        "median": round(float(median(values)), 6),
        "minimum": round(float(min(values)), 6),
        "maximum": round(float(max(values)), 6),
    }


def _baseline(
    entries: list[dict[str, Any]], *, minimum_samples: int = MIN_BASELINE_SAMPLES
) -> dict[str, Any]:
    baseline: dict[str, Any] = {
        "status": "AVAILABLE" if len(entries) >= minimum_samples else "INSUFFICIENT_HISTORY",
        "sample_size": len(entries),
        "minimum_samples": minimum_samples,
        "metrics": {},
        "revenue_by_currency": {},
    }
    if len(entries) < minimum_samples:
        return baseline

    metric_names = sorted(
        (NUMERIC_ANALYTICS_FIELDS - {"revenue"}) | set(DERIVED_METRICS)
    )
    snapshots = [metric_snapshot(entry["observed_metrics"]) for entry in entries]
    for metric in metric_names:
        values = [snapshot[metric] for snapshot in snapshots if metric in snapshot]
        if len(values) >= minimum_samples:
            baseline["metrics"][metric] = _stat(values)

    revenue_groups: dict[str, list[float]] = {}
    revenue_rate_groups: dict[str, list[float]] = {}
    for entry in entries:
        metrics = entry["observed_metrics"]
        revenue = metrics.get("revenue")
        currency = metrics.get("currency")
        if not isinstance(revenue, (int, float)) or not currency:
            continue
        code = str(currency).upper()
        revenue_groups.setdefault(code, []).append(float(revenue))
        rate = _safe_rate(revenue, metrics.get("views"))
        if rate is not None:
            revenue_rate_groups.setdefault(code, []).append(rate)
    for currency in sorted(revenue_groups):
        values = revenue_groups[currency]
        rates = revenue_rate_groups.get(currency, [])
        if len(values) < minimum_samples:
            continue
        item: dict[str, Any] = {"revenue": _stat(values)}
        if len(rates) >= minimum_samples:
            item["revenue_per_1000_views"] = _stat(rates)
        baseline["revenue_by_currency"][currency] = item
    return baseline


def _relation(value: float, baseline_value: float) -> str:
    if abs(value - baseline_value) <= 1e-9:
        return "AT_BASELINE"
    return "ABOVE_BASELINE" if value > baseline_value else "BELOW_BASELINE"


def _comparison(
    metrics: dict[str, Any], baseline: dict[str, Any]
) -> dict[str, Any]:
    if baseline["status"] != "AVAILABLE":
        return {
            "status": "INSUFFICIENT_HISTORY",
            "metrics": {},
            "revenue": None,
        }
    snapshot = metric_snapshot(metrics)
    output: dict[str, Any] = {
        "status": "AVAILABLE",
        "metrics": {},
        "revenue": None,
    }
    for metric, stats in baseline["metrics"].items():
        if metric not in snapshot:
            continue
        observed = snapshot[metric]
        baseline_value = float(stats["median"])
        delta = observed - baseline_value
        output["metrics"][metric] = {
            "observed": round(observed, 6),
            "baseline_median": round(baseline_value, 6),
            "delta": round(delta, 6),
            "delta_percent": (
                None
                if baseline_value == 0
                else round(delta / baseline_value * 100.0, 6)
            ),
            "relation": _relation(observed, baseline_value),
        }

    revenue = metrics.get("revenue")
    currency = metrics.get("currency")
    if isinstance(revenue, (int, float)) and currency:
        group = baseline["revenue_by_currency"].get(str(currency).upper())
        if group:
            baseline_value = float(group["revenue"]["median"])
            delta = float(revenue) - baseline_value
            output["revenue"] = {
                "currency": str(currency).upper(),
                "observed": float(revenue),
                "baseline_median": baseline_value,
                "delta": round(delta, 6),
                "delta_percent": (
                    None
                    if baseline_value == 0
                    else round(delta / baseline_value * 100.0, 6)
                ),
                "relation": _relation(float(revenue), baseline_value),
            }
    return output


def _ledger_entry(
    record: ExperimentRecord, analytics: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "experiment_id": record.id,
        "content_id": record.content_id,
        "platform": record.platform,
        "format": record.format,
        "topic_tags": list(record.topic_tags),
        "archetype": record.archetype,
        "hook_type": record.hook_type,
        "cta_type": record.cta_type,
        "evaluation_after_days": record.evaluation_after_days,
        "primary_variable": record.primary_variable,
        "note": record.note,
        "comparison_group": record.comparison_group,
        "variant_label": record.variant_label,
        "cohort_key": cohort_key(
            record.platform, record.format, record.evaluation_after_days
        ),
        "observation_status": "NO_MATCHING_DATA",
        "published_at": None,
        "observed_at": None,
        "evaluation_due_at": None,
        "observed_metrics": None,
        "prior_baseline": None,
        "prior_baseline_comparison": None,
        "input_index": record.input_index,
    }
    metrics = analytics.get(record.content_id)
    if metrics is None:
        return item
    if str(metrics.get("platform", "")).casefold() != record.platform.casefold():
        raise ManifestError(
            f"Platform mismatch for historical content_id {record.content_id}: "
            f"registry is {record.platform}, analytics are {metrics.get('platform')}."
        )
    published_at = parse_timestamp(
        str(metrics["published_at"]), f"{record.content_id}.published_at"
    )
    observed_at = parse_timestamp(
        str(metrics["observed_at"]), f"{record.content_id}.observed_at"
    )
    due = published_at + timedelta(days=record.evaluation_after_days)
    status = "WINDOW_PENDING" if observed_at < due else "EVALUATED"
    item.update(
        {
            "observation_status": status,
            "published_at": published_at.isoformat(),
            "observed_at": observed_at.isoformat(),
            "evaluation_due_at": due.isoformat(),
            "observed_metrics": metrics,
        }
    )
    return item


def _published_sort_key(entry: dict[str, Any]) -> tuple[int, str, int]:
    if entry["published_at"] is None:
        return (1, "", int(entry["input_index"]))
    return (0, str(entry["published_at"]), int(entry["input_index"]))


def _comparison_groups(
    registry: ExperimentRegistry, ledger: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {entry["experiment_id"]: entry for entry in ledger}
    group_names: list[str] = []
    for record in registry.experiments:
        if record.comparison_group and record.comparison_group not in group_names:
            group_names.append(record.comparison_group)
    output: list[dict[str, Any]] = []
    for group_name in group_names:
        records = [
            record
            for record in registry.experiments
            if record.comparison_group == group_name
        ]
        members = []
        for record in records:
            entry = by_id[record.id]
            members.append(
                {
                    "experiment_id": record.id,
                    "variant_label": record.variant_label,
                    "primary_variable_value": (
                        list(record.topic_tags)
                        if record.primary_variable == "topic_tags"
                        else getattr(record, record.primary_variable)
                    ),
                    "observation_status": entry["observation_status"],
                    "published_at": entry["published_at"],
                    "observed_at": entry["observed_at"],
                    "observed_metrics": entry["observed_metrics"],
                }
            )
        output.append(
            {
                "comparison_group": group_name,
                "primary_variable": records[0].primary_variable,
                "member_count": len(members),
                "mature_member_count": sum(
                    1 for member in members if member["observation_status"] == "EVALUATED"
                ),
                "members": members,
                "interpretation": (
                    "Descriptive side-by-side observation only. No winner is selected and "
                    "the changed variable is not claimed to have caused any difference."
                ),
            }
        )
    return output


def analyze_experiments(
    registry: ExperimentRegistry,
    analytics: dict[str, dict[str, Any]],
    *,
    minimum_samples: int = MIN_BASELINE_SAMPLES,
) -> dict[str, Any]:
    ledger = [_ledger_entry(record, analytics) for record in registry.experiments]
    ledger.sort(key=_published_sort_key)

    evaluated = [entry for entry in ledger if entry["observation_status"] == "EVALUATED"]
    cohorts: dict[str, list[dict[str, Any]]] = {}
    for entry in evaluated:
        cohorts.setdefault(entry["cohort_key"], []).append(entry)

    cohort_baselines: dict[str, dict[str, Any]] = {}
    for key in sorted(cohorts):
        baseline = _baseline(cohorts[key], minimum_samples=minimum_samples)
        cohort_baselines[key] = {
            "cohort_key": key,
            **baseline,
        }

    for entry in ledger:
        if entry["observation_status"] != "EVALUATED":
            continue
        published_at = parse_timestamp(
            str(entry["published_at"]), f"{entry['content_id']}.published_at"
        )
        prior = [
            candidate
            for candidate in evaluated
            if candidate["cohort_key"] == entry["cohort_key"]
            and candidate["experiment_id"] != entry["experiment_id"]
            and parse_timestamp(
                str(candidate["published_at"]),
                f"{candidate['content_id']}.published_at",
            )
            < published_at
        ]
        baseline = _baseline(prior, minimum_samples=minimum_samples)
        entry["prior_baseline"] = baseline
        entry["prior_baseline_comparison"] = _comparison(
            entry["observed_metrics"], baseline
        )

    return {
        "baseline_version": BASELINE_VERSION,
        "experiment_registry_version": registry.version,
        "minimum_baseline_samples": minimum_samples,
        "disclaimer": (
            "Baselines and relations are descriptive first-party history, not forecasts, "
            "quality scores, or causal attribution."
        ),
        "ledger": ledger,
        "cohort_baselines": [cohort_baselines[key] for key in sorted(cohort_baselines)],
        "comparison_groups": _comparison_groups(registry, ledger),
    }
