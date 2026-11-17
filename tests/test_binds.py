"""Key bindings: the model, the keymap and the map the page draws."""
import os
import shutil
import tempfile
import unittest

from PySide6.QtCore import QCoreApplication, QObject, Qt, Signal

from niri_settings.binds import (BindsModel, action_text, parse_action, parse_combo, role,
                       short_label)
from niri_settings.binds_view import BindsView
from niri_settings.config import MANAGED, Config, ReadOnlyError
from niri_settings.keymap import Keymap
from niri_settings.schema import actions

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "corpus", "default", "config.kdl")
INCLUDES = os.path.join(HERE, "corpus", "includes")


class StubBackend(QObject):
    """What BindsView needs from the app's Backend, without timers or IPC."""
    changed = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.notice = ""

    def _edit(self, fn):
        try:
            fn()
        except ReadOnlyError as e:
            self.notice = str(e)
            return False
        return True

    def _touch(self):
        self.changed.emit()


class Base(unittest.TestCase):
    layout = "us"

    def setUp(self):
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        os.environ["XDG_STATE_HOME"] = os.path.join(self.tmp, "state")
        os.environ["XDG_CONFIG_HOME"] = os.path.join(self.tmp, "xdg")

    def load(self, source=DEFAULT, extra=""):
        folder = os.path.join(self.tmp, "niri")
        if os.path.isdir(source):
            shutil.copytree(source, folder)
        else:
            os.makedirs(folder)
            shutil.copy(source, os.path.join(folder, "config.kdl"))
        self.main = os.path.join(folder, "config.kdl")
        if extra:
            with open(self.main, "a", encoding="utf-8") as f:
                f.write(extra)
        self.config = Config(self.main)
        self.model = BindsModel(lambda: self.config, Keymap(self.layout))
        return self.model

    def view(self):
        self.backend = StubBackend(self.config)
        return BindsView(self.backend, self.model)

    def text(self):
        return self.config.tree.render(self.main)


class Names(Base):
    def test_combo_spellings_are_one_key(self):
        self.assertEqual(parse_combo("Mod+Shift+H"), parse_combo("shift+MOD+H"))
        self.assertEqual(parse_combo("Control+Win+x")[0], frozenset({"Ctrl", "Super"}))
        self.assertEqual(parse_combo("Print"), (frozenset(), "Print"))
        k = Keymap("us")
        self.assertEqual(k.canonical("H"), k.canonical("h"))
        self.assertEqual(k.canonical("Page_Down"), k.canonical("Next"))
        self.assertEqual(k.written(k.canonical("page_down")), "Page_Down")
        self.assertEqual(k.written("h"), "H")

    def test_keymap_follows_the_layout(self):
        us, fi = Keymap("us"), Keymap("fi")
        self.assertEqual(us.keycode("Minus"), 20)
        self.assertFalse(us.iso)
        self.assertTrue(fi.iso)
        if fi.native:  # needs libxkbcommon and the xkb data files
            self.assertEqual(fi.keycode("Minus"), 61)
            self.assertIsNone(fi.keycode("BracketLeft"))
            self.assertEqual(fi.label(47), "Ö")

    def test_action_text_round_trip(self):
        for text in ('spawn "alacritty" "-e" "fish"', "focus-workspace 3", "close-window",
                     "quit skip-confirmation=true", 'set-column-width "-10%"',
                     'move-column-to-workspace "chat" focus=false'):
            self.assertEqual(action_text(parse_action(text)), text)
        self.assertEqual(parse_action("close-window;")["name"], "close-window")
        for bad in ("", "a; b", 'spawn "unclosed'):
            with self.assertRaises(ValueError):
                parse_action(bad)

    def test_categories_and_labels(self):
        self.assertEqual(actions.category("focus-column-left"), actions.FOCUS)
        self.assertEqual(actions.category("focus-workspace"), actions.WORKSPACES)
        self.assertEqual(actions.category("move-column-to-monitor-left"), actions.WORKSPACES)
        self.assertEqual(actions.category("close-window"), actions.WINDOWS)
        self.assertEqual(actions.category("spawn-sh"), actions.SYSTEM)
        self.assertEqual(short_label(parse_action('spawn "/usr/bin/foot" "-e"')), "foot")
        self.assertEqual(short_label(parse_action('spawn-sh "wpctl set-volume x 1"')), "wpctl")
        self.assertEqual(short_label(parse_action("focus-workspace 3")), "focus ws 3")
        self.assertEqual(role(parse_action("quit")), "quit")
        self.assertEqual(role(parse_action('spawn "kitty"')), "terminal")
        self.assertIsNone(role(parse_action('spawn "fuzzel"')))


