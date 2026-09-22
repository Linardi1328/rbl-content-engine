from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

from rbl_content_engine.publishing.core import (
    HttpResponse,
    InstagramReelsPublisher,
    PublishBlocked,
    PublishError,
    ScheduleQueue,
    TikTokPublisher,
    YouTubePublisher,
    _tiktok_chunk_plan,
    approve_post_manifest,
    publish_due_jobs,
    validate_post_manifest,
)


class FakeTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
        timeout: int = 120,
    ) -> HttpResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "body": body,
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        return self.responses.pop(0)


def response(
    payload: Mapping[str, Any] | None = None,
    *,
    status: int = 200,
    headers: Mapping[str, str] | None = None,
) -> HttpResponse:
    body = b"" if payload is None else json.dumps(payload).encode("utf-8")
    return HttpResponse(status=status, headers=dict(headers or {}), body=body)


def make_manifest(tmp: Path, scheduled_at: str = "2026-10-02T19:30:00+08:00") -> dict[str, Any]:
    default = tmp / "master.mp4"
    instagram = tmp / "instagram.mp4"
    tiktok = tmp / "tiktok.mp4"
    youtube = tmp / "youtube.mp4"
    for path in (default, instagram, tiktok, youtube):
        path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 4096)

    manifest = {
        "schema_version": "1.0.0",
        "post_id": "RBL-TEST-001",
        "scheduled_at": scheduled_at,
        "assets": {
            "default": {"path": str(default), "ai_generated": True},
            "instagram": {
                "path": str(instagram),
                "public_url": "https://media.example.test/rbl-test.mp4",
                "ai_generated": True,
            },
            "tiktok": {
                "path": str(tiktok),
                "ai_generated": True,
                "promotional_overlay_free": True,
            },
            "youtube": {"path": str(youtube), "ai_generated": True},
        },
        "platforms": {
            "instagram": {
                "enabled": True,
                "caption": "Do good.",
                "share_to_feed": True,
            },
            "tiktok": {
                "enabled": True,
                "caption": "Character matters #DoGood",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "consent": {
                    "confirmed": True,
                    "confirmed_at": "2026-10-02T18:00:00+08:00",
                    "previewed": True,
                    "metadata_editable": True,
                    "music_usage_confirmed": True,
                },
            },
            "youtube": {
                "enabled": True,
                "title": "Do Good | RBL Productions",
                "description": "Character matters.",
                "tags": ["character", "good deeds"],
                "privacy_status": "public",
            },
        },
    }
    manifest["approval"] = {
        "human_confirmed": True,
        "confirmed_at": "2026-10-02T18:15:00+08:00",
        "asset_sha256": {
            "instagram": hashlib.sha256(instagram.read_bytes()).hexdigest(),
            "tiktok": hashlib.sha256(tiktok.read_bytes()).hexdigest(),
            "youtube": hashlib.sha256(youtube.read_bytes()).hexdigest(),
        },
    }
    return manifest


