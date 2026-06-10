import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from score_health import load_thresholds, traffic_tier
from score_health import main as score_main


CSV_HEADER = "date,note_title,views,likes,collects,comments,shares,content_type,keyword,status_note\n"


def metrics_row(title: str, views: int, likes: int) -> str:
    return f"2026-06-01,{title},{views},{likes},0,0,0,how-to,敏感肌,\n"


class TrafficTierTest(unittest.TestCase):
    def test_tier_boundaries_match_diagnosis_rubric(self):
        thresholds = load_thresholds()
        self.assertEqual(traffic_tier(199, thresholds)[0], "Tier 1")
        self.assertEqual(traffic_tier(200, thresholds)[0], "Tier 2")
        self.assertEqual(traffic_tier(500, thresholds)[0], "Tier 3")
        self.assertEqual(traffic_tier(2000, thresholds)[0], "Tier 4")
        self.assertEqual(traffic_tier(20000, thresholds)[0], "Tier 5")
        self.assertEqual(traffic_tier(100000, thresholds)[0], "Tier 6")

    def test_bundled_thresholds_file_is_loaded(self):
        thresholds = load_thresholds()
        self.assertEqual(thresholds["exit_criteria"]["min_notes"], 5)
        self.assertEqual(thresholds["exit_criteria"]["min_avg_views"], 500)
        self.assertEqual(thresholds["exit_criteria"]["min_avg_engagement_rate"], 3.0)


class ScoreHealthMainTest(unittest.TestCase):
    def run_score(self, metrics: str, extra_args: list[str] | None = None) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.csv"
            output_path = Path(tmp) / "06-health-report.md"
            metrics_path.write_text(metrics)
            argv = [
                "score_health.py",
                "--metrics",
                str(metrics_path),
                "--output",
                str(output_path),
                *(extra_args or []),
            ]
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(score_main(), 0)
            return output_path.read_text()

    def test_healthy_metrics_pass_exit_criteria(self):
        metrics = CSV_HEADER + "".join(metrics_row(f"note-{i}", 800, 40) for i in range(5))
        report = self.run_score(metrics)
        self.assertIn("- Exit Criteria: PASS", report)
        self.assertIn("Tier 3", report)
        self.assertIn("- Notes Analyzed: 5 (most recent of 5 recorded)", report)

    def test_recent_window_excludes_old_rows(self):
        old_rows = "".join(metrics_row(f"old-{i}", 10, 0) for i in range(5))
        new_rows = "".join(metrics_row(f"new-{i}", 1000, 50) for i in range(5))
        report = self.run_score(CSV_HEADER + old_rows + new_rows, ["--recent", "5"])
        self.assertIn("- Notes Analyzed: 5 (most recent of 10 recorded)", report)
        self.assertIn("- Exit Criteria: PASS", report)

        full_report = self.run_score(CSV_HEADER + old_rows + new_rows, ["--recent", "0"])
        self.assertIn("- Notes Analyzed: 10 (most recent of 10 recorded)", full_report)
        self.assertIn("- Exit Criteria: FAIL", full_report)

    def test_warning_outside_recent_window_still_fails_exit_criteria(self):
        flagged = "2026-06-01,flagged,800,40,0,0,0,how-to,敏感肌,suppression warning\n"
        clean = "".join(metrics_row(f"new-{i}", 800, 40) for i in range(5))
        report = self.run_score(CSV_HEADER + flagged + clean, ["--recent", "5"])
        self.assertIn("- Warning Flags: 1", report)
        self.assertIn("- Exit Criteria: FAIL", report)

    def test_explicit_missing_thresholds_path_fails_loudly(self):
        metrics = CSV_HEADER + metrics_row("note", 800, 40)
        with self.assertRaises(SystemExit) as ctx:
            self.run_score(metrics, ["--thresholds", "/no/such/file.json"])
        self.assertIn("Thresholds file not found", str(ctx.exception))

    def test_partial_thresholds_override_merges_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp) / "override.json"
            override.write_text('{"exit_criteria": {"min_notes": 3, "min_avg_views": 100, "min_avg_engagement_rate": 1.0}}')
            metrics = CSV_HEADER + "".join(metrics_row(f"note-{i}", 150, 10) for i in range(3))
            report = self.run_score(metrics, ["--thresholds", str(override)])
        # exit criteria come from the override; traffic tiers fall back to defaults
        self.assertIn("- Exit Criteria: PASS", report)
        self.assertIn("Tier 1", report)

    def test_warning_status_note_fails_exit_criteria(self):
        rows = "".join(metrics_row(f"note-{i}", 800, 40) for i in range(4))
        rows += "2026-06-01,flagged,800,40,0,0,0,how-to,敏感肌,suppression warning\n"
        report = self.run_score(CSV_HEADER + rows)
        self.assertIn("- Warning Flags: 1", report)
        self.assertIn("- Exit Criteria: FAIL", report)


if __name__ == "__main__":
    unittest.main()
