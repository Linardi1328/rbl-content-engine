"""Synthetic-only finishing regression and optional real FFmpeg/libass validation."""

from __future__ import annotations

import copy
import math
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from rbl_content_engine.production import finishing, video_job
from rbl_content_engine.acceptance import evaluate_customer_zero
from test_customer_zero_acceptance import build_acceptance_fixture, write_json

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = os.environ.get("RBL_FFMPEG", shutil.which("ffmpeg") or "ffmpeg")
FFPROBE = os.environ.get("RBL_FFPROBE", shutil.which("ffprobe") or "ffprobe")


def attest() -> dict:
    """Return a clearly synthetic human-attestation fixture for validation tests."""
    return {"human_confirmed": True, "reviewer": "SYNTHETIC TEST ONLY", "confirmed_at": "2026-11-11T12:00:00+08:00"}


def timings() -> dict:
    """Build synthetic word cues for testing exact-WAV and human-review guards."""
    return {
        "audio_sha256": "a" * 64,
        "derivation_method": "synthetic test fixture; no real speech",
        "review_status": "HUMAN_CORRECTED",
        **attest(),
        "words": [
            {"word": word, "start": index * 0.15, "end": (index + 1) * 0.15, "verified": True}
            for index, word in enumerate("ONE MORE SHOT".split())
        ],
    }


def wav(path: Path, seconds: float, frequency: int, active_seconds: float | None = None) -> None:
    """Write a local PCM test tone with an optional silent tail."""
    with wave.open(str(path), "wb") as handle:
        handle.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        samples = (
            int(10000 * math.sin(2 * math.pi * frequency * i / 48000))
            if active_seconds is None or i / 48000 < active_seconds
            else 0
            for i in range(round(seconds * 48000))
        )
        handle.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))


def prepare(root: Path) -> tuple[dict[str, Path], Path, Path]:
    """Create synthetic weekly records, silent media and licensed-tone finishing inputs."""
    paths = build_acceptance_fixture(root)
    plan = finishing.read_json(paths["media_plan"])
    job = root / "jobs" / plan["job_id"]
    job.mkdir(parents=True)
    review = job / "review.mp4"
    finishing.run(
        [
            FFMPEG,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=navy:s=720x1280:r=24:d=20",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            str(review),
        ]
    )
    state = finishing.read_json(paths["generation_state"])
    state["final_video"]["local_path"] = str(review)
    paths["generation_state"] = job / "higgsfield-state.json"
    write_json(paths["generation_state"], state)
    voice, music, sfx = (root / name for name in ("synthetic-voice.wav", "synthetic-music.wav", "synthetic-sfx.wav"))
    wav(voice, 5, 880, active_seconds=2)
    wav(music, 20, 220)
    wav(sfx, 0.1, 440)
    cues = timings()
    cues["audio_sha256"] = finishing.sha256(voice)
    cues["words"] = [
        {"word": word, "start": index * 0.15, "end": (index + 1) * 0.15, "verified": True}
        for index, word in enumerate("Beat 1 Beat 2 Beat 3 Beat 4 Beat 5".split())
    ]
    timing_path = root / "timings.json"
    write_json(timing_path, cues)

    def audio(path: Path, gain: int) -> dict:
        """Bind a synthetic tone to its hash, gain and test-only rights attestation."""
        return {
            "path": str(path),
            "sha256": finishing.sha256(path),
            "gain_db": gain,
            "license": "Original generated synthetic test tones only",
            **attest(),
        }

    manifest = {
        "schema_version": "1.0.0",
        "job_id": plan["job_id"],
        "plan": str(paths["media_plan"]),
        "content_package": str(paths["content_package"]),
        "storyboard": str(paths["storyboard"]),
        "narration": {**audio(voice, 0), "engine": "kokoro"},
        "music": audio(music, -18),
        "sfx": [{**audio(sfx, -12), "start_seconds": 10}],
        "timings": str(timing_path),
    }
    manifest_path = root / "finishing.json"
    write_json(manifest_path, manifest)
    return paths, manifest_path, job


