"""Phase 6: window rules. Editing, matching, merging and the page's view."""
import copy
import os
import shutil
import tempfile
import unittest

from PySide6.QtCore import QCoreApplication, QObject, Signal

from niri_settings import ipc, niri_core
from niri_settings import rules as rl
from niri_settings.config import MANAGED, Config, ReadOnlyError
from niri_settings.rules import RulesModel
from niri_settings.rules_view import LayerRulesView, RulesView

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "corpus", "default", "config.kdl")
INCLUDES = os.path.join(HERE, "corpus", "includes")
HAVE_NIRI = shutil.which("niri") is not None


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def match(**props):
    return {"name": "match", "args": [], "props": {k.replace("_", "-"): v for k, v in props.items()}}


def exclude(**props):
    return dict(match(**props), name="exclude")


def prop(name, *args, **props):
    return {"name": name, "args": list(args), "props": props}


def rule(*children, comment=""):
    return {"args": [], "props": {}, "children": list(children), "comment": comment}


class Base(unittest.TestCase):
    def setUp(self):
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
        self.config = Config(self.main)
        self.model = RulesModel(lambda: self.config)
        return self.config

    def text(self, path=None):
        return self.config.tree.render(path or self.main)


class CoreEdits(Base):
    """Rules are rewritten child by child: comments and raw strings stay."""

    def test_read_with_names(self):
        cfg = self.load()
        rules = cfg.rules("window-rule")
        self.assertEqual(len(rules), 4)   # the last two are the /- examples, turned off
        self.assertEqual([r.get("disabled", False) for r in rules], [False, False, True, True])
        self.assertEqual(rules[0]["comment"], "Work around WezTerm's initial configure bug")
        self.assertEqual(rules[3]["comment"], "Example: enable rounded corners for all windows.")
        self.assertEqual(rules[1]["children"][0]["props"]["app-id"], "firefox$")
        self.assertEqual(rules[0]["children"][1], {"name": "default-column-width", "args": [], "props": {},
                                                   "children": []})

    def test_edit_keeps_everything_else(self):
        cfg = self.load()
        before = self.text()
        rules = cfg.rules("window-rule")
        new = copy.deepcopy(rules)
        new[1]["children"][0]["props"]["title"] = "^PiP$"
        new[1]["children"].append(prop("opacity", 0.9))
        cfg.set_rules("window-rule", new)
        text = self.text()
        self.assertIn('match app-id=r#"firefox$"# title="^PiP$"\n    open-floating true\n    opacity 0.9\n}', text)
        self.assertIn("    // - Flatpak Firefox (app-id is \"org.mozilla.firefox\")\n", text)
        self.assertEqual(cfg.pending_count(), 1)
        cfg.set_rules("window-rule", rules)
        self.assertEqual(self.text(), before)
        self.assertEqual(cfg.pending, {})

    def test_one_line_rule_keeps_raw_strings(self):
        self.load(INCLUDES)
        rules = self.config.rules("window-rule")
        gnome = next(i for i, r in enumerate(rules) if r["children"][0]["props"].get("app-id") == r"^org\.gnome\.")
        new = copy.deepcopy(rules)
        new[gnome]["children"][1]["args"] = [False]
        new[gnome]["children"].append(prop("focus-ring", **{}) | {"children": [prop("off")]})
        self.config.set_rules("window-rule", new)
        self.assertIn('window-rule { match app-id=r#"^org\\.gnome\\."#; open-floating false; focus-ring { off; }; }',
                      self.text())

    def test_new_rule_is_multi_line_with_its_name(self):
        cfg = self.load()
        new = cfg.rules("window-rule") + [rule(match(app_id=niri_core.Raw(r"^org\.foo$")), prop("opacity", 0.8),
                                               prop("focus-ring") | {"children": [prop("off"), prop("width", 2)]},
                                               prop("default-column-width") | {"children": [prop("fixed", 480)]},
                                               comment="Foo is see-through")]
        cfg.set_rules("window-rule", new)
        self.assertIn("    clip-to-geometry true\n}\n\n// Foo is see-through\nwindow-rule {\n"
                      '    match app-id=r#"^org\\.foo$"#\n'
                      "    opacity 0.8\n"
                      "    focus-ring {\n        off\n        width 2\n    }\n"
                      "    default-column-width { fixed 480; }\n}\n", self.text())
        self.assertEqual(cfg.rules("window-rule"), new)

    def test_remove_takes_its_comment_and_leaves_one_blank_line(self):
        cfg = self.load()
        before = self.text()
        rules = cfg.rules("window-rule")
        cfg.set_rules("window-rule", rules[:1])
        self.assertNotIn("picture-in-picture player", self.text())
        self.assertNotIn("\n\n\n", self.text())
        cfg.set_rules("window-rule", rules)
        self.assertEqual(cfg.rules("window-rule"), rules)
        self.assertEqual(cfg.pending, {})
        self.assertEqual(self.text(), before)   # nothing pending: reloaded as it was

    def test_move_and_rename(self):
        cfg = self.load()
        first = cfg.rules("window-rule")[0]
        self.assertEqual(self.model.move(0, 1), 1)
        self.assertEqual(cfg.rules("window-rule")[1], first)
        text = self.text()
        self.assertLess(text.index("picture-in-picture player"), text.index("// Work around WezTerm"))
        # moved as written: raw strings and every comment line kept
        self.assertIn("// by setting an empty default-column-width.\nwindow-rule {\n"
                      "    // This regular expression", text)
        self.assertIn('match app-id=r#"^org\\.wezfurlong\\.wezterm$"#', text)
        self.assertNotIn("\n\n\n", text)
        # the name is the first comment line; the rest stays
        self.model.rename(1, "WezTerm fix")
        self.assertIn("// WezTerm fix\n// by setting an empty default-column-width.\nwindow-rule {\n", self.text())
        self.model.rename(0, "")
        self.assertEqual(cfg.rules("window-rule")[0]["comment"], "")
        self.assertIn("\n\nwindow-rule {\n    // This app-id", self.text())
        self.assertEqual(cfg.pending_count(), 2)

    def test_clearing_a_multi_line_name_keeps_the_explanation(self):
        cfg = self.load()
        self.model.rename(0, "")
        # a bare // stands in for the name, so the next line does not become it
        self.assertIn("//\n// by setting an empty default-column-width.\nwindow-rule {\n", self.text())
        self.assertEqual(cfg.rules("window-rule")[0]["comment"], "")
        self.assertEqual(rl.title(cfg.rules("window-rule")[0]), "org.wezfurlong.wezterm")
        # naming it again fills the bare // back in
        self.model.rename(0, "WezTerm fix")
        self.assertIn("\n// WezTerm fix\n// by setting an empty default-column-width.\nwindow-rule {\n",
                      self.text())
        self.assertNotIn("//\n// WezTerm fix", self.text())

    def test_rule_in_included_file_is_edited_there(self):
        self.load(INCLUDES)
        colors = os.path.join(os.path.dirname(self.main), "colors.kdl")
        before = self.text()
        self.model.set_prop(0, "opacity", prop("opacity", 0.5))
        self.assertEqual(self.text(), before)
        self.assertIn("    open-floating true\n    opacity 0.5\n}", self.text(colors))
        # a new rule after it goes to the same file
        self.model.add(rule(prop("opacity", 0.7)), at=1)
        self.assertIn("opacity 0.7", self.text(colors))
        self.assertEqual([r["children"][-1]["args"] for r in self.config.rules("window-rule")][:2], [[0.5], [0.7]])

    @unittest.skipUnless(HAVE_NIRI, "niri is not installed")
    def test_niri_accepts_what_is_written(self):
        cfg = self.load()
        self.model.add(rl.from_template(next(t for t in rl.WINDOW.TEMPLATES if t["id"] == "pip"), None))
        i = len(cfg.rules("window-rule")) - 1
        for path, node in [("default-window-height", {"args": [], "props": {}, "children": [prop("fixed", 270)]}),
                           ("focus-ring/state", {"args": ["off"], "props": {}}),
                           ("shadow/offset", {"args": [], "props": {"x": 0, "y": 5}}),
                           ("popups/background-effect/blur", {"args": [True], "props": {}}),
                           ("geometry-corner-radius", {"args": [8, 8, 0, 0], "props": {}})]:
            self.model.set_prop(i, path, node)
        self.model.add_directive(i, "exclude", {"is-floating": True})
        ok, message = cfg.validate()
        self.assertTrue(ok, message)
        self.assertTrue(cfg.save()[0])
        self.assertEqual(Config(self.main).rules("window-rule")[i], cfg.rules("window-rule")[i])

    def test_edits_that_add_are_previewed_as_added_rules(self):
        cfg = self.load()
        self.model.set_prop(1, "opacity", prop("opacity", 0.5))
        cfg.set("layout/gaps", 3)
        text = cfg.preview_text()
        self.assertIn("gaps 3", text)
        self.assertIn('window-rule {\n    match app-id="firefox$" title="^Picture-in-Picture$"\n'
                      '    opacity 0.5\n}', text)
        self.assertNotIn("open-floating", text)        # unchanged properties are not repeated

    def test_edits_that_cannot_be_shown_wait_for_save(self):
        cfg = self.load()
        self.model.remove(0)
        self.assertEqual(cfg.rule_preview("window-rule"), (None, "a rule was moved or removed"))
        self.assertNotIn("window-rule", cfg.preview_text())

    @unittest.skipUnless(HAVE_NIRI, "niri is not installed")
    def test_niri_accepts_the_preview(self):
        cfg = self.load()
        self.assertTrue(cfg.enable_preview()[0])
        self.model.set_prop(1, "shadow/state", {"args": ["on"], "props": {}})
        self.model.add(rule(match(app_id="^foot$"), prop("opacity", 0.9)))
        ok, message = cfg.write_preview()
        self.assertTrue(ok, message)
        self.assertEqual(read(cfg.preview_file).count("window-rule {"), 2)

    def test_a_rule_after_the_preview_include_stops_the_preview(self):
        cfg = self.load()
        self.assertTrue(cfg.enable_preview()[0])
        self.model.set_prop(1, "opacity", prop("opacity", 0.5))
        self.assertIsNotNone(cfg.rule_preview("window-rule")[0])
        cfg.set_text(self.main, cfg.tree.render(self.main) + 'window-rule {\n    match app-id="x"\n}\n')
        extra, why = cfg.rule_preview("window-rule")
        self.assertIsNone(extra)
        self.assertIn("after the preview include", why)