class MapMatchesConfig(Base):
    """Phase 5 exit check: the map shows `binds {}` exactly."""

    def check(self, source):
        model = self.load(source)
        view = self.view()
        written = [e["name"] for e in self.config.tree.entries("binds")]
        self.assertTrue(written)
        shown = []
        for layer in view.layers:
            view.setLayer(layer["value"])
            caps = [c for rows in (view.rows, view.navRows) for row in rows for c in row
                    if not c["gap"] and c["bound"]]
            keys = [c["key"] for c in caps] + [x["key"] for x in view.extras if x["color"]]
            self.assertEqual(len(keys), len(set(keys)), layer)
            self.assertEqual(len(keys), layer["count"], layer)
            for key in keys:
                view.selectKey(key)
                detail = view.detail
                self.assertTrue(detail["bound"], (layer, key))
                bind = model.at(parse_combo(detail["name"])[0], key)
                self.assertEqual(detail["actionText"], action_text(bind.action))
                shown.append(detail["name"])
        effective = [b.name for b in model.effective()]
        self.assertEqual(sorted(shown), sorted(effective))
        return written, shown

    def test_default_config(self):
        written, shown = self.check(DEFAULT)
        self.assertEqual(sorted(shown), sorted(written))   # no overrides in one file
        self.assertIn("Mod+WheelScrollDown", shown)
        self.assertIn("XF86AudioRaiseVolume", shown)

    def test_default_config_on_a_finnish_layout(self):
        self.layout = "fi"
        self.check(DEFAULT)

    def test_include_tree(self):
        written, shown = self.check(INCLUDES)
        self.assertLessEqual(len(shown), len(written))

    def test_cap_colours_and_modifiers(self):
        self.load()
        view = self.view()
        caps = {c["key"]: c for row in view.rows for c in row if not c["gap"]}
        self.assertEqual(caps["h"]["color"], "#8fb0ff")        # focus-column-left
        self.assertEqual(caps["t"]["color"], "#f2a65a")        # spawn
        self.assertEqual(caps["1"]["color"], "#7fd1a8")        # focus-workspace 1
        self.assertEqual(caps["q"]["color"], "#c4a7ff")        # close-window
        self.assertTrue(caps["Super_L"]["held"])
        self.assertFalse(caps["Shift_L"]["held"])
        view.toggleMod("Shift")
        self.assertEqual(view.layer, "Mod+Shift")
        caps = {c["key"]: c for row in view.rows for c in row if not c["gap"]}
        self.assertTrue(caps["Shift_L"]["held"])
        self.assertEqual(action_text(self.model.at({"Mod", "Shift"}, "e").action), "quit")


class Editing(Base):
    def test_change_action_keeps_the_rest_of_the_line(self):
        model = self.load()
        before = self.text()
        model.set_action({"Mod"}, "T", parse_action('spawn "foot"'))
        after = self.text()
        self.assertIn('Mod+T hotkey-overlay-title="Open a Terminal: alacritty" { spawn "foot"; }', after)
        changed = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
        self.assertEqual(len(changed), 1)
        self.assertEqual(list(self.config.pending), ["binds/Mod+T"])
        ok, message = self.config.validate()
        self.assertTrue(ok, message)
        model.set_action({"Mod"}, "t", parse_action('spawn "alacritty"'))
        self.assertEqual(self.text(), before)
        self.assertFalse(self.config.pending)

    def test_new_bind_props_and_remove(self):
        model = self.load()
        before = self.text()
        self.assertIsNone(model.at({"Mod"}, "g"))
        path = model.set_action({"Mod"}, "g", parse_action("toggle-overview"))
        self.assertEqual(path, "binds/Mod+G")
        self.assertIn("    Mod+G { toggle-overview; }\n", self.text())
        bind = model.at({"Mod"}, "G")
        model.set_prop(bind, "repeat", False)
        model.set_prop(model.at({"Mod"}, "g"), "cooldown-ms", 150)
        model.set_prop(model.at({"Mod"}, "g"), "hotkey-overlay-title", "Overview")
        self.assertIn('Mod+G repeat=false cooldown-ms=150 hotkey-overlay-title="Overview" { toggle-overview; }',
                      self.text())
        ok, message = self.config.validate()
        self.assertTrue(ok, message)
        model.set_prop(model.at({"Mod"}, "g"), "repeat", True)     # the default: dropped
        model.set_prop(model.at({"Mod"}, "g"), "hotkey-overlay-title", None)
        self.assertIn("Mod+G cooldown-ms=150 hotkey-overlay-title=null { toggle-overview; }", self.text())
        model.remove(model.at({"Mod"}, "g"))
        self.assertEqual(self.text(), before)

    def test_allow_when_locked_is_dropped_for_other_actions(self):
        model = self.load()
        bind = model.at(set(), "XF86AudioMute")
        self.assertTrue(bind.props["allow-when-locked"])
        model.set_action(set(), "XF86AudioMute", parse_action("close-window"))
        self.assertEqual(model.at(set(), "XF86AudioMute").props, {})
        ok, message = self.config.validate()
        self.assertTrue(ok, message)

    def test_move_renames_in_place(self):
        model = self.load()
        before = self.text()
        line = next(l for l in before.splitlines() if l.strip().startswith("Mod+O "))
        path = model.move(model.at({"Mod"}, "o"), {"Mod", "Alt"}, "o")
        self.assertEqual(path, "binds/Mod+Alt+O")
        self.assertIn(line.replace("Mod+O ", "Mod+Alt+O ", 1), self.text())
        self.assertEqual(before.count("\n"), self.text().count("\n"))
        self.assertEqual(set(self.config.pending), {"binds/Mod+O", "binds/Mod+Alt+O"})
        with self.assertRaises(ValueError):
            model.move(model.at({"Mod", "Alt"}, "o"), {"Mod"}, "t")   # taken
        model.move(model.at({"Mod", "Alt"}, "o"), {"Mod"}, "o")
        self.assertEqual(self.text(), before)

    def test_save_and_reload(self):
        model = self.load()
        model.set_action({"Mod"}, "g", parse_action('spawn "kitty" "--single-instance"'))
        ok, message = self.config.save()
        self.assertTrue(ok, message)
        fresh = BindsModel(lambda: Config(self.main), Keymap("us"))
        self.assertEqual(action_text(fresh.at({"Mod"}, "g").action), 'spawn "kitty" "--single-instance"')

    def test_binds_are_not_live_previewed(self):
        model = self.load()
        model.set_action({"Mod"}, "g", parse_action("quit"))
        self.assertNotIn("quit", self.config.preview_text())


