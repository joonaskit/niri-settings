"""Phase 4: display drafts, the timed trial and its guard, profiles."""
import copy
import os
import shutil
import sys
import tempfile
import time
import unittest

from niri_settings.config import MANAGED, Config, ReadOnlyError
from niri_settings.displays import DisplayModel, snap_position

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HAVE_NIRI = shutil.which("niri") is not None

LIVE = {
    "DP-1": {"name": "DP-1", "make": "Dell", "model": "U2723QE", "serial": "ABC", "vrr_supported": True,
             "vrr_enabled": False, "current_mode": 0,
             "modes": [{"width": 3840, "height": 2160, "refresh_rate": 60000, "is_preferred": True},
                       {"width": 2560, "height": 1440, "refresh_rate": 59951, "is_preferred": False}],
             "logical": {"x": 0, "y": 0, "width": 2560, "height": 1440, "scale": 1.5, "transform": "Normal"}},
    "eDP-1": {"name": "eDP-1", "make": "BOE", "model": "0x0A", "serial": None, "vrr_supported": False,
              "vrr_enabled": False, "current_mode": 0,
              "modes": [{"width": 2880, "height": 1800, "refresh_rate": 60001, "is_preferred": True}],
              "logical": {"x": 2560, "y": 0, "width": 1440, "height": 900, "scale": 2.0, "transform": "Normal"}},
}


class FakeNiri:
    """Stands in for `niri msg output`: records commands and updates the live state."""

    def __init__(self, live):
        self.live = copy.deepcopy(live)
        self.log = []
        self.fail_on = None

    def outputs(self):
        return copy.deepcopy(self.live)

    def run(self, argv):
        self.log.append(argv[3:])
        name, action, args = argv[3], argv[4], argv[5:]

        class Result:
            returncode, stderr = 0, ""
        if self.fail_on == action:
            Result.returncode, Result.stderr = 1, "Error: mode not supported"
            return Result
        out = self.live[name]
        if action == "scale":
            out["logical"]["scale"] = float(args[0])
        elif action == "mode":
            w, rest = args[0].split("x")
            h, rate = rest.split("@")
            out["current_mode"] = next(i for i, m in enumerate(out["modes"])
                                       if (m["width"], m["height"]) == (int(w), int(h)))
        elif action == "position":
            out["logical"]["x"], out["logical"]["y"] = int(args[1]), int(args[2])
        elif action == "off":
            out["logical"] = None
        return Result


