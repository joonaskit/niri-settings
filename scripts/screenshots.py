#!/usr/bin/env python3
"""Render the README and AppStream screenshots into docs/screenshots/.

    scripts/screenshots.py            # needs a running niri for the Displays page

The app runs offscreen on a copy of tests/corpus/default/config.kdl (with a US
keyboard layout) in a throwaway HOME, so your own config, settings and snapshots
are never touched. Outputs come from niri over IPC; open windows are replaced
with sample ones so no real window titles end up in the pictures.
"""
import glob
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "screenshots")
# file name, page id, what to select first
SHOTS = [
    ("key-bindings", "binds", ("key", "t")),
    ("displays", "displays", None),
    ("window-rules", "window-rules", ("rule", 1)),
    ("layout", "layout", None),
]
SAMPLE_WINDOWS = [("firefox", "Picture-in-Picture"), ("firefox", "niri - Mozilla Firefox"),
                  ("foot", "~/code"), ("org.gnome.Nautilus", "Home")]

work = tempfile.mkdtemp(prefix="niri-settings-shots-")
os.environ["HOME"] = work
os.environ["XDG_CONFIG_HOME"] = os.path.join(work, ".config")
os.environ["XDG_STATE_HOME"] = os.path.join(work, ".local", "state")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, ROOT)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from niri_settings import ipc  # noqa: E402
from niri_settings.binds_view import BindsView  # noqa: E402
from niri_settings.displays_view import DisplaysView  # noqa: E402
from niri_settings.rules_view import LayerRulesView, RulesView  # noqa: E402
from niri_settings.viewmodel import Backend  # noqa: E402

_apply = ipc.NiriState.apply


def sample_apply(self, event):
    """Swap the real windows in niri's event stream for SAMPLE_WINDOWS."""
    if isinstance(event, dict) and "WindowsChanged" in event:
        real = event["WindowsChanged"]["windows"]
        if real:
            fake = [dict(real[i % len(real)], id=1000 + i, app_id=app_id, title=title,
                         is_focused=i == 1, is_floating=i == 0)
                    for i, (app_id, title) in enumerate(SAMPLE_WINDOWS)]
            event = {"WindowsChanged": {"windows": fake}}
    elif isinstance(event, dict) and set(event) & {"WindowOpenedOrChanged", "WindowClosed",
                                                   "WindowFocusChanged"}:
        return False
    return _apply(self, event)


def main() -> int:
    if not ipc.socket_path():
        print("screenshots: niri is not running; the Displays page would be empty", file=sys.stderr)
        return 1
    ipc.NiriState.apply = sample_apply

    cfg_dir = os.path.join(work, ".config", "niri")
    os.makedirs(cfg_dir)
    cfg = os.path.join(cfg_dir, "config.kdl")
    with open(os.path.join(ROOT, "tests", "corpus", "default", "config.kdl"), encoding="utf-8") as fh:
        text = fh.read().replace("    xkb {\n", '    xkb {\n        layout "us"\n', 1)
    with open(cfg, "w", encoding="utf-8") as fh:
        fh.write(text)

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication([sys.argv[0]])
    pkg = os.path.join(ROOT, "niri_settings")
    for font in glob.glob(os.path.join(pkg, "fonts", "*.woff2")):
        QFontDatabase.addApplicationFont(font)
    base = QFont("Inter")
    base.setPixelSize(14)
    app.setFont(base)

    backend = Backend(cfg, live=True)
    backend.skipSetup()
    views = {"displays": DisplaysView(backend), "binds": BindsView(backend),
             "rules": RulesView(backend), "layerRules": LayerRulesView(backend)}
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    for name, view in views.items():
        engine.rootContext().setContextProperty(name, view)
    engine.load(os.path.join(pkg, "qml", "Main.qml"))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    os.makedirs(OUT, exist_ok=True)
    queue = list(SHOTS)

    def step():
        if not queue:
            app.quit()
            return
        name, page, select = queue.pop(0)
        window.go(page)
        if select and select[0] == "key":
            views["binds"].selectKey(select[1])
        elif select and select[0] == "rule":
            views["rules"].select(select[1])

        def grab():
            path = os.path.join(OUT, name + ".png")
            window.grabWindow().save(path)
            print(os.path.relpath(path, ROOT))
            QTimer.singleShot(100, step)
        QTimer.singleShot(1200, grab)  # let the page load and IPC replies arrive

    QTimer.singleShot(1500, step)
    app.exec()
    del engine
    for view in views.values():
        getattr(view, "shutdown", lambda: None)()
    backend.shutdown()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(work, ignore_errors=True)
