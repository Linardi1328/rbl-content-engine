from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .models import EXPERIMENT_PRIMARY_VARIABLES, ManifestError

EXPERIMENT_REGISTRY_VERSION = "RBL_EXPERIMENT_REGISTRY_V1"


@dataclass(frozen=True)
class ExperimentRecord:
    id: str
    content_id: str
    platform: str
    format: str
    topic_tags: tuple[str, ...]
    archetype: str
    hook_type: str
    cta_type: str
    evaluation_after_days: int
    primary_variable: str
    note: str
    comparison_group: str | None = None
    variant_label: str | None = None
    input_index: int = 0


@dataclass(frozen=True)
class ExperimentRegistry:
    version: str
    experiments: tuple[ExperimentRecord, ...]


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{field} must be a non-empty string.")
    return value.strip()


def _days(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 365:
        raise ManifestError(f"{field} must be an integer from 0 to 365.")
    return value


def _tags(raw: Any, field: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise ManifestError(f"{field} must be a non-empty array.")
    values = tuple(_nonempty(value, field) for value in raw)
    if len({value.casefold() for value in values}) != len(values):
        raise ManifestError(f"{field} must be unique case-insensitively.")
    return values


def _variable_value(record: ExperimentRecord, variable: str) -> object:
    if variable == "topic_tags":
        return tuple(tag.casefold() for tag in record.topic_tags)
    return getattr(record, variable).casefold()


def _same_dimension(left: ExperimentRecord, right: ExperimentRecord, field: str) -> bool:
    if field == "topic_tags":
        return {tag.casefold() for tag in left.topic_tags} == {
            tag.casefold() for tag in right.topic_tags
        }
    return getattr(left, field).casefold() == getattr(right, field).casefold()


def _validate_comparison_groups(records: list[ExperimentRecord]) -> None:
    groups: dict[str, list[ExperimentRecord]] = {}
    for record in records:
        if record.comparison_group is None:
            continue
        groups.setdefault(record.comparison_group, []).append(record)

    dimensions = ("topic_tags", "archetype", "hook_type", "format", "cta_type")
    for group_name, members in groups.items():
        if len(members) < 2:
            raise ManifestError(
                f"comparison_group {group_name} must contain at least two experiments."
            )
        variables = {member.primary_variable for member in members}
        if len(variables) != 1:
            raise ManifestError(
                f"comparison_group {group_name} must use one shared primary_variable."
            )
        variable = next(iter(variables))
        platforms = {member.platform.casefold() for member in members}
        horizons = {member.evaluation_after_days for member in members}
        if len(platforms) != 1 or len(horizons) != 1:
            raise ManifestError(
                f"comparison_group {group_name} must keep platform and evaluation horizon constant."
            )
        labels = [member.variant_label for member in members]
        if any(label is None for label in labels):
            raise ManifestError(
                f"comparison_group {group_name} requires variant_label on every member."
            )
        if len({label.casefold() for label in labels if label is not None}) != len(labels):
            raise ManifestError(
                f"comparison_group {group_name} variant labels must be unique."
            )
        reference = members[0]
        for member in members[1:]:
            for dimension in dimensions:
                if dimension == variable:
                    continue
                if not _same_dimension(reference, member, dimension):
                    raise ManifestError(
                        f"comparison_group {group_name} changes {dimension} in addition to "
                        f"the declared primary variable {variable}."
                    )
        if len({_variable_value(member, variable) for member in members}) < 2:
            raise ManifestError(
                f"comparison_group {group_name} must contain at least two distinct values "
                f"for primary variable {variable}."
            )


def load_experiment_registry(path: str | Path) -> ExperimentRegistry:
    registry_path = Path(path)
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Unable to read experiment registry: {exc}") from exc

    if data.get("version") != EXPERIMENT_REGISTRY_VERSION:
        raise ManifestError(f"version must be {EXPERIMENT_REGISTRY_VERSION}.")
    raw_records = data.get("experiments")
    if not isinstance(raw_records, list) or not raw_records:
        raise ManifestError("experiments must be a non-empty array.")

    seen_ids: set[str] = set()
    seen_content_ids: set[str] = set()
    records: list[ExperimentRecord] = []
    for index, raw in enumerate(raw_records):
        if not isinstance(raw, dict):
            raise ManifestError(f"experiments[{index}] must be an object.")
        experiment_id = _nonempty(raw.get("id"), f"experiments[{index}].id")
        content_id = _nonempty(raw.get("content_id"), f"{experiment_id}.content_id")
        if experiment_id in seen_ids:
            raise ManifestError(f"Duplicate experiment id: {experiment_id}")
        if content_id in seen_content_ids:
            raise ManifestError(f"Duplicate experiment content_id: {content_id}")
        seen_ids.add(experiment_id)
        seen_content_ids.add(content_id)

        primary_variable = _nonempty(
            raw.get("primary_variable"), f"{experiment_id}.primary_variable"
        )
        if primary_variable not in EXPERIMENT_PRIMARY_VARIABLES:
            raise ManifestError(
                f"{experiment_id}.primary_variable must be one of: "
                f"{', '.join(sorted(EXPERIMENT_PRIMARY_VARIABLES))}."
            )

        comparison_group = raw.get("comparison_group")
        variant_label = raw.get("variant_label")
        if comparison_group is not None:
            comparison_group = _nonempty(
                comparison_group, f"{experiment_id}.comparison_group"
            )
        if variant_label is not None:
            variant_label = _nonempty(variant_label, f"{experiment_id}.variant_label")
        if (comparison_group is None) != (variant_label is None):
            raise ManifestError(
                f"{experiment_id} must set comparison_group and variant_label together."
            )

        records.append(
            ExperimentRecord(
                id=experiment_id,
                content_id=content_id,
                platform=_nonempty(raw.get("platform"), f"{experiment_id}.platform"),
                format=_nonempty(raw.get("format"), f"{experiment_id}.format"),
                topic_tags=_tags(raw.get("topic_tags"), f"{experiment_id}.topic_tags"),
                archetype=_nonempty(raw.get("archetype"), f"{experiment_id}.archetype"),
                hook_type=_nonempty(raw.get("hook_type"), f"{experiment_id}.hook_type"),
                cta_type=_nonempty(raw.get("cta_type"), f"{experiment_id}.cta_type"),
                evaluation_after_days=_days(
                    raw.get("evaluation_after_days"),
                    f"{experiment_id}.evaluation_after_days",
                ),
                primary_variable=primary_variable,
                note=_nonempty(raw.get("note"), f"{experiment_id}.note"),
                comparison_group=comparison_group,
                variant_label=variant_label,
                input_index=index,
            )
        )

    _validate_comparison_groups(records)
    return ExperimentRegistry(
        version=EXPERIMENT_REGISTRY_VERSION,
        experiments=tuple(records),
    )
