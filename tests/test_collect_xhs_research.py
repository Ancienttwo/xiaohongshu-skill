import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect_xhs_research import main as collect_main


def make_fake_xhs() -> Path:
    temp_dir = Path(tempfile.mkdtemp())
    path = temp_dir / "xhs"
    path.write_text(
        "#!/usr/bin/env python3\n"
        + textwrap.dedent(
            """
            import json
            import sys

            args = sys.argv[1:]
            command = args[0] if args else ""
            if command == "search":
                payload = {
                    "items": [
                        {
                            "id": "note-1",
                            "note_card": {
                                "display_title": "3个修护敏感肌的方法",
                                "type": "image",
                                "desc": "敏感肌 屏障修护 教程",
                                "user": {"nickname": "护肤账号A", "user_id": "user-1"},
                                "interact_info": {
                                    "liked_count": "1200",
                                    "collected_count": "330",
                                    "comment_count": "44"
                                },
                                "image_list": [{"url": "cover"}]
                            }
                        }
                    ]
                }
            elif command == "read":
                payload = {"note_card": {"desc": "详细讲解修护步骤和成分选择"}}
            elif command == "comments":
                payload = {"comments": [{"content": "敏感肌可以用吗？"}, {"content": "收藏了"}]}
            else:
                payload = {}
            print(json.dumps({"ok": True, "schema_version": "1", "data": payload}, ensure_ascii=False))
            """
        ).lstrip()
    )
    path.chmod(0o755)
    return path


class CollectXhsResearchTest(unittest.TestCase):
    def test_collects_live_research_into_markdown_and_evidence(self):
        fake = make_fake_xhs()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "01-client-brief.md"
            output = root / "02-competitor-analysis.md"
            evidence = root / "evidence"
            brief.write_text(
                "\n".join(
                    [
                        "# 01 Client Brief",
                        "",
                        "- Client Name: Clear Skin Lab",
                        "- Industry: Skincare",
                        "",
                        "## Main Vertical",
                        "",
                        "敏感肌修护",
                        "",
                        "## Subtopics",
                        "",
                        "- 屏障修护",
                    ]
                )
                + "\n"
            )
            output.write_text("# 02 Competitor Analysis\n\n## Keyword Map\n\n### Core Keywords\n\n- 敏感肌\n")

            code = collect_main(
                [
                    "--brief",
                    str(brief),
                    "--output",
                    str(output),
                    "--evidence-dir",
                    str(evidence),
                    "--xhs-binary",
                    str(fake),
                    "--max-keywords",
                    "1",
                    "--results-per-keyword",
                    "1",
                    "--read-limit",
                    "1",
                    "--comment-notes",
                    "1",
                    "--comments-per-note",
                    "1",
                ]
            )

            self.assertEqual(code, 0)
            markdown = output.read_text()
            self.assertIn("xhs-cli live research", markdown)
            self.assertIn("3个修护敏感肌的方法", markdown)
            self.assertIn("敏感肌可以用吗？", markdown)
            self.assertTrue((evidence / "01-search-skincare.json").exists())

    def test_all_search_failures_do_not_overwrite_analysis(self):
        temp_dir = Path(tempfile.mkdtemp())
        fake = temp_dir / "xhs"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            "print(json.dumps({'ok': False, 'schema_version': '1', 'error': {'code': 'not_authenticated', 'message': 'need login'}}))\n"
            "raise SystemExit(1)\n"
        )
        fake.chmod(0o755)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "01-client-brief.md"
            output = root / "02-competitor-analysis.md"
            evidence = root / "evidence"
            brief.write_text("- Client Name: Demo\n- Industry: Skincare\n")
            output.write_text("KEEP EXISTING ANALYSIS\n")

            code = collect_main(
                [
                    "--brief",
                    str(brief),
                    "--output",
                    str(output),
                    "--evidence-dir",
                    str(evidence),
                    "--xhs-binary",
                    str(fake),
                    "--max-keywords",
                    "1",
                ]
            )

            self.assertEqual(code, 2)
            self.assertEqual(output.read_text(), "KEEP EXISTING ANALYSIS\n")
            self.assertTrue((evidence / "01-search-skincare.json").exists())


if __name__ == "__main__":
    unittest.main()
