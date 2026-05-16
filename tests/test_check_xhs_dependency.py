import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_xhs_dependency import EXIT_COMMAND_MISSING, EXIT_OK, main as check_main


def make_fake_xhs(commands: set[str]) -> Path:
    temp_dir = Path(tempfile.mkdtemp())
    path = temp_dir / "xhs"
    path.write_text(
        "#!/usr/bin/env python3\n"
        + textwrap.dedent(
            f"""
            import json, sys
            commands = {sorted(commands)!r}
            if "--version" in sys.argv:
                print("xhs, version 0.6.4")
                raise SystemExit(0)
            command = sys.argv[1] if len(sys.argv) > 1 else ""
            if "--help" in sys.argv:
                raise SystemExit(0 if command in commands else 2)
            if command == "status":
                print(json.dumps({{"ok": True, "schema_version": "1", "data": {{"authenticated": True, "user": {{"nickname": "Demo"}}}}}}))
                raise SystemExit(0)
            print(json.dumps({{"ok": True, "schema_version": "1", "data": {{}}}}))
            """
        ).lstrip()
    )
    path.chmod(0o755)
    return path


class CheckXhsDependencyTest(unittest.TestCase):
    def test_research_mode_does_not_require_post_command(self):
        fake = make_fake_xhs({"status", "whoami", "search", "read", "comments", "user", "user-posts", "my-notes", "topics", "hot"})
        self.assertEqual(check_main(["--xhs-binary", str(fake), "--research"]), EXIT_OK)

    def test_default_mode_still_requires_write_post_command(self):
        fake = make_fake_xhs({"status", "whoami", "search", "read", "comments", "user", "user-posts", "my-notes"})
        self.assertEqual(check_main(["--xhs-binary", str(fake)]), EXIT_COMMAND_MISSING)


if __name__ == "__main__":
    unittest.main()
