import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_rbl_launch_video.py"
ASSEMBLER = ROOT / "scripts" / "assemble_rbl_launch_video.py"
INSPECTOR = ROOT / "scripts" / "inspect_higgsfield_request.py"
PLAN = ROOT / "examples" / "production" / "rbl-launch-video-plan.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Phase4CLaunchVideoTests(unittest.TestCase):
    def test_launch_plan_uses_live_verified_seedance_path(self) -> None:
        payload = json.loads(PLAN.read_text(encoding="utf-8"))
        self.assertEqual(
            payload["model"],
            "bytedance/seedance-2.5/text-to-video",
        )
        self.assertEqual(payload["aspect_ratio"], "9:16")
        self.assertEqual(payload["resolution"], "720p")
        self.assertFalse(payload["generate_audio"])
        self.assertEqual(len(payload["shots"]), 5)
        self.assertTrue(
            all(
                shot["application"] == "bytedance/seedance-2.5/text-to-video"
                for shot in payload["shots"]
            )
        )
        self.assertLessEqual(
            sum(float(shot["estimated_cost_usd"]) for shot in payload["shots"]),
            float(payload["project_budget_usd"]),
        )
        self.assertLessEqual(float(payload["project_budget_usd"]), 20.0)

    def test_generator_validates_checked_in_plan(self) -> None:
        module = load_module("launch_generator", GENERATOR)
        plan = module.load_plan()
        self.assertEqual(plan["launch_id"], "RBL-LAUNCH-001")

    def test_generator_state_is_resumable_and_publication_blocked(self) -> None:
        module = load_module("launch_generator_state", GENERATOR)
        plan = module.load_plan()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = module.load_state(plan, path)
            self.assertEqual(state["status"], "GENERATING")
            self.assertEqual(
                state["publication_status"],
                "BLOCKED_PENDING_HUMAN_REVIEW",
            )
            module.write_state(state, path)
            loaded = module.load_state(plan, path)
            self.assertEqual(loaded, state)

    def test_generator_source_contains_no_automatic_retry_loop(self) -> None:
        source = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("no automatic retry will occur", source)
        self.assertNotIn("for attempt in", source)
        self.assertNotIn("while attempt", source)


    def test_failed_shot_requires_explicit_targeted_retry(self) -> None:
        source = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("--retry-shot", source)
        self.assertIn("A new paid attempt requires --retry-shot", source)

    def test_request_inspector_never_submits_generation(self) -> None:
        source = INSPECTOR.read_text(encoding="utf-8")
        self.assertIn("client.status(args.request_id)", source)
        self.assertIn("client.result(args.request_id)", source)
        self.assertNotIn(".submit(", source)
        self.assertNotIn(".subscribe(", source)

    def test_assembler_builds_vertical_silent_review_cut(self) -> None:
        module = load_module("launch_assembler", ASSEMBLER)
        command = module.build_ffmpeg_command(
            [Path("S01.mp4"), Path("S02.mp4")],
            Path("final.mp4"),
        )
        joined = " ".join(command)
        self.assertIn("scale=720:1280", joined)
        self.assertIn("concat=n=2:v=1:a=0", joined)
        self.assertIn("-an", command)
        self.assertEqual(command[-1], "final.mp4")

    def test_assembler_never_publishes(self) -> None:
        source = ASSEMBLER.read_text(encoding="utf-8")
        self.assertIn("PENDING_HUMAN_REVIEW", source)
        self.assertIn("Do not publish", source)
        self.assertNotIn("instagram.com", source)
        self.assertNotIn("tiktok.com", source)


if __name__ == "__main__":
    unittest.main()
