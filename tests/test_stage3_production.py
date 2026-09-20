import unittest
from decimal import Decimal

from rbl_content_engine.production.contracts import (
    GenerationAuthorization,
    GenerationScope,
    KeyframeRecord,
    LockedReference,
    ProviderSnapshot,
    PublicationMethod,
    PublicationReceipt,
    QCStatus,
    SceneCard,
    SocialObservation,
    VideoPrototypeRecord,
)
from rbl_content_engine.production.providers import (
    CostQuote,
    CostUnit,
    ProviderCapability,
)
from rbl_content_engine.production.stage3 import (
    Stage3Phase,
    build_repeatability_records,
    evaluate_keyframe_preflight,
    evaluate_stage3,
    evaluate_video_preflight,
    stage3_report_dict,
    summarize_costs,
)


CAPS = frozenset(
    {
        ProviderCapability.KEYFRAME_IMAGE,
        ProviderCapability.IMAGE_TO_VIDEO,
        ProviderCapability.START_FRAME,
        ProviderCapability.COST_ESTIMATE,
        ProviderCapability.TASK_MONITORING,
    }
)


def snapshot() -> ProviderSnapshot:
    return ProviderSnapshot(
        provider_id="higgsfield",
        channel="plugin",
        observed_at="2026-09-20T17:00:00+08:00",
        capabilities=CAPS,
        model_ids=("nano_banana", "kling3_0_turbo", "z_image"),
        executable_model_ids=("z_image",),
        blocked_model_ids=("nano_banana", "kling3_0_turbo"),
    )


def scene() -> SceneCard:
    return SceneCard(
        scene_id="S01",
        purpose="Synthetic provider-neutral Stage 3 pilot",
        platform="instagram",
        aspect_ratio="9:16",
        duration_seconds=Decimal("5"),
        reference_ids=("REF_MEDIA",),
        prompt="Animate the approved synthetic reference with a slow camera push.",
        required_capabilities=frozenset(
            {ProviderCapability.IMAGE_TO_VIDEO, ProviderCapability.START_FRAME}
        ),
    )


def keyframe(*, approved: bool = True, qc: QCStatus = QCStatus.PASS) -> KeyframeRecord:
    return KeyframeRecord(
        keyframe_id="KF_S01_001",
        scene_id="S01",
        provider_id="higgsfield",
        model_id="nano_banana",
        job_id="job-keyframe-1",
        output_id="output-keyframe-1",
        created_at="2026-09-20T17:05:00+08:00",
        cost_amount=Decimal("1"),
        cost_unit=CostUnit.CREDITS,
        qc_status=qc,
        human_approved=approved,
    )


def video(
    index: int,
    *,
    provider: str = "higgsfield",
    qc: QCStatus = QCStatus.PASS,
    approved: bool = True,
    retries: int = 0,
    unit: CostUnit = CostUnit.CREDITS,
    cost: str = "2",
) -> VideoPrototypeRecord:
    return VideoPrototypeRecord(
        video_id=f"VID_{index:02d}",
        scene_id="S01",
        provider_id=provider,
        model_id="kling3_0_turbo",
        job_ids=(f"job-video-{index}",),
        output_id=f"output-video-{index}",
        created_at=f"2026-09-{20 + index:02d}T17:10:00+08:00",
        start_keyframe_id="KF_S01_001",
        duration_seconds=Decimal("5"),
        retry_count=retries,
        actual_cost_amount=Decimal(cost),
        actual_cost_unit=unit,
        qc_status=qc,
        human_approved=approved,
    )


def receipt(index: int) -> PublicationReceipt:
    return PublicationReceipt(
        video_id=f"VID_{index:02d}",
        platform="instagram",
        content_id=f"IG_{index:02d}",
        published_at=f"2026-10-{index:02d}T12:00:00+08:00",
        method=PublicationMethod.MANUAL_EXTERNAL,
        human_confirmed=True,
    )


def observation(index: int) -> SocialObservation:
    return SocialObservation(
        content_id=f"IG_{index:02d}",
        platform="instagram",
        observed_at=f"2026-10-{index + 7:02d}T12:00:00+08:00",
        metrics={"views": Decimal(str(1000 * index))},
    )


