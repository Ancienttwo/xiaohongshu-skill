import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from publish_note import find_markdown_leaks, markdown_to_xhs_native, prepare_note_from_markdown


class PublishNoteTest(unittest.TestCase):
    def test_prepare_note_converts_markdown_to_xhs_native_body(self):
        draft = textwrap.dedent(
            """
            # Fallback H1

            ## Final Title

            一张图看懂：**八字十神**到底在说什么？

            ## Final Body

            很多人第一次看八字，
            最容易卡在「十神」。

            **十神 = 我和外界的十种关系。**

            🌿 **1｜比劫：和我同类的人**

            - 它不一定好
            - 也不一定坏

            [查看说明](https://example.com)

            ## Hashtags

            #八字 #十神
            """
        )

        note = prepare_note_from_markdown(draft)

        self.assertEqual(note.title, "一张图看懂：八字十神到底在说什么？")
        self.assertIn("十神 = 我和外界的十种关系。", note.full_body)
        self.assertIn("🌿 1｜比劫：和我同类的人", note.full_body)
        self.assertIn("查看说明", note.full_body)
        self.assertNotIn("**", note.full_body)
        self.assertNotIn("[查看说明]", note.full_body)
        self.assertEqual(find_markdown_leaks(note.full_body), [])

    def test_markdown_leak_detector_rejects_common_visible_markers(self):
        text = "## Heading\n\n**bold**\n\n- [ ] todo\n\n| a | b |"
        leaks = find_markdown_leaks(text)
        self.assertIn("heading_marker", leaks)
        self.assertIn("bold_or_italic_marker", leaks)
        self.assertIn("checklist_marker", leaks)
        self.assertIn("markdown_table", leaks)

    def test_markdown_to_xhs_native_turns_table_row_into_native_line(self):
        converted = markdown_to_xhs_native("| Day | Title |\n|---|---|\n| D3 | 十神是什么 |")
        self.assertIn("Day ｜ Title", converted)
        self.assertIn("D3 ｜ 十神是什么", converted)
        self.assertNotIn("|---|", converted)


if __name__ == "__main__":
    unittest.main()
