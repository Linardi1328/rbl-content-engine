"""Generate improved RBL launch scenes with the official Higgsfield Seedance 2.5 API.

Credentials stay in ignored .env.local. Runtime state and media stay in ignored
.production/. The workflow is resumable and never auto-retries a billable mutation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.local"
PLAN_FILE = ROOT / "examples" / "production" / "rbl-launch-video-revision-r2.json"
STATE_FILE = ROOT / ".production" / "rbl-launch-revision-r2.json"
OUTPUT_DIR = ROOT / ".production" / "launch-video-revisions" / "R2"
EXPECTED_MODEL = "bytedance/seedance-2.5/text-to-video"
EXPECTED_REVISION = "RBL-LAUNCH-R2"


def safe_provider_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    message = re.sub(
        r"(?i)(authorization\s*[:=]\s*key\s+)[^\s,;]+",
        r"\1[REDACTED]",
        message,
    )
    message = re.sub(
        r"(?i)(hf_(?:key|api_key|api_secret)\s*[:=]\s*)[^\s,;]+",
        r"\1[REDACTED]",
        message,
    )
    message = re.sub(
        r"(?<![\w-])[A-Za-z0-9._-]{8,}:[A-Za-z0-9._-]{8,}(?![\w-])",
        "[REDACTED_CREDENTIAL]",
        message,
    )
    return message[:1000]


def load_plan(path: Path = PLAN_FILE) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("revision_id") != EXPECTED_REVISION:
        raise ValueError("unexpected scene revision id")
    if plan.get("model") != EXPECTED_MODEL:
        raise ValueError("revision plan must use the live-verified Seedance 2.5 path")
    if plan.get("aspect_ratio") != "9:16":
        raise ValueError("revision plan must remain vertical 9:16")
    if plan.get("resolution") != "720p":
        raise ValueError("revision plan must use 720p review drafts")
    if plan.get("output_format") != "mp4":
        raise ValueError("revision plan output format must be mp4")
    if plan.get("generate_audio") is not False:
        raise ValueError("scene revisions must disable generated audio")

    shots = plan.get("shots")
    if not isinstance(shots, list) or len(shots) != 5:
        raise ValueError("R2 must contain exactly five scenes")

    ids: set[str] = set()
    estimated_total = Decimal("0")
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError("every revision scene must be an object")
        shot_id = str(shot.get("shot_id", "")).strip()
        if shot_id not in {"S01", "S02", "S03", "S04", "S05"} or shot_id in ids:
            raise ValueError("R2 scene IDs must be unique S01-S05")
        ids.add(shot_id)
        if int(shot.get("duration_seconds", 0)) != 4:
            raise ValueError(f"{shot_id}: R2 scene duration must be exactly 4 seconds")
        if not str(shot.get("prompt", "")).strip():
            raise ValueError(f"{shot_id}: revision prompt must not be empty")
        estimated_total += Decimal(str(shot.get("estimated_cost_usd", "0")))

    project_budget = Decimal(str(plan.get("project_budget_usd", "0")))
    if project_budget <= 0 or project_budget > Decimal("20"):
        raise ValueError("R2 project ceiling must remain within US$20")
    if estimated_total > project_budget:
        raise ValueError("planned R2 spend exceeds project ceiling")
    return plan


def load_state(plan: Mapping[str, Any], path: Path = STATE_FILE) -> dict[str, Any]:
    if path.is_file():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("revision_id") != plan.get("revision_id"):
            raise ValueError("existing state belongs to another revision")
        if state.get("model") != EXPECTED_MODEL:
            raise ValueError("existing revision state uses another model")
        return state

    return {
        "schema_version": "0.1.0",
        "revision_id": plan["revision_id"],
        "model": EXPECTED_MODEL,
        "status": "GENERATING",
        "publication_status": "BLOCKED_PENDING_HUMAN_REVIEW",
        "shots": {},
    }


def write_state(state: Mapping[str, Any], path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def extract_video_url(result: Mapping[str, Any]) -> str:
    video = result.get("video")
    if isinstance(video, str) and video.startswith(("https://", "http://")):
        return video
    if isinstance(video, Mapping):
        url = video.get("url")
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            return url
    raise RuntimeError("completed request did not return a recognizable video URL")


def validate_mp4(path: Path) -> None:
    if not path.is_file() or path.stat().st_size < 1024:
        raise RuntimeError(f"output is missing or unexpectedly small: {path}")
    with path.open("rb") as handle:
        if b"ftyp" not in handle.read(64):
            raise RuntimeError(f"output does not look like an MP4: {path}")


def download_video(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "rbl-content-engine/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    partial.replace(destination)
    validate_mp4(destination)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the five improved RBL R2 scenes via official Higgsfield API."
    )
    parser.add_argument(
        "--retry-shot",
        action="append",
        default=[],
        help=(
            "Explicitly authorize a new billable attempt for a terminally failed scene. "
            "May be repeated, e.g. --retry-shot S03."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    retry_shots = set(args.retry_shot)

    if not ENV_FILE.is_file():
        print(
            ".env.local is missing. Configure HF_KEY locally with "
            "scripts/configure_higgsfield_env.py; do not paste it into chat."
        )
        return 2

    load_dotenv(ENV_FILE, override=False)
    if "HF_KEY" not in os.environ:
        print("HF_KEY is not configured in .env.local; no request was submitted.")
        return 2

    plan = load_plan()
    state = load_state(plan)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    import higgsfield_client

    terminal_statuses = {
        "FAILED",
        "CANCELED",
        "MODERATED",
        "PROVIDER_ERROR",
        "OUTPUT_ERROR",
    }

    for shot in plan["shots"]:
        shot_id = shot["shot_id"]
        local_path = OUTPUT_DIR / f"{shot_id}.mp4"
        existing = state["shots"].get(shot_id)

        if (
            isinstance(existing, dict)
            and existing.get("status") == "COMPLETED"
            and local_path.is_file()
        ):
            validate_mp4(local_path)
            print(f"{shot_id}: improved scene already complete; skipping paid submission.")
            continue

        if (
            isinstance(existing, dict)
            and existing.get("status") in terminal_statuses
            and shot_id not in retry_shots
        ):
            print(
                f"{shot_id}: previous R2 state is {existing.get('status')}. "
                f"Inspect request {existing.get('request_id')} before another paid attempt. "
                f"Retry requires --retry-shot {shot_id}."
            )
            return 3

        estimated_cost = str(shot["estimated_cost_usd"])
        print(
            f"{shot_id}: submitting one improved Seedance 2.5 scene "
            + "(budget reservation US$"
            + estimated_cost
            + ")."
        )

        request_id: str | None = None
        terminal_failure: str | None = None

        def on_enqueue(value: str) -> None:
            nonlocal request_id
            request_id = value
            state["shots"][shot_id] = {
                "status": "SUBMITTED",
                "request_id": value,
                "estimated_cost_usd": estimated_cost,
            }
            write_state(state)
            print(f"{shot_id}: enqueued as {value}.")

        def on_queue_update(status: Any) -> None:
            nonlocal terminal_failure
            if isinstance(status, higgsfield_client.Failed):
                terminal_failure = "FAILED"
            elif isinstance(status, higgsfield_client.Cancelled):
                terminal_failure = "CANCELED"
            elif isinstance(status, higgsfield_client.NSFW):
                terminal_failure = "MODERATED"

        try:
            result = higgsfield_client.subscribe(
                EXPECTED_MODEL,
                arguments={
                    "prompt": shot["prompt"],
                    "duration": int(shot["duration_seconds"]),
                    "resolution": plan["resolution"],
                    "aspect_ratio": plan["aspect_ratio"],
                    "output_format": plan["output_format"],
                    "generate_audio": bool(plan["generate_audio"]),
                },
                on_enqueue=on_enqueue,
                on_queue_update=on_queue_update,
            )
        except higgsfield_client.CredentialsMissedError:
            print("Higgsfield credentials are unavailable; no request was submitted.")
            return 2
        except higgsfield_client.HiggsfieldClientError as exc:
            if request_id is not None:
                state["shots"][shot_id] = {
                    **state["shots"].get(shot_id, {}),
                    "status": "PROVIDER_ERROR",
                }
                write_state(state)
            print(
                f"{shot_id}: provider error; no automatic retry will occur. "
                f"Provider message: {safe_provider_error(exc)}"
            )
            return 1

        if terminal_failure is not None:
            state["shots"][shot_id] = {
                **state["shots"].get(shot_id, {}),
                "status": terminal_failure,
            }
            write_state(state)
            print(f"{shot_id}: request ended as {terminal_failure}; stopping.")
            return 1

        if not isinstance(result, Mapping):
            print(f"{shot_id}: provider returned an unexpected result; stopping.")
            return 1

        try:
            video_url = extract_video_url(result)
            download_video(video_url, local_path)
        except Exception as exc:
            state["shots"][shot_id] = {
                **state["shots"].get(shot_id, {}),
                "status": "OUTPUT_ERROR",
            }
            write_state(state)
            print(f"{shot_id}: output could not be validated: {exc}")
            return 1

        state["shots"][shot_id] = {
            "status": "COMPLETED",
            "request_id": request_id,
            "output_url": video_url,
            "local_path": str(local_path.relative_to(ROOT)),
            "estimated_cost_usd": estimated_cost,
        }
        write_state(state)
        print(f"{shot_id}: improved scene saved to {local_path}.")

    state["status"] = "GENERATED"
    state["publication_status"] = "BLOCKED_PENDING_HUMAN_REVIEW"
    state["estimated_spend_usd"] = str(
        sum(
            (Decimal(str(shot["estimated_cost_usd"])) for shot in plan["shots"]),
            Decimal("0"),
        )
    )
    write_state(state)

    print(
        "All five improved scenes are generated. Nothing has been published. "
        "Next: uv run python scripts/assemble_rbl_scene_revision_review.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
