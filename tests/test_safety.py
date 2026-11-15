"""Phase 3: snapshots, write modes, outside edits, error mapping."""
import os
import shutil
import subprocess
import tempfile
import time
import unittest

from app import niri_core
from app.config import IN_PLACE, MANAGED, Config, ReadOnlyError, _parse_error

HERE = os.path.dirname(os.path.abspath(__file__))
HAVE_NIRI = shutil.which("niri") is not None


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def niri_accepts(main):
    return subprocess.run(["niri", "validate", "-c", main], capture_output=True).returncode == 0


@unittest.skipUnless(HAVE_NIRI, "niri is not installed")
class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = tempfile.mkdtemp()
        self.env = {k: os.environ.get(k) for k in ("XDG_STATE_HOME", "XDG_CONFIG_HOME")}
        os.environ["XDG_STATE_HOME"] = os.path.join(self.home, "state")
        os.environ["XDG_CONFIG_HOME"] = os.path.join(self.home, "config")
        shutil.copytree(os.path.join(HERE, "corpus", "includes"), self.tmp, dirs_exist_ok=True)
        self.main = os.path.join(self.tmp, "config.kdl")
        self.colors = os.path.join(self.tmp, "colors.kdl")
        self.cfg = Config(self.main)

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp)
        shutil.rmtree(self.home)

    def tree_on_disk(self):
        return {f: read(f) for f in (self.main, self.colors)}


class Snapshots(Base):
    def test_any_save_can_be_undone(self):
        states = [self.tree_on_disk()]
        for gaps, mode in ((3, "always"), (9, "never")):
            self.cfg.set("layout/gaps", gaps)                      # lives in colors.kdl
            self.cfg.set("layout/center-focused-column", mode)     # lives in config.kdl
            self.assertTrue(self.cfg.save()[0])
            states.append(self.tree_on_disk())
            time.sleep(1.05)  # snapshot ids have one-second resolution
        snaps = self.cfg.snapshots()
        self.assertEqual(len(snaps), 2)
        self.assertEqual(snaps[0]["reason"], "before save")
        self.assertEqual(sorted(snaps[0]["files"]), ["colors.kdl", "config.kdl"])
        # newest snapshot = state before the second save; oldest = the original
        ok, _ = self.cfg.restore_snapshot(snaps[0]["id"])
        self.assertTrue(ok)
        self.assertEqual(self.tree_on_disk(), states[1])
        self.assertEqual(self.cfg.get("layout/gaps"), 3)
        ok, _ = self.cfg.restore_snapshot(snaps[1]["id"])
        self.assertTrue(ok)
        self.assertEqual(self.tree_on_disk(), states[0])
        # each restore was snapshotted too, so it can itself be undone
        self.assertEqual([s["reason"] for s in self.cfg.snapshots()][:2],
                         ["before restore", "before restore"])

    def test_restore_is_validated_and_needs_a_clean_state(self):
        self.cfg.set("layout/gaps", 3)
        self.assertTrue(self.cfg.save()[0])
        snap = self.cfg.snapshots()[0]["id"]
        folder = os.path.join(os.environ["XDG_STATE_HOME"], "niri-settings", "snapshots", snap)
        write(os.path.join(folder, "colors.kdl"), "layout { gaps \"wide\"; }\n")
        before = self.tree_on_disk()
        ok, message = self.cfg.restore_snapshot(snap)
        self.assertFalse(ok)
        self.assertEqual(self.tree_on_disk(), before)
        self.cfg.set("layout/gaps", 5)
        self.assertEqual(self.cfg.restore_snapshot(snap),
                         (False, "Save or revert your unsaved changes first."))

    def test_named_snapshots_survive_pruning(self):
        import app.config as config
        old_keep, config.SNAPSHOT_KEEP = config.SNAPSHOT_KEEP, 2
        try:
            first = self.cfg._snapshot([self.main], "before save")
            self.cfg.name_snapshot(first, "Before blur experiment")
            for _ in range(4):
                self.cfg._snapshot([self.main], "before save")
            snaps = self.cfg.snapshots()
            self.assertEqual(len(snaps), 3)
            self.assertEqual(snaps[-1]["name"], "Before blur experiment")
        finally:
            config.SNAPSHOT_KEEP = old_keep

    def test_failed_write_rolls_back(self):
        self.cfg.set("layout/gaps", 3)
        self.cfg.set("layout/center-focused-column", "always")
        before = self.tree_on_disk()
        import app.config as config
        real, calls = config._write_atomic, []

        def flaky(path, text):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("disk full")
            real(path, text)
        config._write_atomic = flaky
        try:
            ok, message = self.cfg.save()
        finally:
            config._write_atomic = real
        self.assertFalse(ok)
        self.assertIn("disk full", message)
        self.assertEqual(self.tree_on_disk(), before)