class SlashDash(Base):
    """Rules commented out with /- are listed, turned off, and can be turned on."""

    BLOCK_OUT = ("// Example: block out two password managers from screen capture.\n"
                 "// (This example rule is commented out with a \"/-\" in front.)\n"
                 "/-window-rule {\n")

    def test_turn_on_and_off_again(self):
        cfg = self.load()
        before = self.text()
        self.model.set_enabled(2, True)
        text = self.text()
        on = self.BLOCK_OUT.replace("/-window-rule", "window-rule")
        self.assertIn(on, text)
        self.assertNotIn("disabled", cfg.rules("window-rule")[2])
        self.assertEqual(cfg.pending_count(), 1)
        self.assertEqual(text.replace(on, self.BLOCK_OUT), before)
        self.model.set_enabled(2, False)
        self.assertEqual(self.text(), before)
        self.assertEqual(cfg.pending, {})

    def test_editing_a_rule_that_is_off_keeps_it_off(self):
        cfg = self.load()
        self.model.set_prop(3, "opacity", prop("opacity", 0.9))
        self.model.rename(3, "Round corners")
        self.assertIn("// Round corners\n// (This example rule is commented out with a \"/-\" in front.)\n"
                      "/-window-rule {\n    geometry-corner-radius 12\n    clip-to-geometry true\n"
                      "    opacity 0.9\n}\n", self.text())
        self.assertTrue(cfg.rules("window-rule")[3]["disabled"])

    def test_off_rules_move_add_and_remove(self):
        cfg = self.load()
        self.model.move(3, -3)
        self.assertTrue(self.text().index("/-window-rule {\n    geometry") < self.text().index("WezTerm"))
        self.assertEqual([r.get("disabled", False) for r in cfg.rules("window-rule")],
                         [True, False, False, True])
        self.model.remove(0)
        self.assertNotIn("geometry-corner-radius 12", self.text())
        self.model.add(rule(prop("opacity", 0.5), comment="Dim") | {"disabled": True})
        self.assertIn("// Dim\n/-window-rule {\n    opacity 0.5\n}\n", self.text())
        self.assertTrue(cfg.rules("window-rule")[-1]["disabled"])

    def test_only_top_level_nodes_count(self):
        doc = niri_core.load_string('/- include "gone.kdl"\nwindow-rule {\n    /-match app-id="x"\n'
                                    '    opacity 0.5\n}\n/-  layer-rule { opacity 0.1; }\n')
        rules = doc.top_nodes("window-rule")
        self.assertEqual(rules[0]["value"]["children"], [prop("opacity", 0.5)])
        self.assertFalse(rules[0]["disabled"])
        layer = doc.top_nodes("layer-rule")
        self.assertEqual((layer[0]["disabled"], layer[0]["text"]), (True, "/-  layer-rule { opacity 0.1; }"))
        self.assertIsNone(doc.get("layer-rule"))      # the rest of the config still ignores it
        self.assertEqual(doc.list(""), ["window-rule#0"])

    def test_turned_off_rules_never_match(self):
        r = rule(prop("opacity", 0.5)) | {"disabled": True}
        self.assertEqual(rl.check_rule(r, {}).status, rl.NO)

    @unittest.skipUnless(HAVE_NIRI, "niri is not installed")
    def test_niri_accepts_toggled_rules(self):
        cfg = self.load()
        self.model.set_enabled(2, True)
        self.model.set_enabled(1, False)
        ok, message = cfg.validate()
        self.assertTrue(ok, message)


