import json
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "research" / "platforms" / "2026-08-21" / "platforms.json"
DIRECTION_PATH = ROOT / "examples" / "taskpebble" / "direction.json"


class PlatformResearchFixtureIntegrityTests(unittest.TestCase):
    def test_snapshot_and_direction_are_well_formed(self) -> None:
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        direction = json.loads(DIRECTION_PATH.read_text(encoding="utf-8"))

        self.assertEqual(snapshot["research_date"], "2026-08-21")
        date.fromisoformat(snapshot["research_date"])
        self.assertEqual(direction["project"], "TaskPebble")
        self.assertEqual(direction["approval_status"], "PENDING_HUMAN")
        self.assertTrue(direction["objective"])
        self.assertTrue(direction["audience_hypothesis"])

        enabled_targets = [target for target in direction["targets"] if target["enabled"]]
        self.assertEqual(len(enabled_targets), 4)

        for target in enabled_targets:
            self.assertIn(target["platform"], snapshot["platforms"])
            self.assertTrue(target["format"])
            self.assertTrue(target["desired_output"])

    def test_every_platform_has_strategy_and_source_lineage(self) -> None:
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

        for platform_name, platform in snapshot["platforms"].items():
            with self.subTest(platform=platform_name):
                self.assertTrue(platform["audience_intent"])
                self.assertTrue(platform["current_distribution_signals"])
                self.assertTrue(platform["recommended_archetypes"])
                self.assertTrue(platform["rbl_treatments"])
                self.assertTrue(platform["avoid"])
                self.assertTrue(platform["sources"])

                for source in platform["sources"]:
                    self.assertTrue(source["title"])
                    self.assertTrue(source["publisher"])
                    self.assertTrue(source["url"].startswith("https://"))
                    date.fromisoformat(source["accessed_on"])

    def test_snapshot_keeps_market_strategy_separate_from_project_evidence(self) -> None:
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        combined_rules = " ".join(snapshot["rules"]).lower()

        self.assertIn("never be used as evidence for factual project claims", combined_rules)
        self.assertIn("no network research", combined_rules)
        self.assertIn("guaranteed views", combined_rules)


if __name__ == "__main__":
    unittest.main()