class Conflicts(Base):
    def test_override_across_files(self):
        model = self.load(INCLUDES, extra='\nbinds {\n    Mod+T { spawn "emote"; }\n}\n')
        found = {c["combo"]: c for c in model.conflicts()}
        mod_t = found["Mod+T"]
        self.assertEqual(mod_t["kind"], "override")
        self.assertEqual(os.path.basename(mod_t["winner"].file), "config.kdl")
        self.assertEqual(os.path.basename(mod_t["losers"][0].file), "binds.kdl")
        self.assertEqual(action_text(model.at({"Mod"}, "t").action), 'spawn "emote"')
        view = self.view()
        self.assertTrue(any("The later one wins" in c["text"] for c in view.conflicts))
        view.selectKey("t")
        self.assertEqual(len(view.detail["overridden"]), 1)

    def test_edit_goes_to_the_winning_file_and_remove_clears_all(self):
        model = self.load(INCLUDES, extra='\nbinds {\n    Mod+T { spawn "emote"; }\n}\n')
        sub = os.path.join(os.path.dirname(self.main), "sub", "binds.kdl")
        sub_before = self.config.tree.render(sub)
        model.set_action({"Mod"}, "t", parse_action('spawn "kitty"'))
        self.assertIn('spawn "kitty"', self.text())
        self.assertEqual(self.config.tree.render(sub), sub_before)
        model.remove(model.at({"Mod"}, "t"))
        self.assertIsNone(model.at({"Mod"}, "t"))
        self.assertNotIn("Mod+T", self.config.tree.render(sub))

    def test_duplicate_and_shadow(self):
        model = self.load(extra='\nbinds {\n    mod+t { spawn "foot"; }\n    Super+H { close-window; }\n}\n')
        kinds = {(c["combo"], c["kind"]) for c in model.conflicts()}
        self.assertIn(("mod+t", "duplicate"), kinds)
        self.assertIn(("Mod+H", "shadow"), kinds)
        if shutil.which("niri"):
            ok, _ = self.config._validate_stage({})
            self.assertFalse(ok)   # niri itself refuses a key bound twice in one file

    def test_managed_mode_overrides_but_cannot_remove(self):
        model = self.load()
        self.config.set_write_mode(MANAGED)
        before = self.text()
        model.set_action({"Mod"}, "t", parse_action('spawn "foot"'))
        self.assertIn('spawn "foot"', self.config.tree.render(self.config.managed_file))
        self.assertEqual(action_text(model.at({"Mod"}, "t").action), 'spawn "foot"')
        with self.assertRaises(ReadOnlyError):
            model.remove(model.at({"Mod"}, "q"))
        self.assertEqual(self.text().replace(before, ""), "")


