from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rbl_content_engine.weekly import run_weekly_pipeline


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_workspace(root: Path) -> tuple[Path, Path, Path]:
    evidence = root / "evidence.md"
    evidence.write_text(
        "Claim one is supported.\n"
        "Claim two is supported.\n"
        "Claim three is supported.\n"
        "Claim four is supported.\n",
        encoding="utf-8",
    )

    claims = {
        "project": "Synthetic Weekly Story",
        "claims": [
            {
                "id": f"claim-00{index}",
                "text": f"Claim {word} is supported.",
                "evidence": [
                    {
                        "path": "evidence.md",
                        "start_line": index,
                        "end_line": index,
                        "quote": f"Claim {word} is supported.",
                    }
                ],
            }
            for index, word in enumerate(("one", "two", "three", "four"), start=1)
        ],
    }
    brief = {
        "schema_version": "1.0.0",
        "job_id": "RBL-WEEKLY-TEST-001",
        "project": "Synthetic Weekly Story",
        "topic": "a synthetic weekly story",
        "objective": "Build one short-form package for review.",
        "hook": "What happens when the small choice matters?",
        "hook_claim_ids": [],
        "targets": ["youtube", "instagram", "tiktok"],
        "approval_status": "PENDING_HUMAN",
    }
    theme = {
        "schema_version": "1.0.0",
        "theme_id": "test-theme-v1",
        "name": "Test theme",
        "voice": "concise and human",
        "visual_style": "grounded vertical cinematic",
        "target_duration_seconds": 24,
        "beats": [
            {
                "id": "hook",
                "duration_seconds": 4,
                "source": "brief_hook",
                "visual_direction": "Open on a clear unresolved moment.",
            },
            {
                "id": "setup",
                "duration_seconds": 4,
                "source": "next_claim",
                "visual_direction": "Show only supported setup details.",
            },
            {
                "id": "stakes",
                "duration_seconds": 4,
                "source": "next_claim",
                "visual_direction": "Show only supported stakes.",
            },
            {
                "id": "choice",
                "duration_seconds": 4,
                "source": "next_claim",
                "visual_direction": "Show only the supported action.",
            },
            {
                "id": "payoff",
                "duration_seconds": 4,
                "source": "next_claim",
                "visual_direction": "Show only the supported result.",
            },
            {
                "id": "close",
                "duration_seconds": 4,
                "source": "theme_text",
                "text": "Small choices reveal character.",
                "visual_direction": "Close on a neutral reflective image.",
            },
        ],
    }

    claims_path = root / "claims.json"
    brief_path = root / "brief.json"
    theme_path = root / "theme.json"
    write_json(claims_path, claims)
    write_json(brief_path, brief)
    write_json(theme_path, theme)
    return brief_path, claims_path, theme_path


