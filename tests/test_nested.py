"""Window-rule matching checked against a real niri running nested (issue #1).

Starts niri as a window inside the current Wayland session with its own config
and socket, opens foot windows with known app-ids and titles, and checks that
every window's floating, workspace and maximized state is what `rules.check_rule`
and `rules.merged` predict.

It opens windows on your desktop, so it only runs when asked:

    NIRI_SETTINGS_NESTED=1 python -m unittest tests.test_nested -v
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest

from niri_settings import ipc, niri_core
from niri_settings import rules as rl

GAPS = 16

# Each rule's effect shows over IPC: open-floating -> is_floating,
# open-on-workspace -> workspace_id, open-maximized -> the tile fills the output.
CONFIG = r"""
workspace "one"
workspace "two"
layout { gaps %d; }
hotkey-overlay { skip-at-startup; }

// Anchored app-id, literal dot.
window-rule {
    match app-id=r"^float\.test$"
    open-floating true
}

// Unanchored title, case-sensitive: "ws here" and "news" match, "WS" does not.
window-rule {
    match title=r"ws"
    open-on-workspace "two"
}

// Several match lines: either one.
window-rule {
    match app-id=r"^multi\.a$"
    match app-id=r"^multi\.b$"
    open-maximized true
}

// Exclude wins over match.
window-rule {
    match app-id=r"^ex\."
    exclude title=r"skip"
    open-floating true
}

// Anchor at the end only.
window-rule {
    match app-id=r"anchor$"
    open-on-workspace "two"
}

// Case-insensitive flag.
window-rule {
    match app-id=r"(?i)^CASE\.test$"
    open-maximized true
}

// is-floating=false next to a rule that floats some of the same windows.
window-rule {
    match app-id=r"^isf\.float$"
    open-floating true
}
window-rule {
    match app-id=r"^isf\." is-floating=false
    open-on-workspace "two"
}

// A later rule replaces what an earlier one set.
window-rule {
    match app-id=r"^later\."
    open-on-workspace "two"
}
window-rule {
    match app-id=r"^later\.back$"
    open-on-workspace "one"
}

// All matchers of one line must hold.
window-rule {
    match app-id=r"^both\." title=r"^yes$"
    open-floating true
}

