import unittest
from decimal import Decimal

from rbl_content_engine.production import (
    CostQuote,
    CostUnit,
    GenerationNeed,
    ProductionRecord,
    PrototypeStage,
    ProviderCapability,
    ProviderCommitmentRequest,
    ProviderDescriptor,
    StabilityPolicy,
    authorize_provider_commitment,
    evaluate_stability,
    provider_can_satisfy,
)


def complete_record(
    index: int,
    *,
    social: bool = False,
    retry_count: int | None = 0,
    qc_recorded: bool = True,
    cost_amount: Decimal | None = Decimal("0"),
    cost_unit: CostUnit | None = CostUnit.USD,
) -> ProductionRecord:
    return ProductionRecord(
        video_id=f"VID_{index:02d}",
        production_complete=True,
        published=True,
        retry_count=retry_count,
        qc_recorded=qc_recorded,
        actual_cost_amount=cost_amount,
        actual_cost_unit=cost_unit,
        social_observation_recorded=social,
    )


class ProviderNeutralProductionTests(unittest.TestCase):
    def test_provider_capability_matching_is_provider_neutral(self) -> None:
        provider = ProviderDescriptor(
            provider_id="example-renderer",
            channel="plugin",
            capabilities=frozenset(
                {
                    ProviderCapability.IMAGE_TO_VIDEO,
                    ProviderCapability.START_FRAME,
                    ProviderCapability.COST_ESTIMATE,
                }
            ),
        )
        need = GenerationNeed(
            frozenset(
                {
                    ProviderCapability.IMAGE_TO_VIDEO,
                    ProviderCapability.START_FRAME,
                }
            )
        )
        self.assertTrue(provider_can_satisfy(provider, need))

    def test_credit_quote_cannot_be_silently_compared_as_usd(self) -> None:
        quote = CostQuote(
            provider_id="example-renderer",
            amount=Decimal("12.5"),
            unit=CostUnit.CREDITS,
            source="live read-only quote",
        )
        with self.assertRaisesRegex(ValueError, "explicit USD estimate"):
            quote.cash_cost_usd()

    def test_credit_quote_may_carry_explicit_usd_estimate(self) -> None:
        quote = CostQuote(
            provider_id="example-renderer",
            amount=Decimal("12.5"),
            unit=CostUnit.CREDITS,
            source="human-reviewed conversion",
            estimated_usd=Decimal("1.25"),
        )
        self.assertEqual(quote.cash_cost_usd(), Decimal("1.25"))

    def test_early_prototype_stays_in_prove_pipeline(self) -> None:
        records = tuple(complete_record(i, social=True) for i in range(1, 4))
        result = evaluate_stability(records, human_confirmed=True)
        self.assertEqual(result.stage, PrototypeStage.PROVE_PIPELINE)
        self.assertFalse(result.ready_for_provider_stabilization)
        self.assertIn("MINIMUM_PUBLISHED_VIDEO_COUNT_NOT_MET", result.blockers)

    def test_five_videos_without_enough_observations_stays_repeatability(self) -> None:
        records = tuple(
            complete_record(i, social=i <= 2)
            for i in range(1, 6)
        )
        result = evaluate_stability(records, human_confirmed=True)
        self.assertEqual(result.stage, PrototypeStage.PROVE_REPEATABILITY)
        self.assertFalse(result.ready_for_provider_stabilization)
        self.assertIn("MINIMUM_SOCIAL_OBSERVATION_COUNT_NOT_MET", result.blockers)

    def test_missing_production_evidence_blocks_stabilization(self) -> None:
        records = (
            complete_record(1, social=True),
            complete_record(2, social=True),
            complete_record(3, social=True),
            complete_record(4),
            complete_record(5, retry_count=None, qc_recorded=False, cost_amount=None, cost_unit=None),
        )
        result = evaluate_stability(records, human_confirmed=True)
        self.assertEqual(result.stage, PrototypeStage.PROVE_REPEATABILITY)
        self.assertIn("RETRY_DATA_INCOMPLETE", result.blockers)
        self.assertIn("QC_DATA_INCOMPLETE", result.blockers)
        self.assertIn("COST_DATA_INCOMPLETE", result.blockers)

    def test_human_confirmation_is_part_of_stability_gate(self) -> None:
        records = tuple(
            complete_record(i, social=i <= 3)
            for i in range(1, 6)
        )
        result = evaluate_stability(records, human_confirmed=False)
        self.assertEqual(result.stage, PrototypeStage.PROVE_REPEATABILITY)
        self.assertIn("HUMAN_CONFIRMATION_REQUIRED", result.blockers)

    def test_complete_evidence_reaches_stabilize_provider(self) -> None:
        records = tuple(
            complete_record(i, social=i <= 3)
            for i in range(1, 6)
        )
        result = evaluate_stability(records, human_confirmed=True)
        self.assertEqual(result.stage, PrototypeStage.STABILIZE_PROVIDER)
        self.assertTrue(result.ready_for_provider_stabilization)
        self.assertEqual(result.blockers, ())

    def test_provider_commitment_fails_closed_before_stability_gate(self) -> None:
        result = evaluate_stability((), human_confirmed=True)
        request = ProviderCommitmentRequest(
            provider_id="higgsfield",
            recurring_subscription=True,
            human_authorized=True,
        )
        with self.assertRaisesRegex(ValueError, "gate is not ready"):
            authorize_provider_commitment(result, request)

    def test_provider_commitment_requires_explicit_human_authorization(self) -> None:
        records = tuple(
            complete_record(i, social=i <= 3)
            for i in range(1, 6)
        )
        result = evaluate_stability(records, human_confirmed=True)
        request = ProviderCommitmentRequest(
            provider_id="higgsfield",
            recurring_subscription=True,
            human_authorized=False,
        )
        with self.assertRaisesRegex(ValueError, "explicit human authorization"):
            authorize_provider_commitment(result, request)

    def test_provider_commitment_contract_does_not_execute_anything(self) -> None:
        records = tuple(
            complete_record(i, social=i <= 3)
            for i in range(1, 6)
        )
        result = evaluate_stability(
            records,
            human_confirmed=True,
            policy=StabilityPolicy(
                min_completed_published_videos=5,
                min_social_observations=3,
            ),
        )
        request = ProviderCommitmentRequest(
            provider_id="higgsfield",
            recurring_subscription=True,
            human_authorized=True,
        )
        self.assertIs(authorize_provider_commitment(result, request), request)


if __name__ == "__main__":
    unittest.main()
