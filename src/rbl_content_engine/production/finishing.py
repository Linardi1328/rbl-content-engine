"""Offline, additive social finishing of an existing job-scoped silent review cut.

This is a minimum equivalent implementation, not recovered V5 source. Human
attestations bind approved inputs to hashes; this module never aligns or approves
speech, changes generation state, or authorizes publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .video_job import ROOT, resolve_recorded_path, resolve_runtime_paths, validate_video_plan


FINAL = "final-social-review.mp4"
REPORT = "social-finishing-qc.json"
CAPTIONS = "social-captions.ass"
DIGEST = "final-social-review.sha256"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def number(value: Any) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), "Expected numeric seconds/gain")
    result = float(value)
    require(math.isfinite(result), "Non-finite seconds/gain")
    return result


def text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def attestation(record: dict[str, Any]) -> None:
    require(record.get("human_confirmed") is True and text(record.get("reviewer")), "Human review required")
    stamp = datetime.fromisoformat(str(record.get("confirmed_at", "")))
    require(stamp.tzinfo is not None and stamp.utcoffset() is not None, "Review timestamp requires timezone")


def run(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout


def probe(path: Path, ffprobe: str) -> dict[str, Any]:
    return json.loads(run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))


def duration(metadata: dict[str, Any]) -> float:
    value = float(metadata["format"]["duration"])
    require(math.isfinite(value) and value > 0, "Invalid media duration")
    return value


def streams(metadata: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [stream for stream in metadata["streams"] if stream.get("codec_type") == kind]


def audio_levels(path: Path, ffmpeg: str) -> dict[str, float]:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostdin", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    levels = {}
    for name in ("mean_volume", "max_volume"):
        match = re.search(rf"{name}: (-?[0-9.]+) dB", result.stderr)
        require(match is not None, "Audio level measurement failed (possibly silent audio)")
        assert match is not None
        levels[name] = float(match.group(1))
    require(levels["mean_volume"] > -60, "Silent/inaudible audio rejected")
    return levels


def validate_cues(
    timing: dict[str, Any], transcript: str, wav_hash: str, audio_duration: float
) -> list[dict[str, Any]]:
    require(timing.get("audio_sha256") == wav_hash, "Timings must derive from this exact WAV")
    require(text(timing.get("derivation_method")), "Actual-WAV timing derivation method required")
    require(timing.get("review_status") == "HUMAN_CORRECTED", "Machine-estimated/unverified timings rejected")
    attestation(timing)
    cues = timing.get("words")
    tokens = transcript.split()
    require(isinstance(cues, list) and len(cues) == len(tokens) and len(tokens) > 1, "Missing/extra word cues")
    assert isinstance(cues, list)
    previous_end = 0.0
    for token, cue in zip(tokens, cues):
        require(isinstance(cue, dict), "Word cue must be an object")
        require(cue.get("word") == token, "Word cues must exactly follow the verified script")
        require(cue.get("verified") is True, "Every word cue must be human-verified")
        require(len(token) <= 24 and not re.search(r"[{}\\\x00-\x1f]", token), "Unsafe/oversized caption word")
        start, end = number(cue.get("start")), number(cue.get("end"))
        require(0 <= previous_end <= start < end <= audio_duration, "Out-of-order/overlapping/out-of-range cue")
        require(round(start * 100) < round(end * 100), "Word cue collapses at ASS centisecond precision")
        previous_end = end
    return cues


def ass_time(value: float) -> str:
    ticks = round(value * 100)
    return f"{ticks // 360000}:{ticks // 6000 % 60:02}:{ticks // 100 % 60:02}.{ticks % 100:02}"


def render_ass(cues: list[dict[str, Any]]) -> str:
    header = (
        """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, """
        + "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
        + """Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,42,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,60,60,240,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    )
    groups = [list(range(index, min(index + 2, len(cues)))) for index in range(0, len(cues), 2)]
    if len(groups) > 1 and len(groups[-1]) == 1:
        groups[-1].insert(0, groups[-1][0] - 1)
    lines: list[str] = []
    for group in groups:
        for active in group:
            if group is groups[-1] and len(cues) % 2 and active != group[-1]:
                continue
            words = []
            for offset, index in enumerate(group):
                word = cues[index]["word"]
                if index == active:
                    word = "{\\c&H00FFFF&}" + word + "{\\c&HFFFFFF&}"
                words.append(word)
                if offset == 0 and len(group) > 1:
                    words.append("\\N")
            size = min(42, 540 // max(len(cues[index]["word"]) for index in group))
            caption = f"{{\\fs{size}}}" + " ".join(words)
            lines.append(
                f"Dialogue: 0,{ass_time(cues[active]['start'])},{ass_time(cues[active]['end'])},"
                f"Default,,0,0,0,,{caption}"
            )
    require(len(lines) == len(cues), "Caption event count mismatch")
    return header + "\n".join(lines) + "\n"


def validate_lineage(
    plan: dict[str, Any], content: dict[str, Any], storyboard: dict[str, Any], state: dict[str, Any], review: Path
) -> str:
    validate_video_plan(plan)
    job_id = plan.get("job_id")
    require(
        isinstance(job_id, str) and content.get("job_id") == storyboard.get("job_id") == state.get("job_id") == job_id,
        "Job lineage mismatch",
    )
    require(
        content.get("verification_status") == "PASS"
        and content.get("status") == "READY_FOR_HUMAN_REVIEW"
        and content.get("approval_status") == "PENDING_HUMAN",
        "Verified weekly package required",
    )
    require(storyboard.get("approval_status") == "PENDING_HUMAN", "Storyboard review gate required")
    require(
        content.get("planned_duration_seconds")
        == storyboard.get("planned_duration_seconds")
        == plan["target_duration_seconds"],
        "Planned duration lineage mismatch",
    )
    beats, shots = content.get("script_beats"), storyboard.get("shots")
    require(
        isinstance(beats, list) and isinstance(shots, list) and len(beats) == len(shots) == len(plan["shots"]),
        "Storyboard/plan beat count mismatch",
    )
    assert isinstance(beats, list) and isinstance(shots, list)
    for beat, shot, planned in zip(beats, shots, plan["shots"]):
        for key in ("shot_id", "duration_seconds"):
            require(beat.get(key) == shot.get(key) == planned.get(key), "Shot lineage mismatch")
        for key in ("source_claim_ids", "evidence"):
            require(key in beat and key in shot and beat[key] == shot[key], "Claim/evidence lineage mismatch")
        require(text(beat.get("text")) and beat["text"] == shot.get("voiceover"), "Script text lineage mismatch")
    require(
        state.get("status") == "PENDING_HUMAN_REVIEW"
        and state.get("publication_status") == "BLOCKED_PENDING_HUMAN_REVIEW"
        and state.get("model") == plan["model"],
        "Completed silent assembly review gate required",
    )
    require(
        all(state.get("shots", {}).get(s["shot_id"], {}).get("status") == "COMPLETED" for s in plan["shots"]),
        "Completed generation records required",
    )
    final = state.get("final_video", {})
    require(
        final.get("technical_qc") == "PASS"
        and resolve_recorded_path(str(final.get("local_path", ""))) == review.resolve(),
        "Silent assembly QC/path mismatch",
    )
    return " ".join(beat["text"] for beat in beats)


def finish(manifest_path: Path, *, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict[str, Any]:
    manifest = read_json(manifest_path)
    require(manifest.get("schema_version") == "1.0.0", "Unsupported finishing manifest")
    paths = {name: resolve_recorded_path(manifest[name]) for name in ("plan", "content_package", "storyboard")}
    plan = read_json(paths["plan"])
    runtime = resolve_runtime_paths(plan, plan_path=paths["plan"])
    review = runtime.final_video.resolve()
    job_dir = review.parent
    require(
        job_dir.is_dir() and runtime.final_video.parent.absolute() == job_dir and not runtime.final_video.is_symlink(),
        "Existing job directory/review must not be symlinked",
    )
    require(manifest.get("job_id") == plan.get("job_id"), "Finishing manifest job_id mismatch")
    outputs = [job_dir / name for name in (FINAL, REPORT, CAPTIONS, DIGEST)]
    require(
        not any(path.exists() or path.is_symlink() for path in outputs), "Existing final asset/report: use a new job"
    )
    # Exclusive lock prevents competing finishing runs; a stale lock requires
    # operator investigation, never automatic removal/replay.
    lock = job_dir / ".social-finishing.lock"
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        paths.update(
            {
                "silent_review": review,
                "generation_state": runtime.state_file.resolve(),
                "manifest": manifest_path.resolve(),
            }
        )
        audio_entries = [manifest["narration"], manifest["music"], *manifest.get("sfx", [])]
        require(len(audio_entries) <= 10, "At most eight SFX tracks supported")
        audio_paths = []
        for index, entry in enumerate(audio_entries):
            attestation(entry)
            require(text(entry.get("license")), "Approved/licensed audio provenance required")
            path = resolve_recorded_path(entry["path"])
            require(sha256(path) == entry.get("sha256"), "Approved audio bytes changed")
            require(-40 <= number(entry.get("gain_db", 0)) <= 0, "Audio gain must be -40 to 0 dB")
            if index > 1:
                require(0 <= number(entry.get("start_seconds")) < plan["target_duration_seconds"], "Invalid SFX offset")
            audio_paths.append(path)
            paths[f"audio_{index}"] = path
        require(
            manifest["narration"].get("engine") == "kokoro" and audio_paths[0].suffix.lower() == ".wav",
            "Approved Kokoro WAV required",
        )
        paths["timings"] = resolve_recorded_path(manifest["timings"])
        fingerprints = {key: sha256(path) for key, path in paths.items()}
        content, storyboard, state = (
            read_json(paths[key]) for key in ("content_package", "storyboard", "generation_state")
        )
        transcript = validate_lineage(plan, content, storyboard, state, review)
        video_meta = probe(review, ffprobe)
        video_streams = streams(video_meta, "video")
        require(
            len(video_streams) == 1 and not streams(video_meta, "audio"), "Input must be a silent single-video review"
        )
        require((video_streams[0]["width"], video_streams[0]["height"]) == (720, 1280), "Expected 720x1280 video")
        seconds = duration(video_meta)
        require(abs(seconds - plan["target_duration_seconds"]) <= 0.25, "Silent review duration mismatch")
        audio_metas = [probe(path, ffprobe) for path in audio_paths]
        require(
            all(len(streams(meta, "audio")) == 1 for meta in audio_metas), "Each audio input requires one audio stream"
        )
        input_levels = [audio_levels(path, ffmpeg) for path in audio_paths]
        require(
            audio_metas[0]["format"].get("format_name") == "wav"
            and streams(audio_metas[0], "audio")[0].get("codec_name", "").startswith("pcm_"),
            "Narration must be an actual PCM WAV",
        )
        voice_seconds = duration(audio_metas[0])
        require(voice_seconds <= seconds, "Narration must fit the silent video; no truncation/time stretching")
        require(duration(audio_metas[1]) >= seconds, "Music must cover full video; no implicit looping")
        for entry, meta in zip(audio_entries[2:], audio_metas[2:]):
            require(entry["start_seconds"] + duration(meta) <= seconds, "SFX would be truncated")
        cues = validate_cues(read_json(paths["timings"]), transcript, fingerprints["audio_0"], voice_seconds)
        filters_available = run([ffmpeg, "-hide_banner", "-filters"])
        require(
            bool(re.search(r"\bass\s", filters_available)) and "sidechaincompress" in filters_available,
            "FFmpeg with libass and sidechaincompress required (Mac: brew install ffmpeg-full)",
        )
        with tempfile.TemporaryDirectory(prefix=".social-finishing-", dir=job_dir) as temporary:
            staging = Path(temporary)
            (staging / CAPTIONS).write_text(render_ass(cues), encoding="utf-8")
            command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-i", str(review)]
            for path in audio_paths:
                command += ["-i", str(path)]
            filters = [f"[0:v]ass={CAPTIONS},format=yuv420p[v]"]
            for index, entry in enumerate(audio_entries, 1):
                filters.append(
                    f"[{index}:a]aresample=48000,aformat=channel_layouts=stereo,"
                    f"asetpts=PTS-STARTPTS,volume={entry.get('gain_db', 0)}dB,apad,atrim=duration={seconds}[a{index}]"
                )
            filters.append("[a1]asplit=2[voice][key]")
            beds = ["[a2]"]
            for index, entry in enumerate(audio_entries[2:], 3):
                filters.append(f"[a{index}]adelay={round(entry['start_seconds'] * 1000)}:all=1[s{index}]")
                beds.append(f"[s{index}]")
            filters.append("".join(beds) + f"amix=inputs={len(beds)}:normalize=0[bed]")
            filters.append("[bed][key]sidechaincompress=threshold=0.015:ratio=8:attack=10:release=250[ducked]")
            filters.append(
                f"[voice][ducked]amix=inputs=2:normalize=0,alimiter=limit=0.95:latency=1,"
                f"atrim=duration={seconds}[audio]"
            )
            command += [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[v]",
                "-map",
                "[audio]",
                "-t",
                str(seconds),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                FINAL,
            ]
            run(command, cwd=staging)
            output = staging / FINAL
            metadata = probe(output, ffprobe)
            videos, audios = streams(metadata, "video"), streams(metadata, "audio")
            require(
                len(videos) == len(audios) == 1 and len(metadata["streams"]) == 2, "Expected video and audio output"
            )
            require(
                (videos[0]["width"], videos[0]["height"], videos[0]["codec_name"]) == (720, 1280, "h264"),
                "Output dimensions/codec mismatch",
            )
            require(
                audios[0]["codec_name"] == "aac"
                and int(audios[0]["sample_rate"]) == 48000
                and audios[0]["channels"] == 2,
                "Output audio format mismatch",
            )
            require(
                abs(duration(metadata) - seconds) <= 0.15
                and all(abs(float(s["duration"]) - seconds) <= 0.15 for s in (videos[0], audios[0])),
                "Output stream duration mismatch",
            )
            run([ffmpeg, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"])
            output_levels = audio_levels(output, ffmpeg)
            require(
                all(sha256(path) == fingerprints[key] for key, path in paths.items()), "Input changed during finishing"
            )
            report = {
                "schema_version": "1.0.0",
                "job_id": plan["job_id"],
                "status": "PENDING_HUMAN_REVIEW",
                "publication_status": "BLOCKED_PENDING_HUMAN_REVIEW",
                "technical_qc": "PASS",
                "final_video": {
                    "local_path": str(outputs[0].relative_to(ROOT)),
                    "sha256": sha256(output),
                    "width": 720,
                    "height": 1280,
                    "duration_seconds": duration(metadata),
                },
                "inputs": {key: {"path": str(path), "sha256": fingerprints[key]} for key, path in paths.items()},
                "captions": {
                    "events": len(cues),
                    "words": len(transcript.split()),
                    "human_corrected": True,
                    "sha256": sha256(staging / CAPTIONS),
                },
                "qc_checks": [
                    "input_lineage",
                    "exact_wav_cues",
                    "sequential_caption_structure",
                    "dimensions",
                    "audio_format",
                    "stream_durations",
                    "full_decode",
                    "input_integrity",
                ],
                "audio_mix": "narration + licensed bed/SFX; sidechain ducking; peak limiter",
                "audio_levels_dbfs": {"inputs": input_levels, "output": output_levels},
                "ffmpeg_version": run([ffmpeg, "-version"]).splitlines()[0],
                "human_review_required": [
                    "Listen for sync, loudness and ducking",
                    "Inspect caption layout and highlights",
                    "Approve exact final bytes separately via Phase 5",
                ],
            }
            (staging / REPORT).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (staging / DIGEST).write_text(f"{report['final_video']['sha256']}  {FINAL}\n", encoding="utf-8")
            created = []
            try:
                for destination in outputs:
                    os.link(staging / destination.name, destination)  # Atomic no-clobber, including symlinks.
                    created.append(destination)
            except OSError:
                for destination in created:
                    destination.unlink()
                raise
        return report
    finally:
        lock.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    try:
        report = finish(
            args.manifest,
            ffmpeg=str(Path(args.ffmpeg).resolve()) if "/" in args.ffmpeg else args.ffmpeg,
            ffprobe=args.ffprobe,
        )
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Finishing blocked: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
