from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from rbl_content_engine.production.video_job import (
    JOB_ROOT,
    LEGACY_OUTPUT_DIR,
    LEGACY_PLAN_FILE,
    LEGACY_STATE_FILE,
    plan_identity,
    resolve_runtime_paths,
    validate_video_plan,
)


ROOT = Path(__file__).resolve().parents[1]
WEEKLY_PLAN = ROOT / "examples" / "production" / "weekly-video-plan.example.json"
GENERATOR = ROOT / "scripts" / "generate_rbl_launch_video.py"
ASSEMBLER = ROOT / "scripts" / "assemble_rbl_launch_video.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V1JobScopedMediaTests(unittest.TestCase):
    def test_checked_in_weekly_plan_is_valid_and_within_budget(self) -> None:
        plan = json.loads(WEEKLY_PLAN.read_text(encoding="utf-8"))
        validate_video_plan(plan)
        self.assertEqual(plan_identity(plan), ("job_id", "RBL-SAMPLE-WEEKLY-001"))
        self.assertEqual(
            sum(int(shot["duration_seconds"]) for shot in plan["shots"]),
            24,
        )
        self.assertEqual(
            sum(Decimal(str(shot["estimated_cost_usd"])) for shot in plan["shots"]),
            Decimal("18.00"),
        )
        self.assertLessEqual(Decimal(plan["project_budget_usd"]), Decimal("20"))

    def test_two_weekly_jobs_resolve_to_different_runtime_directories(self) -> None:
        base = json.loads(WEEKLY_PLAN.read_text(encoding="utf-8"))
        first = dict(base)
        second = dict(base)
        first["job_id"] = "RBL-WEEK-001"
        second["job_id"] = "RBL-WEEK-002"

        first_paths = resolve_runtime_paths(first, plan_path=WEEKLY_PLAN)
        second_paths = resolve_runtime_paths(second, plan_path=WEEKLY_PLAN)

        self.assertNotEqual(first_paths.state_file, second_paths.state_file)
        self.assertNotEqual(first_paths.output_dir, second_paths.output_dir)
        self.assertEqual(
            first_paths.state_file,
            JOB_ROOT / "RBL-WEEK-001" / "higgsfield-state.json",
        )
        self.assertEqual(
            second_paths.final_video,
            JOB_ROOT / "RBL-WEEK-002" / "review.mp4",
        )

    def test_historical_launch_defaults_remain_unchanged(self) -> None:
        plan = json.loads(LEGACY_PLAN_FILE.read_text(encoding="utf-8"))
        validate_video_plan(plan)
        paths = resolve_runtime_paths(plan, plan_path=LEGACY_PLAN_FILE)
        self.assertTrue(paths.legacy_launch)
        self.assertEqual(paths.state_file, LEGACY_STATE_FILE)
        self.assertEqual(paths.output_dir, LEGACY_OUTPUT_DIR)
        self.assertEqual(
            paths.final_video,
            LEGACY_OUTPUT_DIR / "rbl-launch-review.mp4",
        )

    def test_state_cannot_be_reused_by_another_weekly_job(self) -> None:
        generator = load_module("job_scoped_generator", GENERATOR)
        plan = json.loads(WEEKLY_PLAN.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state = generator.load_state(plan, state_path)
            generator.write_state(state, state_path)

            other = dict(plan)
            other["job_id"] = "RBL-OTHER-WEEK"
            with self.assertRaisesRegex(ValueError, "another video job"):
                generator.load_state(other, state_path)

    def test_job_id_cannot_escape_runtime_root(self) -> None:
        plan = json.loads(WEEKLY_PLAN.read_text(encoding="utf-8"))
        plan["job_id"] = "../escape"
        with self.assertRaisesRegex(ValueError, "letters, numbers"):
            validate_video_plan(plan)

    def test_weekly_plan_requires_20_to_30_second_total(self) -> None:
        plan = json.loads(WEEKLY_PLAN.read_text(encoding="utf-8"))
        plan["shots"] = plan["shots"][:4]
        plan["target_duration_seconds"] = 16
        with self.assertRaisesRegex(ValueError, "between 20 and 30"):
            validate_video_plan(plan)

    def test_weekly_plan_requires_human_review_policy(self) -> None:
        plan = json.loads(WEEKLY_PLAN.read_text(encoding="utf-8"))
        plan["publication_policy"] = "AUTO_PUBLISH"
        with self.assertRaisesRegex(ValueError, "blocked pending human review"):
            validate_video_plan(plan)

    def test_generator_and_assembler_accept_explicit_weekly_plan(self) -> None:
        generator = load_module("job_scoped_generator_parser", GENERATOR)
        assembler = load_module("job_scoped_assembler_parser", ASSEMBLER)

        generated_args = generator.build_parser().parse_args(
            ["--plan", str(WEEKLY_PLAN), "--retry-shot", "S02"]
        )
        assembled_args = assembler.build_parser().parse_args(
            ["--plan", str(WEEKLY_PLAN)]
        )
        self.assertEqual(generated_args.plan, WEEKLY_PLAN)
        self.assertEqual(generated_args.retry_shot, ["S02"])
        self.assertEqual(assembled_args.plan, WEEKLY_PLAN)

    def test_job_runtime_directory_is_gitignored(self) -> None:
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".production/jobs/", text)


if __name__ == "__main__":
    unittest.main()