class ManagedMode(Base):
    def test_user_files_stay_untouched(self):
        ok, _ = self.cfg.set_write_mode(MANAGED)
        self.assertTrue(ok)
        self.assertIn('include optional=true "niri-gui.kdl"\n', read(self.main))
        frozen = self.tree_on_disk()
        self.cfg.set("layout/gaps", 2)
        self.cfg.set("layout/struts/top", 12)               # non-merging: whole section copied
        self.cfg.remove("layout/border/off")                # becomes `on` in the overlay
        self.assertEqual(self.cfg.tree.dirty_files(), [self.cfg.managed_file])
        self.assertTrue(self.cfg.save()[0])
        self.assertEqual(self.tree_on_disk(), frozen)
        overlay = niri_core.load_string(read(self.cfg.managed_file))
        self.assertEqual(overlay.get("layout/gaps"), 2)
        self.assertEqual(overlay.get("layout/struts/left"), 64)
        self.assertEqual(overlay.get("layout/struts/top"), 12)
        self.assertIs(overlay.get("layout/border/on"), True)
        self.assertTrue(niri_accepts(self.main))
        fresh = Config(self.main)
        self.assertEqual(fresh.write_mode, MANAGED)          # remembered per config
        self.assertEqual(fresh.get("layout/gaps"), 2)
        # undo: the snapshot knows the managed file did not exist before
        ok, _ = fresh.restore_snapshot(fresh.snapshots()[0]["id"])
        self.assertTrue(ok)
        self.assertEqual(read(self.cfg.managed_file), "")
        self.assertEqual(Config(self.main).get("layout/gaps"), 20)

    def test_removal_that_needs_the_users_file_is_refused(self):
        self.cfg.set_write_mode(MANAGED)
        with self.assertRaises(ReadOnlyError):
            self.cfg.remove("layout/center-focused-column")
        self.assertEqual(self.cfg.pending, {})

    def test_preview_include_stays_last(self):
        self.assertTrue(self.cfg.enable_preview()[0])
        self.assertTrue(self.cfg.set_write_mode(MANAGED)[0])
        text = read(self.main)
        self.assertLess(text.index("niri-gui.kdl"), text.index("niri-gui-preview.kdl"))
        self.assertTrue(text.endswith('include optional=true "niri-gui-preview.kdl"\n'))

    def test_switching_mode_keeps_unsaved_changes(self):
        self.cfg.set("layout/gaps", 2)
        self.assertEqual(self.cfg.tree.dirty_files(), [self.colors])
        self.cfg.set_write_mode(MANAGED)
        self.assertEqual(self.cfg.pending, {"layout/gaps": 2})
        self.assertEqual(self.cfg.tree.dirty_files(), [self.cfg.managed_file])
        self.cfg.set_write_mode(IN_PLACE)
        self.assertEqual(self.cfg.pending, {"layout/gaps": 2})
        self.assertEqual(self.cfg.tree.dirty_files(), [self.colors])


