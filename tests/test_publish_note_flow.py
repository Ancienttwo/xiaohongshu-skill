import contextlib
import io
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_note
from xhs_cli_utils import XhsCliError


DRAFT = textwrap.dedent(
    """\
    ## Final Title

    敏感肌修护三步法

    ## Final Body

    第一步：温和清洁。

    第二步：屏障修护。

    ## Hashtags

    #敏感肌
    """
)


class PublishFlowTest(unittest.TestCase):
    def run_publish(self, tmp: Path, *, run_xhs_side_effect) -> tuple[int, dict]:
        draft_path = tmp / "draft.md"
        image_path = tmp / "cover.png"
        draft_path.write_text(DRAFT)
        image_path.write_bytes(b"png")
        argv = [
            "publish_note.py",
            "--client-dir",
            str(tmp),
            "--draft",
            str(draft_path),
            "--images",
            str(image_path),
            "--post",
        ]
        post_result = SimpleNamespace(data={"id": "note-1"}, envelope={"ok": True, "data": {"id": "note-1"}})
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(publish_note, "run_xhs", side_effect=run_xhs_side_effect), \
             mock.patch.object(publish_note, "run_xhs_command", return_value=post_result), \
             contextlib.redirect_stdout(stdout):
            code = publish_note.main()
        return code, json.loads(stdout.getvalue())

    def test_verify_failure_after_successful_post_is_not_reported_as_failed(self):
        def fake_run_xhs(args, **kwargs):
            if args[0] == "whoami":
                return {"nickname": "studio"}
            raise XhsCliError("xhs_timeout", "my-notes timed out")

        with tempfile.TemporaryDirectory() as tmp:
            code, payload = self.run_publish(Path(tmp), run_xhs_side_effect=fake_run_xhs)

            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["status"], "DONE_WITH_CONCERNS")
            self.assertEqual(payload["note_id"], "note-1")
            self.assertEqual(payload["verify_error"]["code"], "xhs_timeout")

            log = (Path(tmp) / "xhs-action-log.md").read_text()
            self.assertIn("verify_error", log)
            self.assertIn("note-1", log)
            # verify failure must not create a metrics row
            self.assertFalse((Path(tmp) / "metrics.csv").exists())

    def test_successful_post_and_verify_appends_metrics(self):
        def fake_run_xhs(args, **kwargs):
            if args[0] == "whoami":
                return {"nickname": "studio"}
            return {"notes": [{"id": "note-1", "display_title": "敏感肌修护三步法", "view_count": 12, "likes": 1}]}

        with tempfile.TemporaryDirectory() as tmp:
            code, payload = self.run_publish(Path(tmp), run_xhs_side_effect=fake_run_xhs)

            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "DONE")
            self.assertIsNone(payload["verify_error"])

            metrics = (Path(tmp) / "metrics.csv").read_text()
            self.assertIn("敏感肌修护三步法", metrics)
            log = (Path(tmp) / "xhs-action-log.md").read_text()
            self.assertIn('"markdown_leaks": []', log)


if __name__ == "__main__":
    unittest.main()
