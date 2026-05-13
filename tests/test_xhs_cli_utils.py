import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from xhs_cli_utils import XhsCliError, get_xhs_version, run_xhs


def make_fake_xhs(body: str) -> Path:
    temp_dir = Path(tempfile.mkdtemp())
    path = temp_dir / "xhs"
    path.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body).lstrip())
    path.chmod(0o755)
    return path


class XhsCliUtilsTest(unittest.TestCase):
    def test_success_envelope_returns_data(self):
        fake = make_fake_xhs(
            """
            import json
            import sys
            if "--version" in sys.argv:
                print("xhs, version 0.6.4")
                raise SystemExit(0)
            print(json.dumps({"ok": True, "schema_version": "1", "data": {"authenticated": True}}))
            """
        )

        self.assertEqual(get_xhs_version(str(fake)), (0, 6, 4))
        self.assertEqual(run_xhs(["status"], binary=str(fake)), {"authenticated": True})

    def test_error_envelope_raises_structured_error(self):
        fake = make_fake_xhs(
            """
            import json
            print(json.dumps({
                "ok": False,
                "schema_version": "1",
                "error": {"code": "not_authenticated", "message": "need login"}
            }))
            raise SystemExit(1)
            """
        )

        with self.assertRaises(XhsCliError) as context:
            run_xhs(["status"], binary=str(fake))
        self.assertEqual(context.exception.code, "not_authenticated")

    def test_schema_drift_is_rejected(self):
        fake = make_fake_xhs(
            """
            import json
            print(json.dumps({"ok": True, "schema_version": "2", "data": {}}))
            """
        )

        with self.assertRaises(XhsCliError) as context:
            run_xhs(["search", "护肤"], binary=str(fake))
        self.assertEqual(context.exception.code, "schema_drift")

    def test_non_json_output_is_rejected(self):
        fake = make_fake_xhs(
            """
            print("plain text")
            """
        )

        with self.assertRaises(XhsCliError) as context:
            run_xhs(["search", "护肤"], binary=str(fake))
        self.assertEqual(context.exception.code, "non_json_output")


if __name__ == "__main__":
    unittest.main()
