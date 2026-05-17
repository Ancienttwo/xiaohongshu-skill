import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnose_workspace import discover_workspace_dirs, evaluate_client_dir
from init_client_workspace import main as init_main


class WorkspacePathsTest(unittest.TestCase):
    def test_init_creates_default_workspace_under_profile_vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"HOME": tmp}):
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "init_client_workspace.py",
                        "--client",
                        "Clear Skin Lab",
                        "--profile",
                        "clear-skin-lab",
                        "--industry",
                        "Skincare",
                        "--root",
                        str(ROOT),
                    ],
                ):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(init_main(), 0)

            client_dir = Path(tmp) / ".growth" / "vault" / "clear-skin-lab" / "xiaohongshu"
            self.assertTrue((client_dir / "01-client-brief.md").exists())
            self.assertTrue((client_dir / "metrics.csv").exists())
            self.assertTrue((client_dir / "lessons").is_dir())
            self.assertTrue((Path(tmp) / ".growth" / "vault" / "_library" / "xiaohongshu" / "personas").is_dir())
            self.assertTrue((Path(tmp) / ".growth" / "vault" / "_library" / "xiaohongshu" / "benchmarks").is_dir())
            self.assertTrue((Path(tmp) / ".growth" / "vault" / "_library" / "_shared" / "offers").is_dir())

            discovered = discover_workspace_dirs(Path(tmp) / ".growth")
            self.assertEqual(discovered, [client_dir])
            self.assertEqual(evaluate_client_dir(client_dir)["client_slug"], "clear-skin-lab")

    def test_discover_keeps_platform_first_legacy_workspace_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            client_dir = Path(tmp) / ".growth" / "xiaohongshu" / "clear-skin-lab"
            client_dir.mkdir(parents=True)
            (client_dir / "01-client-brief.md").write_text("brief")

            discovered = discover_workspace_dirs(Path(tmp) / ".growth")
            self.assertEqual(discovered, [client_dir])
            self.assertEqual(evaluate_client_dir(client_dir)["client_slug"], "clear-skin-lab")

    def test_discover_prefers_vault_workspace_over_legacy_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / ".growth" / "vault" / "astrozi" / "xiaohongshu"
            legacy = Path(tmp) / ".growth" / "xiaohongshu" / "astrozi"
            canonical.mkdir(parents=True)
            legacy.mkdir(parents=True)
            (canonical / "01-client-brief.md").write_text("canonical")
            (legacy / "01-client-brief.md").write_text("legacy")

            self.assertEqual(discover_workspace_dirs(Path(tmp) / ".growth"), [canonical])

    def test_discover_does_not_treat_platform_library_as_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / ".growth" / "vault" / "_library" / "xiaohongshu"
            library.mkdir(parents=True)
            (library / "personas").mkdir()
            client_dir = Path(tmp) / ".growth" / "vault" / "astrozi" / "xiaohongshu"
            client_dir.mkdir(parents=True)
            (client_dir / "01-client-brief.md").write_text("brief")

            self.assertEqual(discover_workspace_dirs(Path(tmp) / ".growth"), [client_dir])


if __name__ == "__main__":
    unittest.main()
