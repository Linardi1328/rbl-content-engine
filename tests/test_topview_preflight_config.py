import json
import unittest
from pathlib import Path

from rbl_content_engine.topview.preflight import evaluate_preflight
from test_topview_validation import minimal_manifest, ready_capabilities


ROOT = Path(__file__).resolve().parents[1]


class TopviewPreflightConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = json.loads(
            (ROOT / ".production" / "topview-state.example.json").read_text(
                encoding="utf-8"
            )
        )

    def test_required_video_method_needs_recorded_live_generation_config(self) -> None:
        result = evaluate_preflight(
            minimal_manifest("image_to_video"),
            self.state,
            ready_capabilities(),
            chargeable_operations_authorized=True,
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn(
            "no live generation configuration recorded for required task type image_to_video",
            result.blockers,
        )

    def test_recorded_live_generation_config_satisfies_config_preflight_layer(self) -> None:
        capabilities = ready_capabilities()
        capabilities["generation_configs"] = [
            {
                "task_type": "image_to_video",
                "submit_model": "synthetic-submit-model",
                "resolutions": ["720p", "1080p"],
                "durations_seconds": [5],
                "required_fields": ["firstFrameFileId"],
                "native_audio": False,
                "billing_hint": "synthetic test fixture",
            }
        ]
        result = evaluate_preflight(
            minimal_manifest("image_to_video"),
            self.state,
            capabilities,
            chargeable_operations_authorized=True,
        )
        self.assertEqual(result.status, "READY")
        self.assertTrue(result.ready)


if __name__ == "__main__":
    unittest.main()
