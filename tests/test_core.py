"""Round-trip and edit tests for niri_core and Config. Run: python3 -m unittest -v"""
import glob
import os
import shutil
import subprocess
import tempfile
import unittest

from app import niri_core
from app.config import Config

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = sorted(glob.glob(os.path.join(HERE, "corpus", "*", "config.kdl")))
HAVE_NIRI = shutil.which("niri") is not None


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def changed_lines(a, b):
    a, b = a.splitlines(), b.splitlines()
    return [(x, y) for x, y in zip(a, b) if x != y]


class RoundTrip(unittest.TestCase):
    def test_untouched_files_are_byte_identical(self):
        self.assertTrue(CORPUS)
        for main in CORPUS:
            tree = niri_core.load_tree(main)
            for f in tree.files():
                if tree.exists(f):
                    self.assertEqual(tree.render(f), read(f), f)
            self.assertEqual(tree.dirty_files(), [])

    def test_set_and_set_back_is_byte_identical(self):
        for main in CORPUS:
            tree = niri_core.load_tree(main)
            src = tree.source_of("layout/gaps")
            old = tree.get("layout/gaps")
            tree.set("layout/gaps", 31, src["file"])
            self.assertEqual(tree.get("layout/gaps"), 31)
            tree.set("layout/gaps", old, src["file"])
            self.assertEqual(tree.dirty_files(), [])


class Includes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copytree(os.path.join(HERE, "corpus", "includes"), self.tmp, dirs_exist_ok=True)
        self.main = os.path.join(self.tmp, "config.kdl")
        self.tree = niri_core.load_tree(self.main)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_later_include_wins_and_sections_merge(self):
        t = self.tree
        self.assertEqual(t.get("layout/gaps"), 20)
        self.assertEqual(t.source_of("layout/gaps")["file"], os.path.join(self.tmp, "colors.kdl"))
        self.assertEqual(t.source_of("layout/gaps")["line"], 2)
        self.assertEqual(t.get("layout/focus-ring/active-color"), "blue")
        self.assertEqual(t.get("layout/focus-ring/width"), 3)  # merged from the main file
        self.assertEqual(t.get("layout/center-focused-column"), "on-overflow")

    def test_non_merging_section_is_replaced(self):
        self.assertEqual(self.tree.get("layout/struts/left"), 64)
        self.assertIsNone(self.tree.get("layout/struts/top"))

    def test_values_and_syntax(self):
        t = self.tree
        self.assertIsNone(t.get("layout/always-center-single-column"))  # slashdashed
        self.assertIs(t.get("prefer-no-csd"), True)
        self.assertIs(t.get("layout/border/off"), True)
        self.assertEqual(t.get("output[DP-1]/scale"), 1.5)
        self.assertEqual(t.get("spawn-at-startup#0"),
                         {"args": ["waybar", "--log-level", "debug"], "props": {}})
        self.assertEqual(t.get("window-rule#1/match")["props"], {"app-id": r"^org\.gnome\."})
        self.assertEqual(t.get("binds/Mod+T/spawn"), "foot")
        self.assertEqual(t.get("binds/Mod+T")["props"], {"hotkey-overlay-title": "Terminal"})
        self.assertEqual(t.source_of("layout/gaps")["overridden_by"], ["output[DP-1]"])
        self.assertIn("window-rule#1", t.list(""))
        self.assertEqual(len(t.files()), 4)  # includes the missing optional file

    def test_edit_touches_only_its_line(self):
        t = self.tree
        before = t.render(self.main)
        t.set("layout/center-focused-column", "always", self.main)
        diff = changed_lines(before, t.render(self.main))
        self.assertEqual(diff, [('    center-focused-column "on-overflow"',
                                 '    center-focused-column "always"')])
        self.assertEqual(t.dirty_files(), [self.main])

    def test_trailing_comment_survives(self):
        self.tree.set("layout/gaps", 7, self.main)
        self.assertIn("    gaps 7 // trailing comment\n", self.tree.render(self.main))

    def test_insert_and_remove(self):
        t = self.tree
        t.set("layout/struts/left", 10, self.main)        # one-line block
        self.assertIn("struts { top 8; bottom 8; left 10; }", t.render(self.main))
        t.set("layout/focus-ring/inactive-color", "#505050", self.main)  # multi-line block
        self.assertIn('        active-color "#7fc8ff"\n        inactive-color "#505050"\n    }',
                      t.render(self.main))
        t.remove("layout/border/off", self.main)
        self.assertIn("border { width 2; }", t.render(self.main))
        t.remove("prefer-no-csd", self.main)
        self.assertNotIn("prefer-no-csd", t.render(self.main))
        t.set("overview/zoom", 0.4, self.main)
        self.assertTrue(t.render(self.main).endswith("overview {\n    zoom 0.4\n}\n"))
        self.assertEqual(t.get("overview/zoom"), 0.4)

    def test_parse_error_has_file_and_line(self):
        with open(self.main, "a") as fh:
            fh.write("layout {\n")
        with self.assertRaises(niri_core.KdlError) as cm:
            niri_core.load_tree(self.main)
        self.assertEqual(cm.exception.file, self.main)


