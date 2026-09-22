from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from rbl_content_engine.acceptance import evaluate_customer_zero
from rbl_content_engine.production.video_job import EXPECTED_MODEL


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_acceptance_fixture(root: Path) -> dict[str, Path]:
    job_id = "RBL-CUSTOMER-ZERO-001"
    durations = [4, 4, 4, 4, 4]
    claim_ids = [["c1"], ["c2"], ["c3"], ["c4"], []]

    content_beats = []
    storyboard_shots = []
    media_shots = []
    for index, duration in enumerate(durations, start=1):
        shot_id = f"S{index:02d}"
        beat_id = f"beat-{index}"
        source_claim_ids = claim_ids[index - 1]
        content_beats.append(
            {
                "id": beat_id,
                "shot_id": shot_id,
                "duration_seconds": duration,
                "source": "next_claim" if source_claim_ids else "theme_text",
                "text": f"Beat {index}",
                "source_claim_ids": source_claim_ids,
                "evidence": [],
                "visual_direction": f"Visual {index}",
            }
        )
        storyboard_shots.append(
            {
                "shot_id": shot_id,
                "beat_id": beat_id,
                "duration_seconds": duration,
                "voiceover": f"Beat {index}",
                "visual_direction": f"Visual {index}",
                "source_claim_ids": source_claim_ids,
                "evidence": [],
            }
        )
        media_shots.append(
            {
                "shot_id": shot_id,
                "purpose": beat_id,
                "duration_seconds": duration,
                "application": EXPECTED_MODEL,
                "estimated_cost_usd": "3.00",
                "prompt": f"Controlled synthetic test prompt for {shot_id}",
            }
        )

    content_package = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "project": "Acceptance Fixture",
        "topic": "Fixture",
        "objective": "Exercise acceptance evaluator",
        "targets": ["instagram"],
        "theme": {
            "theme_id": "fixture-theme",
            "name": "Fixture",
            "voice": "neutral",
            "visual_style": "vertical",
        },
        "planned_duration_seconds": 20,
        "status": "READY_FOR_HUMAN_REVIEW",
        "verification_status": "PASS",
        "approval_status": "PENDING_HUMAN",
        "script_beats": content_beats,
        "used_claim_ids": ["c1", "c2", "c3", "c4"],
        "unused_claim_ids": [],
        "generated_artifacts": [],
    }
    storyboard = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "theme_id": "fixture-theme",
        "visual_style": "vertical",
        "planned_duration_seconds": 20,
        "approval_status": "PENDING_HUMAN",
        "shots": storyboard_shots,
    }
    media_plan = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "title": "Acceptance Fixture Media",
        "platform_targets": ["instagram"],
        "aspect_ratio": "9:16",
        "target_duration_seconds": 20,
        "project_budget_usd": "20.00",
        "publication_policy": "PENDING_HUMAN_REVIEW_BEFORE_ANY_PUBLICATION",
        "shots": media_shots,
        "model": EXPECTED_MODEL,
        "resolution": "720p",
        "output_format": "mp4",
        "generate_audio": False,
    }

    final_video = root / "review.mp4"
    final_video.write_bytes(b"fixture-video-bytes" * 128)
    final_export = root / "instagram.mp4"
    final_export.write_bytes(final_video.read_bytes())
    asset_hash = hashlib.sha256(final_export.read_bytes()).hexdigest()

    generation_state = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "model": EXPECTED_MODEL,
        "status": "PENDING_HUMAN_REVIEW",
        "publication_status": "BLOCKED_PENDING_HUMAN_REVIEW",
        "shots": {
            shot["shot_id"]: {
                "status": "COMPLETED",
                "request_id": f"req-{shot['shot_id']}",
                "local_path": str(root / f"{shot['shot_id']}.mp4"),
                "estimated_cost_usd": "3.00",
            }
            for shot in media_shots
        },
        "final_video": {
            "local_path": str(final_video),
            "width": 720,
            "height": 1280,
            "duration_seconds": 20.0,
            "technical_qc": "PASS",
            "actual_spend_usd": None,
        },
    }
    for shot in media_shots:
        (root / f"{shot['shot_id']}.mp4").write_bytes(b"clip" * 512)

    scheduled_at = "2026-09-23T20:00:00+08:00"
    public_url = "https://media.example.invalid/customer-zero-001.mp4"
    manifest = {
        "schema_version": "1.0.0",
        "post_id": job_id,
        "scheduled_at": scheduled_at,
        "assets": {
            "instagram": {
                "path": str(final_export),
                "public_url": public_url,
                "ai_generated": True,
            }
        },
        "platforms": {
            "instagram": {
                "enabled": True,
                "caption": "Customer Zero acceptance fixture",
                "share_to_feed": True,
            }
        },
        "approval": {
            "human_confirmed": True,
            "confirmed_at": "2026-09-23T19:30:00+08:00",
            "asset_sha256": {"instagram": asset_hash},
            "asset_public_urls": {"instagram": public_url},
        },
    }
    receipt = {
        "schema_version": "1.0.0",
        "post_id": job_id,
        "scheduled_at": scheduled_at,
        "job_status": "COMPLETE",
        "platforms": {
            "instagram": {
                "status": "PUBLISHED",
                "provider_id": "provider-123",
                "container_id": "container-123",
                "completed_at": "2026-09-23T12:01:00+00:00",
            }
        },
        "asset_ai_generated": True,
        "updated_at": "2026-09-23T12:01:01+00:00",
    }

    paths = {
        "content_package": root / "content-package.json",
        "storyboard": root / "storyboard.json",
        "media_plan": root / "media-plan.json",
        "generation_state": root / "generation-state.json",
        "post_manifest": root / "post-manifest.json",
        "publication_receipt": root / "receipt.json",
    }
    write_json(paths["content_package"], content_package)
    write_json(paths["storyboard"], storyboard)
    write_json(paths["media_plan"], media_plan)
    write_json(paths["generation_state"], generation_state)
    write_json(paths["post_manifest"], manifest)
    write_json(paths["publication_receipt"], receipt)
    return paths