class PublishingManifestTests(unittest.TestCase):
    def test_manifest_requires_final_human_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(Path(directory))
            del manifest["approval"]
            with self.assertRaisesRegex(PublishBlocked, "human publication approval"):
                validate_post_manifest(manifest)

    def test_manifest_requires_explicit_human_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(Path(directory))
            manifest["approval"]["human_confirmed"] = False
            with self.assertRaisesRegex(PublishBlocked, "human_confirmed"):
                validate_post_manifest(manifest)

    def test_manifest_blocks_asset_changed_after_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_manifest(root)
            Path(manifest["assets"]["youtube"]["path"]).write_bytes(
                b"changed after approval"
            )
            with self.assertRaisesRegex(PublishBlocked, "changed after human approval"):
                validate_post_manifest(manifest)

    def test_approve_post_manifest_hashes_current_enabled_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_manifest(root)
            del manifest["approval"]
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            approved = approve_post_manifest(
                path,
                human_confirmed=True,
                confirmed_at=datetime(2026, 10, 2, 10, 15, tzinfo=timezone.utc),
            )

            self.assertTrue(approved["approval"]["human_confirmed"])
            self.assertEqual(
                set(approved["approval"]["asset_sha256"]),
                {"instagram", "tiktok", "youtube"},
            )
            validate_post_manifest(json.loads(path.read_text(encoding="utf-8")))

    def test_approve_post_manifest_requires_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_manifest(root)
            del manifest["approval"]
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(PublishBlocked, "explicit human confirmation"):
                approve_post_manifest(path, human_confirmed=False)

    def test_manifest_requires_timezone_aware_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(Path(directory))
            manifest["scheduled_at"] = "2026-10-02T19:30:00"
            with self.assertRaises(ValueError):
                validate_post_manifest(manifest)

    def test_tiktok_requires_overlay_free_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(Path(directory))
            manifest["assets"]["tiktok"]["promotional_overlay_free"] = False
            with self.assertRaisesRegex(ValueError, "promotional_overlay_free"):
                validate_post_manifest(manifest)

    def test_tiktok_requires_per_post_consent_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(Path(directory))
            del manifest["platforms"]["tiktok"]["consent"]
            with self.assertRaisesRegex(ValueError, "consent"):
                validate_post_manifest(manifest)

    def test_instagram_requires_public_https_video_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(Path(directory))
            del manifest["assets"]["instagram"]["public_url"]
            with self.assertRaisesRegex(ValueError, "public_url"):
                validate_post_manifest(manifest)


