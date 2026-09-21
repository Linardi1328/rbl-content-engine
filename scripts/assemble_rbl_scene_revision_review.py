"""Assemble the improved R2 RBL scenes into a raw 20-second review reel."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_FILE = ROOT / "examples" / "production" / "rbl-launch-video-revision-r2.json"
STATE_FILE = ROOT / ".production" / "rbl-launch-revision-r2.json"
OUTPUT_DIR = ROOT / ".production" / "launch-video-revisions" / "R2"
FINAL_VIDEO = OUTPUT_DIR / "rbl-launch-r2-scene-review.mp4"


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


def main() -> int:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("ffmpeg and ffprobe are required for local assembly.")
        return 2

    plan = load_json(PLAN_FILE)
    state = load_json(STATE_FILE)
    if state.get("revision_id") != plan.get("revision_id"):
        print("R2 live state does not match the revision plan.")
        return 1
    if state.get("status") != "GENERATED":
        print("All five improved scenes must be generated before assembly.")
        return 1

    inputs: list[Path] = []
    for shot in plan["shots"]:
        shot_id = shot["shot_id"]
        record = state.get("shots", {}).get(shot_id)
        if not isinstance(record, dict) or record.get("status") != "COMPLETED":
            print(f"{shot_id}: missing completed R2 generation record.")
            return 1
        local_path = ROOT / record["local_path"]
        if not local_path.is_file():
            print(f"{shot_id}: improved scene file is missing: {local_path}")
            return 1
        inputs.append(local_path)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(build_ffmpeg_command(inputs, FINAL_VIDEO), check=True)

    metadata = probe_video(FINAL_VIDEO)
    streams = metadata.get("streams") or []
    if not streams:
        print("R2 review contains no video stream.")
        return 1
    stream = streams[0]
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    duration = float((metadata.get("format") or {}).get("duration", 0))
    if (width, height) != (720, 1280):
        print(f"R2 review has unexpected dimensions: {width}x{height}.")
        return 1
    if not 18.0 <= duration <= 22.5:
        print(f"R2 review has unexpected duration: {duration:.2f}s.")
        return 1

    state["status"] = "PENDING_HUMAN_REVIEW"
    state["publication_status"] = "BLOCKED_PENDING_HUMAN_REVIEW"
    state["raw_review_video"] = {
        "local_path": str(FINAL_VIDEO.relative_to(ROOT)),
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 3),
        "technical_qc": "PASS",
    }
    STATE_FILE.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(str(FINAL_VIDEO))
    print(
        "Status: PENDING_HUMAN_REVIEW. Upload this raw scene reel for visual QC "
        "before applying final RBL branding, copy, logo, and sound."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
