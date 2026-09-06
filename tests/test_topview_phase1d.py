import copy
import json
import tempfile
import unittest
from pathlib import Path

from rbl_content_engine.topview.pilot import (
    apply_phase_1d_preflight,
    confirm_phase_1d_preflight,
    evaluate_phase_1d_preflight,
    evaluate_reference_pilot_status,
)
from rbl_content_engine.topview.references import (
    approve_reference,
    initialize_reference_registry,
    lock_reference,
    record_remote_asset,
    validate_reference_registry,
)
from rbl_content_engine.topview.validator import CANONICAL_CAPABILITIES, validate_state


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "examples" / "topview" / "reference-pilot"


def load_manifest() -> dict:
    return json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


def load_state() -> dict:
    return json.loads(
        (ROOT / ".production" / "topview-state.example.json").read_text(
            encoding="utf-8"
        )
    )


def live_capabilities() -> dict:
    capabilities = []
    for capability_id in sorted(CANONICAL_CAPABILITIES):
        capabilities.append(
            {
                "id": capability_id,
                "status": "VERIFIED_LIVE",
                "tool_name": f"observed_{capability_id}",
                "chargeable": capability_id
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
                "verified_at": "2026-09-06T14:00:00Z",
                "schema_notes": "synthetic live-discovery fixture",
                "source": "LIVE_MCP",
            }
        )
    return {
        "schema_version": "0.1.0",
        "captured_at": "2026-09-06T14:00:00Z",
        "operator_environment": "codex",
        "session": {
            "status": "READY",
            "mcp_name": "synthetic-topview-mcp",
            "mcp_version": "test",
            "connected": True,
            "authenticated": True,
            "notes": "synthetic fixture only",
        },
        "account": {
            "account_hint": "test-account",
            "canvas_id": "canvas-observed-001",
            "canvas_access": True,
            "ownership_permission": True,
        },
        "capabilities": capabilities,
        "generation_configs": [
            {
                "task_type": "image_to_video",
                "submit_model": "synthetic-live-image-to-video",
                "supported_resolutions": ["720p", "1080p"],
                "supported_durations": [5],
                "required_fields": ["prompt", "image"],
                "native_audio": False,
                "billing_hint": "synthetic fixture; no call performed",
            }
        ],
    }


