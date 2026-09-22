"""Assemble generated RBL video-job shots into a vertical human-review cut."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from rbl_content_engine.production.video_job import (
    LEGACY_OUTPUT_DIR,
    LEGACY_PLAN_FILE,
    LEGACY_STATE_FILE,
    ROOT,
    plan_identity,
    resolve_recorded_path,
    resolve_runtime_paths,
    state_path_string,
    validate_video_plan,
)


PLAN_FILE = LEGACY_PLAN_FILE
STATE_FILE = LEGACY_STATE_FILE
OUTPUT_DIR = LEGACY_OUTPUT_DIR
FINAL_VIDEO = OUTPUT_DIR / "rbl-launch-review.mp4"


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"required file is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_ffmpeg_command(inputs: list[Path], output: Path) -> list[str]:
    command = ["ffmpeg", "-y"]
    for path in inputs:
        command.extend(["-i", str(path)])

    filters: list[str] = []
    labels: list[str] = []
    for index in range(len(inputs)):
        label = f"v{index}"
        filters.append(
            f"[{index}:v]"
            "scale=720:1280:force_original_aspect_ratio=decrease,"
            "pad=720:1280:(ow-iw)/2:(oh-ih)/2,"
            "fps=30,setsar=1"
            f"[{label}]"
        )
        labels.append(f"[{label}]")

    filters.append("".join(labels) + f"concat=n={len(inputs)}:v=1:a=0[outv]")
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    return command


def probe_video(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble one generated RBL video job for human review."
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=PLAN_FILE,
        help="Tracked video plan. Defaults to the historical launch plan.",
    )
    parser.add_argument("--state-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--final-video",
        type=Path,
        default=None,
        help="Optional final review-cut path override.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print(
            "ffmpeg/ffprobe are required for local assembly. Install them locally, "
            "then rerun. No generated shot will be resubmitted."
        )
        return 2

    plan = load_json(args.plan)
    validate_video_plan(plan)
    runtime = resolve_runtime_paths(
        plan,
        plan_path=args.plan,
        state_file=args.state_file,
        output_dir=args.output_dir,
    )
    state = load_json(runtime.state_file)

    identity_key, identity = plan_identity(plan)
    if state.get(identity_key) != identity:
        print("Live generation state does not match the video plan.")
        return 1
    if state.get("status") != "GENERATED":
        print("All planned video shots must be generated before assembly.")
        return 1

    inputs: list[Path] = []
    for shot in plan["shots"]:
        shot_id = shot["shot_id"]
        record = state.get("shots", {}).get(shot_id)
        if not isinstance(record, dict) or record.get("status") != "COMPLETED":
            print(f"{shot_id}: missing completed generation record.")
            return 1
        local_path = resolve_recorded_path(str(record["local_path"]))
        if not local_path.is_file():
            print(f"{shot_id}: generated local MP4 is missing: {local_path}")
            return 1
        inputs.append(local_path)

    runtime.output_dir.mkdir(parents=True, exist_ok=True)
    final_video = (
        args.final_video
        if args.final_video is not None and args.final_video.is_absolute()
        else ROOT / args.final_video
        if args.final_video is not None
        else runtime.final_video
    )
    final_video.parent.mkdir(parents=True, exist_ok=True)
    command = build_ffmpeg_command(inputs, final_video)
    subprocess.run(command, check=True)

    metadata = probe_video(final_video)
    streams = metadata.get("streams") or []
    if not streams:
        print("Final video contains no video stream.")
        return 1

    stream = streams[0]
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    duration = float((metadata.get("format") or {}).get("duration", 0))

    if (width, height) != (720, 1280):
        print(f"Final video has unexpected dimensions: {width}x{height}.")
        return 1
    expected_duration = float(plan["target_duration_seconds"])
    if not expected_duration - 2.5 <= duration <= expected_duration + 2.5:
        print(
            "Final video has unexpected duration: "
            f"{duration:.2f}s (expected about {expected_duration:.2f}s)."
        )
        return 1

    state["status"] = "PENDING_HUMAN_REVIEW"
    state["publication_status"] = "BLOCKED_PENDING_HUMAN_REVIEW"
    state["final_video"] = {
        "local_path": state_path_string(final_video),
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 3),
        "technical_qc": "PASS",
        "actual_spend_usd": None,
        "spend_note": (
            "Per-request actual API charge is not inferred from the generated media "
            "response; consult the Higgsfield API billing console for actual spend."
        ),
    }
    runtime.state_file.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(str(final_video))
    print(
        "Status: PENDING_HUMAN_REVIEW. Do not publish this file until the human "
        "owner explicitly approves the final cut."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
