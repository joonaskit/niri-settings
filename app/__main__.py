"""Run with: python3 -m app [--config PATH] [--offline]"""

import argparse
import glob
import os
import sys

from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .binds_view import BindsView
from .displays_view import DisplaysView
from .rules_view import RulesView
from .viewmodel import Backend

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    parser = argparse.ArgumentParser(prog="niri-settings")
    parser.add_argument("--config", help="main config file (default: $NIRI_CONFIG or ~/.config/niri/config.kdl)")
    parser.add_argument("--offline", action="store_true", help="do not talk to niri over IPC")
    args, qt_args = parser.parse_known_args()

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication([sys.argv[0], *qt_args])
    app.setApplicationName("niri settings")
    app.setDesktopFileName("niri-settings")
    for font in glob.glob(os.path.join(HERE, "fonts", "*.woff2")):
        QFontDatabase.addApplicationFont(font)
    base = QFont("Inter")
    base.setPixelSize(14)
    app.setFont(base)

    backend = Backend(args.config, live=not args.offline)
    displays = DisplaysView(backend)
    binds = BindsView(backend)
    rules = RulesView(backend)
    app.aboutToQuit.connect(displays.shutdown)
    app.aboutToQuit.connect(backend.shutdown)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("displays", displays)
    engine.rootContext().setContextProperty("binds", binds)
    engine.rootContext().setContextProperty("rules", rules)
    engine.load(os.path.join(HERE, "qml", "Main.qml"))
    if not engine.rootObjects():
        return 1
    code = app.exec()
    del engine  # tear the QML down before the backend it binds to
    return code


if __name__ == "__main__":
    sys.exit(main())