class Phase1DTopviewTests(unittest.TestCase):
    def test_repository_routes_phase1d_and_keeps_live_registry_private(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertIn("docs/topview/PHASE_1D_PILOT.md", agents)
        self.assertIn("source drift after locking is a hard stop", agents)
        self.assertIn(".production/topview-references.json", gitignore)
        self.assertNotIn(".production/topview-references.example.json", gitignore)

    def test_tracked_reference_registry_example_matches_fixture_hashes(self) -> None:
        registry = json.loads(
            (ROOT / ".production" / "topview-references.example.json").read_text(
                encoding="utf-8"
            )
        )
        result = validate_reference_registry(registry, ROOT, manifest=load_manifest())
        self.assertTrue(result.valid, result.to_dict())
        self.assertEqual(registry["status"], "AWAITING_REMOTE_REGISTRATION")

    def test_phase1d_blocks_without_real_live_discovery(self) -> None:
        capabilities = json.loads(
            (ROOT / ".production" / "topview-capabilities.example.json").read_text(
                encoding="utf-8"
            )
        )
        result = evaluate_phase_1d_preflight(load_manifest(), load_state(), capabilities)
        self.assertEqual(result.status, "BLOCKED")
        self.assertFalse(result.ready_for_confirmation)
        self.assertTrue(any("not READY" in blocker for blocker in result.blockers))

    def test_reference_staging_requires_human_confirmed_ready_preflight(self) -> None:
        with self.assertRaisesRegex(ValueError, "preflight status READY"):
            initialize_reference_registry(
                load_manifest(),
                load_state(),
                ROOT,
                ["REF_PRODUCT"],
                timestamp="2026-09-06T14:01:00Z",
            )

    def test_full_phase1d_reference_lifecycle_stops_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            asset_dir = workspace / "assets"
            asset_dir.mkdir()
            product = asset_dir / "product.txt"
            style = asset_dir / "style.txt"
            product.write_text("approved product fixture\n", encoding="utf-8")
            style.write_text("approved style fixture\n", encoding="utf-8")

            manifest = load_manifest()
            manifest["references"][0]["source"] = "assets/product.txt"
            manifest["references"][1]["source"] = "assets/style.txt"
            state = load_state()
            capabilities = live_capabilities()

            preflight = evaluate_phase_1d_preflight(manifest, state, capabilities)
            self.assertTrue(preflight.ready_for_confirmation, preflight.to_dict())
            self.assertEqual(preflight.status, "READY_FOR_CONFIRMATION")

            state = apply_phase_1d_preflight(
                state,
                capabilities,
                preflight,
                checked_at="2026-09-06T14:02:00Z",
            )
            self.assertEqual(state["preflight"]["status"], "APPROVAL_REQUIRED")
            self.assertEqual(state["approval_required"], "PREFLIGHT_CONFIRMATION")

            state = confirm_phase_1d_preflight(
                state,
                human_confirmed=True,
                confirmed_at="2026-09-06T14:03:00Z",
            )
            self.assertEqual(state["preflight"]["status"], "READY")
            self.assertTrue(validate_state(state).valid)

            registry, state = initialize_reference_registry(
                manifest,
                state,
                workspace,
                ["REF_PRODUCT", "REF_STYLE_MASTER"],
                timestamp="2026-09-06T14:04:00Z",
            )
            self.assertEqual(registry["status"], "AWAITING_REMOTE_REGISTRATION")
            self.assertEqual(state["current_phase"], "REFERENCES")
            self.assertEqual(state["generated_tasks"], [])

            with self.assertRaisesRegex(ValueError, "remote asset ID"):
                approve_reference(
                    registry,
                    state,
                    "REF_PRODUCT",
                    human_confirmed=True,
                    timestamp="2026-09-06T14:05:00Z",
                )

            registry, state = record_remote_asset(
                registry,
                state,
                "REF_PRODUCT",
                "topview-asset-product-observed",
                timestamp="2026-09-06T14:06:00Z",
            )
            registry, state = record_remote_asset(
                registry,
                state,
                "REF_STYLE_MASTER",
                "topview-asset-style-observed",
                timestamp="2026-09-06T14:07:00Z",
            )
            self.assertEqual(registry["status"], "AWAITING_HUMAN_APPROVAL")
            self.assertEqual(state["approval_required"], "REFERENCE_APPROVAL")

            with self.assertRaisesRegex(ValueError, "explicit human confirmation"):
                approve_reference(
                    registry,
                    state,
                    "REF_PRODUCT",
                    human_confirmed=False,
                    timestamp="2026-09-06T14:08:00Z",
                )

            registry, state = approve_reference(
                registry,
                state,
                "REF_PRODUCT",
                human_confirmed=True,
                timestamp="2026-09-06T14:09:00Z",
            )
            registry, state = approve_reference(
                registry,
                state,
                "REF_STYLE_MASTER",
                human_confirmed=True,
                timestamp="2026-09-06T14:10:00Z",
            )
            self.assertEqual(registry["status"], "AWAITING_REFERENCE_LOCK")

            registry, state = lock_reference(
                registry,
                state,
                workspace,
                "REF_PRODUCT",
                timestamp="2026-09-06T14:11:00Z",
            )
            registry, state = lock_reference(
                registry,
                state,
                workspace,
                "REF_STYLE_MASTER",
                timestamp="2026-09-06T14:12:00Z",
            )
            self.assertEqual(registry["status"], "COMPLETE")
            self.assertIsNone(state["approval_required"])
            self.assertEqual(state["generated_tasks"], [])
            self.assertEqual(state["budget"]["actual_project_spend_usd"], 0)

            status = evaluate_reference_pilot_status(
                manifest, state, capabilities, registry, str(workspace)
            )
            self.assertTrue(status.complete, status.to_dict())
            self.assertEqual(status.status, "COMPLETE")
            self.assertTrue(validate_state(state).valid)

            product.write_text("silently changed product fixture\n", encoding="utf-8")
            drift = validate_reference_registry(registry, workspace, manifest=manifest)
            self.assertFalse(drift.valid)
            self.assertIn(
                "REFERENCE_SOURCE_DRIFT", {issue.code for issue in drift.issues}
            )

            blocked = evaluate_reference_pilot_status(
                manifest, state, capabilities, registry, str(workspace)
            )
            self.assertEqual(blocked.status, "BLOCKED")

    def test_locked_reference_cannot_be_repointed_to_another_remote_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            fixture = workspace / "product.txt"
            fixture.write_text("fixture\n", encoding="utf-8")
            manifest = load_manifest()
            manifest["references"] = [copy.deepcopy(manifest["references"][0])]
            manifest["references"][0]["source"] = "product.txt"
            manifest["scenes"][0]["references"] = ["REF_PRODUCT"]
            manifest["style"]["reference_id"] = None

            state = load_state()
            capabilities = live_capabilities()
            preflight = evaluate_phase_1d_preflight(manifest, state, capabilities)
            state = apply_phase_1d_preflight(
                state, capabilities, preflight, checked_at="2026-09-06T14:20:00Z"
            )
            state = confirm_phase_1d_preflight(
                state, human_confirmed=True, confirmed_at="2026-09-06T14:21:00Z"
            )
            registry, state = initialize_reference_registry(
                manifest,
                state,
                workspace,
                ["REF_PRODUCT"],
                timestamp="2026-09-06T14:22:00Z",
            )
            registry, state = record_remote_asset(
                registry,
                state,
                "REF_PRODUCT",
                "asset-1",
                timestamp="2026-09-06T14:23:00Z",
            )
            registry, state = approve_reference(
                registry,
                state,
                "REF_PRODUCT",
                human_confirmed=True,
                timestamp="2026-09-06T14:24:00Z",
            )
            registry, state = lock_reference(
                registry,
                state,
                workspace,
                "REF_PRODUCT",
                timestamp="2026-09-06T14:25:00Z",
            )

            with self.assertRaisesRegex(ValueError, "locked references"):
                record_remote_asset(
                    registry,
                    state,
                    "REF_PRODUCT",
                    "asset-2",
                    timestamp="2026-09-06T14:26:00Z",
                )


if __name__ == "__main__":
    unittest.main()