class Managed(Base):
    @unittest.skipUnless(HAVE_NIRI, "niri is not installed")
    def test_new_rules_go_to_the_managed_file_and_user_rules_are_read_only(self):
        cfg = self.load(INCLUDES)
        self.assertTrue(cfg.set_write_mode(MANAGED)[0])
        n = len(cfg.rules("window-rule"))
        self.model.add(rule(match(app_id="^mpv$"), prop("variable-refresh-rate", True), comment="mpv VRR"))
        self.assertEqual(cfg.tree.dirty_files(), [cfg.managed_file])
        self.assertIn("// mpv VRR\nwindow-rule {", self.text(cfg.managed_file))
        self.model.set_prop(n, "opacity", prop("opacity", 0.9))       # its own rule: fine
        before = {f: self.text(f) for f in cfg.tree.files()}
        with self.assertRaises(ReadOnlyError):
            self.model.set_prop(0, "opacity", prop("opacity", 0.9))
        with self.assertRaises(ReadOnlyError):
            self.model.remove(0)
        with self.assertRaises(ReadOnlyError):
            self.model.add(rule(prop("opacity", 0.9)), at=0)          # in between user rules
        self.assertEqual({f: self.text(f) for f in cfg.tree.files()}, before)
        self.assertTrue(cfg.save()[0])