class OutsideEdits(Base):
    def test_rebase_keeps_both_sides(self):
        self.cfg.set("layout/center-focused-column", "always")
        write(self.colors, read(self.colors).replace("gaps 20", "gaps 44  // edited in vim"))
        self.assertTrue(self.cfg.changed_on_disk())
        self.assertEqual(self.cfg.rebase(), [])
        self.assertEqual(self.cfg.get("layout/gaps"), 44)
        self.assertEqual(self.cfg.pending, {"layout/center-focused-column": "always"})
        self.assertTrue(self.cfg.save()[0])
        self.assertIn("gaps 44  // edited in vim", read(self.colors))
        self.assertIn('center-focused-column "always"', read(self.main))

    def test_same_setting_on_both_sides_is_a_conflict(self):
        self.cfg.set("layout/gaps", 5)
        self.cfg.set("layout/focus-ring/width", 6)
        write(self.colors, read(self.colors).replace("gaps 20", "gaps 44"))
        self.assertEqual(self.cfg.rebase(), ["layout/gaps"])
        self.assertEqual(self.cfg.conflicts["layout/gaps"], {"mine": 5, "disk": 44})
        self.assertEqual(self.cfg.get("layout/gaps"), 44)
        self.assertEqual(self.cfg.pending, {"layout/focus-ring/width": 6})
        self.assertFalse(self.cfg.save()[0])                 # blocked until resolved
        self.cfg.resolve_conflicts(keep_mine=True)
        self.assertEqual(self.cfg.pending, {"layout/gaps": 5, "layout/focus-ring/width": 6})
        self.assertTrue(self.cfg.save()[0])
        self.assertIn("gaps 5", read(self.colors))

    def test_preview_file_is_not_read_back_as_config(self):
        self.assertTrue(self.cfg.enable_preview()[0])
        self.cfg.set("layout/gaps", 5)
        self.cfg.write_preview()
        self.assertIn("gaps 5", read(self.cfg.preview_file))
        write(self.colors, read(self.colors).replace("gaps 20", "gaps 44"))
        self.assertEqual(self.cfg.rebase(), ["layout/gaps"])     # not hidden by the overlay
        self.assertEqual(self.cfg.get("layout/gaps"), 44)
        # a leftover overlay from a killed app is emptied on start
        self.assertEqual(Config(self.main).get("layout/gaps"), 44)
        self.assertEqual(read(self.cfg.preview_file), "")

    def test_taking_the_files_side(self):
        self.cfg.set("layout/gaps", 5)
        write(self.colors, read(self.colors).replace("gaps 20", "gaps 44"))
        self.cfg.rebase()
        self.cfg.resolve_conflicts(keep_mine=False)
        self.assertEqual(self.cfg.pending, {})
        self.assertEqual(self.cfg.get("layout/gaps"), 44)

    def test_same_value_on_both_sides_is_not_a_conflict(self):
        self.cfg.set("layout/gaps", 44)
        write(self.colors, read(self.colors).replace("gaps 20", "gaps 44"))
        self.assertEqual(self.cfg.rebase(), [])
        self.assertEqual(self.cfg.pending, {})

    def test_broken_file_on_disk_changes_nothing(self):
        self.cfg.set("layout/gaps", 5)
        write(self.colors, "layout {\n")
        with self.assertRaises(niri_core.KdlError):
            self.cfg.rebase()
        self.assertEqual(self.cfg.pending, {"layout/gaps": 5})

    def test_save_refuses_when_disk_changed(self):
        self.cfg.set("layout/gaps", 5)
        write(self.colors, read(self.colors).replace("gaps 20", "gaps 44"))
        ok, _ = self.cfg.save()
        self.assertFalse(ok)
        self.assertIn("gaps 44", read(self.colors))


class ErrorMapping(Base):
    def test_error_points_at_the_setting(self):
        self.cfg.set("layout/center-focused-column", "sideways")
        ok, _ = self.cfg.validate()
        self.assertFalse(ok)
        err = self.cfg.last_error
        self.assertEqual(err["file"], self.main)
        self.assertEqual(err["path"], "layout/center-focused-column")
        self.assertEqual(err["line"], 9)
        self.assertIn("expected one of", err["summary"])
        self.cfg.set("layout/center-focused-column", "always")
        self.assertTrue(self.cfg.validate()[0])
        self.assertIsNone(self.cfg.last_error)

    def test_error_in_an_included_file(self):
        self.cfg.set("layout/gaps", "wide")
        self.assertFalse(self.cfg.validate()[0])
        self.assertEqual(self.cfg.last_error["file"], self.colors)
        self.assertEqual(self.cfg.last_error["path"], "layout/gaps")

    def test_report_without_a_location(self):
        err = _parse_error("Error:   × something odd")
        self.assertEqual((err["file"], err["line"], err["summary"]), (None, None, "something odd"))

    def test_path_at(self):
        tree = self.cfg.tree
        self.assertEqual(tree.path_at(self.main, 14), "layout/focus-ring/width")
        self.assertEqual(tree.path_at(self.main, 22), "output[DP-1]/scale")
        self.assertEqual(tree.path_at(self.main, 27), "window-rule#1/match#0")
        self.assertEqual(tree.path_at(self.colors, 6), "window-rule#0")
        self.assertIsNone(tree.path_at(self.main, 6))


if __name__ == "__main__":
    unittest.main()
