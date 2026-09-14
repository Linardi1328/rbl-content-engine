from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from rbl_content_engine.revenue.analytics import load_analytics
from rbl_content_engine.revenue.models import (
    Hypothesis,
    ManifestError,
    Opportunity,
    load_manifest,
)
from rbl_content_engine.revenue.reporting import build_outputs
from rbl_content_engine.revenue.scoring import rank_opportunities, score_opportunity

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/revenue-intelligence/opportunities.json"
ANALYTICS = ROOT / "examples/revenue-intelligence/analytics.csv"


class RevenueIntelligenceTests(unittest.TestCase):
    def manifest(self):
        return load_manifest(MANIFEST, workspace=ROOT)

    def test_documented_scoring_and_risk_penalty(self):
        manifest = self.manifest()
        first = manifest.opportunities[0]
        weighted, penalty, final = score_opportunity(first)
        self.assertEqual(weighted, 92.0)
        self.assertEqual(penalty, 4.0)
        self.assertEqual(final, 88.0)
        ranked = rank_opportunities(manifest.opportunities)
        self.assertEqual([item.id for item in ranked], [
            "opp-event-ops-long",
            "opp-build-short",
            "opp-review-guide",
        ])
        self.assertEqual([item.final_score for item in ranked], [88.0, 75.0, 66.0])

    def test_invalid_factor_range_fails_closed(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        data["opportunities"][0]["factors"]["creator_fit"] = 6
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "0 to 5"):
                load_manifest(path, workspace=ROOT)

    def test_unknown_monetization_route_fails_closed(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        data["opportunities"][0]["monetization_routes"] = ["MAGIC_MONEY"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "unknown monetization"):
                load_manifest(path, workspace=ROOT)

    def test_ranking_preserves_input_order_on_ties(self):
        hypothesis = Hypothesis(
            audience="audience",
            hook="hook",
            primary_metric="views",
            target=10,
            direction="AT_LEAST",
        )
        factors = {
            "demand_signal": 3,
            "creator_fit": 3,
            "originality": 3,
            "production_efficiency": 3,
            "evergreen_value": 3,
            "monetization_fit": 3,
            "risk": 1,
        }
        opportunities = [
            Opportunity(
                id="first",
                topic="First",
                platform="youtube",
                format="long_form",
                factors=dict(factors),
                factor_notes={},
                monetization_routes=("NONE",),
                hypothesis=hypothesis,
                input_index=0,
            ),
            Opportunity(
                id="second",
                topic="Second",
                platform="youtube",
                format="long_form",
                factors=dict(factors),
                factor_notes={},
                monetization_routes=("NONE",),
                hypothesis=hypothesis,
                input_index=1,
            ),
        ]
        self.assertEqual(
            [item.id for item in rank_opportunities(opportunities)],
            ["first", "second"],
        )

    def test_research_snapshot_lineage_is_retained(self):
        outputs = build_outputs(self.manifest())
        for name, content in outputs.items():
            self.assertIn("research/platforms/2026-08-21/platforms.json", content, name)
            self.assertIn("2026-08-21", content, name)

    def test_csv_aliases_extra_columns_and_observations(self):
        analytics = load_analytics(ANALYTICS)
        self.assertEqual(analytics["yt-event-ops-001"]["views"], 4200)
        self.assertEqual(analytics["yt-event-ops-001"]["watch_time_minutes"], 1380.0)
        self.assertNotIn("Extra Column", analytics["yt-event-ops-001"])

        outputs = build_outputs(self.manifest(), analytics)
        hypotheses = json.loads(outputs["hypotheses.json"])["hypotheses"]
        by_id = {item["opportunity_id"]: item for item in hypotheses}
        self.assertEqual(by_id["opp-event-ops-long"]["observation_status"], "TARGET_MET")
        self.assertEqual(by_id["opp-build-short"]["observation_status"], "TARGET_MISSED")
        self.assertEqual(by_id["opp-review-guide"]["observation_status"], "UNOBSERVED")

    def test_at_most_hypothesis(self):
        manifest = self.manifest()
        original = manifest.opportunities[0]
        modified = Opportunity(
            id=original.id,
            topic=original.topic,
            platform=original.platform,
            format=original.format,
            factors=original.factors,
            factor_notes=original.factor_notes,
            monetization_routes=original.monetization_routes,
            hypothesis=Hypothesis(
                audience=original.hypothesis.audience,
                hook=original.hypothesis.hook,
                primary_metric="views",
                target=5000,
                direction="AT_MOST",
            ),
            content_id=original.content_id,
            input_index=original.input_index,
        )
        altered = type(manifest)(
            version=manifest.version,
            research_snapshot=manifest.research_snapshot,
            opportunities=(modified,),
        )
        outputs = build_outputs(altered, load_analytics(ANALYTICS))
        hypothesis = json.loads(outputs["hypotheses.json"])["hypotheses"][0]
        self.assertEqual(hypothesis["observation_status"], "TARGET_MET")

    def test_missing_matching_metric_yields_no_matching_data(self):
        manifest = self.manifest()
        analytics = load_analytics(ANALYTICS)
        analytics["yt-event-ops-001"].pop("leads", None)
        original = manifest.opportunities[0]
        modified = Opportunity(
            id=original.id,
            topic=original.topic,
            platform=original.platform,
            format=original.format,
            factors=original.factors,
            factor_notes=original.factor_notes,
            monetization_routes=original.monetization_routes,
            hypothesis=Hypothesis(
                audience=original.hypothesis.audience,
                hook=original.hypothesis.hook,
                primary_metric="leads",
                target=5,
                direction="AT_LEAST",
            ),
            content_id=original.content_id,
            input_index=original.input_index,
        )
        altered = type(manifest)(
            version=manifest.version,
            research_snapshot=manifest.research_snapshot,
            opportunities=(modified,),
        )
        hypothesis = json.loads(build_outputs(altered, analytics)["hypotheses.json"])[
            "hypotheses"
        ][0]
        self.assertEqual(hypothesis["observation_status"], "NO_MATCHING_DATA")

    def test_missing_required_csv_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "analytics.csv"
            path.write_text(
                "Video ID,Platform,Publish Date\nabc,youtube,2026-09-10\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ManifestError, "missing required"):
                load_analytics(path)

    def test_duplicate_canonical_csv_mapping_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "analytics.csv"
            path.write_text(
                "Video ID,Platform,Publish Date,Views,View Count\n"
                "abc,youtube,2026-09-10,10,10\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ManifestError, "both map to views"):
                load_analytics(path)

    def test_negative_analytics_metric_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "analytics.csv"
            path.write_text(
                "Video ID,Platform,Publish Date,Views\nabc,youtube,2026-09-10,-1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ManifestError, "non-negative"):
                load_analytics(path)

    def test_duplicate_content_rows_aggregate_additive_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "analytics.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow([
                    "content_id",
                    "platform",
                    "published_at",
                    "views",
                    "watch_time_minutes",
                    "average_view_duration_seconds",
                ])
                writer.writerow(["x", "youtube", "2026-09-10", 100, 20, 12])
                writer.writerow(["x", "youtube", "2026-09-10", 300, 70, 20])
            analytics = load_analytics(path)
            self.assertEqual(analytics["x"]["views"], 400)
            self.assertEqual(analytics["x"]["watch_time_minutes"], 90.0)
            self.assertEqual(analytics["x"]["average_view_duration_seconds"], 18.0)

    def test_outputs_are_deterministic_and_do_not_claim_guaranteed_performance(self):
        manifest = self.manifest()
        analytics = load_analytics(ANALYTICS)
        first = build_outputs(manifest, analytics)
        second = build_outputs(manifest, analytics)
        self.assertEqual(first, second)
        combined = "\n".join(first.values()).lower()
        self.assertNotIn("guaranteed views", combined)
        self.assertNotIn("guaranteed revenue", combined)
        self.assertIn("does not establish causality", combined)

    def test_research_snapshot_cannot_escape_workspace(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        data["research_snapshot"]["path"] = "../outside.json"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "inside the workspace"):
                load_manifest(path, workspace=ROOT)


if __name__ == "__main__":
    unittest.main()
