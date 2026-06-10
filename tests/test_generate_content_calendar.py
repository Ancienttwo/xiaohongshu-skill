import contextlib
import io
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_content_calendar import main as calendar_main


BRIEF = textwrap.dedent(
    """\
    # 01 Client Brief

    - Client Name: Clear Skin Lab
    - Industry: Skincare
    """
)

STRATEGY = textwrap.dedent(
    """\
    # 03 Account Strategy

    - Main Vertical: 敏感肌修护

    ## Topic Architecture

    - Pillar 1: 敏感肌修护
    - Pillar 2: 屏障修护
    """
)

ANALYSIS = textwrap.dedent(
    """\
    # 02 Competitor Analysis

    ## Keyword Map

    ### Core Keywords

    - 敏感肌

    ### Long-tail Keywords

    - 敏感肌怎么修护

    ### Trigger Keywords

    - 避坑

    ## Repeatable Content Patterns

    1. question-led hook: observed in 3 sampled notes

    ## Research Summary

    - What title patterns work repeatedly: question-led hooks

    ## Benchmark Notes

    | Account | Note Title | Content Type | Cover Style | Visible Metrics | Hook Angle | Keywords |
    |---|---|---|---|---|---|---|
    | 护肤账号A | 敏感肌到底怎么办？ | image | image-led cover | likes=10 | question-led hook | 敏感肌 |
    """
)

PLAYBOOK = textwrap.dedent(
    """\
    # Client Playbook

    ## Hard Rules

    | Key | Type | Confidence | Occurrences | Rule |
    |---|---|---:|---:|---|
    | `prefer-question-hooks` | title | 6.0 | 3 | Use question hooks |
    | `reduce-daily-volume` | cadence | 6.0 | 3 | Lower daily volume |
    """
)


class GenerateContentCalendarTest(unittest.TestCase):
    def run_calendar(self, tmp: Path, *, with_playbook: bool) -> str:
        (tmp / "01-client-brief.md").write_text(BRIEF)
        (tmp / "03-account-strategy.md").write_text(STRATEGY)
        (tmp / "02-competitor-analysis.md").write_text(ANALYSIS)
        if with_playbook:
            (tmp / "playbook.md").write_text(PLAYBOOK)
        output = tmp / "04-content-calendar.md"
        argv = [
            "generate_content_calendar.py",
            "--brief",
            str(tmp / "01-client-brief.md"),
            "--strategy",
            str(tmp / "03-account-strategy.md"),
            "--analysis",
            str(tmp / "02-competitor-analysis.md"),
            "--output",
            str(output),
        ]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(calendar_main(), 0)
        return output.read_text()

    def test_calendar_uses_research_signals_and_benchmark_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            calendar = self.run_calendar(Path(tmp), with_playbook=False)

        self.assertIn("- Core keywords: 敏感肌", calendar)
        self.assertIn("## Benchmark Note Anchors", calendar)
        self.assertIn("敏感肌到底怎么办？", calendar)
        self.assertIn("| D1 | 0 |", calendar)
        self.assertIn("| D3 | 1 |", calendar)
        self.assertIn("| D4 | 2 |", calendar)
        self.assertIn("Playbook Rules Applied: 0", calendar)

    def test_playbook_rules_change_volume_and_title_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            calendar = self.run_calendar(Path(tmp), with_playbook=True)

        self.assertIn("Playbook Rules Applied: 2", calendar)
        # reduce-daily-volume caps D4-D7 at one note per day
        self.assertIn("| D4 | 1 |", calendar)
        self.assertIn("- D4-D7: 1 note per day by default", calendar)
        # prefer-question-hooks biases the selected D3 title toward a question
        d3_row = next(line for line in calendar.splitlines() if line.startswith("| D3 |"))
        self.assertIn("？", d3_row)


if __name__ == "__main__":
    unittest.main()