@unittest.skipUnless(HAVE_NIRI, "niri is not installed")
class Displays(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = tempfile.mkdtemp()
        self.env = {k: os.environ.get(k) for k in ("XDG_STATE_HOME", "XDG_CONFIG_HOME")}
        os.environ["XDG_STATE_HOME"] = os.path.join(self.home, "state")
        os.environ["XDG_CONFIG_HOME"] = os.path.join(self.home, "config")
        shutil.copytree(os.path.join(HERE, "corpus", "includes"), self.tmp, dirs_exist_ok=True)
        self.main = os.path.join(self.tmp, "config.kdl")
        self.cfg = Config(self.main)
        self.niri = FakeNiri(LIVE)
        self.model = DisplayModel(lambda: self.cfg, self.niri.outputs, self.niri.run)
        self.model.refresh()

    def tearDown(self):
        self.model.end_trial(keep=False)
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp)
        shutil.rmtree(self.home)

    def read(self):
        with open(self.main, encoding="utf-8") as fh:
            return fh.read()

    def test_draft_is_config_then_live(self):
        d = self.model.draft("DP-1")            # corpus sets only `scale 1.5` for DP-1
        self.assertEqual((d["mode"], d["scale"], d["x"], d["y"], d["transform"], d["vrr"]),
                         ("3840x2160@60.000", 1.5, 0, 0, "normal", "off"))
        self.assertEqual(self.model.logical_size("DP-1", d), (2560, 1440))
        self.assertEqual(self.model.draft("eDP-1")["scale"], 2.0)   # nothing in config: live
        info = self.model.describe("DP-1")
        self.assertEqual(info["overrides"], ["gaps"])
        self.assertIn('output "DP-1" {', info["kdl"])
        self.assertEqual(len(info["modes"]), 2)

    def test_edits_go_to_the_config_only(self):
        self.model.set_scale("DP-1", 2)
        self.model.set_mode("eDP-1", "2880x1800@60.001")
        self.model.set_position("eDP-1", 1920, 0)
        self.model.set_vrr("DP-1", "on-demand")
        self.assertEqual(self.niri.log, [])                     # nothing sent to niri
        self.assertEqual(self.cfg.get("output[DP-1]/scale"), 2)
        self.assertEqual(self.cfg.get("output[eDP-1]/position")["props"], {"x": 1920, "y": 0})
        self.assertEqual(self.cfg.validate(), (True, ""))
        self.assertEqual(self.model.logical_size("DP-1", self.model.draft("DP-1")), (1920, 1080))
        self.assertEqual(sorted(self.model.untried()), ["DP-1", "eDP-1"])

    def test_output_matched_by_make_model_serial(self):
        self.cfg.set("output[Dell U2723QE ABC]/scale", 1.25)
        self.assertEqual(self.model.key_for("DP-1"), "DP-1")     # connector section comes first
        self.cfg.revert()
        self.cfg.remove("output[DP-1]")
        self.cfg.set("output[Dell U2723QE ABC]/scale", 1.25)
        self.assertEqual(self.model.key_for("DP-1"), "Dell U2723QE ABC")
        self.assertEqual(self.model.draft("DP-1")["scale"], 1.25)

    def test_trial_reverts_without_touching_the_config(self):
        before = self.read()
        self.model.set_scale("DP-1", 3)
        self.model.set_position("eDP-1", 1280, 0)
        apply, undo = self.model.trial_plan()
        self.assertEqual([c[3:] for c in apply],
                         [["DP-1", "scale", "3"], ["eDP-1", "position", "set", "1280", "0"]])
        self.assertEqual([c[3:] for c in undo],
                         [["eDP-1", "position", "set", "2560", "0"], ["DP-1", "scale", "1.5"]])
        self.assertTrue(self.model.start_trial(seconds=30))
        self.assertTrue(self.model.trial_running)
        self.model.refresh()
        self.assertEqual(self.model.untried(), [])              # niri now shows the draft
        self.assertEqual(self.read(), before)                   # config untouched
        self.model.end_trial(keep=False)
        self.assertFalse(self.model.trial_running)
        self.assertEqual(self.read(), before)

    def test_keep_leaves_drafts_for_save(self):
        self.model.set_scale("DP-1", 2)
        self.assertTrue(self.model.start_trial(seconds=30))
        self.model.end_trial(keep=True)
        self.model.refresh()
        self.assertEqual(self.model.untried(), [])
        self.assertEqual(self.cfg.pending, {"output[DP-1]/scale": 2})
        self.assertTrue(self.cfg.save()[0])
        self.assertIn("scale 2", self.read())

    def test_refused_change_ends_the_trial(self):
        self.niri.fail_on = "mode"
        self.model.set_mode("DP-1", "2560x1440@59.951")
        self.assertFalse(self.model.start_trial(seconds=30))
        self.assertIn("not supported", self.model.trial_error)
        self.assertFalse(self.model.trial_running)

    def test_turning_an_output_off_is_one_command(self):
        self.model.set_enabled("eDP-1", False)
        self.model.set_scale("eDP-1", 1)
        apply, undo = self.model.trial_plan()
        self.assertEqual([c[3:] for c in apply], [["eDP-1", "off"]])
        self.assertEqual([c[3:] for c in undo], [["eDP-1", "on"]])

    def test_safe_keys_need_no_trial(self):
        self.model.set_backdrop("DP-1", "#101010")
        self.assertEqual(self.model.untried(), [])
        self.assertEqual(self.cfg.get("output[DP-1]/backdrop-color"), "#101010")

    def test_display_changes_stay_out_of_the_preview_overlay(self):
        self.assertTrue(self.cfg.enable_preview()[0])
        self.model.set_scale("DP-1", 3)
        self.cfg.set("layout/gaps", 30)
        self.cfg.write_preview()
        with open(self.cfg.preview_file) as fh:
            overlay = fh.read()
        self.assertIn("gaps 30", overlay)
        self.assertNotIn("output", overlay)

    def test_new_output_section_goes_above_trailing_includes(self):
        self.assertTrue(self.cfg.enable_preview()[0])
        self.model.set_scale("eDP-1", 1.75)
        text = self.cfg.tree.render(self.main)
        self.assertLess(text.index('output "eDP-1"'), text.index("niri-gui-preview.kdl"))
        self.assertEqual(self.cfg.validate(), (True, ""))

    def test_managed_mode_refuses_a_display_set_in_the_users_file(self):
        self.assertTrue(self.cfg.set_write_mode(MANAGED)[0])
        with self.assertRaises(ReadOnlyError):
            self.model.set_scale("DP-1", 2)                      # DP-1 is in config.kdl
        self.model.set_scale("eDP-1", 1.75)                      # eDP-1 is nowhere yet: fine
        self.assertEqual(self.cfg.tree.dirty_files(), [self.cfg.managed_file])

    def test_profiles(self):
        docked = self.model.snapshot_profile()
        self.model.set_enabled("eDP-1", False)
        self.model.set_scale("DP-1", 2)
        self.assertFalse(self.model.matches_profile(docked))
        laptop_closed = self.model.snapshot_profile()
        self.model.apply_profile(docked)
        self.assertTrue(self.model.matches_profile(docked))
        self.assertEqual(self.cfg.pending, {})                   # back to the saved state
        self.model.apply_profile(laptop_closed)
        self.assertTrue(self.model.matches_profile(laptop_closed))

    def test_snapping(self):
        dp = {"x": 0, "y": 0, "w": 2560, "h": 1440}
        edp = {"w": 1440, "h": 900}
        self.assertEqual(snap_position(edp, 2550, 10, [dp]), (2560, 0, "left"))
        self.assertEqual(snap_position(edp, -1450, 530, [dp]), (-1440, 540, "right"))
        self.assertEqual(snap_position(edp, 3000, 2000, [dp]), (3000, 2000, ""))


class Guard(unittest.TestCase):
    """The guard process, driven with harmless commands instead of niri."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.flag = os.path.join(self.tmp, "reverted")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def spawn(self, seconds):
        import json
        import subprocess
        return subprocess.Popen([sys.executable, "-m", "niri_settings.output_guard", str(seconds),
                                 json.dumps([["touch", self.flag]])],
                                stdin=subprocess.PIPE, text=True, cwd=ROOT)

    def test_timeout_reverts(self):
        guard = self.spawn(0.5)
        guard.wait(timeout=10)
        guard.stdin.close()
        self.assertTrue(os.path.exists(self.flag))

    def test_keep_does_not_revert(self):
        guard = self.spawn(5)
        guard.stdin.write("keep\n")
        guard.stdin.close()
        guard.wait(timeout=10)
        self.assertFalse(os.path.exists(self.flag))

    def test_app_dying_reverts_at_once(self):
        guard = self.spawn(60)
        start = time.time()
        guard.stdin.close()            # what a crash of the settings app looks like
        guard.wait(timeout=10)
        self.assertTrue(os.path.exists(self.flag))
        self.assertLess(time.time() - start, 5)


if __name__ == "__main__":
    unittest.main()