def evaluate(paths: dict[str, Path], *, confirmed: bool = True) -> dict:
    return evaluate_customer_zero(
        content_package_path=paths["content_package"],
        storyboard_path=paths["storyboard"],
        media_plan_path=paths["media_plan"],
        generation_state_path=paths["generation_state"],
        post_manifest_path=paths["post_manifest"],
        publication_receipt_path=paths["publication_receipt"],
        human_confirmed_real_content=confirmed,
    )


class CustomerZeroAcceptanceTests(unittest.TestCase):
    def test_complete_fixture_passes_when_human_confirms_real_content(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            result = evaluate(build_acceptance_fixture(Path(directory)))
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["failed_checks"], [])
            self.assertEqual(result["enabled_platforms"], ["instagram"])
            self.assertEqual(result["network_calls"], 0)
            self.assertEqual(result["paid_mutations"], 0)

    def test_synthetic_or_unconfirmed_run_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            result = evaluate(
                build_acceptance_fixture(Path(directory)),
                confirmed=False,
            )
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("real_content_confirmation", result["failed_checks"])

    def test_partial_publication_receipt_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            paths = build_acceptance_fixture(Path(directory))
            receipt = json.loads(
                paths["publication_receipt"].read_text(encoding="utf-8")
            )
            receipt["job_status"] = "PARTIAL"
            receipt["platforms"]["instagram"]["status"] = "FAILED"
            receipt["platforms"]["instagram"]["error"] = "provider failure"
            write_json(paths["publication_receipt"], receipt)

            result = evaluate(paths)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("publication_receipt_complete", result["failed_checks"])
            self.assertIn("enabled_platforms_complete", result["failed_checks"])
            self.assertIn("live_publication_observed", result["failed_checks"])

    def test_native_scheduled_only_is_not_enough_for_customer_zero(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            paths = build_acceptance_fixture(Path(directory))
            receipt = json.loads(
                paths["publication_receipt"].read_text(encoding="utf-8")
            )
            receipt["platforms"]["instagram"]["status"] = "NATIVE_SCHEDULED"
            write_json(paths["publication_receipt"], receipt)

            result = evaluate(paths)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("live_publication_observed", result["failed_checks"])

    def test_media_plan_must_match_storyboard_duration(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            paths = build_acceptance_fixture(Path(directory))
            media = json.loads(paths["media_plan"].read_text(encoding="utf-8"))
            media["shots"][0]["duration_seconds"] = 5
            media["target_duration_seconds"] = 21
            write_json(paths["media_plan"], media)

            result = evaluate(paths)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("media_plan_storyboard_alignment", result["failed_checks"])

    def test_generation_must_stop_at_human_review_gate(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            paths = build_acceptance_fixture(Path(directory))
            state = json.loads(
                paths["generation_state"].read_text(encoding="utf-8")
            )
            state["status"] = "APPROVED_FOR_PUBLICATION"
            write_json(paths["generation_state"], state)

            result = evaluate(paths)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("generation_state", result["failed_checks"])

    def test_changed_asset_after_approval_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".production") as directory:
            paths = build_acceptance_fixture(Path(directory))
            manifest = json.loads(paths["post_manifest"].read_text(encoding="utf-8"))
            asset_path = Path(manifest["assets"]["instagram"]["path"])
            asset_path.write_bytes(asset_path.read_bytes() + b"changed")

            result = evaluate(paths)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("publication_manifest", result["failed_checks"])


if __name__ == "__main__":
    unittest.main()
