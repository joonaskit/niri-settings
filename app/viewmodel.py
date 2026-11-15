"""Backend: the one object QML talks to. QML never touches files or niri."""

from __future__ import annotations

import os
import time

from PySide6.QtCore import (Property, QFileSystemWatcher, QObject, QTimer, Signal, Slot)

from . import ipc, niri_core
from .config import MANAGED, Config, ReadOnlyError
from .schema import layout as layout_schema

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
                         ("files", "Config files")]),
]

SAMPLE_COLUMNS = [("Terminal", 1 / 3), ("Firefox", None), ("Editor", None), ("Files", 1 / 3)]


def _show(value) -> str:
    """A config value as the user would read it in the file."""
    if value is None:
        return "not set"
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
    changed = Signal()         # config values, pending count, validation
    stateChanged = Signal()    # niri windows / workspaces
    _ipcEvent = Signal()       # from the event-stream thread

    def __init__(self, main_path: str | None = None, live: bool = True):
        super().__init__()
        self.config = Config(main_path)
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
        return len(self.config.pending)

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
        return [{"path": p.replace("/", " › "), "mine": _show(c["mine"]), "disk": _show(c["disk"])}
                for p, c in self.config.conflicts.items()]

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
