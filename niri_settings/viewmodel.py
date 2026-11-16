"""Backend: the one object QML talks to. QML never touches files or niri."""

from __future__ import annotations

import os
import shlex
import time

from PySide6.QtCore import (Property, QFileSystemWatcher, QObject, QTimer, Signal, Slot)

from . import ipc, niri_core
from .config import FILE, MANAGED, RULES, Config, ReadOnlyError
from .schema import layout as layout_schema
from .schema import pages as page_schema

# (group, [(page id, title)]) in sidebar order, from the concept screens.
SECTIONS = [
    ("Desktop", [("displays", "Displays"), ("layout", "Layout"),
                 ("appearance", "Appearance & blur"), ("animations", "Animations"),
                 ("workspaces", "Workspaces"), ("overview", "Overview & Alt-Tab")]),
    ("Input", [("keyboard", "Keyboard"), ("pointer", "Touchpad & mouse"),
               ("tablet", "Tablet & touch"), ("binds", "Key bindings"),
               ("gestures", "Gestures & hot corners")]),
    ("Rules & session", [("window-rules", "Window rules"), ("layer-rules", "Layer rules"),
                         ("startup", "Startup apps"), ("environment", "Environment"),
                         ("misc", "Miscellaneous"), ("files", "Config files")]),
]

SAMPLE_COLUMNS = [("Terminal", 1 / 3), ("Firefox", None), ("Editor", None), ("Files", 1 / 3)]


def _show(value) -> str:
    """A config value as the user would read it in the file."""
    if value is None:
        return "not set"
    if isinstance(value, list):
        return f"{len(value)} rule{'s' if len(value) != 1 else ''}"
    if value is True:
        return "on"
    if isinstance(value, dict):
        return niri_core.format_node("x", value)[2:]
    return niri_core.format_value(value)


def _when(stamp: float) -> str:
    then, now = time.localtime(stamp), time.localtime()
    clock = time.strftime("%H:%M", then)
    if then[:3] == now[:3]:
        return "today " + clock
    if time.time() - stamp < 6 * 86400:
        return time.strftime("%a ", then) + clock
    return time.strftime("%-d %b ", then) + clock


def _fraction_label(p: float) -> str:
    for den in (2, 3, 4, 5, 6, 8):
        for num in range(1, den):
            if abs(p - num / den) < 0.002:
                return f"{num}/{den}"
    return f"{round(p * 100)}%"