// State matchers decide open-* properties as the window was when it opened:
// not focused, active or urgent, alone in its column.
window-rule {
    match app-id=r"^st\.foc$" is-focused=true
    open-on-workspace "two"
}
window-rule {
    match app-id=r"^st\.act$" is-active=false
    open-floating true
}
window-rule {
    match app-id=r"^st\.col$" is-active-in-column=true
    open-maximized true
}
window-rule {
    match app-id=r"^st\.urg$" is-urgent=false
    open-on-workspace "two"
}
""" % GAPS

# (app-id, title) of each test window.
WINDOWS = [
    ("float.test", "plain"),
    ("float.testx", "plain"),       # anchored: no match
    ("floatxtest", "plain"),        # the dot is literal: no match
    ("other.test", "ws here"),
    ("other.test", "news"),
    ("other.test", "WS"),
    ("multi.a", "plain"),
    ("multi.b", "plain"),
    ("multi.c", "plain"),
    ("ex.one", "keep"),
    ("ex.two", "skip me"),
    ("x.anchor", "plain"),
    ("anchor.x", "plain"),
    ("case.TEST", "plain"),
    ("isf.float", "plain"),
    ("isf.tiled", "plain"),
    ("later.stay", "plain"),
    ("later.back", "plain"),
    ("both.a", "yes"),
    ("both.b", "no"),
    ("st.foc", "plain"),
    ("st.act", "plain"),
    ("st.col", "plain"),
    ("st.urg", "plain"),
]

ENABLED = os.environ.get("NIRI_SETTINGS_NESTED") == "1"
CAN_RUN = bool(shutil.which("niri") and shutil.which("foot") and os.environ.get("WAYLAND_DISPLAY"))


class NestedNiri:
    """niri running as a window in the current session, with its own socket."""

    def __init__(self, config_text: str):
        self.tmp = tempfile.mkdtemp(prefix="niri-nested-")
        self.config = os.path.join(self.tmp, "config.kdl")
        with open(self.config, "w", encoding="utf-8") as fh:
            fh.write(config_text)
        self.proc = None
        self.socket = None
        self._log = None
        self._old_socket = os.environ.get("NIRI_SOCKET")

    def __enter__(self):
        env = dict(os.environ)
        env.pop("NIRI_SOCKET", None)
        self._log = open(os.path.join(self.tmp, "niri.log"), "w")
        self.proc = subprocess.Popen(["niri", "-c", self.config], env=env, stdout=self._log, stderr=self._log)
        runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        suffix = f".{self.proc.pid}.sock"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and self.socket is None:
            if self.proc.poll() is not None:
                raise RuntimeError("nested niri exited: " + self.log())
            found = [f for f in os.listdir(runtime) if f.startswith("niri.") and f.endswith(suffix)]
            if found:
                self.socket = os.path.join(runtime, found[0])
            time.sleep(0.1)
        if self.socket is None:
            self.__exit__()
            raise RuntimeError("nested niri did not open its socket: " + self.log())
        os.environ["NIRI_SOCKET"] = self.socket
        self._wait(lambda: ipc.request("Workspaces"), "IPC")
        return self

    def __exit__(self, *exc):
        if self._old_socket is None:
            os.environ.pop("NIRI_SOCKET", None)
        else:
            os.environ["NIRI_SOCKET"] = self._old_socket
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        if self._log:
            self._log.close()
        shutil.rmtree(self.tmp, True)

    def log(self) -> str:
        try:
            with open(os.path.join(self.tmp, "niri.log"), encoding="utf-8", errors="replace") as fh:
                return fh.read()[-2000:]
        except OSError:
            return ""

    def _wait(self, fn, what, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = fn()
            if result:
                return result
            time.sleep(0.1)
        raise RuntimeError(f"timed out waiting for {what}")

    def spawn(self, *argv):
        ipc.request({"Action": {"Spawn": {"command": list(argv)}}})

    def windows(self) -> list[dict]:
        return (ipc.request("Windows") or {}).get("Windows", [])

    def workspaces(self) -> list[dict]:
        return (ipc.request("Workspaces") or {}).get("Workspaces", [])

    def open_windows(self, specs, home: str):
        """Open one foot per (app-id, title), one at a time so rules see each alone.

        Each opens with `home` focused: a window sent to another workspace takes
        the focus there, and the next window would otherwise open on it.
        """
        for app_id, title in specs:
            ipc.request({"Action": {"FocusWorkspace": {"reference": {"Name": home}}}})
            before = len(self.windows())
            self.spawn("foot", f"--app-id={app_id}", f"--title={title}", "--", "sleep", "600")
            self._wait(lambda: len(self.windows()) > before, f"window {app_id}")
        # Let every window settle into its final size.
        time.sleep(1)


@unittest.skipUnless(ENABLED, "set NIRI_SETTINGS_NESTED=1 to run against a nested niri")
@unittest.skipUnless(CAN_RUN, "needs niri, foot and a Wayland session")
class AgainstRealNiri(unittest.TestCase):
    def test_predictions_match_niri(self):
        with NestedNiri(CONFIG) as niri:
            rules = [dict(n["value"], comment=n["comment"])
                     for n in niri_core.load_tree(niri.config).top_nodes(rl.NAME)]
            workspaces = {w["id"]: w for w in niri.workspaces()}
            names = {w["id"]: w["name"] for w in workspaces.values()}
            start = next(w["name"] for w in workspaces.values() if w["is_focused"])
            outputs = ipc.outputs()

            niri.open_windows(WINDOWS, start)
            windows = {w["id"]: w for w in niri.windows()}
            workspaces = {w["id"]: w for w in niri.workspaces()}
            facts = rl.window_facts(windows, workspaces, set())

            problems = []
            for wid, w in sorted(windows.items()):
                verdicts = [rl.check_rule(r, facts[wid]) for r in rules]
                maybe = [i for i, v in enumerate(verdicts) if v.status == rl.MAYBE]
                if maybe:
                    problems.append(f"{w['app_id']} / {w['title']}: rules {maybe} unknown")
                    continue
                opened = [rl.check_rule(r, rl.at_open(facts[wid])) for r in rules]
                props = {m["path"]: m["value"] for m in rl.merged(rules, verdicts, opened)}
                want = {
                    "floating": props.get("open-floating") == "true",
                    "workspace": props.get("open-on-workspace", f'"{start}"').strip('"'),
                    "maximized": props.get("open-maximized") == "true",
                }
                width = outputs[workspaces[w["workspace_id"]]["output"]]["logical"]["width"]
                got = {
                    "floating": w["is_floating"],
                    "workspace": names[w["workspace_id"]],
                    "maximized": not w["is_floating"] and w["layout"]["tile_size"][0] == width - 2 * GAPS,
                }
                if want != got:
                    diff = {k: f"predicted {want[k]}, niri {got[k]}" for k in want if want[k] != got[k]}
                    problems.append(f"{w['app_id']} / {w['title']}: {diff}")

            self.assertEqual(len(windows), len(WINDOWS), "every test window opened")
            self.assertEqual(problems, [], "\n" + "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