class Lockout(Base):
    def test_only_quit_and_only_terminal_need_a_confirm(self):
        model = self.load()
        quit_bind = model.at({"Mod", "Shift"}, "e")
        self.assertEqual(model.lockout(quit_bind), "")          # Ctrl+Alt+Delete also quits
        model.remove(model.at({"Ctrl", "Alt"}, "Delete"))
        quit_bind = model.at({"Mod", "Shift"}, "e")
        self.assertIn("only key for quit", model.lockout(quit_bind))
        self.assertIn("only key for quit", model.lockout(quit_bind, parse_action("close-window")))
        self.assertEqual(model.lockout(quit_bind, parse_action("quit skip-confirmation=true")), "")
        terminal = model.at({"Mod"}, "t")
        self.assertIn("terminal", model.lockout(terminal))
        self.assertEqual(model.lockout(terminal, parse_action('spawn "kitty"')), "")
        self.assertEqual(model.lockout(model.at({"Mod"}, "d")), "")

    def test_view_asks_before_removing(self):
        self.load()
        view = self.view()
        view.selectKey("t")
        view.removeBind()
        self.assertIn("terminal", view.confirmText)
        self.assertIsNotNone(self.model.at({"Mod"}, "t"))
        view.confirm(False)
        self.assertEqual(view.confirmText, "")
        self.assertIsNotNone(self.model.at({"Mod"}, "t"))
        view.setActionText('spawn "fuzzel"')
        self.assertEqual(view.confirmLabel, "Change anyway")
        view.confirm(True)
        self.assertEqual(action_text(self.model.at({"Mod"}, "t").action), 'spawn "fuzzel"')
        view.selectKey("d")
        view.removeBind()                                        # not a lockout: no question
        self.assertEqual(view.confirmText, "")
        self.assertIsNone(self.model.at({"Mod"}, "d"))


class View(Base):
    META, SHIFT = Qt.KeyboardModifier.MetaModifier.value, Qt.KeyboardModifier.ShiftModifier.value

    def test_recording_selects_a_combination(self):
        self.load()
        view = self.view()
        self.assertFalse(view.recorded(43, self.META, "h"))      # not recording
        view.startRecording("select")
        self.assertFalse(view.recorded(133, self.META, ""))      # only a modifier so far
        self.assertEqual(view.recording, "select")
        self.assertTrue(view.recorded(26, self.META | self.SHIFT, "E"))
        self.assertEqual(view.recording, "")
        self.assertEqual(view.layer, "Mod+Shift")
        self.assertEqual(view.detail["actionText"], "quit")
        view.startRecording("select")
        self.assertTrue(view.recorded(9, 0, ""))                 # Esc cancels
        self.assertEqual(view.detail["actionText"], "quit")

    def test_recording_moves_a_bind(self):
        self.load()
        view = self.view()
        view.selectKey("o")
        view.startRecording("move")
        self.assertTrue(view.recorded(57, self.META, "n"))       # Mod+N is free
        self.assertEqual(view.detail["name"], "Mod+N")
        self.assertEqual(view.detail["actionText"], "toggle-overview")
        self.assertIsNone(self.model.at({"Mod"}, "o"))
        view.startRecording("move")
        view.recorded(28, self.META, "t")                        # Mod+T is taken
        self.assertIn("already bound", view.detail["error"])
        self.assertEqual(view.detail["name"], "Mod+N")

    def test_typing_an_action(self):
        self.load()
        view = self.view()
        view.selectKey("g")
        self.assertFalse(view.detail["bound"])
        self.assertEqual(view.detail["status"], "free")
        view.setActionText('spawn "unclosed')
        self.assertNotEqual(view.detail["error"], "")
        self.assertFalse(self.config.pending)
        view.pickAction("focus-workspace")
        self.assertEqual(view.detail["actionText"], "focus-workspace 1")
        self.assertTrue(view.detail["bound"])
        view.setProp("cooldown-ms", 200)
        view.setTitleHidden(True)
        self.assertTrue(view.detail["titleHidden"])
        self.assertEqual(view.detail["cooldown"], 200)
        ok, message = self.config.validate()
        self.assertTrue(ok, message)
        names = [m["name"] for m in view.actionMatches("focus-workspace-d")]
        self.assertIn("focus-workspace-down", names)

    def test_pointer_trigger_and_missing_key(self):
        self.layout = "fi"
        self.load()
        view = self.view()
        view.selectKey("MouseMiddle")
        self.assertTrue(view.detail["pointer"])
        self.assertTrue(any(x["key"] == "MouseMiddle" and x["selected"] for x in view.extras))
        view.setActionText("close-window")
        self.assertIn("    Mod+MouseMiddle { close-window; }\n", self.text())
        if self.model.keymap.native:
            view.selectKey(self.model.keymap.canonical("BracketLeft"))
            self.assertTrue(view.detail["missing"])


if __name__ == "__main__":
    unittest.main()
