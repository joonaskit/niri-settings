"""Phase 8: the first-run flow and the packaging files."""
import configparser
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from unittest import mock

from PySide6.QtCore import QCoreApplication

import niri_settings
from niri_settings import config as config_mod
from niri_settings.config import IN_PLACE, MANAGED, Config
from niri_settings.viewmodel import Backend

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT = os.path.join(HERE, "corpus", "default", "config.kdl")
HAVE_NIRI = shutil.which("niri") is not None


class Base(unittest.TestCase):
    def setUp(self):
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        saved = {k: os.environ.get(k) for k in ("XDG_STATE_HOME", "XDG_CONFIG_HOME")}
        os.environ["XDG_STATE_HOME"] = os.path.join(self.tmp, "state")
        os.environ["XDG_CONFIG_HOME"] = os.path.join(self.tmp, "xdg")

        def restore():
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(restore)
        self.folder = os.path.join(self.tmp, "niri")
        os.makedirs(self.folder)
        self.main = os.path.join(self.folder, "config.kdl")

    def read(self, name="config.kdl"):
        with open(os.path.join(self.folder, name), encoding="utf-8") as fh:
            return fh.read()


class FirstRun(Base):
    def test_a_new_config_needs_setup_once(self):
        shutil.copy(DEFAULT, self.main)
        backend = Backend(self.main, live=False)
        self.addCleanup(backend.shutdown)
        self.assertTrue(backend.setupNeeded)
        backend.skipSetup()
        self.assertFalse(backend.setupNeeded)
        again = Backend(self.main, live=False)
        self.addCleanup(again.shutdown)
        self.assertFalse(again.setupNeeded)
        forced = Backend(self.main, live=False, setup=True)
        self.addCleanup(forced.shutdown)
        self.assertTrue(forced.setupNeeded)

    def test_a_write_mode_on_record_counts_as_set_up(self):
        shutil.copy(DEFAULT, self.main)
        config_mod._save_settings({"write_mode": {self.main: IN_PLACE}})
        self.assertTrue(Config(self.main).setup_done)

    def test_in_place_without_preview_leaves_the_files_alone(self):
        shutil.copy(DEFAULT, self.main)
        before = self.read()
        cfg = Config(self.main)
        self.assertEqual(cfg.first_run(IN_PLACE, False), (True, ""))
        self.assertEqual(self.read(), before)
        self.assertTrue(Config(self.main).setup_done)

    @unittest.skipUnless(HAVE_NIRI, "needs niri")
    def test_managed_with_preview_adds_both_includes_in_order(self):
        shutil.copy(DEFAULT, self.main)
        cfg = Config(self.main)
        ok, message = cfg.first_run(MANAGED, True)
        self.assertTrue(ok, message)
        text = self.read()
        managed = text.index('include optional=true "niri-gui.kdl"')
        preview = text.index('include optional=true "niri-gui-preview.kdl"')
        self.assertLess(managed, preview, "the preview include must stay last")
        again = Config(self.main)
        self.assertEqual(again.write_mode, MANAGED)
        self.assertTrue(again.setup_done)
        self.assertTrue(again.preview_enabled)
        self.assertEqual(len(again.snapshots()), 2, "each include line is its own snapshotted write")

    @unittest.skipUnless(HAVE_NIRI, "needs niri")
    def test_a_missing_config_starts_from_niris_default(self):
        with mock.patch.object(config_mod, "DEFAULT_CONFIGS", (DEFAULT,)):
            cfg = Config(self.main)
            self.assertEqual(cfg.default_source(), DEFAULT)
            ok, message = cfg.first_run(IN_PLACE, True)
        self.assertTrue(ok, message)
        with open(DEFAULT, encoding="utf-8") as fh:
            self.assertTrue(self.read().startswith(fh.read()))
        self.assertTrue(Config(self.main).validate()[0])

    @unittest.skipUnless(HAVE_NIRI, "needs niri")
    def test_a_missing_config_without_a_default_still_validates(self):
        with mock.patch.object(config_mod, "DEFAULT_CONFIGS", ()):
            cfg = Config(self.main)
            ok, message = cfg.first_run(MANAGED, False)
        self.assertTrue(ok, message)
        self.assertIn('include optional=true "niri-gui.kdl"', self.read())

    def test_skip_still_creates_a_missing_config(self):
        with mock.patch.object(config_mod, "DEFAULT_CONFIGS", (DEFAULT,)):
            backend = Backend(self.main, live=False)
            self.addCleanup(backend.shutdown)
            self.assertFalse(backend.setupInfo["exists"])
            self.assertEqual(backend.skipSetup(), "")
        self.assertFalse(backend.setupNeeded)
        self.assertTrue(os.path.exists(self.main))
        self.assertNotIn("include optional", self.read())
        self.assertEqual(backend.writeMode, IN_PLACE)

    def test_an_unwritable_folder_is_reported_not_raised(self):
        os.chmod(self.folder, 0o500)
        self.addCleanup(os.chmod, self.folder, 0o700)
        if os.access(self.folder, os.W_OK):
            self.skipTest("running as root")
        ok, message = Config(self.main).first_run(IN_PLACE, False)
        self.assertFalse(ok)
        self.assertIn("Could not create", message)
        self.assertFalse(Config(self.main).setup_done)


