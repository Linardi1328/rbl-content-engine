"""Generate the five-shot RBL launch reel with official Higgsfield Seedance 2.5.

This script is intentionally resumable and never auto-retries a billable mutation.
Runtime request IDs, media URLs, and downloaded outputs stay under ignored .production/.
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

from rbl_content_engine.production.video_job import (
    EXPECTED_MODEL,
    LEGACY_OUTPUT_DIR,
    LEGACY_PLAN_FILE,
    LEGACY_STATE_FILE,
    ROOT,
    plan_identity,
    resolve_runtime_paths,
    state_path_string,
    validate_video_plan,
)


ENV_FILE = ROOT / ".env.local"
PLAN_FILE = LEGACY_PLAN_FILE
STATE_FILE = LEGACY_STATE_FILE
OUTPUT_DIR = LEGACY_OUTPUT_DIR


def safe_provider_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    message = re.sub(
        r"(?i)(authorization\\s*[:=]\\s*key\\s+)[^\\s,;]+",
        r"\\1[REDACTED]",
        message,
    )
    message = re.sub(
        r"(?i)(hf_(?:key|api_key|api_secret)\\s*[:=]\\s*)[^\\s,;]+",
        r"\\1[REDACTED]",
        message,
    )
    message = re.sub(
        r"(?<![\\w-])[A-Za-z0-9._-]{8,}:[A-Za-z0-9._-]{8,}(?![\\w-])",
        "[REDACTED_CREDENTIAL]",
        message,
    )
    return message[:1000]


def load_plan(path: Path = PLAN_FILE) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("video plan must be a JSON object")
    validate_video_plan(plan)
    return plan


def load_state(plan: Mapping[str, Any], path: Path = STATE_FILE) -> dict[str, Any]:
    identity_key, identity = plan_identity(plan)
    if path.is_file():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get(identity_key) != identity:
            raise ValueError("existing live state belongs to another video job")
        if state.get("model") != EXPECTED_MODEL:
            raise ValueError("existing live state uses another model")
        return state

    return {
        "schema_version": "1.0.0",
        identity_key: identity,
        "model": EXPECTED_MODEL,
        "status": "GENERATING",
        "publication_status": "BLOCKED_PENDING_HUMAN_REVIEW",
        "shots": {},
    }


def write_state(state: Mapping[str, Any], path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
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
        raise RuntimeError(f"downloaded output is missing or unexpectedly small: {path}")
    with path.open("rb") as handle:
        header = handle.read(64)
    if b"ftyp" not in header:
        raise RuntimeError(f"downloaded output does not look like an MP4: {path}")


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
        description="Generate resumable RBL Seedance 2.5 video-job shots."
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=PLAN_FILE,
        help="Tracked video plan. Defaults to the historical launch plan.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Optional runtime-state override; weekly jobs default under .production/jobs/<job_id>/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional generated-media directory override.",
    )
    parser.add_argument(
        "--retry-shot",
        action="append",
        default=[],
        help=(
            "Explicitly allow a new billable submission for a terminally failed shot. "
            "May be repeated. Example: --retry-shot S02"
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

    plan = load_plan(args.plan)
    runtime = resolve_runtime_paths(
        plan,
        plan_path=args.plan,
        state_file=args.state_file,
        output_dir=args.output_dir,
    )
    state = load_state(plan, runtime.state_file)
    runtime.output_dir.mkdir(parents=True, exist_ok=True)

    import higgsfield_client

    for shot in plan["shots"]:
        shot_id = shot["shot_id"]
        local_path = runtime.output_dir / f"{shot_id}.mp4"
        existing = state["shots"].get(shot_id)

        if (
            isinstance(existing, dict)
            and existing.get("status") == "COMPLETED"
            and local_path.is_file()
        ):
            validate_mp4(local_path)
            print(f"{shot_id}: already complete; skipping billable submission.")
            continue

        terminal_statuses = {
            "FAILED",
            "CANCELED",
            "MODERATED",
            "PROVIDER_ERROR",
            "OUTPUT_ERROR",
        }
        if (
            isinstance(existing, dict)
            and existing.get("status") in terminal_statuses
            and shot_id not in retry_shots
        ):
            print(
                f"{shot_id}: previous state is {existing.get('status')}. "
                f"Inspect request {existing.get('request_id')} first. "
                f"A new paid attempt requires --retry-shot {shot_id}."
            )
            return 3

        estimated_cost = str(shot["estimated_cost_usd"])
        print(
            f"{shot_id}: submitting one billable Seedance 2.5 request "
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
            write_state(state, runtime.state_file)
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
            print("Higgsfield credentials are unavailable; no new request will be submitted.")
            return 2
        except higgsfield_client.HiggsfieldClientError as exc:
            if request_id is not None:
                state["shots"][shot_id] = {
                    **state["shots"].get(shot_id, {}),
                    "status": "PROVIDER_ERROR",
                }
                write_state(state, runtime.state_file)
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
            write_state(state, runtime.state_file)
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
            write_state(state, runtime.state_file)
            print(f"{shot_id}: output could not be validated: {exc}")
            return 1

        state["shots"][shot_id] = {
            "status": "COMPLETED",
            "request_id": request_id,
            "output_url": video_url,
            "local_path": state_path_string(local_path),
            "estimated_cost_usd": estimated_cost,
        }
        write_state(state, runtime.state_file)
        print(f"{shot_id}: completed and saved to {local_path}.")

    state["status"] = "GENERATED"
    state["estimated_spend_usd"] = str(
        sum(
            (Decimal(str(shot["estimated_cost_usd"])) for shot in plan["shots"]),
            Decimal("0"),
        )
    )
    write_state(state, runtime.state_file)

    if runtime.legacy_launch:
        next_command = "uv run python scripts/assemble_rbl_launch_video.py"
    else:
        next_command = (
            "uv run python scripts/assemble_rbl_launch_video.py "
            f"--plan {args.plan}"
        )
    print(
        "All video-job shots are generated. No content has been published. "
        f"Next: {next_command}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
