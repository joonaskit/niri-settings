"""Phase 7: schema-driven pages, the source editor, and section coverage."""
import os
import re
import shutil
import tempfile
import unittest

from PySide6.QtCore import QCoreApplication

from niri_settings import niri_core
from niri_settings.config import FILE, MANAGED, Config, ReadOnlyError
from niri_settings.schema import pages
from niri_settings.viewmodel import SECTIONS, Backend

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "corpus", "default", "config.kdl")
INCLUDES = os.path.join(HERE, "corpus", "includes")
DOCS = "/usr/share/doc/niri/wiki/Configuration:-Introduction.md"
HAVE_NIRI = shutil.which("niri") is not None


class Base(unittest.TestCase):
    def setUp(self):
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = {k: os.environ.get(k) for k in ("XDG_STATE_HOME", "XDG_CONFIG_HOME")}
        os.environ["XDG_STATE_HOME"] = os.path.join(self.tmp, "state")
        os.environ["XDG_CONFIG_HOME"] = os.path.join(self.tmp, "xdg")
        self.addCleanup(self.restore_env)

    def restore_env(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def load(self, source=DEFAULT):
        folder = os.path.join(self.tmp, "niri")
        if os.path.isdir(source):
            shutil.copytree(source, folder)
        else:
            os.makedirs(folder)
            shutil.copy(source, os.path.join(folder, "config.kdl"))
        self.main = os.path.join(folder, "config.kdl")
        self.backend = Backend(self.main, live=False)
        self.addCleanup(self.backend.shutdown)
        self.cfg = self.backend.config
        return self.backend

    def text(self, path=None):
        return self.cfg.tree.render(path or self.main)

    def assert_valid(self):
        ok, message = self.cfg.validate()
        self.assertTrue(ok, message)


class Schema(unittest.TestCase):
    def test_every_page_in_the_sidebar_is_built(self):
        custom = {"layout", "displays", "binds", "window-rules", "layer-rules", "files"}
        for _, items in SECTIONS:
            for page_id, title in items:
                self.assertTrue(page_id in custom or page_id in pages.PAGES, page_id)

    def test_settings_are_well_formed(self):
        kinds = {"slider", "segmented", "flag", "onoff", "widths", "struts", "number", "decimal", "text",
                 "color", "select", "bool", "offflag", "xy", "animation", "workspaces", "startup", "environment",
                 "colors"}
        seen = set()
        for page_id, page in pages.PAGES.items():
            for group in page["groups"]:
                for s in group["settings"]:
                    self.assertIn(s["kind"], kinds, s)
                    self.assertTrue(s["label"], s)
                    key = (s["path"], s["kind"])
                    if page_id != "layout":
                        self.assertNotIn(key, seen, s["path"])
                    seen.add(key)
                    if s["kind"] in ("segmented", "select"):
                        self.assertTrue(s["options"], s)

    @unittest.skipUnless(os.path.exists(DOCS), "niri docs are not installed")
    def test_every_top_level_section_is_covered(self):
        """The milestone's exit check: each section in the docs has a page or is source only."""
        with open(DOCS, encoding="utf-8") as fh:
            docs = fh.read()
        listed = set(re.findall(r"\* \[`([a-z-]+)", docs))
        self.assertIn("recent-windows", listed)
        covered = {s for s, _, _ in pages.COVERAGE}
        self.assertEqual(listed - covered, set())
        # the top-level options page (Miscellaneous)
        misc = open(DOCS.replace("Introduction", "Miscellaneous"), encoding="utf-8").read()
        for name in re.findall(r"^### `([a-z-]+)`", misc, re.M):
            self.assertIn(name, covered, name)
        ids = {i for _, items in SECTIONS for i, _ in items}
        for section, page_id, note in pages.COVERAGE:
            self.assertTrue(page_id == "source" or page_id in ids, section)
            self.assertTrue(note)

    def test_page_for(self):
        self.assertEqual(pages.page_for("layout/gaps"), "layout")
        self.assertEqual(pages.page_for("layout/shadow/softness"), "appearance")
        self.assertEqual(pages.page_for("input/touchpad/tap"), "pointer")
        self.assertEqual(pages.page_for("input/keyboard/xkb"), "keyboard")
        self.assertEqual(pages.page_for("window-rule#2/match#0"), "window-rules")
        self.assertEqual(pages.page_for("layer-rule#0/opacity"), "layer-rules")
        self.assertEqual(pages.page_for("binds/Mod+T"), "binds")
        self.assertEqual(pages.page_for("output[DP-1]/scale"), "displays")
        self.assertEqual(pages.page_for("animations/window-open/spring"), "animations")
        self.assertIsNone(pages.page_for("debug/disable-cursor-plane"))


@unittest.skipUnless(HAVE_NIRI, "niri is not installed")
class Settings(Base):
    def test_edits_from_every_kind_validate(self):
        b = self.load()
        b.setDecimal("animations/slowdown", 1)
        b.setDecimal("input/touchpad/accel-speed", "-0,5")
        b.setValue("cursor/xcursor-size", 32.0)
        b.setText("cursor/xcursor-theme", "Adwaita")
        b.setText("layout/background-color", "#1e1e2e")
        b.setText("input/touchpad/scroll-method", "edge")
        b.setBool("layout/shadow/draw-behind-window", True, False)
        b.setEnabled("blur", False)
        b.setEnabled("overview/workspace-shadow", False)
        b.setXY("layout/shadow/offset", 2, 8)
        b.setFlag("gestures/hot-corners/top-right", True)
        self.assertEqual(b.setNumbers("input/tablet/calibration-matrix", "1 0 0 0 1 0"), "")
        self.assertIn("numbers", b.setNumbers("input/touch/calibration-matrix", "1 x"))
        text = self.text()
        for line in ("slowdown 1.0", "accel-speed -0.5", "xcursor-size 32", 'xcursor-theme "Adwaita"',
                     'scroll-method "edge"', "draw-behind-window true", "offset x=2 y=8",
                     "calibration-matrix 1.0 0.0 0.0 0.0 1.0 0.0"):
            self.assertIn(line, text)
        self.assertFalse(b.isEnabled("blur", True))
        self.assertEqual(b.xy("layout/shadow/offset"), [2, 8])
        self.assert_valid()
        # defaults remove the setting again
        b.setBool("layout/shadow/draw-behind-window", False, False)
        b.setEnabled("blur", True)
        b.resetValue("cursor/xcursor-size")
        self.assertIsNone(self.cfg.get("layout/shadow/draw-behind-window"))
        self.assertTrue(b.isEnabled("blur", True))
        self.assertIsNone(self.cfg.get("cursor/xcursor-size"))

    def test_animation_modes(self):
        b = self.load()
        path = "animations/window-open"
        self.assertEqual(b.animation(path)["mode"], "default")
        b.setAnimationMode(path, "spring")
        b.setSpring(path, "0.8", 600, "0.001")
        self.assertIn("spring damping-ratio=0.8 stiffness=600 epsilon=0.001", self.text())
        self.assert_valid()
        b.setAnimationMode(path, "easing")
        a = b.animation(path)
        self.assertEqual((a["mode"], a["duration"], a["curve"]), ("easing", 250, "ease-out-cubic"))
        self.assertIsNone(self.cfg.get(path + "/spring"))
        self.assert_valid()
        b.setAnimationMode(path, "off")
        self.assertEqual(b.animation(path)["mode"], "off")
        b.setAnimationMode(path, "default")
        self.assertIsNone(self.cfg.get(path))
        self.assertEqual(self.cfg.pending, {})

    def test_spring_writes_decimals(self):
        b = self.load()
        b.setAnimationMode("animations/window-close", "spring")
        self.assertIn("damping-ratio=1.0 ", self.text())     # niri rejects damping-ratio=1
        self.assert_valid()

    def test_lists(self):
        b = self.load()
        self.assertEqual(b.startupList("spawn-at-startup"), [{"index": 0, "text": "waybar", "disabled": False}])
        self.assertEqual(b.setStartup("spawn-at-startup", -1, "foot --server"), "")
        self.assertEqual(b.setStartup("spawn-sh-at-startup", -1, "swaybg -i ~/bg.png | logger"), "")
        self.assertEqual(b.setStartup("spawn-at-startup", 0, "waybar -c ~/w.json"), "")
        self.assertIn("Check the quotes", b.setStartup("spawn-at-startup", -1, "foo 'bar"))
        text = self.text()
        self.assertIn('spawn-at-startup "waybar" "-c" "~/w.json"\n', text)
        self.assertIn('spawn-at-startup "foot" "--server"\n', text)
        self.assertIn('spawn-sh-at-startup "swaybg -i ~/bg.png | logger"\n', text)
        self.assertEqual(self.cfg.pending_count(), 3)
        self.assert_valid()
        b.removeStartup("spawn-at-startup", 1)
        self.assertNotIn("--server", self.text())
        b.setStartupEnabled("spawn-at-startup", 0, False)
        self.assertIn('\n/-spawn-at-startup "waybar" "-c" "~/w.json"\n', self.text())
        self.assertEqual(b.setStartup("spawn-at-startup", 0, "waybar"), "")   # editing keeps it off
        self.assertTrue(b.startupList("spawn-at-startup")[0]["disabled"])
        self.assert_valid()
        b.setStartupEnabled("spawn-at-startup", 0, True)
        self.assertIn('\nspawn-at-startup "waybar"\n', self.text())

        self.assertEqual(b.addWorkspace("chat"), "")
        self.assertIn("already", b.addWorkspace("chat"))
        b.setWorkspaceOutput("chat", "DP-1")
        self.assertEqual(b.workspaces[0]["output"], "DP-1")
        self.assertIn('workspace "chat" {\n    open-on-output "DP-1"\n}', self.text())

        self.assertEqual(b.setEnv("QT_QPA_PLATFORM", "wayland"), "")
        self.assertIn("no spaces", b.setEnv("BAD NAME", "x"))
        self.assertEqual([e["name"] for e in b.environment], ["QT_QPA_PLATFORM"])
        self.assert_valid()
        b.removeEnv("QT_QPA_PLATFORM")
        b.removeWorkspace("chat")
        self.assertEqual(b.environment, [])

    def test_search(self):
        b = self.load()
        hits = b.searchSettings("shadow")
        self.assertIn("appearance", {h["page"] for h in hits})
        self.assertIn("overview", {h["page"] for h in hits})
        self.assertEqual([h["setting"]["path"] for h in b.searchSettings("natural trackball")],
                         ["input/trackball/natural-scroll"])
        self.assertEqual(b.searchSettings("  "), [])


class SourceEditor(Base):
    def test_text_edit_is_one_pending_change(self):
        b = self.load()
        before = self.text()
        new = before.replace("    gaps 16\n", "    gaps 24\n")
        self.assertEqual(b.setFileText(self.main, new)["error"], "")
        self.assertEqual(self.cfg.get("layout/gaps"), 24)
        self.assertEqual(self.cfg.pending_count(), 1)
        self.assertIn("+    gaps 24", self.cfg.diff())
        # a setting changed from a page afterwards stacks on top
        b.setValue("layout/border/width", 6.0)
        self.assertEqual(self.cfg.pending_count(), 2)
        # back to the saved text: nothing pending
        b.setValue("layout/border/width", 4.0)
        b.setFileText(self.main, before)
        self.assertEqual(self.cfg.pending, {})

    def test_text_that_does_not_parse_changes_nothing(self):
        b = self.load()
        before = self.text()
        result = b.setFileText(self.main, before.replace("layout {", "layout {{", 1))
        self.assertNotEqual(result["error"], "")
        self.assertGreater(result["line"], 0)
        self.assertEqual(self.text(), before)
        self.assertEqual(self.cfg.pending, {})

    @unittest.skipUnless(HAVE_NIRI, "niri is not installed")
    def test_niri_errors_and_save(self):
        b = self.load()
        bad = self.text().replace("    gaps 16\n", "    gaps \"wide\"\n")
        self.assertEqual(b.setFileText(self.main, bad)["error"], "")   # parses; niri rejects it
        ok, _ = self.cfg.validate()
        self.assertFalse(ok)
        self.assertFalse(self.cfg.save()[0])
        good = bad.replace('gaps "wide"', "gaps 8")
        b.setFileText(self.main, good)
        self.assertTrue(self.cfg.save()[0])
        self.assertEqual(Config(self.main).get("layout/gaps"), 8)

    def test_new_include_is_loaded(self):
        b = self.load(INCLUDES)
        extra = os.path.join(os.path.dirname(self.main), "extra.kdl")
        with open(extra, "w", encoding="utf-8") as fh:
            fh.write("prefer-no-csd\n")
        b.setFileText(self.main, self.text() + 'include "extra.kdl"\n')
        self.assertIn(extra, self.cfg.tree.files())
        self.assertIs(self.cfg.get("prefer-no-csd"), True)

    def test_outside_edit_conflicts_with_a_text_edit(self):
        b = self.load()
        b.setFileText(self.main, self.text().replace("gaps 16", "gaps 24"))
        with open(self.main, "a", encoding="utf-8") as fh:
            fh.write("\nprefer-no-csd\n")
        self.assertEqual(self.cfg.rebase(), [FILE + os.path.normpath(self.main)])
        self.assertEqual(b.conflicts[0]["path"], "config.kdl (edited as text)")
        self.cfg.resolve_conflicts(keep_mine=True)
        self.assertEqual(self.cfg.get("layout/gaps"), 24)

    @unittest.skipUnless(HAVE_NIRI, "niri is not installed")
    def test_managed_mode_keeps_user_files_read_only(self):
        b = self.load(INCLUDES)
        self.assertTrue(self.cfg.set_write_mode(MANAGED)[0])
        self.assertFalse(b.fileWritable(self.main))
        self.assertTrue(b.fileWritable(self.cfg.managed_file))
        self.assertIn("read-only", b.setFileText(self.main, "prefer-no-csd\n")["error"])
        with self.assertRaises(ReadOnlyError):
            self.cfg.set_text(self.main, "")

    def test_links_both_ways(self):
        b = self.load()
        seen = []
        b.sourceRequested.connect(lambda f, line: seen.append((f, line)))
        b.showSource("layout/gaps")
        line = seen[0][1]
        self.assertEqual(self.text().splitlines()[line - 1].strip(), "gaps 16")
        here = b.pathAt(self.main, line)
        self.assertEqual((here["path"], here["page"], here["pageTitle"]), ("layout › gaps", "layout", "Layout"))
        tp = self.text().splitlines().index("    touchpad {") + 2
        self.assertEqual(b.pathAt(self.main, tp)["page"], "pointer")
        self.assertEqual(b.pathAt(self.main, 1)["page"], "")       # a comment line


class Formatting(unittest.TestCase):
    def test_whole_floats_keep_their_point(self):
        self.assertEqual(niri_core.format_value(1.0), "1.0")
        self.assertEqual(niri_core.format_value(0.25), "0.25")
        self.assertEqual(niri_core.format_value(3), "3")

    def test_top_level_node_without_block(self):
        self.assertEqual(niri_core.format_block("spawn-at-startup", {"args": ["a", "b"], "props": {}}),
                         'spawn-at-startup "a" "b"')


class LayoutColors(Base):
    """The colours cards of focus-ring, border and tab-indicator, with gradients."""

    def rows(self, path="layout/focus-ring"):
        return {r["state"]: r for r in self.backend.blockColors(path, {"urgent": "#9b0000"})}

    def test_colours_are_read_and_written(self):
        b = self.load()
        rows = self.rows()
        self.assertEqual(rows["active"]["color"], "#7fc8ff")
        self.assertEqual(rows["urgent"]["color"], "")              # not set: niri's default
        self.assertEqual(rows["urgent"]["fallback"], "#9b0000")
        self.assertEqual(rows["active"]["gradient"], {})
        b.setText("layout/focus-ring/active-color", "#000000")
        self.assertIn('        active-color "#000000"\n', self.text())
        b.setText("layout/focus-ring/active-color", "")             # empty: removed
        self.assertIsNone(self.cfg.get("layout/focus-ring/active-color"))

    def test_gradient_added_edited_and_removed(self):
        b = self.load()
        path = "layout/border/active-gradient"
        self.assertEqual(b.setGradient(path, b.gradientDefault("active")), "")
        self.assertIn('        active-gradient from="#80c8ff" to="#bbddff" angle=45\n', self.text())
        self.assertEqual(self.rows("layout/border")["active"]["gradient"]["angle"], 45)
        value = dict(b.gradientDefault("active"), angle=180, rel="workspace-view")
        self.assertEqual(b.setGradient(path, value), "")
        self.assertIn('active-gradient from="#80c8ff" to="#bbddff" relative-to="workspace-view"\n', self.text())
        self.assertIn("whole number", b.setGradient(path, dict(value, angle="12.5")))
        self.assert_valid()
        b.resetValue(path)
        self.assertIsNone(self.cfg.get(path))

    def test_a_gradient_the_editor_cannot_show_is_listed_as_kdl(self):
        self.load()
        self.cfg.set("layout/tab-indicator/urgent-gradient",
                     {"args": [], "props": {"from": "#800", "to": "#a33", "in": "hsl"}})
        row = self.rows("layout/tab-indicator")["urgent"]
        self.assertEqual(row["gradient"], {})
        self.assertEqual(row["kdl"], 'from="#800" to="#a33" in="hsl"')

    def test_is_on_moved_to_config(self):
        b = self.load()
        self.assertFalse(self.cfg.is_on("layout/border", False))      # `off` in the default config
        self.assertTrue(self.cfg.is_on("layout/focus-ring", True))
        b.setOn("layout/border", True, False)
        self.assertTrue(b.isOn("layout/border", False))


class Suggestions(Base):
    """Output and workspace names offered by open-on-output, map-to-output and open-on-workspace."""

    MONITOR = {"HDMI-A-1": {"name": "HDMI-A-1", "make": "Samsung Electric Company", "model": "C32HG7x",
                            "serial": "HTRK300541"},
               "eDP-1": {"name": "eDP-1", "make": "BOE", "model": "0x0BCA", "serial": "Unknown"}}

    def connect(self, b):
        """Pretend niri is running with these monitors."""
        from unittest import mock
        b._version = "26.04"
        patch = mock.patch("niri_settings.ipc.outputs", return_value=dict(self.MONITOR))
        patch.start()
        self.addCleanup(patch.stop)

    def test_outputs_from_niri_and_the_config(self):
        b = self.load()
        self.connect(b)
        rows = b.suggestions("outputs")
        got = {s["value"]: s["note"] for s in rows}
        self.assertEqual(got["HDMI-A-1"], "Samsung Electric Company C32HG7x · by port")
        self.assertEqual(got["Samsung Electric Company C32HG7x HTRK300541"],
                         "same monitor as HDMI-A-1 · by make, model and serial")
        self.assertNotIn("BOE 0x0BCA Unknown", got)                    # no real serial: by port only
        self.assertEqual(got["eDP-1"], "BOE 0x0BCA · by port")
        # both names of one monitor share a group, which the list colours alike
        groups = {s["value"]: (s["group"], s["by"]) for s in rows}
        self.assertEqual(groups["HDMI-A-1"][0], groups["Samsung Electric Company C32HG7x HTRK300541"][0])
        self.assertNotEqual(groups["HDMI-A-1"][0], groups["eDP-1"][0])
        self.assertEqual(groups["Samsung Electric Company C32HG7x HTRK300541"][1], "monitor")
        self.cfg.set("output[DP-3]/scale", 2)
        got = {s["value"]: (s["note"], s["group"]) for s in b.suggestions("outputs")}
        self.assertEqual(got["DP-3"], ("in your config, not connected", -1))

    def test_unknown_output_gets_a_note(self):
        b = self.load()
        self.assertEqual(b.suggestionNote("outputs", "DP-9"), "")      # offline: cannot tell
        self.connect(b)
        b.suggestions("outputs")
        self.assertEqual(b.suggestionNote("outputs", "hdmi-a-1"), "")  # niri ignores case
        self.assertEqual(b.suggestionNote("outputs", "samsung electric company c32hg7x htrk300541"), "")
        self.assertIn("No connected or configured output", b.suggestionNote("outputs", "DP-9"))
        self.assertEqual(b.suggestionNote("outputs", ""), "")

    def test_named_workspaces(self):
        b = self.load()
        self.assertEqual(b.suggestions("workspaces"), [])
        self.assertEqual(b.addWorkspace("chat"), "")
        b.setWorkspaceOutput("chat", "HDMI-A-1")
        self.assertEqual(b.suggestions("workspaces"),
                         [{"value": "chat", "note": "named workspace on HDMI-A-1", "group": -1, "by": "",
                           "match": "chat"}])
        self.assertEqual(b.suggestionNote("workspaces", "chat"), "")
        self.assertEqual(b.suggestionNote("workspaces", "Chat"), "The named workspace is written “chat”.")
        self.assertIn("No named workspace", b.suggestionNote("workspaces", "mail"))

    def test_schema_marks_the_name_fields(self):
        from niri_settings.schema import window_rules
        self.assertEqual(window_rules.PROP_PATHS["open-on-output"]["suggest"], "outputs")
        self.assertEqual(window_rules.PROP_PATHS["open-on-workspace"]["suggest"], "workspaces")


if __name__ == "__main__":
    unittest.main()
