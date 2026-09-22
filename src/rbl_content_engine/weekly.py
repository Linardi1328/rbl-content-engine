"""Minimum V1 weekly short-form content package.

This module is intentionally offline and deterministic. It turns a human-authored
weekly brief, local evidence-backed claims, and a human-authored channel theme into
one canonical 20-30 second script/storyboard package for human review.

It performs no network calls, model calls, media generation, scheduling, or publishing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .prooflab import VerifiedClaim, VerificationStatus, require_verified_claims


SUPPORTED_TARGETS = ("youtube", "instagram", "tiktok")
APPROVAL_STATUS = "PENDING_HUMAN"


@dataclass(frozen=True)
class ClaimVerification:
    claim: VerifiedClaim
    evidence: tuple[dict[str, Any], ...]
    errors: tuple[str, ...]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _workspace_path(workspace_root: Path, raw: str) -> Path:
    root = workspace_root.resolve()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace root: {raw}") from exc
    return resolved


def _verify_evidence_ref(
    workspace_root: Path,
    ref: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    raw_path = ref.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None, "evidence path is missing"

    try:
        path = _workspace_path(workspace_root, raw_path)
    except ValueError as exc:
        return None, str(exc)

    if not path.is_file():
        return None, f"evidence file does not exist: {raw_path}"

    start = ref.get("start_line")
    end = ref.get("end_line")
    quote = ref.get("quote")
    if not isinstance(start, int) or not isinstance(end, int):
        return None, "evidence line range must use integers"
    if start < 1 or end < start:
        return None, "evidence line range is invalid"
    if not isinstance(quote, str) or not quote:
        return None, "evidence quote must be non-empty"

    lines = path.read_text(encoding="utf-8").splitlines()
    if end > len(lines):
        return None, "evidence line range exceeds file length"
    selected = "\n".join(lines[start - 1 : end])
    if quote not in selected:
        return None, "evidence quote was not found in the referenced line range"

    return (
        {
            "path": raw_path,
            "start_line": start,
            "end_line": end,
            "quote": quote,
            "ref": f"{raw_path}:L{start}-L{end}",
        },
        None,
    )


def verify_claim_manifest(
    workspace_root: Path,
    manifest: Mapping[str, Any],
) -> tuple[str, tuple[ClaimVerification, ...]]:
    project = manifest.get("project")
    if not isinstance(project, str) or not project.strip():
        raise ValueError("claim manifest project must be non-empty")

    raw_claims = manifest.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims:
        raise ValueError("claim manifest must contain at least one claim")

    seen: set[str] = set()
    results: list[ClaimVerification] = []

    for raw in raw_claims:
        if not isinstance(raw, Mapping):
            raise ValueError("every claim must be an object")
        claim_id = raw.get("id")
        text = raw.get("text")
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise ValueError("claim id must be non-empty")
        if claim_id in seen:
            raise ValueError(f"duplicate claim id: {claim_id}")
        seen.add(claim_id)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{claim_id} text must be non-empty")

        raw_refs = raw.get("evidence")
        evidence: list[dict[str, Any]] = []
        errors: list[str] = []
        if not isinstance(raw_refs, list) or not raw_refs:
            errors.append("claim has no evidence references")
        else:
            for index, raw_ref in enumerate(raw_refs, start=1):
                if not isinstance(raw_ref, Mapping):
                    errors.append(f"evidence #{index} is not an object")
                    continue
                verified, error = _verify_evidence_ref(workspace_root, raw_ref)
                if error is not None:
                    errors.append(f"evidence #{index}: {error}")
                elif verified is not None:
                    evidence.append(verified)

        status = (
            VerificationStatus.VERIFIED
            if evidence and not errors
            else VerificationStatus.UNSUPPORTED
        )
        claim = VerifiedClaim(
            claim_id=claim_id,
            text=text,
            evidence_refs=tuple(item["ref"] for item in evidence),
            status=status,
        )
        results.append(
            ClaimVerification(
                claim=claim,
                evidence=tuple(evidence),
                errors=tuple(errors),
            )
        )

    return project, tuple(results)


def _validate_brief(brief: Mapping[str, Any]) -> None:
    for key in ("job_id", "project", "topic", "objective", "hook"):
        value = brief.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"brief.{key} must be non-empty")

    if brief.get("approval_status") != APPROVAL_STATUS:
        raise ValueError(f"brief.approval_status must be {APPROVAL_STATUS}")

    targets = brief.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("brief.targets must contain at least one platform")
    if len(set(targets)) != len(targets):
        raise ValueError("brief.targets must not contain duplicates")
    for target in targets:
        if target not in SUPPORTED_TARGETS:
            raise ValueError(f"unsupported short-form target: {target}")


def _validate_theme(theme: Mapping[str, Any]) -> int:
    for key in ("theme_id", "name", "voice", "visual_style"):
        value = theme.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"theme.{key} must be non-empty")

    beats = theme.get("beats")
    if not isinstance(beats, list) or not beats:
        raise ValueError("theme.beats must be a non-empty list")

    seen: set[str] = set()
    total = 0
    for beat in beats:
        if not isinstance(beat, Mapping):
            raise ValueError("every theme beat must be an object")
        beat_id = beat.get("id")
        if not isinstance(beat_id, str) or not beat_id.strip():
            raise ValueError("theme beat id must be non-empty")
        if beat_id in seen:
            raise ValueError(f"duplicate theme beat id: {beat_id}")
        seen.add(beat_id)

        duration = beat.get("duration_seconds")
        if not isinstance(duration, int) or isinstance(duration, bool) or duration < 1:
            raise ValueError(f"theme beat {beat_id} duration_seconds must be positive")
        total += duration

        source = beat.get("source")
        if source not in {"brief_hook", "next_claim", "theme_text"}:
            raise ValueError(
                f"theme beat {beat_id} source must be brief_hook, next_claim, or theme_text"
            )
        if source == "theme_text":
            text = beat.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"theme beat {beat_id} theme_text requires text")

        visual = beat.get("visual_direction")
        if not isinstance(visual, str) or not visual.strip():
            raise ValueError(f"theme beat {beat_id} visual_direction must be non-empty")

    declared = theme.get("target_duration_seconds")
    if not isinstance(declared, int) or declared != total:
        raise ValueError("theme.target_duration_seconds must equal the sum of beat durations")
    if total < 20 or total > 30:
        raise ValueError("V1 weekly short-form duration must be between 20 and 30 seconds")
    return total


def _render_verifier_report(
    *,
    project: str,
    brief: Mapping[str, Any],
    theme: Mapping[str, Any],
    verifications: tuple[ClaimVerification, ...],
    status: str,
) -> str:
    lines = [
        "# Weekly Content Verifier",
        "",
        f"- job_id: {brief['job_id']}",
        f"- project: {project}",
        f"- verification_status: {status}",
        f"- approval_status: {APPROVAL_STATUS}",
        f"- theme_id: {theme['theme_id']}",
        "",
        "## Claims",
        "",
    ]
    for item in verifications:
        lines.append(
            f"### {item.claim.claim_id} — {item.claim.status.value.upper()}"
        )
        lines.append("")
        lines.append(item.claim.text)
        lines.append("")
        if item.evidence:
            lines.append("Evidence:")
            for ref in item.evidence:
                lines.append(f"- {ref['ref']} — {ref['quote']}")
        if item.errors:
            lines.append("Errors:")
            for error in item.errors:
                lines.append(f"- {error}")
        lines.append("")

    lines.extend(
        [
            "## Boundary",
            "",
            "The channel theme controls creative structure and visual direction only.",
            "It is not evidence for factual claims.",
            "",
            f"approval_status: {APPROVAL_STATUS}",
            "",
        ]
    )
    return "\n".join(lines)


def _render_script(
    *,
    brief: Mapping[str, Any],
    theme: Mapping[str, Any],
    beats: list[dict[str, Any]],
    total_duration: int,
) -> str:
    lines = [
        f"# {brief['job_id']} — Short-form Script",
        "",
        f"- Topic: {brief['topic']}",
        f"- Objective: {brief['objective']}",
        f"- Theme: {theme['name']} ({theme['theme_id']})",
        f"- Voice: {theme['voice']}",
        f"- Targets: {', '.join(brief['targets'])}",
        f"- Planned duration: {total_duration}s",
        f"- Approval: {APPROVAL_STATUS}",
        "",
    ]

    cursor = 0
    for beat in beats:
        start = cursor
        end = cursor + int(beat["duration_seconds"])
        cursor = end
        lines.append(f"## {beat['id']} — {start:02d}s–{end:02d}s")
        lines.append("")
        lines.append(str(beat["text"]))
        lines.append("")
        if beat["source_claim_ids"]:
            lines.append(
                "Evidence claims: " + ", ".join(beat["source_claim_ids"])
            )
            for ref in beat["evidence"]:
                lines.append(f"- {ref['ref']}")
            lines.append("")

    lines.extend(
        [
            "## Review gate",
            "",
            "This is draft material. Human review is required before media generation or publication.",
            "",
            f"approval_status: {APPROVAL_STATUS}",
            "",
        ]
    )
    return "\n".join(lines)


def run_weekly_pipeline(
    *,
    workspace_root: Path,
    brief_path: Path,
    claims_path: Path,
    theme_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    root = workspace_root.resolve()
    brief = _read_json(_workspace_path(root, str(brief_path)))
    claims_manifest = _read_json(_workspace_path(root, str(claims_path)))
    theme = _read_json(_workspace_path(root, str(theme_path)))

    _validate_brief(brief)
    total_duration = _validate_theme(theme)

    project, verifications = verify_claim_manifest(root, claims_manifest)
    if project != brief["project"]:
        raise ValueError("brief.project must match claim manifest project")

    output = output_dir
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise ValueError("output directory escapes workspace root") from exc
    output.mkdir(parents=True, exist_ok=True)

    blocked = tuple(
        item for item in verifications if not item.claim.publishable
    )
    verification_status = "BLOCKED" if blocked else "PASS"
    verifier_text = _render_verifier_report(
        project=project,
        brief=brief,
        theme=theme,
        verifications=verifications,
        status=verification_status,
    )
    (output / "verifier-report.md").write_text(verifier_text, encoding="utf-8")

    if blocked:
        result = {
            "schema_version": "1.0.0",
            "job_id": brief["job_id"],
            "project": project,
            "status": "BLOCKED",
            "approval_status": APPROVAL_STATUS,
            "blocked_claim_ids": [item.claim.claim_id for item in blocked],
            "generated_artifacts": ["verifier-report.md"],
        }
        (output / "content-package.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return result

    claims = tuple(item.claim for item in verifications)
    require_verified_claims(claims)
    required_claim_beats = sum(
        1 for beat in theme["beats"] if beat["source"] == "next_claim"
    )
    if required_claim_beats > len(claims):
        raise ValueError(
            "theme requires more next_claim beats than verified claims available"
        )
    by_id = {item.claim.claim_id: item for item in verifications}

    claim_iter = iter(claims)
    used_claim_ids: list[str] = []
    script_beats: list[dict[str, Any]] = []

    for beat_index, raw_beat in enumerate(theme["beats"], start=1):
        source = raw_beat["source"]
        source_claim_ids: list[str] = []
        evidence: list[dict[str, Any]] = []

        if source == "brief_hook":
            text = brief["hook"]
        elif source == "theme_text":
            text = raw_beat["text"]
        else:
            try:
                claim = next(claim_iter)
            except StopIteration as exc:
                raise ValueError(
                    "theme requires more next_claim beats than verified claims available"
                ) from exc
            text = claim.text
            source_claim_ids.append(claim.claim_id)
            used_claim_ids.append(claim.claim_id)
            evidence.extend(by_id[claim.claim_id].evidence)

        script_beats.append(
            {
                "id": raw_beat["id"],
                "shot_id": f"S{beat_index:02d}",
                "duration_seconds": raw_beat["duration_seconds"],
                "source": source,
                "text": text,
                "source_claim_ids": source_claim_ids,
                "evidence": evidence,
                "visual_direction": raw_beat["visual_direction"],
            }
        )

    unused_claim_ids = [
        claim.claim_id for claim in claims if claim.claim_id not in used_claim_ids
    ]
    package = {
        "schema_version": "1.0.0",
        "job_id": brief["job_id"],
        "project": project,
        "topic": brief["topic"],
        "objective": brief["objective"],
        "targets": list(brief["targets"]),
        "theme": {
            "theme_id": theme["theme_id"],
            "name": theme["name"],
            "voice": theme["voice"],
            "visual_style": theme["visual_style"],
        },
        "planned_duration_seconds": total_duration,
        "status": "READY_FOR_HUMAN_REVIEW",
        "verification_status": "PASS",
        "approval_status": APPROVAL_STATUS,
        "script_beats": script_beats,
        "used_claim_ids": used_claim_ids,
        "unused_claim_ids": unused_claim_ids,
        "generated_artifacts": [
            "content-package.json",
            "script.md",
            "storyboard.json",
            "verifier-report.md",
        ],
    }

    storyboard = {
        "schema_version": "1.0.0",
        "job_id": brief["job_id"],
        "theme_id": theme["theme_id"],
        "visual_style": theme["visual_style"],
        "planned_duration_seconds": total_duration,
        "approval_status": APPROVAL_STATUS,
        "shots": [
            {
                "shot_id": beat["shot_id"],
                "beat_id": beat["id"],
                "duration_seconds": beat["duration_seconds"],
                "voiceover": beat["text"],
                "visual_direction": beat["visual_direction"],
                "source_claim_ids": beat["source_claim_ids"],
                "evidence": beat["evidence"],
            }
            for beat in script_beats
        ],
    }

    (output / "content-package.json").write_text(
        json.dumps(package, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "storyboard.json").write_text(
        json.dumps(storyboard, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "script.md").write_text(
        _render_script(
            brief=brief,
            theme=theme,
            beats=script_beats,
            total_duration=total_duration,
        ),
        encoding="utf-8",
    )
    return package