class CueTests(unittest.TestCase):
    def test_valid_cues_render_one_highlight_per_word_with_context(self) -> None:
        """Check each word gets exactly one highlight while adjacent context stays visible."""
        cue_list = finishing.validate_cues(timings(), "ONE MORE SHOT", "a" * 64, 1)
        events = [line for line in finishing.render_ass(cue_list).splitlines() if line.startswith("Dialogue:")]
        self.assertEqual(len(events), 3)
        for event in events:
            self.assertEqual(event.count("\\c&H00FFFF&"), 1)
            self.assertIn("\\N", event)
        self.assertIn("{\\c&H00FFFF&}SHOT", events[-1])

    def test_bad_cues_fail_closed(self) -> None:
        """Reject incomplete, unordered, unsafe or unverified timing inputs."""
        mutations = {
            "missing": lambda t: t["words"].pop(),
            "extra": lambda t: t["words"].append(t["words"][-1]),
            "out of order": lambda t: t["words"].reverse(),
            "overlap": lambda t: t["words"][1].update(start=0.1),
            "negative": lambda t: t["words"][0].update(start=-1),
            "nan": lambda t: t["words"][0].update(start=float("nan")),
            "boolean": lambda t: t["words"][0].update(start=False),
            "zero": lambda t: t["words"][0].update(end=0),
            "sub-centisecond": lambda t: t["words"][0].update(end=0.001),
            "unverified word": lambda t: t["words"][1].update(verified=False),
            "wrong WAV": lambda t: t.update(audio_sha256="b" * 64),
            "unverified alignment": lambda t: t.update(review_status="NOT_HUMAN_VERIFIED"),
            "no derivation": lambda t: t.pop("derivation_method"),
            "no human": lambda t: t.update(human_confirmed=False),
            "naive timestamp": lambda t: t.update(confirmed_at="2026-11-11T12:00:00"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                candidate = copy.deepcopy(timings())
                mutate(candidate)
                with self.assertRaises(ValueError):
                    finishing.validate_cues(candidate, "ONE MORE SHOT", "a" * 64, 1)
        with self.assertRaises(ValueError):
            finishing.validate_cues(timings(), "ONE MORE SHOT", "a" * 64, 0.2)


class AttestationTests(unittest.TestCase):
    def test_valid_nonblank_attestations_remain_accepted(self) -> None:
        """Preserve manual attestations without guessing license validity or alignment."""
        for value in (
            "Owner",
            "  Licensed original score  ",
            "Manual alignment from actual WAV",
            "REPLACE_WITH_REVIEWER is a quoted label in this description",
        ):
            self.assertTrue(finishing.attested_text(value))
        finishing.attestation(attest())
        finishing.timing_attestation(timings())

    def test_placeholders_fail_before_media_commands_without_state_changes(self) -> None:
        """Reject template/blank attestations despite affirmative flags, before any subprocess."""
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            root = Path(directory)
            paths = build_acceptance_fixture(root)
            plan = finishing.read_json(paths["media_plan"])
            job = root / "jobs" / plan["job_id"]
            job.mkdir(parents=True)
            review = job / "review.mp4"
            review.write_bytes(b"synthetic silent media; must not be probed")
            state = finishing.read_json(paths["generation_state"])
            state["final_video"]["local_path"] = str(review)
            write_json(job / "higgsfield-state.json", state)
            # Deliberately non-media bytes prove these guards run before probing,
            # loudness analysis, libass discovery, or rendering is even attempted.
            voice = root / "voice.wav"
            voice.write_bytes(b"synthetic audio; must not be decoded")
            audio = {
                "path": str(voice),
                "sha256": finishing.sha256(voice),
                "gain_db": 0,
                "license": "Original synthetic fixture",
                **attest(),
            }
            manifest = {
                "schema_version": "1.0.0",
                "job_id": plan["job_id"],
                "plan": str(paths["media_plan"]),
                "content_package": str(paths["content_package"]),
                "storyboard": str(paths["storyboard"]),
                "narration": {**audio, "engine": "kokoro"},
                "music": dict(audio),
                "sfx": [{**audio, "start_seconds": 10}],
                "timings": str(root / "timings.json"),
            }
            timing = timings()
            timing["audio_sha256"] = finishing.sha256(voice)
            manifest_path = root / "finishing.json"
            cases = [
                (track, field, sentinel)
                for track in ("narration", "music", "sfx")
                for field, sentinel in (
                    ("reviewer", "REPLACE_WITH_REVIEWER"),
                    ("license", "REPLACE_WITH_APPROVED_LICENSE_AND_SOURCE"),
                )
            ]
            cases += [
                ("timing", "reviewer", "REPLACE_WITH_REVIEWER"),
                ("timing", "derivation_method", "REPLACE_WITH_METHOD_DERIVED_FROM_ACTUAL_WAV"),
            ]
            for track, field, sentinel in cases:
                for invalid in (sentinel, f"  {sentinel}  ", "", "   "):
                    with self.subTest(track=track, field=field, value=invalid):
                        candidate, cue_input = copy.deepcopy(manifest), copy.deepcopy(timing)
                        record = (
                            cue_input
                            if track == "timing"
                            else candidate["sfx"][0]
                            if track == "sfx"
                            else candidate[track]
                        )
                        record[field] = invalid
                        self.assertTrue(record["human_confirmed"])
                        self.assertEqual(record["confirmed_at"], "2026-11-11T12:00:00+08:00")
                        self.assertEqual(cue_input["review_status"], "HUMAN_CORRECTED")
                        self.assertTrue(all(cue["verified"] for cue in cue_input["words"]))
                        write_json(manifest_path, candidate)
                        write_json(root / "timings.json", cue_input)
                        before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
                        with (
                            patch.object(video_job, "JOB_ROOT", root / "jobs"),
                            patch.object(finishing.subprocess, "run") as subprocess_run,
                        ):
                            with self.assertRaises(ValueError):
                                finishing.finish(manifest_path)
                            subprocess_run.assert_not_called()
                        after = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
                        self.assertEqual(after, before)
                        self.assertFalse((job / ".social-finishing.lock").exists())
                        self.assertEqual(
                            sorted(path.name for path in job.iterdir()), ["higgsfield-state.json", "review.mp4"]
                        )
            # Valid attestations must pass the same preflight and reach probing.
            write_json(manifest_path, manifest)
            write_json(root / "timings.json", timing)
            with (
                patch.object(video_job, "JOB_ROOT", root / "jobs"),
                patch.object(finishing.subprocess, "run", side_effect=RuntimeError("media probing reached")) as probe,
            ):
                with self.assertRaisesRegex(RuntimeError, "media probing reached"):
                    finishing.finish(manifest_path)
                probe.assert_called_once()


class FinishingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """Require a local libass-enabled FFmpeg before running media integration tests."""
        if not shutil.which(FFMPEG) or " ass " not in finishing.run([FFMPEG, "-hide_banner", "-filters"]):
            raise unittest.SkipTest("Set RBL_FFMPEG to a libass-enabled FFmpeg for media integration")

    def test_real_render_ducking_integrity_no_clobber_and_acceptance(self) -> None:
        """Verify rendered media, ducking, immutable outputs and finished-file acceptance lineage."""
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            root = Path(directory)
            paths, manifest, job = prepare(root)
            state_before = paths["generation_state"].read_bytes()
            review_hash = finishing.sha256(job / "review.mp4")
            with patch.object(video_job, "JOB_ROOT", root / "jobs"):
                report = finishing.finish(manifest, ffmpeg=FFMPEG, ffprobe=FFPROBE)
                with self.assertRaisesRegex(ValueError, "Existing final"):
                    finishing.finish(manifest, ffmpeg=FFMPEG, ffprobe=FFPROBE)
            self.assertEqual(report["status"], "PENDING_HUMAN_REVIEW")
            self.assertEqual(paths["generation_state"].read_bytes(), state_before)
            self.assertEqual(finishing.sha256(job / "review.mp4"), review_hash)
            final = job / finishing.FINAL
            self.assertEqual(finishing.sha256(final), report["final_video"]["sha256"])
            self.assertEqual(report["captions"]["events"], 10)
            self.assertEqual((job / finishing.DIGEST).read_text().split()[0], finishing.sha256(final))

            # Measure the 220Hz music component under voice and in a later quiet
            # interval. This tests actual sidechain behavior, rather than graph text.
            def music_amplitude(start: float) -> float:
                """Measure the synthetic music frequency in a decoded half-second audio window."""
                raw = subprocess.run(
                    [
                        FFMPEG,
                        "-v",
                        "error",
                        "-ss",
                        str(start),
                        "-i",
                        str(final),
                        "-t",
                        "0.5",
                        "-vn",
                        "-ac",
                        "1",
                        "-ar",
                        "48000",
                        "-f",
                        "s16le",
                        "-",
                    ],
                    capture_output=True,
                    check=True,
                ).stdout
                values = struct.unpack(f"<{len(raw) // 2}h", raw)
                return abs(sum(v * math.sin(2 * math.pi * 220 * i / 48000) for i, v in enumerate(values))) / len(values)

            self.assertLess(music_amplitude(1), music_amplitude(8) * 0.5)
            # Copy exact bytes into the previously synthetic approved export,
            # then record a new synthetic approval hash for evaluator regression.
            post = finishing.read_json(paths["post_manifest"])
            shutil.copyfile(final, post["assets"]["instagram"]["path"])
            post["approval"]["asset_sha256"]["instagram"] = finishing.sha256(final)
            write_json(paths["post_manifest"], post)
            arguments = {f"{key}_path": path for key, path in paths.items()}
            result = evaluate_customer_zero(**arguments, human_confirmed_real_content=True)
            self.assertEqual(result["status"], "PASS", result["failed_checks"])
            approved_hash = post["approval"]["asset_sha256"]["instagram"]
            # A newly approved but different export still cannot sever lineage.
            alternate = Path(post["assets"]["instagram"]["path"])
            alternate.write_bytes(b"different approved export")
            post["approval"]["asset_sha256"]["instagram"] = finishing.sha256(alternate)
            write_json(paths["post_manifest"], post)
            result = evaluate_customer_zero(**arguments, human_confirmed_real_content=True)
            self.assertIn("social_finishing_lineage", result["failed_checks"])
            shutil.copyfile(final, alternate)
            post["approval"]["asset_sha256"]["instagram"] = approved_hash
            write_json(paths["post_manifest"], post)
            # Even an otherwise complete fixture fails if upstream bytes drift.
            content = paths["content_package"]
            content.write_text(content.read_text() + "\n")
            result = evaluate_customer_zero(**arguments, human_confirmed_real_content=True)
            self.assertIn("social_finishing_lineage", result["failed_checks"])

    def test_blocked_inputs_never_emit_final_or_change_state(self) -> None:
        """Ensure invalid inputs and occupied output paths preserve upstream state."""
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            root = Path(directory)
            paths, manifest_path, job = prepare(root)
            manifest = finishing.read_json(manifest_path)
            original_state = paths["generation_state"].read_bytes()
            for label in ("license", "drift", "script", "lock", "existing", "symlink"):
                with self.subTest(label=label), patch.object(video_job, "JOB_ROOT", root / "jobs"):
                    candidate = copy.deepcopy(manifest)
                    if label == "license":
                        candidate["music"]["license"] = ""
                    elif label == "drift":
                        candidate["narration"]["sha256"] = "0" * 64
                    elif label == "script":
                        cue_path = Path(candidate["timings"])
                        cues = finishing.read_json(cue_path)
                        cues["words"][0]["word"] = "Invented"
                        write_json(cue_path, cues)
                    elif label == "lock":
                        (job / ".social-finishing.lock").touch()
                    elif label == "existing":
                        (job / finishing.FINAL).write_bytes(b"approved bytes")
                    elif label == "symlink":
                        (job / finishing.FINAL).symlink_to(job / "absent.mp4")
                    write_json(manifest_path, candidate)
                    with self.assertRaises((ValueError, FileExistsError)):
                        finishing.finish(manifest_path, ffmpeg=FFMPEG, ffprobe=FFPROBE)
                    self.assertEqual(paths["generation_state"].read_bytes(), original_state)
                    self.assertFalse((job / finishing.REPORT).exists())
                    if label == "existing":
                        self.assertEqual((job / finishing.FINAL).read_bytes(), b"approved bytes")
                    if label in ("existing", "symlink"):
                        (job / finishing.FINAL).unlink()
                    if label == "lock":
                        (job / ".social-finishing.lock").unlink()
                    if label == "script":
                        cues["words"][0]["word"] = "Beat"
                        write_json(cue_path, cues)

    def test_decode_failure_does_not_install_outputs(self) -> None:
        """Verify failed decode QC leaves no installed finishing outputs or state changes."""
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            root = Path(directory)
            paths, manifest, job = prepare(root)
            state_before = paths["generation_state"].read_bytes()
            real_run = finishing.run

            def fail_decode(command: list[str], *, cwd: Path | None = None) -> str:
                """Simulate a decode failure while allowing other local media commands to run."""
                if "-xerror" in command:
                    raise subprocess.CalledProcessError(1, command, stderr="synthetic decode failure")
                return real_run(command, cwd=cwd)

            with patch.object(video_job, "JOB_ROOT", root / "jobs"), patch.object(finishing, "run", fail_decode):
                with self.assertRaises(subprocess.CalledProcessError):
                    finishing.finish(manifest, ffmpeg=FFMPEG, ffprobe=FFPROBE)
            self.assertEqual(paths["generation_state"].read_bytes(), state_before)
            for name in (
                finishing.FINAL,
                finishing.REPORT,
                finishing.CAPTIONS,
                finishing.DIGEST,
                ".social-finishing.lock",
            ):
                self.assertFalse((job / name).exists())