@unittest.skipUnless(HAVE_NIRI, "niri is not installed")
class ConfigSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = tempfile.mkdtemp()
        os.environ["XDG_STATE_HOME"] = self.state
        shutil.copytree(os.path.join(HERE, "corpus", "includes"), self.tmp, dirs_exist_ok=True)
        self.main = os.path.join(self.tmp, "config.kdl")
        self.cfg = Config(self.main)

    def tearDown(self):
        shutil.rmtree(self.tmp)
        shutil.rmtree(self.state)

    def test_corpus_edits_validate(self):
        for main in CORPUS:
            tmp = tempfile.mkdtemp()
            shutil.copytree(os.path.dirname(main), tmp, dirs_exist_ok=True)
            cfg = Config(os.path.join(tmp, "config.kdl"))
            cfg.set("layout/gaps", 24)
            cfg.set("layout/center-focused-column", "always")
            cfg.set("layout/struts/left", 32)
            cfg.set("layout/default-column-width/proportion", 0.33333)
            cfg.set("layout/always-center-single-column", True)
            cfg.remove("layout/border/off")
            self.assertEqual(cfg.validate(), (True, ""), main)
            ok, _ = cfg.save()
            self.assertTrue(ok)
            run = subprocess.run(["niri", "validate", "-c", cfg.main], capture_output=True)
            self.assertEqual(run.returncode, 0)
            shutil.rmtree(tmp)

    def test_edit_goes_to_owning_file_and_revert_is_exact(self):
        colors = os.path.join(self.tmp, "colors.kdl")
        before = read(colors)
        self.cfg.set("layout/gaps", 2)
        self.assertEqual(self.cfg.tree.dirty_files(), [colors])
        self.assertEqual(self.cfg.pending, {"layout/gaps": 2})
        self.cfg.set("layout/gaps", 20)  # back to the saved value
        self.assertEqual(self.cfg.pending, {})
        self.cfg.set("layout/gaps", 2)
        self.cfg.revert()
        self.assertEqual(self.cfg.tree.render(colors), before)
        self.assertEqual(read(colors), before)

    def test_bad_edit_never_reaches_disk(self):
        before = read(self.main)
        self.cfg.set("layout/center-focused-column", "sideways")
        ok, message = self.cfg.save()
        self.assertFalse(ok)
        self.assertIn("config.kdl", message)
        self.assertEqual(read(self.main), before)

    def test_save_writes_only_changed_lines_and_snapshots(self):
        before = read(self.main)
        self.cfg.set("layout/center-focused-column", "never")
        ok, _ = self.cfg.save()
        self.assertTrue(ok)
        self.assertEqual(len(changed_lines(before, read(self.main))), 1)
        snaps = os.listdir(os.path.join(self.state, "niri-settings", "snapshots"))
        self.assertEqual(len(snaps), 1)
        snap = os.path.join(self.state, "niri-settings", "snapshots", snaps[0], "config.kdl")
        self.assertEqual(read(snap), before)
        self.assertEqual(self.cfg.pending, {})

    def test_preview_overlay(self):
        self.assertFalse(self.cfg.preview_enabled)
        self.assertEqual(self.cfg.write_preview(), (True, ""))
        self.assertFalse(os.path.exists(self.cfg.preview_file))  # off until enabled
        ok, _ = self.cfg.enable_preview()
        self.assertTrue(ok)
        self.assertTrue(read(self.main).endswith('include optional=true "niri-gui-preview.kdl"\n'))
        saved = {f: read(f) for f in (self.main, os.path.join(self.tmp, "colors.kdl"))}
        self.cfg.set("layout/gaps", 40)
        self.cfg.set("layout/struts/right", 5)
        self.cfg.remove("layout/border/off")
        self.assertEqual(self.cfg.write_preview(), (True, ""))
        overlay = niri_core.load_string(read(self.cfg.preview_file))
        self.assertEqual(overlay.get("layout/gaps"), 40)
        self.assertEqual(overlay.get("layout/struts/left"), 64)   # whole section copied
        self.assertEqual(overlay.get("layout/struts/right"), 5)
        self.assertIs(overlay.get("layout/border/on"), True)
        for f, text in saved.items():
            self.assertEqual(read(f), text)  # real files untouched by preview
        run = subprocess.run(["niri", "validate", "-c", self.main], capture_output=True)
        self.assertEqual(run.returncode, 0)
        self.cfg.revert()
        self.cfg.write_preview()
        self.assertEqual(read(self.cfg.preview_file), "")


if __name__ == "__main__":
    unittest.main()
