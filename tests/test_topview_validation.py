import copy
import json
import unittest
from pathlib import Path

from rbl_content_engine.topview.preflight import evaluate_preflight
from rbl_content_engine.topview.validator import (
    CANONICAL_CAPABILITIES,
    validate_capabilities,
    validate_manifest,
    validate_state,
)


ROOT = Path(__file__).resolve().parents[1]


def minimal_manifest(method: str = "existing_asset") -> dict:
    return {
        "schema_version": "0.2.0",
        "project": {
            "id": "RBL-TEST-001",
            "platform": "instagram",
            "format": "9:16",
            "runtime_target_seconds": 5,
        },
        "verification_boundary": {
            "source": "rbl_content_engine.prooflab",
            "gate": "require_verified_claims",
            "policy": "FAIL_CLOSED",
            "verified_claim_ids": [],
        },
        "budget_policy": {
            "target_monthly_usd": 60,
            "normal_monthly_cap_usd": 100,
            "absolute_monthly_ceiling_usd": 150,
            "per_video_cap_usd": 10,
            "retries_count_against_budget": True,
            "premium_generation_requires_reason": True,
            "prefer_existing_assets": True,
            "default_max_ai_generated_seconds_per_short": 10,
        },
        "approval_gates": [
            "REFERENCE_APPROVAL",
            "STORYBOARD_KEYFRAME_APPROVAL",
            "DRAFT_720P_APPROVAL",
            "FINAL_1080P_APPROVAL",
            "TIMELINE_APPROVAL",
            "EXPORT_PUBLICATION_APPROVAL",
        ],
        "references": [],
        "style": {"reference_id": None, "locked": True, "written_constraints": []},
        "environments": [],
        "scenes": [
            {
                "id": "S01",
                "purpose": "hook",
                "duration_seconds": 5,
                "content_lineage": {
                    "verification_status": "NOT_APPLICABLE",
                    "claim_ids": [],
                    "evidence_refs": [],
                },
                "references": [],
                "environment_id": None,
                "shot": {"framing": "medium"},
                "generation": {
                    "method": method,
                    "requested_model": None,
                    "resolution_draft": "source" if method == "existing_asset" else "720p",
                    "resolution_final": "source" if method == "existing_asset" else "1080p",
                    "native_audio": False,
                    "target_clip_seconds": 5,
                    "long_clip_justification": None,
                    "premium_generation_reason": None,
                    "estimated_cost_usd": 0 if method == "existing_asset" else 1,
                },
                "storyboard": {
                    "start_frame_required": False,
                    "end_frame_required": False,
                    "approved_start_frame_id": None,
                    "approved_end_frame_id": None,
                    "approval_status": "HUMAN_REQUIRED",
                },
                "entry_state": {
                    "characters": [],
                    "positions": {},
                    "clothing": {},
                    "objects": {},
                    "environment": None,
                    "camera_direction": None,
                    "emotional_state": {},
                },
                "exit_state": {
                    "characters": [],
                    "positions": {},
                    "clothing": {},
                    "objects": {},
                    "environment": None,
                    "camera_direction": None,
                    "emotional_state": {},
                },
                "continuity": {
                    "preserve_identity": True,
                    "preserve_environment": True,
                    "duplicates_allowed": False,
                    "continues_from_scene": None,
                    "object_count_constraints": [],
                    "notes": "",
                },
                "qc": {"required_checks": ["factual_lineage"]},
                "approval": {
                    "reference": "HUMAN_REQUIRED",
                    "storyboard": "HUMAN_REQUIRED",
                    "video_draft": "HUMAN_REQUIRED",
                    "final": "HUMAN_REQUIRED",
                },
            }
        ],
    }


def ready_capabilities() -> dict:
    capabilities = []
    for cap_id in sorted(CANONICAL_CAPABILITIES):
        capabilities.append(
            {
                "id": cap_id,
                "status": "VERIFIED_LIVE",
                "tool_name": f"observed_{cap_id}",
                "chargeable": cap_id
                in {
                    "image_generation",
                    "text_to_video",
                    "image_to_video",
                    "omni_reference",
                    "motion_control",
                    "targeted_video_edit",
                    "timeline_edit",
                    "timeline_export",
                },
                "verified_at": "2026-09-06T08:30:00Z",
                "schema_notes": "synthetic test fixture",
                "source": "LIVE_MCP",
            }
        )
    return {
        "schema_version": "0.1.0",
        "captured_at": "2026-09-06T08:30:00Z",
        "operator_environment": "codex",
        "session": {
            "status": "READY",
            "mcp_name": "synthetic-topview-mcp",
            "mcp_version": "test",
            "connected": True,
            "authenticated": True,
            "notes": "synthetic test fixture",
        },
        "account": {
            "account_hint": "test",
            "canvas_id": "canvas-test",
            "canvas_access": True,
            "ownership_permission": True,
        },
        "capabilities": capabilities,
        "generation_configs": [],
    }


class TopviewValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = json.loads(
            (ROOT / ".production" / "topview-state.example.json").read_text(
                encoding="utf-8"
            )
        )

    def test_safe_capability_example_is_valid_but_not_live_ready(self) -> None:
        snapshot = json.loads(
            (ROOT / ".production" / "topview-capabilities.example.json").read_text(
                encoding="utf-8"
            )
        )
        result = validate_capabilities(snapshot)
        self.assertTrue(result.valid, result.to_dict())
        self.assertEqual(snapshot["session"]["status"], "NOT_DISCOVERED")
        self.assertFalse(
            any(cap["status"] == "VERIFIED_LIVE" for cap in snapshot["capabilities"])
        )

    def test_minimal_non_factual_manifest_is_valid(self) -> None:
        result = validate_manifest(minimal_manifest())
        self.assertTrue(result.valid, result.to_dict())

    def test_unsupported_or_conflicting_lineage_cannot_enter_manifest(self) -> None:
        for blocked_status in ("UNSUPPORTED", "CONFLICTING"):
            with self.subTest(status=blocked_status):
                manifest = minimal_manifest()
                manifest["scenes"][0]["content_lineage"] = {
                    "verification_status": blocked_status,
                    "claim_ids": ["claim-001"],
                    "evidence_refs": ["evidence.md:1"],
                }
                result = validate_manifest(manifest)
                self.assertFalse(result.valid)
                self.assertIn(
                    "LINEAGE_STATUS_BLOCKED", {issue.code for issue in result.issues}
                )

    def test_verified_lineage_requires_claim_and_evidence(self) -> None:
        manifest = minimal_manifest()
        manifest["scenes"][0]["content_lineage"] = {
            "verification_status": "VERIFIED",
            "claim_ids": [],
            "evidence_refs": [],
        }
        result = validate_manifest(manifest)
        codes = {issue.code for issue in result.issues}
        self.assertIn("VERIFIED_CLAIMS_EMPTY", codes)
        self.assertIn("VERIFIED_EVIDENCE_EMPTY", codes)

    def test_long_ai_clip_requires_justification(self) -> None:
        manifest = minimal_manifest("image_to_video")
        manifest["scenes"][0]["generation"]["target_clip_seconds"] = 12
        result = validate_manifest(manifest)
        self.assertIn(
            "LONG_CLIP_JUSTIFICATION_REQUIRED",
            {issue.code for issue in result.issues},
        )

    def test_verified_live_capability_requires_observed_tool_metadata(self) -> None:
        snapshot = ready_capabilities()
        snapshot["capabilities"][0]["tool_name"] = None
        snapshot["capabilities"][0]["source"] = "NOT_OBSERVED"
        snapshot["capabilities"][0]["verified_at"] = None
        result = validate_capabilities(snapshot)
        codes = {issue.code for issue in result.issues}
        self.assertIn("VERIFIED_LIVE_SOURCE", codes)
        self.assertIn("VERIFIED_LIVE_TOOL", codes)
        self.assertIn("VERIFIED_LIVE_TIME", codes)

    def test_state_cannot_contain_generation_tasks_before_ready_preflight(self) -> None:
        state = copy.deepcopy(self.state)
        state["generated_tasks"] = [
            {
                "task_id": "task-1",
                "task_type": "image_to_video",
                "scene_id": "S01",
                "model": "synthetic",
                "status": "RUNNING",
                "estimated_cost_usd": 1,
                "actual_cost_usd": None,
                "output_id": None,
            }
        ]
        result = validate_state(state)
        self.assertIn("TASKS_BEFORE_PREFLIGHT", {issue.code for issue in result.issues})

    def test_preflight_blocks_when_live_discovery_has_not_run(self) -> None:
        capabilities = json.loads(
            (ROOT / ".production" / "topview-capabilities.example.json").read_text(
                encoding="utf-8"
            )
        )
        result = evaluate_preflight(minimal_manifest(), self.state, capabilities)
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any("not READY" in blocker for blocker in result.blockers))

    def test_non_chargeable_manifest_can_be_locally_ready(self) -> None:
        result = evaluate_preflight(
            minimal_manifest(), self.state, ready_capabilities()
        )
        self.assertEqual(result.status, "READY_NON_CHARGEABLE")
        self.assertTrue(result.ready)
        self.assertFalse(result.chargeable_operations_required)

    def test_phase_1_preflight_blocks_chargeable_generation_even_when_tools_are_ready(self) -> None:
        result = evaluate_preflight(
            minimal_manifest("image_to_video"), self.state, ready_capabilities()
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(result.chargeable_operations_required)
        self.assertIn(
            "chargeable Topview generation is not authorized in the current Phase 1 scope",
            result.blockers,
        )


if __name__ == "__main__":
    unittest.main()
