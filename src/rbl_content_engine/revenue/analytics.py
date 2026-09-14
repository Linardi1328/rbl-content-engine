from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import re
from typing import Any

from .models import ManifestError

REQUIRED_FIELDS = {"content_id", "platform", "published_at", "observed_at", "views"}
INTEGER_FIELDS = {
    "views",
    "impressions",
    "likes",
    "comments",
    "shares",
    "subscribers_gained",
    "clicks",
    "leads",
    "sales",
}
FLOAT_FIELDS = {"watch_time_minutes", "average_view_duration_seconds", "revenue"}

ALIASES = {
    "content_id": {"content_id", "content id", "video_id", "video id", "post_id", "post id"},
    "platform": {"platform", "network", "channel_platform"},
    "published_at": {"published_at", "published at", "published", "publish_date", "publish date"},
    "observed_at": {"observed_at", "observed at", "exported_at", "exported at", "snapshot_at", "snapshot at", "data_as_of", "data as of"},
    "views": {"views", "view_count", "view count", "plays", "video_views", "video views"},
    "impressions": {"impressions", "impression_count", "impression count"},
    "watch_time_minutes": {"watch_time_minutes", "watch time minutes", "watch_time", "watch time", "minutes_watched", "minutes watched"},
    "average_view_duration_seconds": {"average_view_duration_seconds", "average view duration seconds", "avg_view_duration_seconds", "avg view duration seconds", "average_view_duration", "average view duration"},
    "likes": {"likes", "like_count", "like count"},
    "comments": {"comments", "comment_count", "comment count"},
    "shares": {"shares", "share_count", "share count"},
    "subscribers_gained": {"subscribers_gained", "subscribers gained", "subs_gained", "subs gained", "followers_gained", "followers gained"},
    "revenue": {"revenue", "estimated_revenue", "estimated revenue", "gross_revenue", "gross revenue"},
    "currency": {"currency", "currency_code", "currency code"},
    "clicks": {"clicks", "link_clicks", "link clicks"},
    "leads": {"leads", "lead_count", "lead count"},
    "sales": {"sales", "sale_count", "sale count", "orders"},
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


NORMALIZED_ALIASES = {
    canonical: {_norm(alias) for alias in aliases | {canonical}}
    for canonical, aliases in ALIASES.items()
}


def _map_headers(headers: list[str]) -> dict[str, str]:
    canonical_to_source: dict[str, str] = {}
    for source in headers:
        normalized = _norm(source)
        matches = [
            canonical
            for canonical, aliases in NORMALIZED_ALIASES.items()
            if normalized in aliases
        ]
        if not matches:
            continue
        if len(matches) > 1:
            raise ManifestError(
                f"Analytics header {source!r} ambiguously maps to: {', '.join(matches)}"
            )
        canonical = matches[0]
        if canonical in canonical_to_source:
            raise ManifestError(
                f"Analytics columns {canonical_to_source[canonical]!r} and {source!r} both map to {canonical}."
            )
        canonical_to_source[canonical] = source
    missing = sorted(REQUIRED_FIELDS - set(canonical_to_source))
    if missing:
        raise ManifestError(
            f"Analytics CSV missing required field(s): {', '.join(missing)}"
        )
    return canonical_to_source


def parse_timestamp(value: str, field: str) -> datetime:
    text = value.strip()
    if not text:
        raise ManifestError(f"{field} must be non-empty.")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ManifestError(f"{field} must be an ISO datetime with timezone.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManifestError(f"{field} must include a timezone offset.")
    return parsed


def _parse_number(value: str, field: str, *, integer: bool) -> int | float | None:
    text = value.strip()
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise ManifestError(f"{field} must be numeric.") from exc
    if number < 0:
        raise ManifestError(f"{field} must be non-negative.")
    if integer:
        if not number.is_integer():
            raise ManifestError(f"{field} must be an integer.")
        return int(number)
    return number


def _normalized_row(row: dict[str, str], mapping: dict[str, str], line: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for canonical, source in mapping.items():
        raw = row.get(source, "")
        field = f"analytics line {line} {canonical}"
        if canonical in INTEGER_FIELDS:
            result[canonical] = _parse_number(raw, field, integer=True)
        elif canonical in FLOAT_FIELDS:
            result[canonical] = _parse_number(raw, field, integer=False)
        elif canonical in {"published_at", "observed_at"}:
            parsed = parse_timestamp(raw, field)
            result[canonical] = parsed.isoformat()
        else:
            text = raw.strip()
            if canonical in {"content_id", "platform"} and not text:
                raise ManifestError(f"{field} must be non-empty.")
            result[canonical] = text or None
    if result.get("views") is None:
        raise ManifestError(f"analytics line {line} views must be present.")
    if parse_timestamp(result["observed_at"], f"analytics line {line} observed_at") < parse_timestamp(
        result["published_at"], f"analytics line {line} published_at"
    ):
        raise ManifestError(f"analytics line {line} observed_at cannot be before published_at.")
    return result


def load_analytics(path: str | Path) -> dict[str, dict[str, Any]]:
    csv_path = Path(path)
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ManifestError("Analytics CSV has no header row.")
            mapping = _map_headers(list(reader.fieldnames))
            rows = [
                _normalized_row(row, mapping, line)
                for line, row in enumerate(reader, start=2)
                if any((value or "").strip() for value in row.values())
            ]
    except OSError as exc:
        raise ManifestError(f"Unable to read analytics CSV: {exc}") from exc
    if not rows:
        raise ManifestError("Analytics CSV contains no data rows.")

    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        content_id = row["content_id"]
        if content_id in output:
            raise ManifestError(
                f"Duplicate analytics rows for content_id {content_id}. Phase 2A requires one cumulative snapshot per content item to avoid double-counting."
            )
        output[content_id] = row
    return output
