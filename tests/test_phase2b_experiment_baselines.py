from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from rbl_content_engine.revenue.analytics import load_analytics
from rbl_content_engine.revenue.models import ManifestError
from rbl_content_engine.revenue.phase2b import (
    VERSION,
    analyze,
    load_experiments,
    load_history,
    main as phase2b_main,
    markdown_report,
    write_outputs,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "examples/revenue-intelligence/experiments.json"
ANALYTICS = ROOT / "examples/revenue-intelligence/analytics.csv"
HISTORY = ROOT / "examples/revenue-intelligence/history.csv"


class Phase2BExperimentBaselineTests(unittest.TestCase):
    def payload(self):
        return analyze(
            load_experiments(EXPERIMENTS),
            load_analytics(ANALYTICS),
            load_history(HISTORY),
        )

    def test_fixture_produces_matched_baseline_comparisons(self):
        payload = self.payload()
        self.assertEqual(payload["version"], VERSION)
        by_id = {
            item["experiment"]["id"]: item for item in payload["experiments"]
        }
        long = by_id["exp-event-ops-long"]
        self.assertEqual(long["status"], "EVALUATED")
        self.assertEqual(long["baseline_cohort"]["sample_size"], 5)
        self.assertEqual(long["metric_comparisons"]["views"]["median"], 3200.0)
        self.assertEqual(
            long["metric_comparisons"]["views"]["comparison"], "ABOVE_BASELINE"
        )
        self.assertEqual(long["metric_comparisons"]["watch_time_minutes"]["median"], 1020.0)
        self.assertEqual(long["metric_comparisons"]["leads"]["median"], 4.0)
        self.assertEqual(
            long["metric_comparisons"]["leads"]["comparison"], "ABOVE_BASELINE"
        )
        short = by_id["exp-event-ops-short"]
        self.assertEqual(short["status"], "EVALUATED")
        self.assertEqual(short["baseline_cohort"]["sample_size"], 4)
        self.assertEqual(short["metric_comparisons"]["views"]["median"], 4200.0)
        self.assertEqual(
            short["metric_comparisons"]["views"]["comparison"], "ABOVE_BASELINE"
        )
        self.assertEqual(
            short["metric_comparisons"]["watch_time_minutes"]["median"], 197.5
        )
        self.assertEqual(short["metric_comparisons"]["leads"]["median"], 1.5)

    def test_report_retains_treatment_metadata_and_noncausal_language(self):
        report = markdown_report(self.payload())
        self.assertIn("problem_first", report)
        self.assertIn("build_in_public_explainer", report)
        self.assertIn("service_or_khlim_interest", report)
        self.assertIn("### Treatment context", report)
        self.assertIn("matched n=3", report)
        self.assertIn("views: median", report)
        self.assertIn("not causal attribution", report)
        self.assertNotIn("caused the increase", report.lower())
        self.assertNotIn("guaranteed", report.lower())

    def test_duplicate_experiment_content_id_fails_closed(self):
        data = json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
        data["experiments"][1]["content_id"] = data["experiments"][0]["content_id"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(
                ManifestError, "Duplicate experiment content_id"
            ):
                load_experiments(path)

    def test_unknown_metric_and_route_fail_closed(self):
        data = json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
        data["experiments"][0]["metrics"] = ["magic_metric"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "unsupported metric"):
                load_experiments(path)
        data = json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
        data["experiments"][0]["treatment"]["monetization_routes"] = [
            "MAGIC_MONEY"
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "unknown monetization"):
                load_experiments(path)

    def test_route_integrity_matches_phase2a(self):
        data = json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
        data["experiments"][0]["treatment"]["monetization_routes"] = [
            "SERVICE_LEAD",
            "SERVICE_LEAD",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "must be unique"):
                load_experiments(path)
        data = json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
        data["experiments"][0]["treatment"]["monetization_routes"] = [
            "NONE",
            "SERVICE_LEAD",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "NONE cannot be combined"):
                load_experiments(path)

    def test_duplicate_history_content_id_fails_closed(self):
        rows = list(csv.reader(HISTORY.read_text(encoding="utf-8").splitlines()))
        rows.append(rows[1])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerows(rows)
            with self.assertRaisesRegex(ManifestError, "duplicate content_id"):
                load_history(path)

    def test_immature_history_row_fails_closed(self):
        rows = list(csv.DictReader(HISTORY.read_text(encoding="utf-8").splitlines()))
        rows[0]["observed_at"] = "2026-07-02T10:00:00+08:00"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ManifestError, "not mature"):
                load_history(path)

    def test_platform_mismatch_fails_closed(self):
        manifest = load_experiments(EXPERIMENTS)
        analytics = load_analytics(ANALYTICS)
        analytics["yt-event-ops-001"]["platform"] = "tiktok"
        with self.assertRaisesRegex(ManifestError, "platform does not match"):
            analyze(manifest, analytics, load_history(HISTORY))

    def test_window_pending_is_explicit_per_metric(self):
        manifest = load_experiments(EXPERIMENTS)
        analytics = load_analytics(ANALYTICS)
        analytics["short-build-001"]["observed_at"] = "2026-09-12T18:30:00+08:00"
        payload = analyze(manifest, analytics, load_history(HISTORY))
        item = next(
            x
            for x in payload["experiments"]
            if x["experiment"]["id"] == "exp-event-ops-short"
        )
        self.assertEqual(item["status"], "WINDOW_PENDING")
        self.assertTrue(
            all(
                result["comparison"] == "WINDOW_PENDING"
                for result in item["metric_comparisons"].values()
            )
        )

    def test_revenue_comparisons_are_currency_safe(self):
        data = json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
        data["experiments"][0]["metrics"] = ["revenue"]
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "experiments.json"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "revenue_currency"):
                load_experiments(manifest_path)

        data["experiments"][0]["revenue_currency"] = "MYR"
        rows = list(csv.DictReader(HISTORY.read_text(encoding="utf-8").splitlines()))
        fieldnames = list(rows[0].keys()) + ["revenue", "currency"]
        for index, row in enumerate(rows):
            row["revenue"] = str(10 + index)
            row["currency"] = "MYR"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "experiments.json"
            history_path = root / "history.csv"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            with history_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            manifest = load_experiments(manifest_path)
            analytics = load_analytics(ANALYTICS)
            payload = analyze(manifest, analytics, load_history(history_path))
            long = next(
                x
                for x in payload["experiments"]
                if x["experiment"]["id"] == "exp-event-ops-long"
            )
            self.assertEqual(long["metric_comparisons"]["revenue"]["currency"], "MYR")
            self.assertEqual(long["metric_comparisons"]["revenue"]["median"], 12.0)
            self.assertEqual(
                long["metric_comparisons"]["revenue"]["comparison"],
                "ABOVE_BASELINE",
            )
            analytics["yt-event-ops-001"]["currency"] = "USD"
            with self.assertRaisesRegex(ManifestError, "currency mismatch"):
                analyze(manifest, analytics, load_history(history_path))

            rows[0]["currency"] = ""
            with history_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ManifestError, "currency is required"):
                load_history(history_path)

    def test_missing_current_data_is_explicit(self):
        manifest = load_experiments(EXPERIMENTS)
        analytics = load_analytics(ANALYTICS)
        analytics.pop("short-build-001")
        payload = analyze(manifest, analytics, load_history(HISTORY))
        item = next(
            x
            for x in payload["experiments"]
            if x["experiment"]["id"] == "exp-event-ops-short"
        )
        self.assertEqual(item["status"], "NO_MATCHING_DATA")
        self.assertEqual(item["metric_comparisons"], {})

    def test_insufficient_baseline_is_not_overinterpreted(self):
        manifest = load_experiments(EXPERIMENTS)
        analytics = load_analytics(ANALYTICS)
        history = load_history(HISTORY)[:2]
        payload = analyze(manifest, analytics, history)
        long = next(
            x
            for x in payload["experiments"]
            if x["experiment"]["id"] == "exp-event-ops-long"
        )
        self.assertEqual(
            long["metric_comparisons"]["views"]["comparison"],
            "INSUFFICIENT_BASELINE",
        )
        self.assertIsNone(long["metric_comparisons"]["views"]["delta"])

    def test_generated_artifacts_are_byte_deterministic_and_cli_runs(self):
        payload = self.payload()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            first_paths = write_outputs(first, payload)
            second_paths = write_outputs(second, payload)
            for left, right in zip(first_paths, second_paths, strict=True):
                self.assertEqual(left.read_bytes(), right.read_bytes())
            cli_output = root / "cli"
            result = phase2b_main(
                [
                    str(EXPERIMENTS),
                    "--analytics",
                    str(ANALYTICS),
                    "--history",
                    str(HISTORY),
                    "--output",
                    str(cli_output),
                ]
            )
            self.assertEqual(result, 0)
            self.assertTrue((cli_output / "experiment-baselines.json").is_file())
            self.assertTrue((cli_output / "experiment-baselines.md").is_file())
            parsed = json.loads(
                (cli_output / "experiment-baselines.json").read_text(encoding="utf-8")
            )
            self.assertEqual(parsed, payload)

    def test_analysis_is_deterministic(self):
        manifest = load_experiments(EXPERIMENTS)
        analytics = load_analytics(ANALYTICS)
        history = load_history(HISTORY)
        self.assertEqual(
            analyze(manifest, analytics, history), analyze(manifest, analytics, history)
        )


if __name__ == "__main__":
    unittest.main()