class WeeklyContentPipelineTests(unittest.TestCase):
    def test_builds_reviewable_short_with_claim_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief, claims, theme = build_workspace(root)
            result = run_weekly_pipeline(
                workspace_root=root,
                brief_path=brief,
                claims_path=claims,
                theme_path=theme,
                output_dir=Path("output"),
            )

            self.assertEqual(result["status"], "READY_FOR_HUMAN_REVIEW")
            self.assertEqual(result["verification_status"], "PASS")
            self.assertEqual(result["approval_status"], "PENDING_HUMAN")
            self.assertEqual(result["planned_duration_seconds"], 24)
            self.assertEqual(
                result["used_claim_ids"],
                ["claim-001", "claim-002", "claim-003", "claim-004"],
            )

            output = root / "output"
            self.assertTrue((output / "script.md").is_file())
            self.assertTrue((output / "storyboard.json").is_file())
            storyboard = json.loads(
                (output / "storyboard.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(storyboard["shots"]), 6)
            self.assertEqual(
                storyboard["shots"][1]["source_claim_ids"],
                ["claim-001"],
            )
            self.assertEqual(
                storyboard["shots"][1]["evidence"][0]["ref"],
                "evidence.md:L1-L1",
            )

    def test_identical_inputs_are_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief, claims, theme = build_workspace(root)
            for out in ("out-a", "out-b"):
                run_weekly_pipeline(
                    workspace_root=root,
                    brief_path=brief,
                    claims_path=claims,
                    theme_path=theme,
                    output_dir=Path(out),
                )
            for name in (
                "content-package.json",
                "script.md",
                "storyboard.json",
                "verifier-report.md",
            ):
                self.assertEqual(
                    (root / "out-a" / name).read_bytes(),
                    (root / "out-b" / name).read_bytes(),
                )

    def test_unsupported_claim_blocks_script_and_storyboard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief, claims_path, theme = build_workspace(root)
            claims = json.loads(claims_path.read_text(encoding="utf-8"))
            claims["claims"][1]["evidence"][0]["quote"] = "not present"
            write_json(claims_path, claims)

            result = run_weekly_pipeline(
                workspace_root=root,
                brief_path=brief,
                claims_path=claims_path,
                theme_path=theme,
                output_dir=Path("output"),
            )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["blocked_claim_ids"], ["claim-002"])
            self.assertFalse((root / "output" / "script.md").exists())
            self.assertFalse((root / "output" / "storyboard.json").exists())
            self.assertTrue((root / "output" / "verifier-report.md").is_file())

    def test_evidence_path_escape_blocks_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief, claims_path, theme = build_workspace(root)
            claims = json.loads(claims_path.read_text(encoding="utf-8"))
            claims["claims"][0]["evidence"][0]["path"] = "../outside.md"
            write_json(claims_path, claims)

            result = run_weekly_pipeline(
                workspace_root=root,
                brief_path=brief,
                claims_path=claims_path,
                theme_path=theme,
                output_dir=Path("output"),
            )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("claim-001", result["blocked_claim_ids"])

    def test_hook_claim_ids_attach_verified_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief_path, claims, theme = build_workspace(root)
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            brief["hook"] = "Claim one is supported."
            brief["hook_claim_ids"] = ["claim-001"]
            write_json(brief_path, brief)

            result = run_weekly_pipeline(
                workspace_root=root,
                brief_path=brief_path,
                claims_path=claims,
                theme_path=theme,
                output_dir=Path("output"),
            )
            hook = result["script_beats"][0]
            self.assertEqual(hook["source_claim_ids"], ["claim-001"])
            self.assertEqual(hook["evidence"][0]["ref"], "evidence.md:L1-L1")
            self.assertNotIn("claim-001", result["unused_claim_ids"])

    def test_unknown_hook_claim_id_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief_path, claims, theme = build_workspace(root)
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            brief["hook_claim_ids"] = ["missing-claim"]
            write_json(brief_path, brief)

            with self.assertRaisesRegex(ValueError, "unknown claim IDs"):
                run_weekly_pipeline(
                    workspace_root=root,
                    brief_path=brief_path,
                    claims_path=claims,
                    theme_path=theme,
                    output_dir=Path("output"),
                )

    def test_project_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief_path, claims, theme = build_workspace(root)
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            brief["project"] = "Different Project"
            write_json(brief_path, brief)

            with self.assertRaisesRegex(ValueError, "brief.project"):
                run_weekly_pipeline(
                    workspace_root=root,
                    brief_path=brief_path,
                    claims_path=claims,
                    theme_path=theme,
                    output_dir=Path("output"),
                )

    def test_theme_must_stay_within_v1_20_to_30_seconds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief, claims, theme_path = build_workspace(root)
            theme = json.loads(theme_path.read_text(encoding="utf-8"))
            theme["beats"][0]["duration_seconds"] = 11
            theme["target_duration_seconds"] = 31
            write_json(theme_path, theme)

            with self.assertRaisesRegex(ValueError, "between 20 and 30"):
                run_weekly_pipeline(
                    workspace_root=root,
                    brief_path=brief,
                    claims_path=claims,
                    theme_path=theme_path,
                    output_dir=Path("output"),
                )

    def test_theme_beat_cannot_be_shorter_than_generation_clip_floor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief, claims, theme_path = build_workspace(root)
            theme = json.loads(theme_path.read_text(encoding="utf-8"))
            theme["beats"][0]["duration_seconds"] = 3
            theme["beats"][1]["duration_seconds"] = 5
            write_json(theme_path, theme)

            with self.assertRaisesRegex(ValueError, "4-8 second"):
                run_weekly_pipeline(
                    workspace_root=root,
                    brief_path=brief,
                    claims_path=claims,
                    theme_path=theme_path,
                    output_dir=Path("output"),
                )

    def test_theme_cannot_require_more_claim_beats_than_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief, claims_path, theme_path = build_workspace(root)
            claims = json.loads(claims_path.read_text(encoding="utf-8"))
            claims["claims"] = claims["claims"][:3]
            write_json(claims_path, claims)

            with self.assertRaisesRegex(ValueError, "more next_claim beats"):
                run_weekly_pipeline(
                    workspace_root=root,
                    brief_path=brief,
                    claims_path=claims_path,
                    theme_path=theme_path,
                    output_dir=Path("output"),
                )

    def test_human_approval_state_cannot_be_preapproved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief_path, claims, theme = build_workspace(root)
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            brief["approval_status"] = "APPROVED"
            write_json(brief_path, brief)

            with self.assertRaisesRegex(ValueError, "PENDING_HUMAN"):
                run_weekly_pipeline(
                    workspace_root=root,
                    brief_path=brief_path,
                    claims_path=claims,
                    theme_path=theme,
                    output_dir=Path("output"),
                )

    def test_unsupported_platform_target_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief_path, claims, theme = build_workspace(root)
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            brief["targets"].append("facebook")
            write_json(brief_path, brief)

            with self.assertRaisesRegex(ValueError, "unsupported short-form target"):
                run_weekly_pipeline(
                    workspace_root=root,
                    brief_path=brief_path,
                    claims_path=claims,
                    theme_path=theme,
                    output_dir=Path("output"),
                )

    def test_checked_in_weekly_fixture_runs_end_to_end(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        fixture_root = repo_root / "examples" / "weekly"
        with tempfile.TemporaryDirectory(dir=fixture_root) as directory:
            output = Path(directory)
            result = run_weekly_pipeline(
                workspace_root=repo_root,
                brief_path=Path("examples/weekly/sample-brief.json"),
                claims_path=Path("examples/weekly/sample-claims.json"),
                theme_path=Path("examples/weekly/sample-channel-theme.json"),
                output_dir=output,
            )
            self.assertEqual(result["status"], "READY_FOR_HUMAN_REVIEW")
            self.assertEqual(result["planned_duration_seconds"], 22)
            self.assertEqual(
                result["used_claim_ids"],
                ["claim-001", "claim-002", "claim-003", "claim-004"],
            )
            self.assertTrue((output / "script.md").is_file())
            self.assertTrue((output / "storyboard.json").is_file())

    def test_weekly_cli_runs_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief, claims, theme = build_workspace(root)
            env = dict(os.environ)
            repo_root = Path(__file__).resolve().parents[1]
            env["PYTHONPATH"] = str(repo_root / "src")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "rbl_content_engine",
                    "weekly",
                    "--workspace-root",
                    str(root),
                    "--brief",
                    str(brief),
                    "--claims",
                    str(claims),
                    "--theme",
                    str(theme),
                    "--output",
                    "output",
                ],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "READY_FOR_HUMAN_REVIEW")


if __name__ == "__main__":
    unittest.main()
