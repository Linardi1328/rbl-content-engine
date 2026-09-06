import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase1DContractTests(unittest.TestCase):
    def test_reference_schema_and_examples_are_parseable(self) -> None:
        for path in (
            ROOT / "schemas" / "topview-references.schema.json",
            ROOT / ".production" / "topview-references.example.json",
            ROOT / "examples" / "topview" / "reference-pilot" / "manifest.json",
        ):
            with self.subTest(path=path):
                value = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(value, dict)

    def test_reference_schema_limits_pilot_to_two_references(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "topview-references.schema.json").read_text(
                encoding="utf-8"
            )
        )
        pilot_ids = schema["properties"]["pilot_reference_ids"]
        self.assertEqual(pilot_ids["minItems"], 1)
        self.assertEqual(pilot_ids["maxItems"], 2)
        fingerprint = schema["$defs"]["referenceRecord"]["properties"]["source_sha256"]
        self.assertEqual(fingerprint["pattern"], "^[a-f0-9]{64}$")

    def test_phase1d_docs_keep_generation_out_of_scope(self) -> None:
        pilot = (ROOT / "docs" / "topview" / "PHASE_1D_PILOT.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("does not authorize image generation", pilot)
        self.assertIn("actual project spend remains US$0", pilot)
        self.assertIn("SHA-256", pilot)
        self.assertIn("Only canvas owner can perform this operation.", pilot)


if __name__ == "__main__":
    unittest.main()
