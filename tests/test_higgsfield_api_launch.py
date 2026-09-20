import json
import unittest
from pathlib import Path
from decimal import Decimal

from rbl_content_engine.production.contracts import QCStatus
from rbl_content_engine.production.higgsfield_api import (
    HIGGSFIELD_API_PROVIDER_ID,
    HiggsfieldApiGenerationRequest,
    extract_first_media_url,
    submit_generation,
    upload_reference,
    wait_for_result,
)
from rbl_content_engine.production.launch import (
    LaunchProject,
    LaunchShot,
    LaunchShotResult,
    LaunchStatus,
    approve_for_publication,
    prepare_human_review,
)
from rbl_content_engine.production.providers import CostUnit


class FakeController:
    request_id = "request-123"

    def get(self):
        return {"video": {"url": "https://example.invalid/output.mp4"}}


class FakeClient:
    def __init__(self):
        self.submissions = []

    def submit(self, application, arguments):
        self.submissions.append((application, dict(arguments)))
        return FakeController()

    def upload_file(self, path):
        return f"https://example.invalid/uploads/{path.split('/')[-1]}"


def launch_project() -> LaunchProject:
    return LaunchProject(
        launch_id="RBL-LAUNCH-001",
        title="RBL Content Engine Launch",
        platform_targets=("instagram", "tiktok", "youtube_shorts"),
        shots=(
            LaunchShot(
                shot_id="S01",
                purpose="Hook",
                duration_seconds=Decimal("5"),
                application="catalog/model/image-to-video",
                estimated_cost_usd=Decimal("2"),
                prompt="Controlled launch hook.",
            ),
            LaunchShot(
                shot_id="S02",
                purpose="Proof",
                duration_seconds=Decimal("5"),
                application="catalog/model/image-to-video",
                estimated_cost_usd=Decimal("2"),
                prompt="Controlled proof shot.",
            ),
        ),
        project_budget_usd=Decimal("10"),
    )


class HiggsfieldApiLaunchTests(unittest.TestCase):
    def test_api_request_retains_usd_quote(self) -> None:
        request = HiggsfieldApiGenerationRequest(
            application="catalog/model/image-to-video",
            arguments={"prompt": "test"},
            quote_usd=Decimal("1.25"),
            purpose="launch shot",
        )
        quote = request.quote()
        self.assertEqual(quote.provider_id, HIGGSFIELD_API_PROVIDER_ID)
        self.assertEqual(quote.unit, CostUnit.USD)
        self.assertEqual(quote.amount, Decimal("1.25"))


    def test_unresolved_catalog_application_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "resolved from the live Higgsfield API catalog"):
            HiggsfieldApiGenerationRequest(
                application="LIVE_CATALOG_REQUIRED",
                arguments={"prompt": "test"},
                quote_usd=Decimal("1"),
                purpose="launch shot",
            )

    def test_checked_in_launch_plan_is_review_gated_and_within_budget(self) -> None:
        payload = json.loads(
            Path("examples/production/rbl-launch-video-plan.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            payload["publication_policy"],
            "PENDING_HUMAN_REVIEW_BEFORE_ANY_PUBLICATION",
        )
        self.assertEqual(payload["aspect_ratio"], "9:16")
        self.assertEqual(len(payload["shots"]), 5)
        self.assertEqual(
            sum(Decimal(shot["estimated_cost_usd"]) for shot in payload["shots"]),
            Decimal("15.00"),
        )
        self.assertLessEqual(Decimal("15.00"), Decimal(payload["project_budget_usd"]))
        self.assertTrue(
            all(shot["application"] == "bytedance/seedance-2.5/text-to-video" for shot in payload["shots"])
        )

    def test_adapter_submits_exactly_once_and_preserves_request_id(self) -> None:
        client = FakeClient()
        request = HiggsfieldApiGenerationRequest(
            application="catalog/model/image-to-video",
            arguments={"prompt": "test", "duration": 5},
            quote_usd=Decimal("1.00"),
            purpose="test shot",
        )
        submission, controller = submit_generation(request, client=client)
        self.assertEqual(submission.request_id, "request-123")
        self.assertEqual(len(client.submissions), 1)
        self.assertIs(controller.__class__, FakeController)

    def test_wait_uses_existing_controller_without_resubmission(self) -> None:
        result = wait_for_result(FakeController())
        self.assertEqual(result["video"]["url"], "https://example.invalid/output.mp4")

    def test_upload_reference_uses_sdk_upload(self) -> None:
        url = upload_reference("/tmp/ref.png", client=FakeClient())
        self.assertEqual(url, "https://example.invalid/uploads/ref.png")

    def test_media_url_extraction_handles_video_and_image(self) -> None:
        self.assertEqual(
            extract_first_media_url({"video": {"url": "https://x/video.mp4"}}),
            "https://x/video.mp4",
        )
        self.assertEqual(
            extract_first_media_url({"images": [{"url": "https://x/image.png"}]}),
            "https://x/image.png",
        )

    def test_launch_budget_blocks_estimated_overrun(self) -> None:
        with self.assertRaisesRegex(ValueError, "estimated shot spend exceeds"):
            LaunchProject(
                launch_id="L",
                title="Launch",
                platform_targets=("instagram",),
                shots=(
                    LaunchShot(
                        "S01",
                        "hook",
                        Decimal("5"),
                        "app",
                        Decimal("11"),
                        "prompt",
                    ),
                ),
                project_budget_usd=Decimal("10"),
            )

    def test_review_requires_every_shot_and_qc_pass(self) -> None:
        project = launch_project()
        incomplete = (
            LaunchShotResult(
                "S01",
                "req-1",
                "https://x/s1.mp4",
                Decimal("1.50"),
                QCStatus.PASS,
            ),
        )
        with self.assertRaisesRegex(ValueError, "every planned shot"):
            prepare_human_review(
                project,
                incomplete,
                final_video_url="https://x/final.mp4",
            )

    def test_completed_video_stops_at_pending_human_review(self) -> None:
        project = launch_project()
        results = (
            LaunchShotResult(
                "S01",
                "req-1",
                "https://x/s1.mp4",
                Decimal("1.50"),
                QCStatus.PASS,
            ),
            LaunchShotResult(
                "S02",
                "req-2",
                "https://x/s2.mp4",
                Decimal("1.75"),
                QCStatus.PASS,
            ),
        )
        review = prepare_human_review(
            project,
            results,
            final_video_url="https://x/final.mp4",
            actual_editing_cost_usd=Decimal("0"),
        )
        self.assertEqual(review.status, LaunchStatus.PENDING_HUMAN_REVIEW)
        self.assertFalse(review.human_approved_for_publication)

    def test_publication_approval_requires_explicit_human_confirmation(self) -> None:
        project = launch_project()
        results = tuple(
            LaunchShotResult(
                shot.shot_id,
                f"req-{shot.shot_id}",
                f"https://x/{shot.shot_id}.mp4",
                Decimal("1"),
                QCStatus.PASS,
            )
            for shot in project.shots
        )
        review = prepare_human_review(
            project,
            results,
            final_video_url="https://x/final.mp4",
        )
        with self.assertRaisesRegex(ValueError, "explicit human"):
            approve_for_publication(review, human_confirmed=False)

        approved = approve_for_publication(review, human_confirmed=True)
        self.assertEqual(approved.status, LaunchStatus.APPROVED_FOR_PUBLICATION)
        self.assertTrue(approved.human_approved_for_publication)


if __name__ == "__main__":
    unittest.main()
