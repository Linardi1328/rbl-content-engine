import json
import unittest
from pathlib import Path

from rbl_content_engine.topview.media import inspect_media_reference
from rbl_content_engine.topview.validator import validate_manifest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "examples" / "topview" / "reference-pilot"
EXPECTED_SHA256 = "a3df5b95c9b469a04b0a11359fe8149858d9524ffe2eb96484e6dc11c0862af1"


class Phase1DBMediaReferenceTests(unittest.TestCase):
    def test_tracked_png_fixture_is_real_media_with_stable_hash(self) -> None:
        inspection = inspect_media_reference(
            ROOT,
            "examples/topview/reference-pilot/ref-media.png",
        )
        self.assertEqual(inspection.format, "PNG")
        self.assertEqual(inspection.mime_type, "image/png")
        self.assertEqual(inspection.media_kind, "image")
        self.assertEqual((inspection.width, inspection.height), (256, 256))
        self.assertEqual(inspection.byte_size, 1557)
        self.assertEqual(inspection.sha256, EXPECTED_SHA256)
        self.assertTrue(inspection.to_dict()["visual_reference_candidate"])
        self.assertFalse(inspection.to_dict()["paid_generation_authorized"])

    def test_metadata_text_fixture_is_not_accepted_as_phase1db_media(self) -> None:
        with self.assertRaisesRegex(ValueError, "accepts only"):
            inspect_media_reference(
                ROOT,
                "examples/topview/reference-pilot/ref-product.txt",
            )

    def test_media_manifest_is_valid_and_points_to_real_png(self) -> None:
        manifest = json.loads(
            (FIXTURE_DIR / "media-manifest.json").read_text(encoding="utf-8")
        )
        result = validate_manifest(manifest)
        self.assertTrue(result.valid, result.to_dict())
        self.assertEqual(len(manifest["references"]), 1)
        reference = manifest["references"][0]
        self.assertEqual(reference["id"], "REF_MEDIA")
        self.assertEqual(reference["type"], "image")
        self.assertEqual(reference["source"], "examples/topview/reference-pilot/ref-media.png")
        self.assertEqual(manifest["scenes"][0]["generation"]["method"], "image_to_video")

    def test_phase1db_docs_require_remote_media_semantics_and_zero_generation(self) -> None:
        docs = (ROOT / "docs" / "topview" / "PHASE_1D_B_MEDIA_PILOT.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("remote object is positively verified as media/image-backed", docs)
        self.assertIn("generic Canvas node or metadata card alone", docs)
        self.assertIn("generated tasks = 0", docs)
        self.assertIn("actual spend = US$0", docs)
        self.assertIn("does **not** authorize storyboard/keyframe generation", docs)


if __name__ == "__main__":
    unittest.main()
