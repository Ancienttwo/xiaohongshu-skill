import contextlib
import io
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from learn_client_edits import detect_calendar_patterns, detect_text_bias_patterns
from learn_client_edits import main as learn_main
from playbook_utils import load_playbook_rules


DRAFT_CALENDAR = textwrap.dedent(
    """\
    # 04 Content Calendar

    | Day | Publish Count | Title | Content Type | Keyword | Cover Direction | Publish Time |
    |---|---:|---|---|---|---|---|
    | D3 | 1 | 敏感肌修护完整避坑指南新手必看版 | how-to | 敏感肌 | cover | 20:00 |
    | D4 | 3 | 敏感肌修护结果对比真实记录全过程 | proof | 敏感肌 | cover | 20:00 |
    """
)

FINAL_CALENDAR = textwrap.dedent(
    """\
    # 04 Content Calendar

    | Day | Publish Count | Title | Content Type | Keyword | Cover Direction | Publish Time |
    |---|---:|---|---|---|---|---|
    | D3 | 1 | 敏感肌避坑指南 | how-to | 敏感肌 | cover | 20:00 |
    | D4 | 1 | 敏感肌结果对比 | proof | 敏感肌 | cover | 20:00 |
    """
)


class DetectPatternsTest(unittest.TestCase):
    def test_shorter_titles_and_lower_volume_are_detected(self):
        keys = {item["key"] for item in detect_calendar_patterns(DRAFT_CALENDAR, FINAL_CALENDAR)}
        self.assertIn("prefer-shorter-titles", keys)
        self.assertIn("reduce-daily-volume", keys)

    def test_emoji_removal_is_detected(self):
        patterns = detect_text_bias_patterns("标题🌿✨", "标题")
        self.assertIn("reduce-emoji-usage", {item["key"] for item in patterns})

    def test_added_questions_are_detected(self):
        patterns = detect_text_bias_patterns("第一行\n第二行", "怎么做？\n为什么？")
        self.assertIn("prefer-question-hooks", {item["key"] for item in patterns})


class LearnMainTest(unittest.TestCase):
    def run_learn(self, client_dir: Path, draft: Path, final: Path) -> dict:
        argv = [
            "learn_client_edits.py",
            "--client-dir",
            str(client_dir),
            "--draft",
            str(draft),
            "--final",
            str(final),
            "--json",
        ]
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
            self.assertEqual(learn_main(), 0)
        return json.loads(stdout.getvalue())

    def test_lessons_are_recorded_and_become_loadable_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            client_dir = Path(tmp)
            draft = client_dir / "04-content-calendar.v1.md"
            final = client_dir / "04-content-calendar.md"
            draft.write_text(DRAFT_CALENDAR)
            final.write_text(FINAL_CALENDAR)

            payload = self.run_learn(client_dir, draft, final)
            self.assertTrue(Path(payload["lesson"]).exists())
            self.assertIn("reduce-daily-volume", payload["rules"])

            # One occurrence stays below the default has_rule confidence gate;
            # a repeated edit must push it over.
            self.run_learn(client_dir, draft, final)
            rules = load_playbook_rules(client_dir / "playbook.md")
            self.assertGreaterEqual(float(rules["reduce-daily-volume"]["confidence"]), 3.0)

            playbook = (client_dir / "playbook.md").read_text()
            self.assertIn("`reduce-daily-volume`", playbook)

    def test_lessons_override_hand_edited_table_rows_per_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            client_dir = Path(tmp)
            draft = client_dir / "04-content-calendar.v1.md"
            final = client_dir / "04-content-calendar.md"
            draft.write_text(DRAFT_CALENDAR)
            final.write_text(FINAL_CALENDAR)
            self.run_learn(client_dir, draft, final)

            # Hand-edit the rendered playbook: tamper with a lessons-backed key
            # and add a manual-only key.
            playbook_path = client_dir / "playbook.md"
            playbook = playbook_path.read_text()
            playbook += "\n| `manual-rule` | title | 9.0 | 4 | Operator added by hand |\n"
            playbook = playbook.replace("| `reduce-daily-volume` | cadence | 3.0 |", "| `reduce-daily-volume` | cadence | 9.9 |")
            playbook_path.write_text(playbook)

            rules = load_playbook_rules(playbook_path)
            self.assertIn("manual-rule", rules)
            self.assertEqual(float(rules["reduce-daily-volume"]["confidence"]), 3.0)


if __name__ == "__main__":
    unittest.main()