class Backend(QObject):
    sourceRequested = Signal(str, int)   # open Config files at file, line
    changed = Signal()         # config values, pending count, validation
    stateChanged = Signal()    # niri windows / workspaces
    _ipcEvent = Signal()       # from the event-stream thread

    def __init__(self, main_path: str | None = None, live: bool = True, setup: bool = False):
        super().__init__()
        self.config = Config(main_path)
        self._setup = setup or not self.config.setup_done
        self._revision = 0
        self._valid = (True, "")
        self._error = None
        self._notice = ""
        self._block = ""
        self._version = ipc.version() if live else None
        self._outputs = ipc.outputs() if self._version else {}
        self.state = ipc.NiriState()
        self._stream = None

        self._validate_timer = QTimer(self, singleShot=True, interval=250)
        self._validate_timer.timeout.connect(self._run_validation)
        self._preview_timer = QTimer(self, singleShot=True, interval=150)
        self._preview_timer.timeout.connect(self._run_preview)
        self._state_timer = QTimer(self, singleShot=True, interval=50)
        self._state_timer.timeout.connect(self.stateChanged)
        self._ipcEvent.connect(self._state_timer.start)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._watcher.directoryChanged.connect(self._on_file_changed)
        self._rewatch()

        if self._version:
            self._stream = ipc.EventStream(self.state, self._ipcEvent.emit)
            self._stream.start()
        self._run_validation()

    # -- lifecycle

    def shutdown(self):
        """Leave niri as the saved config says: empty the preview file."""
        self.config.clear_preview()
        if self._stream:
            self._stream.stop()

    def _rewatch(self):
        if self._watcher.files():
            self._watcher.removePaths(self._watcher.files())
        files = [f for f in self.config.tree.files()
                 if f != self.config.preview_file and os.path.exists(f)]
        if files:
            self._watcher.addPaths(files)
        folder = os.path.dirname(self.config.main)
        if folder not in self._watcher.directories():
            self._watcher.addPath(folder)

    def _on_file_changed(self, _path: str):
        if not self.config.changed_on_disk():
            return
        had_pending = bool(self.config.pending)
        try:
            conflicts = self.config.rebase()
        except niri_core.KdlError as e:
            # Probably a half-written file. Keep the current view; the next
            # change event tries again, and Save stays blocked meanwhile.
            self._notice = f"The file on disk does not parse yet ({os.path.basename(e.file)}:{e.line})"
        else:
            if conflicts:
                self._notice = ""
            elif had_pending:
                self._notice = "Reloaded an outside edit; your unsaved changes were kept"
            else:
                self._notice = "Reloaded after an outside edit"
        self._rewatch()
        self._touch(keep_notice=True)

    def _touch(self, keep_notice: bool = False):
        if not keep_notice:
            self._notice = ""
        self._revision += 1
        self.changed.emit()
        self._validate_timer.start()
        self._preview_timer.start()

    def _set_valid(self, valid: tuple[bool, str]):
        error = None if valid[0] else self.config.last_error
        if valid != self._valid or error != self._error:
            self._valid, self._error = valid, error
            self.changed.emit()

    def _run_validation(self):
        self._set_valid(self.config.validate() if self.config.pending else (True, ""))

    def _run_preview(self):
        ok, message = self.config.write_preview()
        if not ok and self._valid[0]:
            self._set_valid((False, message))

    def _edit(self, fn) -> bool:
        """Run a config edit; a refused one becomes a notice instead of a crash."""
        try:
            fn()
        except ReadOnlyError as e:
            self._notice = str(e)
            self._touch(keep_notice=True)
            return False
        return True

    # -- shell

    @Property(int, notify=changed)
    def revision(self):
        return self._revision

    @Property("QVariantList", constant=True)
    def sections(self):
        return [{"group": g, "pages": [{"id": i, "title": t} for i, t in pages]}
                for g, pages in SECTIONS]

    @Property(bool, constant=True)
    def connected(self):
        return self._version is not None

    @Property(str, constant=True)
    def statusText(self):
        if self._version:
            return f"niri {self._version} · connected via IPC"
        return "niri not running · editing files only"

    @Property(int, notify=changed)
    def pendingCount(self):
        return self.config.pending_count()

    @Property(bool, notify=changed)
    def valid(self):
        return self._valid[0]

    @Property(str, notify=changed)
    def validationText(self):
        return self._valid[1]

    @Property(str, notify=changed)
    def notice(self):
        return self._notice

    @Property(str, notify=changed)
    def errorSummary(self):
        """One line: what niri rejected and where."""
        e = self._error
        if not e:
            return self._valid[1].splitlines()[0] if self._valid[1] else ""
        where = f" · {os.path.basename(e['file'])}:{e['line']}" if e["file"] and e["line"] else ""
        return (e["summary"] or "niri rejected the config") + where

    @Slot(str, str, result=str)
    def errorFor(self, path, kind):
        """The validation error if it belongs to this setting, else ""."""
        e = self._error
        if not e or not e["path"]:
            return ""
        at = e["path"]
        owns = at == path
        if kind in ("struts", "widths", "bind"):
            owns = owns or at.startswith(path + "/")
        elif kind == "onoff":
            owns = at in (path + "/on", path + "/off")
        return (e["summary"] or "niri rejected this value") if owns else ""

    @Property("QVariantList", notify=changed)
    def conflicts(self):
        out = []
        for p, c in self.config.conflicts.items():
            if p.startswith(FILE):
                out.append({"path": os.path.basename(p[len(FILE):]) + " (edited as text)",
                            "mine": "your text", "disk": "the file's new text"})
            else:
                out.append({"path": p.replace("/", " › ") if p not in RULES else p + "s",
                            "mine": _show(c["mine"]), "disk": _show(c["disk"])})
        return out

    @Slot(bool)
    def resolveConflicts(self, keep_mine):
        self._edit(lambda: self.config.resolve_conflicts(keep_mine))
        self._touch()

    @Property(str, notify=changed)
    def targetText(self):
        home = os.path.expanduser("~")
        cfg = self.config
        fallback = cfg.managed_file if cfg.write_mode == MANAGED else cfg.main
        files = cfg.tree.dirty_files() or [fallback]
        names = [("~" + f[len(home):]) if f.startswith(home) else f for f in files]
        return "writes to " + ", ".join(names) + ", comments kept"

    @Property(bool, notify=changed)
    def previewEnabled(self):
        return self.config.preview_enabled

    @Property(str, notify=changed)
    def diffText(self):
        return self.config.diff()

    def _finish(self, ok: bool, message: str):
        """Report the outcome of a save-like action."""
        if not ok and self.config.last_error:
            self._set_valid((False, message))  # niri rejected it: show as validation error
            self._notice = ""
        else:
            self._notice = message
        self._rewatch()
        self._touch(keep_notice=True)

    @Property(str, notify=changed)
    def blockReason(self):
        """Why Save is refused right now (e.g. untried display changes), or ""."""
        return self._block

    def set_block(self, reason: str):
        if reason != self._block:
            self._block = reason
            self.changed.emit()

    @Slot()
    def save(self):
        if self._block:
            self._notice = self._block
            self.changed.emit()
            return
        self._finish(*self.config.save())

    @Slot()
    def revert(self):
        try:
            self.config.reload()
        except niri_core.KdlError:
            self.config.revert()
        self._rewatch()
        self._touch()

    @Slot()
    def enablePreview(self):
        self._finish(*self.config.enable_preview())

    # -- first run

    @Property(bool, notify=changed)
    def setupNeeded(self):
        return self._setup

    @Property("QVariantMap", notify=changed)
    def setupInfo(self):
        cfg = self.config
        home = os.path.expanduser("~")
        mode, reason = cfg.suggested_mode()
        exists = os.path.exists(cfg.main)
        files = [f for f in cfg.tree.files()
                 if f not in (cfg.preview_file, cfg.managed_file) and cfg.tree.exists(f)]
        return {
            "path": ("~" + cfg.main[len(home):]) if cfg.main.startswith(home) else cfg.main,
            "exists": exists,
            "files": len(files),
            "defaultSource": cfg.default_source() or "",
            "suggested": cfg.write_mode if cfg.managed_enabled else mode,
            "reason": reason,
            "managedIncluded": cfg.managed_enabled,
            "previewIncluded": cfg.preview_enabled,
        }

    @Slot(str, bool, result=str)
    def finishSetup(self, mode, preview):
        """Apply the first-run choices. Returns an error, or "" when done."""
        ok, message = self.config.first_run(mode, preview)
        if not ok:
            return message
        self._setup = False
        self._notice = "Set up for " + ("managed" if mode == MANAGED else "in-place") + " mode"
        self._rewatch()
        self._touch(keep_notice=True)
        return ""

    @Slot(result=str)
    def skipSetup(self):
        """Keep the current write mode and no live preview. A missing config.kdl
        is still created from niri's default, so a later save cannot leave
        niri with only the saved settings."""
        ok, message = self.config.first_run(self.config.write_mode, False)
        if not ok:
            return message
        self._setup = False
        self._rewatch()
        self._touch()
        return ""

    # -- write mode, files, snapshots

    @Property(str, notify=changed)
    def writeMode(self):
        return self.config.write_mode

    @Slot(str)
    def setWriteMode(self, mode):
        self._finish(*self.config.set_write_mode(mode))

    @Property("QVariantList", notify=changed)
    def includeTree(self):
        cfg, tree = self.config, self.config.tree
        dirty = set(tree.dirty_files())
        out = []
        for f in tree.files():
            tag = ""
            if f == cfg.managed_file:
                tag = "managed"
            elif f == cfg.preview_file:
                tag = "preview"
            elif not tree.exists(f):
                tag = "(optional, missing)"
            out.append({"path": f, "name": os.path.relpath(f, os.path.dirname(cfg.main)),
                        "depth": tree.depth(f), "dirty": f in dirty, "tag": tag,
                        "missing": not tree.exists(f) and f not in dirty})
        return out

    @Slot(str, result="QVariantList")
    def fileLines(self, path):
        try:
            return self.config.file_lines(path)
        except KeyError:
            return []

    @Property("QVariantList", notify=changed)
    def snapshots(self):
        return [{"id": s["id"], "name": s["name"],
                 "title": s["name"] or "Auto · " + (s["reason"] or "before save"),
                 "when": _when(s["time"]), "files": ", ".join(s["files"])}
                for s in self.config.snapshots()]

    @Slot(str)
    def restoreSnapshot(self, snap_id):
        self._finish(*self.config.restore_snapshot(snap_id))

    @Slot(str, str)
    def nameSnapshot(self, snap_id, name):
        self.config.name_snapshot(snap_id, name)
        self.changed.emit()

    # -- settings

    @Property("QVariantList", constant=True)
    def layoutSettings(self):
        return layout_schema.SETTINGS

    @Slot(str, result="QVariant")
    def value(self, path):
        return self.config.get(path)

    @Slot(str, "QVariant")
    def setValue(self, path, value):
        if isinstance(value, float) and value == int(value):
            value = int(value)
        if self.config.get(path) == value:
            return
        if self._edit(lambda: self.config.set(path, value)):
            self._touch()

    @Slot(str, bool)
    def setFlag(self, path, on):
        if self._edit(lambda: self.config.set(path, True) if on else self.config.remove(path)):
            self._touch()

    @Slot(str, bool, result=bool)
    def isOn(self, path, default):
        """Whether a section with on/off flags (focus-ring, border) is enabled."""
        cfg = self.config
        if cfg.get(path + "/off") is not None:
            # A later `on` beats an earlier `off`, and the other way round.
            on, off = cfg.source(path + "/on"), cfg.source(path + "/off")
            order = cfg.tree.files()
            return bool(on) and ((order.index(on["file"]), on["line"])
                                 > (order.index(off["file"]), off["line"]))
        if cfg.get(path + "/on") is not None:
            return True
        if cfg.get(path) is not None and path == "layout/border":
            # Historic special case: a border section in the main file enables it.
            return cfg.source(path)["file"] == cfg.main
        return default

    @Slot(str, bool, bool)
    def setOn(self, path, on, default):
        cfg = self.config

        def apply():
            cfg.remove(path + "/off")
            cfg.remove(path + "/on")
            if self.isOn(path, default) != on:
                cfg.set(path + ("/on" if on else "/off"), True)
        if self._edit(apply):
            self._touch()

    @Slot(str, result=str)
    def hint(self, path):
        """`section › key · file:line`, plus any per-output override."""
        text = path.replace("/", " › ")
        src = self.config.source(path)
        if not src:
            return text + " · not set, niri default"
        where = f"{os.path.basename(src['file'])}:{src['line']}"
        over = src["overridden_by"]
        return f"{text} · {where}" + (f" · overridden by {', '.join(over)}" if over else "")

    @Slot(result="QVariantList")
    def layoutOverrides(self):
        tree = self.config.tree
        return [p for p in tree.list("") if p.startswith(("output[", "workspace["))
                and tree.get(p + "/layout") is not None]

    # default-column-width and its presets

    @Slot(str, result="QVariantList")
    def widthPresets(self, presets_path):
        tree = self.config.tree
        paths = tree.list(presets_path)
        if not paths:
            return [{"label": _fraction_label(p), "kind": "proportion", "value": p}
                    for p in (0.33333, 0.5, 0.66667)]
        out = []
        for p in paths:
            kind = p.rsplit("/", 1)[1].split("#")[0]
            value = tree.get(p)
            label = _fraction_label(value) if kind == "proportion" else f"{value:g} px"
            out.append({"label": label, "kind": kind, "value": value})
        return out

    @Slot(str, result="QVariant")
    def widthCurrent(self, path):
        for kind in ("proportion", "fixed"):
            v = self.config.get(f"{path}/{kind}")
            if v is not None:
                return {"kind": kind, "value": v}
        return {"kind": "", "value": 0}

    @Slot(str, str, "QVariant")
    def setWidth(self, path, kind, value):
        other = "fixed" if kind == "proportion" else "proportion"

        def apply():
            if self.config.get(f"{path}/{other}") is not None:
                if self.config.write_mode == MANAGED:
                    self.config.tree.copy_node(path, self.config.managed_file)
                self.config.remove(f"{path}/{other}")
            self.config.set(f"{path}/{kind}", value)
        if self._edit(apply):
            self._touch()

    # -- layout preview

    @Property("QVariantList", notify=stateChanged)
    def previewColumns(self):
        """Columns of the focused workspace: width as a share of the output."""
        cols = []
        if self._stream:
            with self._stream.lock:
                ws = self.state.focused_workspace()
                raw = self.state.columns(ws["id"]) if ws else []
                out_w = ((self._outputs.get(ws["output"]) or {}).get("logical") or {}).get("width") if ws else None
                gaps = float(self.config.get("layout/gaps", 16) or 0)
                for col in raw:
                    sizes = [(w.get("layout") or {}).get("tile_size") or [0, 0] for w in col]
                    width = max(s[0] for s in sizes)
                    total_h = sum(s[1] + gaps for s in sizes) or 1
                    share = (width + gaps) / max(1.0, (out_w or 1920) - gaps)
                    cols.append({
                        "share": min(1.0, share),
                        "focused": any(w.get("is_focused") for w in col),
                        "rows": [{"label": w.get("title") or w.get("app_id") or "",
                                  "share": (s[1] + gaps) / total_h,
                                  "focused": bool(w.get("is_focused"))}
                                 for w, s in zip(col, sizes)],
                    })
        if cols:
            if not any(c["focused"] for c in cols):
                cols[0]["focused"] = True
            return cols
        # No niri, or an empty workspace: a sample that follows the settings.
        current = self.config.get("layout/default-column-width/proportion", 0.5)
        return [{"share": share or current, "focused": i == 1,
                 "rows": [{"label": name, "share": 1.0, "focused": i == 1}]}
                for i, (name, share) in enumerate(SAMPLE_COLUMNS)]

    @Property(bool, notify=stateChanged)
    def previewIsLive(self):
        return self._stream is not None and bool(self.state.windows)

    # -- schema-driven pages

    @Property("QVariantMap", constant=True)
    def pages(self):
        return page_schema.PAGES

    @Property("QVariantList", constant=True)
    def coverage(self):
        titles = {i: t for _, pages in SECTIONS for i, t in pages}
        return [{"section": s, "page": p, "pageTitle": titles.get(p, ""), "note": note}
                for s, p, note in page_schema.COVERAGE]

    @Slot(str, result="QVariantList")
    def searchSettings(self, query):
        """Settings of every schema page whose label, path or hint matches."""
        q = query.strip().lower()
        titles = {i: t for _, pages in SECTIONS for i, t in pages}
        out = []
        if not q:
            return out
        for page_id, page in page_schema.PAGES.items():
            for group in page["groups"]:
                for s in group["settings"]:
                    text = " ".join([s["label"], s["path"], s.get("hint", "")]).lower()
                    if all(word in text for word in q.split()):
                        out.append({"page": page_id, "pageTitle": titles.get(page_id, page["title"]),
                                    "setting": s})
        return out

    @Slot(str, result=str)
    def pageOf(self, path):
        return page_schema.page_for(path) or ""

    def _apply_edit(self, fn):
        if self._edit(fn):
            self._touch()

    @Slot(str)
    def resetValue(self, path):
        """Remove a setting so niri's default applies."""
        if self.config.get(path) is not None:
            self._apply_edit(lambda: self.config.remove(path))

    @Slot(str, "QVariant")
    def setDecimal(self, path, value):
        try:
            number = float(str(value).strip().replace(",", "."))
        except ValueError:
            return
        if self.config.get(path) != number:
            self._apply_edit(lambda: self.config.set(path, number))

    @Slot(str, str)
    def setText(self, path, text):
        """A string setting; empty text removes it."""
        if text == "":
            self.resetValue(path)
        elif self.config.get(path) != text:
            self._apply_edit(lambda: self.config.set(path, text))

    @Slot(str, str, result=str)
    def setNumbers(self, path, text):
        """Several numbers as one node, e.g. a calibration matrix. Returns an error or ""."""
        if not text.strip():
            self.resetValue(path)
            return ""
        try:
            numbers = [float(x) for x in text.replace(",", " ").split()]
        except ValueError:
            return "Type numbers separated by spaces"
        value = {"args": numbers, "props": {}}
        if self.config.get(path) != value:
            self._apply_edit(lambda: self.config.set(path, value))
        return ""

    @Slot(str, bool, bool)
    def setBool(self, path, on, default):
        """A node that takes true / false; niri's default removes it."""
        if on == default:
            self.resetValue(path)
        elif self.config.get(path) is not on:
            # Written as `name true`: a bare `name` is a flag, which these nodes reject.
            self._apply_edit(lambda: self.config.set(path, {"args": [on], "props": {}}))

    @Slot(str, bool, result=bool)
    def isEnabled(self, path, default):
        """A section that is on unless it has an `off` flag."""
        if self.config.get(path + "/off") is not None:
            return False
        return default or self.config.get(path) is not None

    @Slot(str, bool)
    def setEnabled(self, path, on):
        if on:
            self.resetValue(path + "/off")
        elif self.config.get(path + "/off") is None:
            self._apply_edit(lambda: self.config.set(path + "/off", True))

    @Slot(str, int, int)
    def setXY(self, path, x, y):
        value = {"args": [], "props": {"x": int(x), "y": int(y)}}
        if self.config.get(path) != value:
            self._apply_edit(lambda: self.config.set(path, value))

    @Slot(str, result="QVariantList")
    def xy(self, path):
        v = self.config.get(path)
        props = v.get("props", {}) if isinstance(v, dict) else {}
        return [props.get("x"), props.get("y")] if props else []

    @Slot(str, result="QVariant")
    def text(self, path):
        """A value as it is written after the node name, for text fields."""
        v = self.config.get(path)
        if v is None or v is True:
            return ""
        if isinstance(v, dict):
            return " ".join(niri_core.format_value(a) for a in v.get("args", []))
        return str(v) if isinstance(v, str) else niri_core.format_value(v)

    # animations

    @Slot(str, result="QVariantMap")
    def animation(self, path):
        cfg = self.config
        spring = cfg.get(path + "/spring")
        props = spring.get("props", {}) if isinstance(spring, dict) else {}
        if cfg.get(path + "/off") is not None:
            mode = "off"
        elif spring is not None:
            mode = "spring"
        elif cfg.get(path + "/duration-ms") is not None or cfg.get(path + "/curve") is not None:
            mode = "easing"
        else:
            mode = "default"
        curve = cfg.get(path + "/curve")
        return {"mode": mode, "damping": props.get("damping-ratio", 1.0), "stiffness": props.get("stiffness", 800),
                "epsilon": props.get("epsilon", 0.0001), "duration": cfg.get(path + "/duration-ms", 250),
                "curve": curve if isinstance(curve, str) else "ease-out-cubic"}

    @Slot(str, str)
    def setAnimationMode(self, path, mode):
        cfg = self.config
        current = self.animation(path)
        if mode == current["mode"]:
            return

        def apply():
            for leaf in ("off", "spring", "duration-ms", "curve"):
                if cfg.get(f"{path}/{leaf}") is not None and not (mode == "off" and leaf != "off"):
                    cfg.remove(f"{path}/{leaf}")
            if mode == "off":
                cfg.set(path + "/off", True)
            elif mode == "spring":
                cfg.set(path + "/spring", {"args": [], "props": {
                    "damping-ratio": 1.0, "stiffness": 800, "epsilon": 0.0001}})
            elif mode == "easing":
                cfg.set(path + "/duration-ms", 250)
                cfg.set(path + "/curve", "ease-out-cubic")
        self._apply_edit(apply)

    @Slot(str, "QVariant", "QVariant", "QVariant")
    def setSpring(self, path, damping, stiffness, epsilon):
        try:
            value = {"args": [], "props": {"damping-ratio": float(str(damping).replace(",", ".")),
                                           "stiffness": int(float(stiffness)),
                                           "epsilon": float(str(epsilon).replace(",", "."))}}
        except ValueError:
            return
        if self.config.get(path + "/spring") != value:
            self._apply_edit(lambda: self.config.set(path + "/spring", value))

    # named workspaces

    @Property("QVariantList", notify=changed)
    def workspaces(self):
        out = []
        for p in self.config.tree.list(""):
            if not p.startswith("workspace["):
                continue
            name = p[len("workspace["):-1]
            src = self.config.source(p)
            output = self.config.get(p + "/open-on-output")
            out.append({"name": name, "output": output if isinstance(output, str) else "",
                        "where": f"{os.path.basename(src['file'])}:{src['line']}" if src else ""})
        return out

    @Slot(str, result=str)
    def addWorkspace(self, name):
        name = name.strip()
        if not name:
            return "Type a name"
        if any(w["name"] == name for w in self.workspaces):
            return f"There is already a workspace called {name}"
        self._apply_edit(lambda: self.config.set(f"workspace[{name}]", True))
        return ""

    @Slot(str)
    def removeWorkspace(self, name):
        self._apply_edit(lambda: self.config.remove(f"workspace[{name}]"))

    @Slot(str, str)
    def setWorkspaceOutput(self, name, output):
        path = f"workspace[{name}]/open-on-output"
        if output.strip():
            if self.config.get(path) != output.strip():
                self._apply_edit(lambda: self.config.set(path, output.strip()))
        else:
            self.resetValue(path)

    @Property("QVariantList", notify=changed)
    def outputNames(self):
        names = list(self._outputs)
        names += [p[len("output["):-1] for p in self.config.tree.list("") if p.startswith("output[")]
        return sorted(set(names))

    # startup commands

    @Slot(str, result="QVariantList")
    def startupList(self, kind):
        out = []
        for i, entry in enumerate(self.config.rules(kind)):
            args = [str(a) for a in entry.get("args", [])]
            text = args[0] if kind == "spawn-sh-at-startup" and args else shlex.join(args)
            out.append({"index": i, "text": text, "disabled": bool(entry.get("disabled"))})
        return out

    @Slot(str, int, str, result=str)
    def setStartup(self, kind, index, text):
        """Add (index -1) or change one startup command. Returns an error or ""."""
        text = text.strip()
        if not text:
            return "Type a command"
        if kind == "spawn-sh-at-startup":
            args = [text]
        else:
            try:
                args = shlex.split(text)
            except ValueError as e:
                return f"Check the quotes: {e}"
        entries = self.config.rules(kind)
        entry = {"args": args, "props": {}, "comment": ""}
        if 0 <= index < len(entries):
            if entries[index].get("args") == args:
                return ""
            entry["comment"] = entries[index].get("comment", "")
            if entries[index].get("disabled"):
                entry["disabled"] = True
            entries[index] = entry
        else:
            entries.append(entry)
        self._apply_edit(lambda: self.config.set_rules(kind, entries))
        return ""

    @Slot(str, int, bool)
    def setStartupEnabled(self, kind, index, on):
        """Turn a startup command on, or off (commented out with /-)."""
        entries = self.config.rules(kind)
        if 0 <= index < len(entries) and bool(on) == bool(entries[index].get("disabled")):
            if on:
                entries[index].pop("disabled")
            else:
                entries[index]["disabled"] = True
            self._apply_edit(lambda: self.config.set_rules(kind, entries))

    @Slot(str, int)
    def removeStartup(self, kind, index):
        entries = self.config.rules(kind)
        if 0 <= index < len(entries):
            del entries[index]
            self._apply_edit(lambda: self.config.set_rules(kind, entries))

    # environment

    @Property("QVariantList", notify=changed)
    def environment(self):
        found: dict[str, dict] = {}
        for e in self.config.tree.entries("environment"):
            args = e["value"]["args"]
            value = args[0] if args else None
            found[e["name"]] = {"name": e["name"], "value": "" if value is None else str(value),
                                "unset": value is None,
                                "where": f"{os.path.basename(e['file'])}:{e['line']}"}
        return list(found.values())

    @Slot(str, str, result=str)
    def setEnv(self, name, value):
        name = name.strip()
        if not name or any(c in name for c in " =/\\"):
            return "A variable name has no spaces, = or slashes"
        if self.config.get(f"environment/{name}") != value:
            self._apply_edit(lambda: self.config.set(f"environment/{name}", value))
        return ""

    @Slot(str)
    def removeEnv(self, name):
        self._apply_edit(lambda: self.config.remove(f"environment/{name}"))

    # -- source editor and links between settings and source

    @Slot(str)
    def showSource(self, path):
        """Open Config files where a setting is written."""
        src = self.config.source(path)
        if src:
            self.sourceRequested.emit(src["file"], src["line"])

    @Slot(str, result=str)
    def fileText(self, path):
        try:
            return self.config.tree.render(path)
        except KeyError:
            return ""

    @Slot(str, result=bool)
    def fileWritable(self, path):
        return self.config._writable(os.path.normpath(path))

    @Slot(str, str, result="QVariantMap")
    def setFileText(self, path, text):
        """Take the editor's text as an unsaved change. Returns {error, line}."""
        try:
            self.config.set_text(path, text)
        except niri_core.KdlError as e:
            return {"error": e.message, "line": e.line}
        except ReadOnlyError as e:
            return {"error": str(e), "line": 0}
        self._rewatch()
        self._touch()
        return {"error": "", "line": 0}

    @Slot(str, int, result="QVariantMap")
    def pathAt(self, path, line):
        """The setting on a line of a file, and the page that edits it."""
        try:
            at = self.config.tree.path_at(path, line)
        except (KeyError, niri_core.KdlError):
            at = None
        page = page_schema.page_for(at) if at else None
        titles = {i: t for _, pages in SECTIONS for i, t in pages}
        return {"path": (at or "").replace("/", " › "), "page": page or "",
                "pageTitle": titles.get(page, "") if page else ""}
