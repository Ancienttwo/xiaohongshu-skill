import contextlib
import io
import json
import sys
import tempfile
import textwrap
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect_xhs_research import main as collect_main
import collect_xhs_research


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

            self.assertEqual(code, 1)
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


    def test_evidence_is_sanitized_and_private(self):
        fake = make_fake_xhs()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "01-client-brief.md"
            output = root / "02-competitor-analysis.md"
            evidence = root / "evidence"
            brief.write_text("- Client Name: Demo\n- Industry: Skincare\n")
            output.write_text("# 02 Competitor Analysis\n")

            code = collect_main([
                "--brief", str(brief), "--output", str(output), "--evidence-dir", str(evidence),
                "--xhs-binary", str(fake), "--max-keywords", "1", "--results-per-keyword", "1",
                "--read-limit", "1", "--comment-notes", "1",
            ])

            self.assertEqual(code, 1)
            payload = json.loads((evidence / "01-search-skincare.json").read_text())
            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("user-1", serialized)
            self.assertNotIn("cover", serialized)
            self.assertNotIn("xsec_token", serialized)
            mode = (evidence / "01-search-skincare.json").stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_read_detail_merges_missing_title_and_recomputes_hook(self):
        temp_dir = Path(tempfile.mkdtemp())
        fake = temp_dir / "xhs"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            + textwrap.dedent(
                """
                import json, sys
                command = sys.argv[1] if len(sys.argv) > 1 else ""
                if command == "search":
                    payload = {"items": [{"id": "note-1", "note_card": {"type": "image", "desc": "泛泛描述", "user": {"nickname": "账号A", "user_id": "user-1"}, "interact_info": {}}}]}
                elif command == "read":
                    payload = {"note_card": {"display_title": "7个敏感肌修护步骤", "desc": "教程 方法", "interact_info": {"liked_count": "9"}, "image_list": [{"url": "https://cdn.example/cover.jpg"}]}}
                elif command == "comments":
                    payload = {"comments": []}
                else:
                    payload = {}
                print(json.dumps({"ok": True, "schema_version": "1", "data": payload}, ensure_ascii=False))
                """
            ).lstrip()
        )
        fake.chmod(0o755)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "01-client-brief.md"
            output = root / "02-competitor-analysis.md"
            brief.write_text("- Client Name: Demo\n- Industry: Skincare\n")
            output.write_text("# Existing\n")
            code = collect_main([
                "--brief", str(brief), "--output", str(output), "--xhs-binary", str(fake),
                "--max-keywords", "1", "--results-per-keyword", "1", "--read-limit", "1",
                "--allow-partial", "--overwrite",
            ])
            markdown = output.read_text()
            self.assertEqual(code, 0)
            self.assertIn("7个敏感肌修护步骤", markdown)
            self.assertNotIn("Untitled note", markdown)
            self.assertIn("number/list hook", markdown)
            self.assertIn("likes=9", markdown)

    def test_partial_success_preserves_existing_analysis_without_overwrite(self):
        temp_dir = Path(tempfile.mkdtemp())
        fake = temp_dir / "xhs"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            + textwrap.dedent(
                """
                import json, sys
                command = sys.argv[1] if len(sys.argv) > 1 else ""
                keyword = sys.argv[2] if len(sys.argv) > 2 else ""
                if command == "search" and keyword == "Skincare":
                    print(json.dumps({"ok": False, "schema_version": "1", "error": {"code": "xhs_timeout", "message": "timeout"}}))
                    raise SystemExit(1)
                if command == "search":
                    payload = {"items": [{"id": "note-1", "note_card": {"display_title": "敏感肌方法", "user": {"nickname": "账号A", "user_id": "user-1"}, "interact_info": {}}}]}
                elif command == "read":
                    payload = {"note_card": {"desc": "详情"}}
                elif command == "comments":
                    payload = {"comments": []}
                else:
                    payload = {}
                print(json.dumps({"ok": True, "schema_version": "1", "data": payload}, ensure_ascii=False))
                """
            ).lstrip()
        )
        fake.chmod(0o755)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "01-client-brief.md"
            output = root / "02-competitor-analysis.md"
            brief.write_text("- Client Name: Demo\n- Industry: Skincare\n\n## Subtopics\n\n- 敏感肌\n")
            output.write_text("# Manual Analysis\n\nKEEP MANUAL SECTION\n")
            code = collect_main([
                "--brief", str(brief), "--output", str(output), "--xhs-binary", str(fake),
                "--max-keywords", "2", "--results-per-keyword", "1", "--read-limit", "1",
            ])
            markdown = output.read_text()
            self.assertEqual(code, 1)
            self.assertIn("KEEP MANUAL SECTION", markdown)
            self.assertIn("## Live Research Evidence", markdown)
            self.assertIn("Research Status: PARTIAL", markdown)
            self.assertIn("Failed keyword: Skincare", markdown)

    def test_negative_numeric_args_are_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            collect_main(["--brief", "brief.md", "--output", "out.md", "--results-per-keyword", "-1"])


    def test_account_enrichment_uses_user_and_user_posts(self):
        temp_dir = Path(tempfile.mkdtemp())
        fake = temp_dir / "xhs"
        log = temp_dir / "calls.log"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            + textwrap.dedent(
                f"""
                import json, sys
                from pathlib import Path
                Path({str(log)!r}).open("a").write(" ".join(sys.argv[1:]) + "\\n")
                command = sys.argv[1] if len(sys.argv) > 1 else ""
                if command == "search":
                    payload = {{"items": [{{"id": "note-1", "note_card": {{"display_title": "敏感肌方法", "user": {{"nickname": "账号A", "user_id": "user-1"}}, "interact_info": {{}}}}}}]}}
                elif command == "read":
                    payload = {{"note_card": {{"desc": "详情"}}}}
                elif command == "comments":
                    payload = {{"comments": []}}
                elif command == "user":
                    payload = {{"user": {{"nickname": "账号A", "followers": "8888", "desc": "皮肤科护士｜敏感肌修护"}}}}
                elif command == "user-posts":
                    payload = {{"items": [{{"note_card": {{"display_title": "屏障修护清单"}}}}, {{"note_card": {{"display_title": "成分避雷"}}}}]}}
                else:
                    payload = {{}}
                print(json.dumps({{"ok": True, "schema_version": "1", "data": payload}}, ensure_ascii=False))
                """
            ).lstrip()
        )
        fake.chmod(0o755)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "01-client-brief.md"
            output = root / "02-competitor-analysis.md"
            brief.write_text("- Client Name: Demo\n- Industry: Skincare\n")
            output.write_text("# Existing\n")
            code = collect_main([
                "--brief", str(brief), "--output", str(output), "--xhs-binary", str(fake),
                "--max-keywords", "1", "--results-per-keyword", "1", "--read-limit", "1",
                "--account-limit", "1", "--allow-partial", "--overwrite",
            ])
            markdown = output.read_text()
            self.assertEqual(code, 0)
            self.assertIn("8888", markdown)
            self.assertIn("皮肤科护士", markdown)
            self.assertIn("2 sampled recent posts", markdown)
            self.assertIn("屏障修护清单; 成分避雷", markdown)
            self.assertIn("user user-1", log.read_text())
            self.assertIn("user-posts user-1", log.read_text())

    def test_retries_transient_search_timeout_before_success(self):
        temp_dir = Path(tempfile.mkdtemp())
        fake = temp_dir / "xhs"
        counter = temp_dir / "count.txt"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            + textwrap.dedent(
                f"""
                import json, sys
                from pathlib import Path
                command = sys.argv[1] if len(sys.argv) > 1 else ""
                counter = Path({str(counter)!r})
                if command == "search":
                    count = int(counter.read_text() or "0") if counter.exists() else 0
                    counter.write_text(str(count + 1))
                    if count == 0:
                        print(json.dumps({{"ok": False, "schema_version": "1", "error": {{"code": "xhs_timeout", "message": "timeout"}}}}))
                        raise SystemExit(1)
                    payload = {{"items": [{{"id": "note-1", "note_card": {{"display_title": "敏感肌方法", "user": {{"nickname": "账号A", "user_id": "user-1"}}, "interact_info": {{}}}}}}]}}
                elif command == "read":
                    payload = {{"note_card": {{"desc": "详情"}}}}
                elif command == "comments":
                    payload = {{"comments": []}}
                else:
                    payload = {{}}
                print(json.dumps({{"ok": True, "schema_version": "1", "data": payload}}, ensure_ascii=False))
                """
            ).lstrip()
        )
        fake.chmod(0o755)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "01-client-brief.md"
            output = root / "02-competitor-analysis.md"
            brief.write_text("- Client Name: Demo\n- Industry: Skincare\n")
            output.write_text("# Existing\n")
            code = collect_main([
                "--brief", str(brief), "--output", str(output), "--xhs-binary", str(fake),
                "--max-keywords", "1", "--results-per-keyword", "1", "--read-limit", "1",
                "--retries", "1", "--delay-min", "0", "--delay-max", "0", "--allow-partial", "--overwrite",
            ])
            self.assertEqual(code, 0)
            self.assertEqual(counter.read_text(), "2")
            self.assertIn("敏感肌方法", output.read_text())

    def test_blocking_search_error_stops_without_other_keywords(self):
        temp_dir = Path(tempfile.mkdtemp())
        fake = temp_dir / "xhs"
        log = temp_dir / "calls.log"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            + textwrap.dedent(
                f"""
                import json, sys
                from pathlib import Path
                Path({str(log)!r}).open("a").write(" ".join(sys.argv[1:]) + "\\n")
                print(json.dumps({{"ok": False, "schema_version": "1", "error": {{"code": "verification_required", "message": "verify"}}}}))
                raise SystemExit(1)
                """
            ).lstrip()
        )
        fake.chmod(0o755)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "01-client-brief.md"
            output = root / "02-competitor-analysis.md"
            brief.write_text("- Client Name: Demo\n- Industry: Skincare\n\n## Subtopics\n\n- 敏感肌\n")
            output.write_text("KEEP\n")
            code = collect_main([
                "--brief", str(brief), "--output", str(output), "--xhs-binary", str(fake), "--max-keywords", "2",
            ])
            self.assertEqual(code, 2)
            self.assertEqual(len(log.read_text().strip().splitlines()), 1)
            self.assertEqual(output.read_text(), "KEEP\n")

    def test_account_enrichment_limitations_are_reported(self):
        temp_dir = Path(tempfile.mkdtemp())
        fake = temp_dir / "xhs"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            + textwrap.dedent(
                """
                import json, sys
                command = sys.argv[1] if len(sys.argv) > 1 else ""
                if command == "search":
                    payload = {"items": [{"id": "note-1", "note_card": {"display_title": "敏感肌方法", "user": {"nickname": "账号A", "user_id": "user-1"}, "interact_info": {}}}]}
                elif command == "read":
                    payload = {"note_card": {"desc": "详情"}}
                elif command == "comments":
                    payload = {"comments": []}
                elif command == "user":
                    print(json.dumps({"ok": False, "schema_version": "1", "error": {"code": "xhs_command_failed", "message": "user failed"}}))
                    raise SystemExit(1)
                elif command == "user-posts":
                    payload = {"items": []}
                else:
                    payload = {}
                print(json.dumps({"ok": True, "schema_version": "1", "data": payload}, ensure_ascii=False))
                """
            ).lstrip()
        )
        fake.chmod(0o755)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "01-client-brief.md"
            output = root / "02-competitor-analysis.md"
            brief.write_text("- Client Name: Demo\n- Industry: Skincare\n")
            output.write_text("# Existing\n")
            code = collect_main([
                "--brief", str(brief), "--output", str(output), "--xhs-binary", str(fake),
                "--max-keywords", "1", "--results-per-keyword", "1", "--read-limit", "1",
                "--account-limit", "1", "--allow-partial", "--overwrite",
            ])
            markdown = output.read_text()
            self.assertEqual(code, 0)
            self.assertIn("Account profile enrichment failed", markdown)
            self.assertIn("Account recent-post enrichment returned no titles", markdown)

    def test_command_delay_applies_after_xhs_commands(self):
        fake = make_fake_xhs()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "01-client-brief.md"
            output = root / "02-competitor-analysis.md"
            brief.write_text("- Client Name: Demo\n- Industry: Skincare\n")
            output.write_text("# Existing\n")
            with mock.patch.object(collect_xhs_research.random, "uniform", return_value=0.01), \
                 mock.patch.object(collect_xhs_research.time, "sleep") as sleep:
                code = collect_main([
                    "--brief", str(brief), "--output", str(output), "--xhs-binary", str(fake),
                    "--max-keywords", "1", "--results-per-keyword", "1", "--read-limit", "1",
                    "--account-limit", "1", "--command-delay-min", "0.01", "--command-delay-max", "0.02",
                    "--allow-partial", "--overwrite",
                ])
            self.assertEqual(code, 0)
            self.assertGreaterEqual(sleep.call_count, 3)
            sleep.assert_any_call(0.01)


if __name__ == "__main__":
    unittest.main()
