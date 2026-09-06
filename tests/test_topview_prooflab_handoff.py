import unittest

from rbl_content_engine.topview.validator import validate_manifest
from test_topview_validation import minimal_manifest


class TopviewProofLabHandoffTests(unittest.TestCase):
    def test_scene_cannot_invent_verified_claim_id_outside_boundary(self) -> None:
        manifest = minimal_manifest()
        manifest["verification_boundary"]["verified_claim_ids"] = ["claim-001"]
        manifest["scenes"][0]["content_lineage"] = {
            "verification_status": "VERIFIED",
            "claim_ids": ["claim-999"],
            "evidence_refs": ["examples/evidence.md:1"],
        }

        result = validate_manifest(manifest)
        self.assertFalse(result.valid)
        self.assertIn(
            "LINEAGE_CLAIM_NOT_VERIFIED",
            {issue.code for issue in result.issues},
        )

    def test_scene_may_use_claim_id_present_in_prooflab_boundary(self) -> None:
        manifest = minimal_manifest()
        manifest["verification_boundary"]["verified_claim_ids"] = ["claim-001"]
        manifest["scenes"][0]["content_lineage"] = {
            "verification_status": "VERIFIED",
            "claim_ids": ["claim-001"],
            "evidence_refs": ["examples/evidence.md:1"],
        }

        result = validate_manifest(manifest)
        self.assertTrue(result.valid, result.to_dict())


if __name__ == "__main__":
    unittest.main()
