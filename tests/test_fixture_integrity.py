import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAIMS_PATH = ROOT / "examples" / "taskpebble" / "claims.json"


class TaskPebbleFixtureIntegrityTests(unittest.TestCase):
    def test_checked_in_claim_references_match_evidence(self) -> None:
        manifest = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))

        self.assertEqual(manifest["project"], "TaskPebble")
        self.assertEqual(len(manifest["claims"]), 4)

        for claim in manifest["claims"]:
            self.assertTrue(claim["id"])
            self.assertTrue(claim["text"])
            self.assertTrue(claim["evidence"])

            for reference in claim["evidence"]:
                evidence_path = (ROOT / reference["path"]).resolve()
                self.assertTrue(evidence_path.is_relative_to(ROOT.resolve()))
                self.assertTrue(evidence_path.is_file())

                lines = evidence_path.read_text(encoding="utf-8").splitlines()
                start = reference["start_line"]
                end = reference["end_line"]

                self.assertGreaterEqual(start, 1)
                self.assertGreaterEqual(end, start)
                self.assertLessEqual(end, len(lines))

                referenced_text = "\n".join(lines[start - 1 : end])
                self.assertIn(reference["quote"], referenced_text)


if __name__ == "__main__":
    unittest.main()