class ScheduleQueueTests(unittest.TestCase):
    def test_queue_orders_jobs_by_scheduled_datetime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = ScheduleQueue(root / "queue.json")
            later = make_manifest(root, "2026-10-03T19:30:00+08:00")
            later["post_id"] = "later"
            earlier = make_manifest(root, "2026-10-02T19:30:00+08:00")
            earlier["post_id"] = "earlier"
            lp = root / "later.json"
            ep = root / "earlier.json"
            lp.write_text(json.dumps(later), encoding="utf-8")
            ep.write_text(json.dumps(earlier), encoding="utf-8")
            queue.add_manifest(lp)
            queue.add_manifest(ep)
            self.assertEqual([job.job_id for job in queue.jobs], ["earlier", "later"])

    def test_due_job_isolated_per_platform(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_manifest(root, "2026-01-01T00:00:00+00:00")
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            queue = ScheduleQueue(root / "queue.json")
            queue.add_manifest(path)

            class Good:
                def publish(self, manifest: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
                    return {"status": "PUBLISHED", "provider_id": "ok"}

            class Bad:
                def publish(self, manifest: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
                    raise PublishError("provider failed")

            def factory(platform: str) -> Any:
                return Bad() if platform == "instagram" else Good()

            events = publish_due_jobs(
                queue,
                now=datetime(2026, 10, 2, tzinfo=timezone.utc),
                receipt_dir=root / "receipts",
                publisher_factory=factory,
            )
            state = queue.jobs[0].platforms
            self.assertEqual(state["instagram"]["status"], "FAILED")
            self.assertEqual(state["youtube"]["status"], "PUBLISHED")
            # Fake TikTok publisher returns PUBLISHED directly in this test.
            self.assertEqual(state["tiktok"]["status"], "PUBLISHED")
            self.assertEqual(queue.jobs[0].status, "PARTIAL")
            self.assertTrue(events)

    def test_uncertain_in_progress_state_is_never_blindly_resubmitted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_manifest(root, "2026-01-01T00:00:00+00:00")
            manifest["platforms"] = {
                "youtube": manifest["platforms"]["youtube"]
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            queue = ScheduleQueue(root / "queue.json")
            job = queue.add_manifest(path)
            job.platforms["youtube"]["status"] = "IN_PROGRESS"
            queue.save()

            called = False

            def factory(platform: str) -> Any:
                nonlocal called
                called = True
                raise AssertionError("must not resubmit uncertain mutation")

            publish_due_jobs(
                queue,
                now=datetime(2026, 10, 2, tzinfo=timezone.utc),
                receipt_dir=root / "receipts",
                publisher_factory=factory,
            )
            self.assertFalse(called)
            self.assertEqual(
                queue.jobs[0].platforms["youtube"]["status"],
                "RECONCILE_REQUIRED",
            )


class InstagramPublisherTests(unittest.TestCase):
    def test_reel_create_status_publish_flow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(Path(directory))
            transport = FakeTransport(
                [
                    response({"id": "container-1"}),
                    response({"status_code": "FINISHED", "status": "Finished"}),
                    response({"id": "media-1"}),
                ]
            )
            publisher = InstagramReelsPublisher(
                graph_version="v99.0",
                ig_user_id="ig-1",
                access_token="secret",
                transport=transport,
                sleep=lambda _: None,
            )
            result = publisher.publish(
                manifest, manifest["platforms"]["instagram"]
            )
            self.assertEqual(result["status"], "PUBLISHED")
            self.assertEqual(result["provider_id"], "media-1")
            self.assertEqual(len(transport.calls), 3)
            self.assertIn("/media_publish", transport.calls[2]["url"])
            self.assertTrue(transport.calls[0]["url"].startswith("https://graph.instagram.com/"))
            self.assertTrue(transport.calls[1]["url"].startswith("https://graph.instagram.com/"))
            self.assertTrue(transport.calls[2]["url"].startswith("https://graph.instagram.com/"))


class TikTokPublisherTests(unittest.TestCase):
    def test_from_env_refreshes_short_lived_access_token_and_persists_rotated_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "tiktok-token.json"
            transport = FakeTransport(
                [
                    response(
                        {
                            "access_token": "new-access",
                            "refresh_token": "new-refresh",
                            "expires_in": 86400,
                            "refresh_expires_in": 31536000,
                            "scope": "video.publish",
                            "open_id": "creator-1",
                            "token_type": "Bearer",
                        }
                    )
                ]
            )
            env = {
                "TIKTOK_CLIENT_KEY": "client-key",
                "TIKTOK_CLIENT_SECRET": "client-secret",
                "TIKTOK_REFRESH_TOKEN": "old-refresh",
                "TIKTOK_TOKEN_STATE_PATH": str(state),
            }
            with patch.dict(os.environ, env, clear=False):
                publisher = TikTokPublisher.from_env(transport=transport)
            self.assertEqual(publisher.access_token, "new-access")
            stored = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(stored["refresh_token"], "new-refresh")
            self.assertNotIn("new-access", state.read_text(encoding="utf-8"))
            body = transport.calls[0]["body"].decode("utf-8")
            self.assertIn("grant_type=refresh_token", body)

    def test_small_file_uses_one_chunk(self) -> None:
        size = 4 * 1024 * 1024
        self.assertEqual(_tiktok_chunk_plan(size), (size, 1))

    def test_direct_post_queries_creator_marks_aigc_and_uploads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(Path(directory))
            transport = FakeTransport(
                [
                    response(
                        {
                            "data": {
                                "creator_username": "rbl",
                                "privacy_level_options": ["PUBLIC_TO_EVERYONE"],
                            },
                            "error": {"code": "ok", "message": ""},
                        }
                    ),
                    response(
                        {
                            "data": {
                                "publish_id": "tt-pub-1",
                                "upload_url": "https://upload.example.test/tiktok",
                            },
                            "error": {"code": "ok", "message": ""},
                        }
                    ),
                    response({}, status=201),
                ]
            )
            publisher = TikTokPublisher(
                access_token="secret",
                transport=transport,
            )
            result = publisher.publish(
                manifest, manifest["platforms"]["tiktok"]
            )
            self.assertEqual(result["status"], "SUBMITTED")
            init_payload = json.loads(transport.calls[1]["body"].decode("utf-8"))
            self.assertTrue(init_payload["post_info"]["is_aigc"])
            self.assertEqual(
                init_payload["post_info"]["privacy_level"],
                "PUBLIC_TO_EVERYONE",
            )
            self.assertEqual(transport.calls[2]["method"], "PUT")

    def test_tiktok_submission_uses_submitted_at_until_reconciliation_completes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_manifest(root, "2026-01-01T00:00:00+00:00")
            manifest["platforms"] = {
                "tiktok": manifest["platforms"]["tiktok"]
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            queue = ScheduleQueue(root / "queue.json")
            queue.add_manifest(path)

            class SubmittedThenPublished:
                def publish(
                    self,
                    manifest: Mapping[str, Any],
                    config: Mapping[str, Any],
                ) -> dict[str, Any]:
                    return {
                        "status": "SUBMITTED",
                        "provider_id": "tt-pub-1",
                    }

                def check_status(self, publish_id: str) -> dict[str, Any]:
                    self_publish_id = publish_id
                    if self_publish_id != "tt-pub-1":
                        raise AssertionError("unexpected publish id")
                    return {
                        "status": "PUBLISHED",
                        "provider_id": publish_id,
                        "public_post_ids": [],
                    }

            publisher = SubmittedThenPublished()
            factory = lambda platform: publisher

            publish_due_jobs(
                queue,
                now=datetime(2026, 10, 2, tzinfo=timezone.utc),
                receipt_dir=root / "receipts",
                publisher_factory=factory,
            )
            first = queue.jobs[0].platforms["tiktok"]
            self.assertEqual(first["status"], "SUBMITTED")
            self.assertIn("submitted_at", first)
            self.assertNotIn("completed_at", first)

            publish_due_jobs(
                queue,
                now=datetime(2026, 10, 2, tzinfo=timezone.utc),
                receipt_dir=root / "receipts",
                publisher_factory=factory,
            )
            final = queue.jobs[0].platforms["tiktok"]
            self.assertEqual(final["status"], "PUBLISHED")
            self.assertIn("completed_at", final)
            self.assertEqual(queue.jobs[0].status, "COMPLETE")

    def test_missing_music_confirmation_blocks_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(Path(directory))
            config = dict(manifest["platforms"]["tiktok"])
            consent = dict(config["consent"])
            consent["music_usage_confirmed"] = False
            config["consent"] = consent
            publisher = TikTokPublisher(
                access_token="secret",
                transport=FakeTransport([]),
            )
            with self.assertRaises(PublishBlocked):
                publisher.publish(manifest, config)


class YouTubePublisherTests(unittest.TestCase):
    def test_upload_sets_synthetic_media_disclosure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(
                Path(directory), "2026-01-01T00:00:00+00:00"
            )
            transport = FakeTransport(
                [
                    response(None, headers={"Location": "https://upload.example/youtube"}),
                    response({"id": "yt-1"}),
                ]
            )
            publisher = YouTubePublisher(
                access_token="secret",
                transport=transport,
            )
            result = publisher.publish(
                manifest, manifest["platforms"]["youtube"]
            )
            self.assertEqual(result["status"], "PUBLISHED")
            metadata = json.loads(transport.calls[0]["body"].decode("utf-8"))
            self.assertTrue(metadata["status"]["containsSyntheticMedia"])
            self.assertEqual(metadata["status"]["privacyStatus"], "public")

    def test_future_upload_uses_native_private_publish_at(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_manifest(
                Path(directory), "2099-01-01T00:00:00+00:00"
            )
            transport = FakeTransport(
                [
                    response(None, headers={"Location": "https://upload.example/youtube"}),
                    response({"id": "yt-2"}),
                ]
            )
            publisher = YouTubePublisher(
                access_token="secret",
                transport=transport,
            )
            result = publisher.publish(
                manifest, manifest["platforms"]["youtube"]
            )
            self.assertEqual(result["status"], "NATIVE_SCHEDULED")
            metadata = json.loads(transport.calls[0]["body"].decode("utf-8"))
            self.assertEqual(metadata["status"]["privacyStatus"], "private")
            self.assertIn("publishAt", metadata["status"])


if __name__ == "__main__":
    unittest.main()
