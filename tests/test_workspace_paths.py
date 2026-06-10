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
from migrate_workspace import find_legacy_workspaces, migrate


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

    def test_legacy_platform_first_workspace_is_flagged_and_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".growth"
            legacy = root / "xiaohongshu" / "clear-skin-lab"
            legacy.mkdir(parents=True)
            (legacy / "01-client-brief.md").write_text("brief")

            self.assertEqual(discover_workspace_dirs(root), [])
            canonical = root / "vault" / "clear-skin-lab" / "xiaohongshu"
            self.assertEqual(find_legacy_workspaces(root), [(legacy, canonical)])

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(migrate(root, apply=True), 0)
            self.assertEqual(discover_workspace_dirs(root), [canonical])
            self.assertEqual((canonical / "01-client-brief.md").read_text(), "brief")
            self.assertEqual(evaluate_client_dir(canonical)["client_slug"], "clear-skin-lab")

    def test_migrate_reports_conflict_when_canonical_duplicate_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".growth"
            canonical = root / "vault" / "astrozi" / "xiaohongshu"
            legacy = root / "xiaohongshu" / "astrozi"
            canonical.mkdir(parents=True)
            legacy.mkdir(parents=True)
            (canonical / "01-client-brief.md").write_text("canonical")
            (legacy / "01-client-brief.md").write_text("legacy")

            self.assertEqual(discover_workspace_dirs(root), [canonical])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(migrate(root, apply=True), 1)
            self.assertEqual((canonical / "01-client-brief.md").read_text(), "canonical")
            self.assertTrue(legacy.exists())

    def test_vault_root_is_never_treated_as_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".growth"
            canonical = root / "vault" / "astrozi" / "xiaohongshu"
            canonical.mkdir(parents=True)
            (canonical / "01-client-brief.md").write_text("canonical")

            # Pointing --root at the vault itself must not classify canonical
            # workspaces as legacy (a previous bug would have moved them into
            # vault/vault/).
            self.assertEqual(find_legacy_workspaces(root / "vault"), [])
            self.assertEqual(find_legacy_workspaces(root), [])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(migrate(root / "vault", apply=True), 0)
            self.assertTrue((canonical / "01-client-brief.md").exists())

    def test_single_workspace_platform_dir_requires_manual_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".growth"
            legacy = root / "xiaohongshu"
            (legacy / "lessons").mkdir(parents=True)
            (legacy / "01-client-brief.md").write_text("brief")

            # The platform dir itself is one workspace: no profile name can be
            # inferred and its content subdirs must not be scattered as
            # pseudo-profiles.
            self.assertEqual(find_legacy_workspaces(root), [(legacy, None)])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(migrate(root, apply=True), 1)
            self.assertTrue((legacy / "01-client-brief.md").exists())
            self.assertTrue((legacy / "lessons").is_dir())

    def test_migrate_moves_profile_under_root_and_vault_platform_first_layouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".growth"
            pre_vault_profile = root / "moon-studio" / "xiaohongshu"
            vault_platform_first = root / "vault" / "xiaohongshu" / "astrozi"
            pre_vault_profile.mkdir(parents=True)
            vault_platform_first.mkdir(parents=True)
            (pre_vault_profile / "01-client-brief.md").write_text("a")
            (vault_platform_first / "01-client-brief.md").write_text("b")

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(migrate(root, apply=True), 0)
            self.assertEqual(
                discover_workspace_dirs(root),
                [
                    root / "vault" / "astrozi" / "xiaohongshu",
                    root / "vault" / "moon-studio" / "xiaohongshu",
                ],
            )

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
