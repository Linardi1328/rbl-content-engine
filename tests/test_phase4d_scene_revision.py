import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "examples" / "production" / "rbl-launch-video-revision-r2.json"
GENERATOR = ROOT / "scripts" / "generate_rbl_scene_revisions.py"
ASSEMBLER = ROOT / "scripts" / "assemble_rbl_scene_revision_review.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Phase4DSceneRevisionTests(unittest.TestCase):
    def test_revision_plan_is_five_scene_seedance_25_vertical(self) -> None:
        payload = json.loads(PLAN.read_text(encoding="utf-8"))
        self.assertEqual(payload["revision_id"], "RBL-LAUNCH-R2")
        self.assertEqual(payload["model"], "bytedance/seedance-2.5/text-to-video")
        self.assertEqual(payload["aspect_ratio"], "9:16")
        self.assertEqual(payload["resolution"], "720p")
        self.assertFalse(payload["generate_audio"])
        self.assertEqual([shot["shot_id"] for shot in payload["shots"]], [
            "S01", "S02", "S03", "S04", "S05"
        ])
        self.assertTrue(all(shot["duration_seconds"] == 4 for shot in payload["shots"]))
        self.assertLessEqual(
            sum(float(shot["estimated_cost_usd"]) for shot in payload["shots"]),
            float(payload["project_budget_usd"]),
        )
        self.assertLessEqual(float(payload["project_budget_usd"]), 20.0)

    def test_prompts_keep_generated_typography_out_of_model_output(self) -> None:
        payload = json.loads(PLAN.read_text(encoding="utf-8"))
        for shot in payload["shots"]:
            prompt = shot["prompt"].lower()
            self.assertIn("no readable text", prompt)
            self.assertIn("no letters", prompt)
            self.assertIn("no watermark", prompt)

    def test_generator_uses_separate_revision_state_and_output_dir(self) -> None:
        module = load_module("r2_generator", GENERATOR)
        plan = module.load_plan()
        self.assertEqual(plan["revision_id"], "RBL-LAUNCH-R2")
        self.assertIn("launch-video-revisions", str(module.OUTPUT_DIR))
        self.assertIn("rbl-launch-revision-r2.json", str(module.STATE_FILE))

    def test_generator_requires_explicit_retry_after_terminal_failure(self) -> None:
        source = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("--retry-shot", source)
        self.assertIn("no automatic retry will occur", source)
        self.assertNotIn("for attempt in", source)

    def test_assembler_produces_silent_vertical_review(self) -> None:
        module = load_module("r2_assembler", ASSEMBLER)
        command = module.build_ffmpeg_command(
            [Path("S01.mp4"), Path("S02.mp4")],
            Path("review.mp4"),
        )
        joined = " ".join(command)
        self.assertIn("scale=720:1280", joined)
        self.assertIn("concat=n=2:v=1:a=0", joined)
        self.assertIn("-an", command)

    def test_revision_stops_before_publication(self) -> None:
        for path in (GENERATOR, ASSEMBLER):
            source = path.read_text(encoding="utf-8")
            self.assertIn("BLOCKED_PENDING_HUMAN_REVIEW", source)
            self.assertNotIn("instagram.com", source)
            self.assertNotIn("tiktok.com", source)


if __name__ == "__main__":
    unittest.main()