class SuggestedMode(Base):
    def test_a_plain_file_suggests_in_place(self):
        shutil.copy(DEFAULT, self.main)
        self.assertEqual(Config(self.main).suggested_mode()[0], IN_PLACE)

    def test_a_symlink_suggests_managed(self):
        real = os.path.join(self.tmp, "dotfiles-config.kdl")
        shutil.copy(DEFAULT, real)
        os.symlink(real, self.main)
        mode, reason = Config(self.main).suggested_mode()
        self.assertEqual(mode, MANAGED)
        self.assertIn("symlink", reason)

    def test_a_git_work_tree_suggests_managed(self):
        shutil.copy(DEFAULT, self.main)
        os.makedirs(os.path.join(self.tmp, ".git"))
        mode, reason = Config(self.main).suggested_mode()
        self.assertEqual(mode, MANAGED)
        self.assertIn("git", reason)


class Packaging(unittest.TestCase):
    def test_versions_agree(self):
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
            project = tomllib.load(fh)["project"]
        self.assertEqual(project["version"], niri_settings.__version__)
        with open(os.path.join(ROOT, "packaging", "niri-settings.spec"), encoding="utf-8") as fh:
            spec = fh.read()
        self.assertEqual(re.search(r"^Version:\s*(\S+)", spec, re.M).group(1), niri_settings.__version__)
        with open(os.path.join(ROOT, "data", "io.github.joonaskit.NiriSettings.metainfo.xml"), encoding="utf-8") as fh:
            self.assertIn(f'version="{niri_settings.__version__}"', fh.read())

    def test_desktop_file_launches_the_installed_command(self):
        path = os.path.join(ROOT, "data", "io.github.joonaskit.NiriSettings.desktop")
        entry = configparser.ConfigParser(interpolation=None)
        entry.optionxform = str
        entry.read(path, encoding="utf-8")
        d = entry["Desktop Entry"]
        self.assertEqual(d["Exec"], "niri-settings")
        self.assertEqual(d["Icon"], "io.github.joonaskit.NiriSettings")
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
            scripts = tomllib.load(fh)["project"]["gui-scripts"]
        self.assertIn("niri-settings", scripts)
        if shutil.which("desktop-file-validate"):
            run = subprocess.run(["desktop-file-validate", path], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_every_icon_is_installed(self):
        with open(os.path.join(ROOT, "packaging", "niri-settings.spec"), encoding="utf-8") as fh:
            spec = fh.read()
        for name in os.listdir(os.path.join(ROOT, "icons")):
            self.assertIn(f"icons/{name}", spec, f"{name} is not installed by the spec")

    def test_metainfo_validates(self):
        if not shutil.which("appstreamcli"):
            self.skipTest("needs appstreamcli")
        path = os.path.join(ROOT, "data", "io.github.joonaskit.NiriSettings.metainfo.xml")
        run = subprocess.run(["appstreamcli", "validate", "--no-net", "--pedantic", path],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_the_package_ships_its_qml_and_fonts(self):
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
            data = tomllib.load(fh)["tool"]["setuptools"]["package-data"]["niri_settings"]
        pkg = os.path.join(ROOT, "niri_settings")
        for sub in ("qml", "fonts"):
            for name in os.listdir(os.path.join(pkg, sub)):
                rel = f"{sub}/{name}"
                self.assertTrue(any(re.fullmatch(p.replace(".", r"\.").replace("*", "[^/]*"), rel)
                                    for p in data), f"{rel} is not packaged")


if __name__ == "__main__":
    unittest.main()
