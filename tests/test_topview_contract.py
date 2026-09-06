import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TopviewContractIntegrityTests(unittest.TestCase):
    def test_contract_json_files_are_parseable(self) -> None:
        paths = [
            ROOT / "schemas" / "topview-production.schema.json",
            ROOT / "schemas" / "topview-state.schema.json",
            ROOT / ".production" / "topview-state.example.json",
        ]

        for path in paths:
            with self.subTest(path=path):
                with path.open(encoding="utf-8") as handle:
                    parsed = json.load(handle)
                self.assertIsInstance(parsed, dict)

    def test_production_schema_preserves_budget_guardrail(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "topview-production.schema.json").read_text(
                encoding="utf-8"
            )
        )
        budget = schema["properties"]["budget_policy"]["properties"]

        self.assertEqual(budget["target_monthly_usd"]["maximum"], 60)
        self.assertEqual(budget["normal_monthly_cap_usd"]["maximum"], 100)
        self.assertEqual(budget["absolute_monthly_ceiling_usd"]["maximum"], 150)
        self.assertTrue(budget["retries_count_against_budget"]["const"])
        self.assertTrue(budget["premium_generation_requires_reason"]["const"])
        self.assertEqual(
            budget["default_max_ai_generated_seconds_per_short"]["maximum"], 10
        )

    def test_production_schema_requires_continuity_and_human_gates(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "topview-production.schema.json").read_text(
                encoding="utf-8"
            )
        )
        required_scene_fields = set(schema["$defs"]["scene"]["required"])

        self.assertIn("entry_state", required_scene_fields)
        self.assertIn("exit_state", required_scene_fields)
        self.assertIn("continuity", required_scene_fields)
        self.assertIn("qc", required_scene_fields)
        self.assertIn("approval", required_scene_fields)

        gates = set(schema["properties"]["approval_gates"]["items"]["enum"])
        self.assertEqual(
            gates,
            {
                "REFERENCE_APPROVAL",
                "STORYBOARD_KEYFRAME_APPROVAL",
                "DRAFT_720P_APPROVAL",
                "FINAL_1080P_APPROVAL",
                "TIMELINE_APPROVAL",
                "EXPORT_PUBLICATION_APPROVAL",
            },
        )

    def test_production_schema_requires_prooflab_verified_handoff(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "topview-production.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(schema["properties"]["schema_version"]["const"], "0.2.0")
        self.assertIn("verification_boundary", schema["required"])

        boundary = schema["properties"]["verification_boundary"]
        self.assertEqual(
            boundary["properties"]["source"]["const"],
            "rbl_content_engine.prooflab",
        )
        self.assertEqual(
            boundary["properties"]["gate"]["const"],
            "require_verified_claims",
        )
        self.assertEqual(boundary["properties"]["policy"]["const"], "FAIL_CLOSED")

        required_scene_fields = set(schema["$defs"]["scene"]["required"])
        self.assertIn("content_lineage", required_scene_fields)

        lineage_variants = schema["$defs"]["contentLineage"]["oneOf"]
        statuses = {
            variant["properties"]["verification_status"]["const"]
            for variant in lineage_variants
        }
        self.assertEqual(statuses, {"VERIFIED", "NOT_APPLICABLE"})

        verified = next(
            variant
            for variant in lineage_variants
            if variant["properties"]["verification_status"]["const"] == "VERIFIED"
        )
        self.assertEqual(verified["properties"]["claim_ids"]["minItems"], 1)
        self.assertEqual(verified["properties"]["evidence_refs"]["minItems"], 1)

        not_applicable = next(
            variant
            for variant in lineage_variants
            if variant["properties"]["verification_status"]["const"]
            == "NOT_APPLICABLE"
        )
        self.assertEqual(not_applicable["properties"]["claim_ids"]["maxItems"], 0)
        self.assertEqual(
            not_applicable["properties"]["evidence_refs"]["maxItems"], 0
        )

        required_checks = schema["$defs"]["qcContract"]["properties"][
            "required_checks"
        ]
        self.assertEqual(required_checks["contains"]["const"], "factual_lineage")

    def test_state_example_starts_safe_and_unexecuted(self) -> None:
        state = json.loads(
            (ROOT / ".production" / "topview-state.example.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(state["current_phase"], "PREFLIGHT")
        self.assertEqual(state["preflight"]["status"], "NOT_STARTED")
        self.assertEqual(state["approval_required"], "PREFLIGHT_CONFIRMATION")
        self.assertEqual(state["generated_tasks"], [])
        self.assertEqual(state["approved_outputs"], [])
        self.assertEqual(state["budget"]["target_monthly_usd"], 60)
        self.assertEqual(state["budget"]["normal_cap_usd"], 100)
        self.assertEqual(state["budget"]["absolute_ceiling_usd"], 150)
        self.assertEqual(state["budget"]["actual_project_spend_usd"], 0)

    def test_live_state_is_gitignored(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".production/topview-state.json", gitignore)
        self.assertNotIn(".production/topview-state.example.json", gitignore)

    def test_agent_instructions_route_topview_work_to_contract_docs(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("RBL Topview Production Operator", agents)
        self.assertIn("docs/topview/WORKFLOW.md", agents)
        self.assertIn("docs/topview/TOOL_MAP.md", agents)
        self.assertIn("4–8 seconds", agents)
        self.assertIn("720p", agents)
        self.assertIn("1080p", agents)

    def test_agent_instructions_align_with_local_prooflab_contract(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertNotIn("- No ProofLab integration.", agents)
        self.assertIn("src/rbl_content_engine/prooflab.py", agents)
        self.assertIn("VerifiedClaim", agents)
        self.assertIn("require_verified_claims()", agents)
        self.assertIn("fail-closed factual boundary", agents)

    def test_workflow_contains_all_canonical_phases_and_failure_levels(self) -> None:
        workflow = (ROOT / "docs" / "topview" / "WORKFLOW.md").read_text(
            encoding="utf-8"
        )
        phases = [
            "PREFLIGHT",
            "CANVAS SETUP",
            "REFERENCES",
            "STYLE",
            "ENVIRONMENTS",
            "SCENECARDS",
            "STORYBOARD / KEYFRAMES",
            "720P VIDEO DRAFT",
            "QC",
            "TARGETED EDIT / REGENERATION",
            "FINAL 1080P GENERATION",
            "TIMELINE / AUDIO",
            "EXPORT",
            "HUMAN APPROVAL",
        ]

        for phase in phases:
            with self.subTest(phase=phase):
                self.assertIn(phase, workflow)

        for level in range(1, 7):
            with self.subTest(level=level):
                self.assertIn(f"| {level} |", workflow)

    def test_workflow_defines_prooflab_as_upstream_fact_boundary(self) -> None:
        workflow = (ROOT / "docs" / "topview" / "WORKFLOW.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("ProofLab factual boundary", workflow)
        self.assertIn("src/rbl_content_engine/prooflab.py", workflow)
        self.assertIn("VerifiedClaim", workflow)
        self.assertIn("require_verified_claims()", workflow)
        self.assertIn("Topview does not perform verification", workflow)
        self.assertIn("NOT_APPLICABLE", workflow)

    def test_tool_map_keeps_hackathon_capabilities_unverified(self) -> None:
        tool_map = (ROOT / "docs" / "topview" / "TOOL_MAP.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("HACKATHON_OBSERVED", tool_map)
        self.assertIn("Canvas ownership/permission inspection", tool_map)
        self.assertIn("Targeted `video_edit`", tool_map)
        self.assertIn("Timeline editing", tool_map)
        self.assertIn("do not invent a tool name", tool_map)
        self.assertIn("topview_get_generation_config", tool_map)


if __name__ == "__main__":
    unittest.main()
