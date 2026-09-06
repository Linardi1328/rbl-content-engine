import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TopviewDiscoveryContractTests(unittest.TestCase):
    def test_capability_schema_and_example_are_parseable(self) -> None:
        for path in (
            ROOT / "schemas" / "topview-capabilities.schema.json",
            ROOT / ".production" / "topview-capabilities.example.json",
        ):
            with self.subTest(path=path):
                parsed = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(parsed, dict)

    def test_live_capability_snapshot_is_gitignored(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".production/topview-capabilities.json", gitignore)
        self.assertNotIn(".production/topview-capabilities.example.json", gitignore)

    def test_agents_routes_topview_work_through_discovery(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("docs/topview/DISCOVERY.md", agents)
        self.assertIn(".production/topview-capabilities.json", agents)
        self.assertIn("provides no paid-generation authorization switch", agents)

    def test_discovery_never_promotes_public_docs_to_verified_live(self) -> None:
        discovery = (ROOT / "docs" / "topview" / "DISCOVERY.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Never promote a capability to `VERIFIED_LIVE`", discovery)
        self.assertIn("Do not execute a paid generation merely to prove a tool exists", discovery)
        self.assertIn("Current ChatGPT-session result", discovery)


if __name__ == "__main__":
    unittest.main()