class Stage3ProductionTests(unittest.TestCase):
    def test_keyframe_preflight_requires_locked_reference_and_authorized_quote(self) -> None:
        quote = CostQuote(
            provider_id="higgsfield",
            amount=Decimal("1"),
            unit=CostUnit.CREDITS,
            source="live estimate",
        )
        auth = GenerationAuthorization(
            authorization_id="AUTH-KF-1",
            provider_id="higgsfield",
            scope=GenerationScope.KEYFRAME,
            human_authorized=True,
            authorized_at="2026-09-20T17:01:00+08:00",
            max_credits=Decimal("2"),
        )
        result = evaluate_keyframe_preflight(
            scene(),
            (
                LockedReference(
                    reference_id="REF_MEDIA",
                    human_approved=True,
                    locked=True,
                    source_sha256="a" * 64,
                ),
            ),
            snapshot(),
            quote,
            auth,
            model_id="z_image",
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.blockers, ())

    def test_keyframe_preflight_fails_closed_on_unlocked_reference(self) -> None:
        quote = CostQuote(
            provider_id="higgsfield",
            amount=Decimal("1"),
            unit=CostUnit.CREDITS,
            source="live estimate",
        )
        auth = GenerationAuthorization(
            authorization_id="AUTH-KF-1",
            provider_id="higgsfield",
            scope=GenerationScope.KEYFRAME,
            human_authorized=True,
            authorized_at="2026-09-20T17:01:00+08:00",
            max_credits=Decimal("2"),
        )
        result = evaluate_keyframe_preflight(
            scene(),
            (LockedReference("REF_MEDIA", True, False),),
            snapshot(),
            quote,
            auth,
            model_id="z_image",
        )
        self.assertFalse(result.ready)
        self.assertIn("REFERENCE_NOT_LOCKED:REF_MEDIA", result.blockers)


    def test_keyframe_preflight_blocks_catalog_model_that_cannot_execute(self) -> None:
        quote = CostQuote(
            provider_id="higgsfield",
            amount=Decimal("1"),
            unit=CostUnit.CREDITS,
            source="live estimate",
        )
        auth = GenerationAuthorization(
            authorization_id="AUTH-KF-2",
            provider_id="higgsfield",
            scope=GenerationScope.KEYFRAME,
            human_authorized=True,
            authorized_at="2026-09-20T17:01:00+08:00",
            max_credits=Decimal("2"),
        )
        result = evaluate_keyframe_preflight(
            scene(),
            (LockedReference("REF_MEDIA", True, True),),
            snapshot(),
            quote,
            auth,
            model_id="nano_banana",
        )
        self.assertFalse(result.ready)
        self.assertIn("MODEL_NOT_EXECUTABLE", result.blockers)

    def test_video_preflight_requires_approved_keyframe(self) -> None:
        quote = CostQuote(
            provider_id="higgsfield",
            amount=Decimal("8"),
            unit=CostUnit.CREDITS,
            source="live estimate",
        )
        auth = GenerationAuthorization(
            authorization_id="AUTH-VID-1",
            provider_id="higgsfield",
            scope=GenerationScope.VIDEO_DRAFT,
            human_authorized=True,
            authorized_at="2026-09-20T17:02:00+08:00",
            max_credits=Decimal("10"),
        )
        result = evaluate_video_preflight(
            scene(),
            keyframe(approved=False),
            snapshot(),
            quote,
            auth,
            model_id="kling3_0_turbo",
        )
        self.assertFalse(result.ready)
        self.assertIn("START_KEYFRAME_NOT_APPROVED", result.blockers)
        self.assertIn("MODEL_NOT_EXECUTABLE", result.blockers)

    def test_video_preflight_rejects_long_clip_without_justification(self) -> None:
        long_scene = SceneCard(
            scene_id="S01",
            purpose="Long test",
            platform="instagram",
            aspect_ratio="9:16",
            duration_seconds=Decimal("9"),
            reference_ids=("REF_MEDIA",),
            prompt="Long synthetic clip.",
            required_capabilities=frozenset(
                {ProviderCapability.IMAGE_TO_VIDEO, ProviderCapability.START_FRAME}
            ),
        )
        quote = CostQuote("higgsfield", Decimal("8"), CostUnit.CREDITS, "live")
        auth = GenerationAuthorization(
            "AUTH-VID-1",
            "higgsfield",
            GenerationScope.VIDEO_DRAFT,
            True,
            "2026-09-20T17:02:00+08:00",
            max_credits=Decimal("10"),
        )
        result = evaluate_video_preflight(
            long_scene,
            keyframe(),
            snapshot(),
            quote,
            auth,
            model_id="kling3_0_turbo",
        )
        self.assertIn("LONG_CLIP_JUSTIFICATION_REQUIRED", result.blockers)

    def test_publication_receipt_cannot_be_unconfirmed(self) -> None:
        with self.assertRaisesRegex(ValueError, "human confirmation"):
            PublicationReceipt(
                video_id="VID_01",
                platform="instagram",
                content_id="IG_01",
                published_at="2026-10-01T12:00:00+08:00",
                method=PublicationMethod.MANUAL_EXTERNAL,
                human_confirmed=False,
            )

    def test_repeatability_rejects_observation_without_publication(self) -> None:
        with self.assertRaisesRegex(ValueError, "no matching publication receipt"):
            build_repeatability_records((video(1),), (), (observation(1),))

    def test_cost_summary_never_mixes_units(self) -> None:
        buckets = summarize_costs(
            (
                video(1, unit=CostUnit.CREDITS, cost="2"),
                video(2, unit=CostUnit.CREDITS, cost="3"),
                video(3, provider="topview", unit=CostUnit.USD, cost="1.25"),
            )
        )
        self.assertEqual(len(buckets), 2)
        self.assertEqual(
            {(b.provider_id, b.unit, b.amount) for b in buckets},
            {
                ("higgsfield", CostUnit.CREDITS, Decimal("5")),
                ("topview", CostUnit.USD, Decimal("1.25")),
            },
        )

    def test_stage3_stays_in_3b_without_approved_keyframe(self) -> None:
        result = evaluate_stage3((), (), (), (), human_confirmed_stability=False)
        self.assertEqual(result.phase, Stage3Phase.PHASE_3B_KEYFRAME)

    def test_stage3_moves_to_3c_after_keyframe(self) -> None:
        result = evaluate_stage3((keyframe(),), (), (), (), human_confirmed_stability=False)
        self.assertEqual(result.phase, Stage3Phase.PHASE_3C_VIDEO)

    def test_stage3_moves_to_3d_after_first_complete_video(self) -> None:
        result = evaluate_stage3(
            (keyframe(),),
            (video(1),),
            (receipt(1),),
            (observation(1),),
            human_confirmed_stability=True,
        )
        self.assertEqual(result.phase, Stage3Phase.PHASE_3D_REPEATABILITY)
        self.assertFalse(result.ready_for_provider_stabilization)

    def test_stage3_reaches_3e_only_with_repeatability_evidence_and_human_gate(self) -> None:
        videos = tuple(video(i, retries=i % 2) for i in range(1, 6))
        receipts = tuple(receipt(i) for i in range(1, 6))
        observations = tuple(observation(i) for i in range(1, 4))
        result = evaluate_stage3(
            (keyframe(),),
            videos,
            receipts,
            observations,
            human_confirmed_stability=True,
        )
        self.assertEqual(result.phase, Stage3Phase.PHASE_3E_STABILIZATION)
        self.assertTrue(result.ready_for_provider_stabilization)
        report = stage3_report_dict(result)
        self.assertEqual(report["provider_selection"], "HUMAN_DECISION_REQUIRED")

    def test_stage3_does_not_auto_stabilize_without_human_confirmation(self) -> None:
        videos = tuple(video(i) for i in range(1, 6))
        receipts = tuple(receipt(i) for i in range(1, 6))
        observations = tuple(observation(i) for i in range(1, 4))
        result = evaluate_stage3(
            (keyframe(),),
            videos,
            receipts,
            observations,
            human_confirmed_stability=False,
        )
        self.assertEqual(result.phase, Stage3Phase.PHASE_3D_REPEATABILITY)
        self.assertIn("HUMAN_CONFIRMATION_REQUIRED", result.blockers)


if __name__ == "__main__":
    unittest.main()