class OutsideEdits(Base):
    def test_rule_edit_survives_an_outside_edit(self):
        cfg = self.load()
        self.model.set_prop(1, "opacity", prop("opacity", 0.5))
        with open(self.main, "a", encoding="utf-8") as fh:
            fh.write("\nprefer-no-csd\n")
        self.assertEqual(cfg.rebase(), [])
        self.assertEqual(rl.get_prop(cfg.rules("window-rule")[1], "opacity")["args"], [0.5])
        self.assertIn("prefer-no-csd", self.text())

    def test_rules_changed_on_both_sides_are_a_conflict(self):
        cfg = self.load()
        self.model.set_prop(1, "opacity", prop("opacity", 0.5))
        text = read(self.main).replace("open-floating true", "open-floating false")
        with open(self.main, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.assertEqual(cfg.rebase(), ["window-rule"])
        cfg.resolve_conflicts(keep_mine=True)
        self.assertEqual(rl.get_prop(cfg.rules("window-rule")[1], "opacity")["args"], [0.5])


class Regex(unittest.TestCase):
    def test_rust_syntax(self):
        cases = [
            (r"^org\.foo$", "org.foo", True), (r"^org\.foo$", "org.foo\n", False),   # Rust $ is the very end
            ("firefox$", "org.mozilla.firefox", True), ("(?i)FIRE", "firefox", True),
            (r"[[:digit:]]+x", "12x", True), (r"[[:alpha:]]", "1", False),
            (r"(?<n>ab)c", "abc", True), (r"\x{41}", "A", True), (r"a\z", "a", True),
            (r"\<foo\>", "a foo b", True), (r"\<foo\>", "afoo", False),
        ]
        for pattern, text, hit in cases:
            rx = rl.compile_regex(pattern)
            self.assertIsNotNone(rx, pattern)
            self.assertEqual(rx.search(text) is not None, hit, (pattern, text))

    def without_regex_package(self):
        saved = rl._regex
        rl._regex = None
        rl._cache.clear()
        self.addCleanup(rl._cache.clear)
        self.addCleanup(setattr, rl, "_regex", saved)

    def test_unsupported_is_unknown_not_a_guess(self):
        self.without_regex_package()
        for pattern in (r"\pL+", r"\p{Greek}", "a(?i)b", "[a-z&&[^x]]", "(?U)a+"):
            self.assertIsNone(rl.compile_regex(pattern), pattern)
        f = {"app-id": "x", "title": "y"}
        self.assertEqual(rl.check_matcher("app-id", r"\pL", f)[0], rl.MAYBE)
        self.assertEqual(rl.regex_error(r"\pL"), "")
        self.assertIn("Not a valid regex", rl.regex_error("(unclosed"))

    @unittest.skipIf(rl._regex is None, "needs the regex package")
    def test_rust_only_syntax_with_the_regex_package(self):
        # Rust's answers; tests/test_nested.py checks the same kinds of pattern against niri.
        cases = [
            (r"\p{Greek}", "αβ", True), (r"^\pL+$", "héllo", True), (r"\PL", "abc", False),
            (r"^[a-z&&[^aeiou]]+$", "bcd", True), (r"^[a-z&&[^aeiou]]+$", "bad", False),
            (r"[a-z--[aeiou]]", "e", False), (r"^[a-c~~b-d]$", "d", True), (r"^[a-c~~b-d]$", "b", False),
            (r"^a(?i)b$", "aB", True), (r"^a(?i)b$", "AB", False),
            (r"^a(?i)b(?-i)c$", "aBc", True), (r"^a(?i)b(?-i)c$", "aBC", False),
            (r"(?i)ß", "SS", False), (r"(?i)^ß$", "ẞ", True),               # simple case folding
            (r"^[[:^digit:]]+$", "abc", True), (r"^[[:^digit:]]+$", "a1", False),
            (r"^[a||b]$", "|", True), (r"\p{Greek}$", "α\n", False),
        ]
        for pattern, text, hit in cases:
            rx = rl.compile_regex(pattern)
            self.assertIsNotNone(rx, pattern)
            self.assertEqual(rx.search(text) is not None, hit, (pattern, text))
        for pattern in ("(?U)a+", "a(?m)b$", "a(?-u)b"):           # still no faithful translation
            self.assertIsNone(rl.compile_regex(pattern), pattern)

    def test_exact(self):
        for text in ("org.mozilla.firefox", "a+b (1) [x]", "c$^d|e"):
            self.assertTrue(rl.compile_regex(rl.exact(text)).search(text))
            self.assertFalse(rl.compile_regex(rl.exact(text)).search(text + "x"))


WINDOWS = {
    1: {"id": 1, "app_id": "org.mozilla.firefox", "title": "Picture-in-Picture", "workspace_id": 10,
        "is_focused": False, "is_floating": True, "is_urgent": False, "layout": {}},
    2: {"id": 2, "app_id": "org.mozilla.firefox", "title": "GitHub — Mozilla Firefox", "workspace_id": 10,
        "is_focused": True, "is_floating": False, "is_urgent": False,
        "layout": {"pos_in_scrolling_layout": [1, 1]}},
    3: {"id": 3, "app_id": "foot", "title": "~ — foot", "workspace_id": 11,
        "is_focused": False, "is_floating": False, "is_urgent": True,
        "layout": {"pos_in_scrolling_layout": [1, 1]}},
    4: {"id": 4, "app_id": None, "title": "nameless", "workspace_id": 10,
        "is_focused": False, "is_floating": False, "is_urgent": False,
        "layout": {"pos_in_scrolling_layout": [2, 1]}},
}
WORKSPACES = {
    10: {"id": 10, "idx": 1, "name": "web", "output": "DP-1", "is_active": True, "is_focused": True,
         "active_window_id": 2},
    11: {"id": 11, "idx": 1, "name": None, "output": "HDMI-A-1", "is_active": True, "is_focused": False,
         "active_window_id": 3},
}


class Matching(unittest.TestCase):
    def setUp(self):
        self.facts = rl.window_facts(WINDOWS, WORKSPACES, set())

    def check(self, r, wid):
        return rl.check_rule(r, self.facts[wid]).status

    def test_facts(self):
        f = self.facts
        self.assertTrue(f[2]["is-active"])
        self.assertFalse(f[3]["is-active"])         # active in its workspace, but not on the focused output
        self.assertTrue(f[4]["is-active-in-column"])  # alone in its column
        self.assertIsNone(f[1]["is-active-in-column"])
        self.assertIsNone(f[1]["at-startup"])
        self.assertIsNone(rl.window_facts(WINDOWS, WORKSPACES, None)[1]["is-window-cast-target"])

    def test_match_semantics(self):
        self.assertEqual(self.check(rule(), 3), rl.YES)                                        # no match: every window
        pip = rule(match(app_id="firefox$", title="^Picture-in-Picture$"))
        self.assertEqual([self.check(pip, w) for w in (1, 2, 3)], [rl.YES, rl.NO, rl.NO])     # all matchers of a line
        either = rule(match(app_id="^foot$"), match(title="^Picture"))
        self.assertEqual([self.check(either, w) for w in (1, 2, 3)], [rl.YES, rl.NO, rl.YES])  # any line
        but = rule(match(app_id="firefox"), exclude(is_floating=True))
        self.assertEqual([self.check(but, w) for w in (1, 2)], [rl.NO, rl.YES])
        self.assertEqual(self.check(rule(match(app_id=".")), 4), rl.NO)                        # no app-id: no match
        self.assertEqual(self.check(rule(match(is_urgent=True)), 3), rl.YES)

    def test_unknown_gives_maybe_until_something_decides(self):
        startup = rule(match(at_startup=True))
        self.assertEqual(self.check(startup, 1), rl.MAYBE)
        self.assertEqual(self.check(rule(match(at_startup=True, app_id="^foot$")), 1), rl.NO)
        self.assertEqual(self.check(rule(match(app_id="^foot$"), match(at_startup=True)), 3), rl.YES)
        self.assertEqual(self.check(rule(match(app_id="foot"), exclude(at_startup=True)), 3), rl.MAYBE)

    def test_reasons(self):
        v = rl.check_rule(rule(match(app_id="^foot$")), self.facts[2])
        self.assertIn("org.mozilla.firefox does not match ^foot$", v.reason)
        v = rl.check_rule(rule(match(app_id="firefox"), exclude(is_floating=True)), self.facts[1])
        self.assertTrue(v.reason.startswith("excluded"))

    def test_merge_later_wins_and_blocks_merge_by_child(self):
        rules = [
            rule(prop("opacity", 0.9), prop("focus-ring") | {"children": [prop("off"), prop("width", 2)]}),
            rule(match(app_id="firefox"), prop("opacity", 1.0),
                 prop("focus-ring") | {"children": [prop("on"), prop("active-color", "red")]}),
            rule(match(app_id="^foot$"), prop("opacity", 0.5)),
            rule(match(at_startup=True), prop("open-on-output", "DP-1")),
        ]
        verdicts = [rl.check_rule(r, self.facts[2]) for r in rules]
        values = {m["path"]: m for m in rl.merged(rules, verdicts)}
        self.assertEqual(values["opacity"]["value"], "1.0")
        self.assertEqual(values["opacity"]["rule"], 1)
        self.assertEqual(values["opacity"]["earlier"], [0])
        self.assertEqual(values["focus-ring/state"]["value"], "on")
        self.assertEqual(values["focus-ring/width"]["value"], "2")
        self.assertEqual(values["focus-ring/active-color"]["value"], '"red"')
        self.assertTrue(values["open-on-output"]["maybe"])

    def test_open_properties_use_the_state_at_open(self):
        # Window 1 floats now, but was not floating when niri opened it.
        rules = [rule(match(app_id="firefox", is_floating=False),
                      prop("open-on-workspace", "two"), prop("opacity", 0.5))]
        now = [rl.check_rule(r, self.facts[1]) for r in rules]
        opened = [rl.check_rule(r, rl.at_open(self.facts[1])) for r in rules]
        self.assertEqual((now[0].status, opened[0].status), (rl.NO, rl.YES))
        values = {m["path"]: m for m in rl.merged(rules, now, opened)}
        self.assertEqual(values["open-on-workspace"]["value"], '"two"')
        self.assertNotIn("opacity", values)              # applies only while the rule matches now
        self.assertEqual(rl.merged(rules, now), [])      # without open verdicts: current state only
        f = rl.at_open(self.facts[2])
        self.assertEqual((f["is-focused"], f["is-active"], f["is-active-in-column"]), (False, False, True))
        self.assertIsNone(f["at-startup"])

    def test_at_startup(self):
        start = 1000.0

        def both(now, opened=None, client=None):
            clock = {"niri_start": start, "now": start + now,
                     "opened": {} if opened is None else {1: start + opened},
                     "client_start": {} if client is None else {1: start + client}}
            return rl.startup(1, clock)

        self.assertEqual(both(10), (True, True))                  # niri's first minute: every window
        self.assertEqual(both(300, opened=30), (False, True))     # seen opening
        self.assertEqual(both(300, opened=200), (False, False))
        self.assertEqual(both(300, client=200), (False, False))   # its process started too late
        self.assertEqual(both(300, client=5), (False, None))      # could have opened any time after
        self.assertEqual(both(300), (False, None))
        self.assertEqual(both(60.2), (None, None))                # too close to call
        self.assertEqual(rl.startup(1, None), (None, None))

        clock = {"niri_start": start, "now": start + 300, "opened": {1: start + 5}, "client_start": {}}
        f = rl.window_facts(WINDOWS, WORKSPACES, set(), clock)
        self.assertFalse(f[1]["at-startup"])
        self.assertTrue(rl.at_open(f[1])["at-startup"])
        self.assertIsNone(rl.at_open(f[2])["at-startup"])
        r = rule(match(at_startup=True), prop("open-on-output", "DP-1"), prop("opacity", 0.5))
        values = {m["path"] for m in rl.merged([r], [rl.check_rule(r, f[1])], [rl.check_rule(r, rl.at_open(f[1]))])}
        self.assertEqual(values, {"open-on-output"})

    def test_cast_targets(self):
        self.assertEqual(rl.cast_targets({"Casts": []}), set())
        self.assertEqual(rl.cast_targets({"Casts": [{"target": {"Window": {"id": 7}}}]}), {7})
        self.assertIsNone(rl.cast_targets(None))
        self.assertIsNone(rl.cast_targets({"Casts": [{"weird": 1}]}))


class Props(unittest.TestCase):
    def test_set_and_remove_nested(self):
        r = rule(match(app_id="x"))
        rl.set_prop(r, "popups/background-effect/blur", prop("blur", True))
        rl.set_prop(r, "focus-ring/state", {"args": ["off"], "props": {}})
        rl.set_prop(r, "focus-ring/state", {"args": ["on"], "props": {}})
        self.assertEqual(rl.get_prop(r, "focus-ring/state")["args"], ["on"])
        self.assertEqual([c["name"] for c in rl.get_prop(r, "focus-ring")["children"]], ["on"])
        self.assertEqual(rl.get_prop(r, "popups/background-effect/blur")["args"], [True])
        rl.set_prop(r, "popups/background-effect/blur", None)
        self.assertIsNone(rl.get_prop(r, "popups"))                 # emptied blocks go
        rl.set_prop(r, "focus-ring/state", None)
        self.assertEqual([c["name"] for c in r["children"]], ["match"])

    def test_summary_and_title(self):
        r = rule(match(app_id=r"^org\.gnome\.Nautilus$"), prop("open-floating", True), prop("opacity", 0.9))
        self.assertEqual(rl.summary(r), "org.gnome.Nautilus · open floating · opacity 0.9")
        self.assertEqual(rl.title(r), "org.gnome.Nautilus")
        self.assertEqual(rl.title(rule(prop("opacity", 1))), "All windows")


class Overlay(unittest.TestCase):
    """Unsaved rule edits shown by adding rules after the saved ones."""

    BASE = [rule(match(app_id="^a$"), prop("opacity", 0.9), comment="A"),
            rule(match(app_id="^b$"), prop("open-floating", True)),
            dict(rule(match(app_id="^c$"), prop("opacity", 0.5)), disabled=True)]

    def edit(self, fn):
        new = copy.deepcopy(self.BASE)
        fn(new)
        return rl.overlay(self.BASE, new)

    def test_nothing_changed(self):
        self.assertEqual(self.edit(lambda r: r[0].update(comment="renamed")), ([], ""))

    def test_new_rule_at_the_end_or_in_the_middle(self):
        added = rule(match(app_id="^d$"), prop("opacity", 0.7))
        self.assertEqual(self.edit(lambda r: r.append(added)), ([rl._body(added)], ""))
        extra, _ = self.edit(lambda r: r.insert(1, rule(prop("open-maximized", True))))
        self.assertEqual(extra, [{"args": [], "props": {}, "children": [prop("open-maximized", True)]}])
        # Rule A after it sets opacity too, so the new rule must not win there.
        self.assertEqual(self.edit(lambda r: r.insert(0, rule(prop("opacity", 1)))),
                         (None, "a later rule also sets opacity"))
        # Rule C sets opacity as well, but it is off.
        self.assertIsNotNone(self.edit(lambda r: r.insert(1, rule(prop("opacity", 1))))[0])

    def test_added_or_changed_properties_carry_the_match_lines(self):
        extra, _ = self.edit(lambda r: r[0]["children"].append(prop("clip-to-geometry", True)))
        self.assertEqual(extra, [{"args": [], "props": {}, "children": [match(app_id="^a$"),
                                                                       prop("clip-to-geometry", True)]}])
        extra, _ = self.edit(lambda r: r[0]["children"].__setitem__(1, prop("opacity", 0.8)))
        self.assertEqual(extra[0]["children"][1], prop("opacity", 0.8))

    def test_merged_blocks_add_only_the_changed_child(self):
        base = [rule(match(app_id="^a$"), {"name": "shadow", "args": [], "props": {},
                                           "children": [prop("on"), prop("softness", 30)]})]
        new = copy.deepcopy(base)
        new[0]["children"][1]["children"].append(prop("spread", 4))
        extra, _ = rl.overlay(base, new)
        self.assertEqual(extra[0]["children"][1], {"name": "shadow", "args": [], "props": {},
                                                    "children": [prop("spread", 4)]})

    def test_a_later_rule_setting_the_same_property_blocks_it(self):
        def fn(r):
            r[0]["children"].append(prop("open-floating", False))
        self.assertEqual(self.edit(fn), (None, "a later rule also sets open floating"))

    def test_turning_on_adds_the_whole_rule_and_turning_off_cannot_be_shown(self):
        extra, _ = self.edit(lambda r: r[2].pop("disabled"))
        self.assertEqual(extra, [{"args": [], "props": {}, "children": [match(app_id="^c$"), prop("opacity", 0.5)]}])
        self.assertEqual(self.edit(lambda r: r[1].update(disabled=True)), (None, "a rule was turned off"))
        self.assertEqual(self.edit(lambda r: r[2]["children"].append(prop("opacity", 1))), ([], ""))

    def test_what_only_save_can_show(self):
        self.assertEqual(self.edit(lambda r: r.pop(0)), (None, "a rule was moved or removed"))
        self.assertEqual(self.edit(lambda r: r.reverse()), (None, "rules were moved"))
        self.assertEqual(self.edit(lambda r: r[0]["children"].__setitem__(0, match(app_id="^z$"))),
                         (None, "a match or exclude line changed"))
        self.assertEqual(self.edit(lambda r: r[1]["children"].pop()), (None, "Open floating was removed from a rule"))

    def test_layer_rules(self):
        base = [rule(match(namespace="^waybar$"), prop("opacity", 0.9))]
        new = copy.deepcopy(base)
        new[0]["children"].append(prop("place-within-backdrop", True))
        extra, _ = rl.overlay(base, new, rl.LAYER)
        self.assertEqual(extra[0]["children"][-1], prop("place-within-backdrop", True))


class StubBackend(QObject):
    changed = Signal()
    stateChanged = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.state = ipc.NiriState()
        self.state.windows = copy.deepcopy(WINDOWS)
        self.state.workspaces = copy.deepcopy(WORKSPACES)
        self.connected = False
        self.notice = ""
        self._error = None

    def _edit(self, fn):
        try:
            fn()
        except ReadOnlyError as e:
            self.notice = str(e)
            return False
        return True

    def _touch(self):
        self.changed.emit()


class View(Base):
    def setUp(self):
        super().setUp()
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.load()
        self.backend = StubBackend(self.config)
        self.view = RulesView(self.backend, self.model)

    def test_list_and_detail(self):
        v = self.view
        self.assertEqual([r["title"] for r in v.rules][1], "Open the Firefox picture-in-picture player as floating by default.")
        v.select(1)
        d = v.detail
        self.assertEqual(d["where"], "config.kdl:322")
        self.assertEqual([(x["kind"], [f["key"] for f in x["fields"]]) for x in d["directives"]],
                         [("match", ["app-id", "title"])])
        self.assertEqual(d["open"][0]["path"], "open-floating")
        self.assertTrue(d["kdl"].startswith("// Open the Firefox"))
        self.assertFalse(d["last"])
        self.assertFalse(d["disabled"])
        v.select(3)
        self.assertTrue(v.detail["last"])
        self.assertTrue(v.detail["disabled"])
        self.assertTrue(v.detail["kdl"].startswith("// Example: enable rounded corners"))
        self.assertIn("\n/-window-rule {", v.detail["kdl"])
        self.assertEqual([r["disabled"] for r in v.rules], [False, False, True, True])
        v.setEnabled(2, True)
        self.assertEqual([r["disabled"] for r in v.rules], [False, False, False, True])
        self.assertEqual(v.selected, 3)

    def test_windows_and_why(self):
        v = self.view
        v.select(1)
        self.assertEqual({w["id"]: w["status"] for w in v.targets}, {1: "yes", 2: "no", 3: "no", 4: "no"})
        v.selectTarget(1)
        why = v.why
        # The rounded-corners example matches every window, but it is turned off.
        self.assertEqual([r["status"] for r in why["rules"]], ["no", "yes", "no", "no"])
        self.assertEqual(why["rules"][3]["reason"], "turned off")
        self.assertEqual([(x["label"], x["value"]) for x in why["values"]], [("Open floating", "true")])
        self.assertEqual(v.rules[1]["status"], "yes")
        v.selectTarget(1)                      # again: deselect
        self.assertFalse(v.why["has"])

    def test_template_uses_the_selected_window(self):
        v = self.view
        v.selectTarget(3)
        v.newRule("opacity")
        self.assertEqual(v.selected, 4)
        self.assertIn('// foot opacity\nwindow-rule {\n    match app-id="^foot$"\n    opacity 0.92\n}', self.text())
        self.assertEqual({w["id"]: w["status"] for w in v.targets}[3], "yes")
        v.newRule("blank")
        self.assertIn('// Rule for foot\nwindow-rule {\n    match app-id="^foot$"\n}', self.text())

    def test_property_editors(self):
        v = self.view
        v.select(1)
        v.addProp("default-floating-position")
        v.setProp("default-floating-position", {"x": 10, "y": 20, "rel": "top-left"})
        v.addProp("default-column-width")
        v.setProp("default-column-width", {"kind": "fixed", "value": "480"})
        v.addProp("opacity")
        v.setProp("opacity", "1.5")
        self.assertIn("goes from 0 to 1", v.detail["error"])
        v.setProp("opacity", "0,8")
        self.assertEqual(v.detail["error"], "")
        v.setProp("geometry-corner-radius", "8 8 0 0")
        v.setProp("focus-ring/state", "off")
        text = self.text()
        for line in ("default-floating-position x=10 y=20", "default-column-width { fixed 480; }",
                     "opacity 0.8", "geometry-corner-radius 8 8 0 0", "focus-ring { off; }"):
            self.assertIn("    " + line + "\n", text)
        kinds = {p["path"]: p["kind"] for p in v.detail["open"] + v.detail["always"]}
        self.assertEqual(kinds["default-column-width"], "size")
        self.assertEqual(kinds["default-floating-position"], "position")
        self.assertEqual(kinds["focus-ring/state"], "onoff")
        v.setProp("geometry-corner-radius", "{ broken")
        self.assertIn("Not valid KDL", v.detail["error"])
        v.removeProp("focus-ring/state")
        self.assertIsNone(rl.get_prop(self.config.rules("window-rule")[1], "focus-ring"))

    def test_matcher_editing(self):
        v = self.view
        v.select(1)
        v.setMatcher("match", 0, "title", "^PiP$")
        v.addMatcher("match", 0, "is-floating")
        self.assertIn('match app-id=r#"firefox$"# title="^PiP$" is-floating=true\n', self.text())
        v.selectTarget(2)
        v.addDirective("exclude")
        self.assertIn('    exclude app-id=r#"^org\\.mozilla\\.firefox$"#\n', self.text())
        v.removeMatcher("exclude", 0, "app-id")          # its last matcher: the line goes
        self.assertNotIn("exclude", self.text())
        v.fillFromTarget("title")
        self.assertIn('title="^GitHub — Mozilla Firefox$"', self.text())

    def test_hint_says_when_edits_reach_niri(self):
        v = self.view
        v.select(1)
        self.assertTrue(v.detail["saved"].startswith("applies when you save"))     # preview off
        self.assertTrue(self.config.enable_preview()[0])
        v._refresh()
        self.assertIn("previewed live; others apply when you save", v.detail["saved"])
        v.addProp("opacity")
        self.assertTrue(v.detail["saved"].startswith("unsaved changes are previewed live; open-time"))
        v.moveRule(-1)
        self.assertEqual(v.detail["saved"], "unsaved changes show after Save: a rule was moved or removed")

    def test_remove_and_move_keep_a_selection(self):
        v = self.view
        v.select(1)
        v.moveRule(-1)
        self.assertEqual(v.selected, 0)
        self.assertTrue(v.detail["first"])
        v.select(3)
        v.removeRule()
        self.assertEqual(v.selected, 2)
        for _ in range(3):
            v.removeRule()
        self.assertEqual(v.selected, -1)
        self.assertFalse(v.detail["has"])


LAYERS = [
    {"namespace": "waybar", "output": "DP-1", "layer": "Top", "keyboard_interactivity": "None"},
    {"namespace": "waybar", "output": "DP-1", "layer": "Top", "keyboard_interactivity": "None"},
    {"namespace": "wallpaper", "output": "DP-1", "layer": "Background", "keyboard_interactivity": "None"},
    {"namespace": "notifications", "output": "DP-1", "layer": "Overlay", "keyboard_interactivity": "None"},
]


class LayerRules(Base):
    """Layer rules: the same model with the layer schema, matched against `niri msg layers`."""

    def setUp(self):
        super().setUp()
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.load()
        self.model = RulesModel(lambda: self.config, rl.LAYER)
        self.backend = StubBackend(self.config)
        self.view = LayerRulesView(self.backend, self.model)
        self.view._layers = copy.deepcopy(LAYERS)

    def test_facts(self):
        start = 1000.0
        f = rl.layer_facts(LAYERS, {"niri_start": start, "now": start + 10})
        self.assertEqual(list(f), ["waybar@DP-1:top", "waybar@DP-1:top#2", "wallpaper@DP-1:background",
                                   "notifications@DP-1:overlay"])
        self.assertEqual(f["waybar@DP-1:top"]["layer"], "top")
        self.assertTrue(f["waybar@DP-1:top"]["at-startup"])
        self.assertIsNone(rl.layer_facts(LAYERS)["waybar@DP-1:top"]["at-startup"])
        self.assertEqual(rl.layer_facts(None), {})

    def test_matching(self):
        f = rl.layer_facts(LAYERS, {"niri_start": 0.0, "now": 300.0})
        bar, wall = f["waybar@DP-1:top"], f["wallpaper@DP-1:background"]

        def check(r, facts):
            return rl.check_rule(r, facts, rl.LAYER)

        self.assertEqual(check(rule(match(namespace="^way")), bar).status, rl.YES)
        self.assertEqual(check(rule(match(namespace="^way")), wall).status, rl.NO)
        self.assertEqual(check(rule(match(layer="top"), match(layer="overlay")), bar).status, rl.YES)
        v = check(rule(match(layer="overlay")), bar)
        self.assertEqual((v.status, v.reason), (rl.NO, "layer is top, not overlay"))
        self.assertEqual(check(rule(match(at_startup=True)), bar).status, rl.NO)
        self.assertEqual(check(rule(match(at_startup=True)), rl.layer_facts(LAYERS)["waybar@DP-1:top"]).status,
                         rl.MAYBE)
        self.assertEqual(check(rule(exclude(layer="background")), wall).reason, "excluded: layer is background")
        self.assertEqual(check(rule(prop("opacity", 0.5)), wall).reason, "applies to every surface")

    def test_summary_title_and_merge(self):
        r = rule(match(namespace="^waybar$", layer="top"), prop("opacity", 0.9),
                 {"name": "shadow", "args": [], "props": {}, "children": [prop("on"), prop("softness", 20)]})
        self.assertEqual(rl.summary(r, rl.LAYER), "waybar top layer · opacity 0.9 · shadow on")
        self.assertEqual(rl.title(r, rl.LAYER), "waybar")
        self.assertEqual(rl.title(rule(prop("opacity", 1)), rl.LAYER), "All layer surfaces")
        self.assertEqual(rl.summary(rule(prop("opacity", 1)), rl.LAYER), "all layer surfaces · opacity 1")
        v = rl.Verdict(rl.YES, "")
        self.assertEqual({m["path"] for m in rl.merged([r], [v], kind=rl.LAYER)},
                         {"opacity", "shadow/state", "shadow/softness"})

    def test_view_targets_and_why(self):
        v = self.view
        self.assertEqual([(t["title"], t["subtitle"]) for t in v.targets],
                         [("notifications", "overlay · DP-1"), ("waybar", "top · DP-1"), ("waybar", "top · DP-1"),
                          ("wallpaper", "background · DP-1")])
        self.assertEqual(v.rules, [])
        self.assertFalse(v.detail["has"])
        self.assertFalse(v.canPick)
        self.assertFalse(v.words["hasOpen"])
        v.selectTarget("waybar@DP-1:top")
        v.newRule("blur")
        self.assertIn('// Blur behind waybar\nlayer-rule {\n    match namespace="^waybar$"\n'
                      '    background-effect { blur true; }\n}', self.text())
        self.assertNotIn("window-rule {\n    match namespace", self.text())
        self.assertEqual([t["status"] for t in v.targets], ["no", "yes", "yes", "no"])
        why = v.why
        self.assertEqual((why["title"], why["subtitle"]), ("waybar", "top layer on DP-1"))
        self.assertEqual([(x["label"], x["value"]) for x in why["values"]], [("Background blur", "true")])
        d = v.detail
        self.assertEqual(d["open"], [])
        self.assertEqual([p["path"] for p in d["always"]], ["background-effect/blur"])
        self.assertNotIn("open-floating", [a["value"] for a in d["addable"]])
        self.assertEqual(self.backend.config.rules("window-rule")[0]["comment"],
                         self.config.rules("window-rule")[0]["comment"])   # window rules untouched

    def test_view_editing(self):
        v = self.view
        v.selectTarget("notifications@DP-1:overlay")
        v.newRule("blank")
        self.assertIn('// Rule for notifications\nlayer-rule {\n    match namespace="^notifications$"\n}',
                      self.text())
        v.addMatcher("match", 0, "layer")                # takes the selected surface's layer
        self.assertIn('match namespace="^notifications$" layer="overlay"\n', self.text())
        field = v.detail["directives"][0]["fields"][1]
        self.assertEqual((field["kind"], [o["value"] for o in field["options"]]),
                         ("enum", ["background", "bottom", "top", "overlay"]))
        self.assertEqual(field["status"], "yes")
        v.setMatcher("match", 0, "layer", "top")
        self.assertIn('layer="top"\n', self.text())
        v.addProp("shadow/state")
        v.addProp("block-out-from")
        v.setProp("geometry-corner-radius", "10")
        text = self.text()
        for line in ("shadow { on; }", 'block-out-from "screencast"', "geometry-corner-radius 10"):
            self.assertIn(line, text)
        v.addDirective("exclude")
        self.assertIn('    exclude namespace="^notifications$"\n', self.text())
        self.assertEqual(v.detail["error"], "")

    def test_poll_refreshes_only_on_change(self):
        v = self.view
        seen = []
        v.changed.connect(lambda: seen.append(1))
        v._fetch = lambda: copy.deepcopy(LAYERS)
        v.poll()
        self.assertEqual(seen, [])
        v._fetch = lambda: LAYERS[:1]
        v.poll()
        self.assertEqual(seen, [1])
        self.assertEqual(len(v.targets), 1)

    @unittest.skipUnless(HAVE_NIRI, "niri is not installed")
    def test_niri_accepts_every_template_and_property(self):
        for t in rl.LAYER.TEMPLATES:
            self.model.add(rl.from_template(t, "waybar", rl.LAYER))
        r = rule(match(namespace="x", layer="bottom", at_startup=False))
        self.model.add(r)
        i = len(self.config.rules("layer-rule")) - 1
        for p in rl.LAYER.PROPS:
            self.view.select(i)
            self.view.addProp(p["path"])
            self.assertEqual(self.view.detail["error"], "", p["path"])
        ok, message = self.config.validate()
        self.assertTrue(ok, message)
        self.assertTrue(self.config.save()[0])
        self.assertEqual(len(Config(self.main).rules("layer-rule")), len(rl.LAYER.TEMPLATES) + 1)


if __name__ == "__main__":
    unittest.main()
