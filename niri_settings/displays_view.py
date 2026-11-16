"""The Displays page's object in QML: a thin Qt layer over DisplayModel."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .config import ReadOnlyError, _load_settings, _save_settings
from .displays import TRANSFORMS, TRIAL_SECONDS, DisplayModel, snap_position


class DisplaysView(QObject):
    changed = Signal()
    trialChanged = Signal()

    def __init__(self, backend, model: DisplayModel | None = None):
        super().__init__(backend)
        self.backend = backend
        self.model = model or DisplayModel(lambda: backend.config)
        self._selected = ""
        self._left = 0
        self._cache = None
        self.model.refresh()
        backend.changed.connect(self._on_backend_changed)
        self._poll = QTimer(self, interval=3000)
        self._poll.timeout.connect(self.refresh)
        if backend.connected:
            self._poll.start()
        self._tick = QTimer(self, interval=1000)
        self._tick.timeout.connect(self._on_tick)
        self._update_block()

    def shutdown(self):
        self.model.end_trial(keep=False)

    # -- state

    def _on_backend_changed(self):
        self._cache = None
        self._update_block()
        self.changed.emit()

    def _update_block(self):
        untried = self.model.untried() if self.backend.connected or self.model.live else []
        self.backend.set_block(
            f"Try the display changes for {', '.join(untried)} before saving" if untried else "")

    @Slot()
    def refresh(self):
        if self.model.refresh():
            self._on_backend_changed()

    @Property("QVariantList", notify=changed)
    def outputs(self):
        if self._cache is None:
            self._cache = [self.model.describe(n) for n in self.model.names()]
        return self._cache

    @Property(str, notify=changed)
    def selected(self):
        names = self.model.names()
        return self._selected if self._selected in names else (names[0] if names else "")

    @Slot(str)
    def select(self, name):
        self._selected = name
        self.changed.emit()

    @Property("QVariantList", constant=True)
    def transforms(self):
        return [{"label": t, "value": t} for t in TRANSFORMS]

    @Property(bool, notify=changed)
    def needsTry(self):
        return bool(self.backend.blockReason)

    # -- edits

    def _edit(self, fn):
        try:
            fn()
        except ReadOnlyError as e:
            self.backend._notice = str(e)
            self.backend._touch(keep_notice=True)
            return
        self.backend._touch()

    @Slot(str, str)
    def setMode(self, name, value):
        self._edit(lambda: self.model.set_mode(name, value))

    @Slot(str, float)
    def setScale(self, name, value):
        self._edit(lambda: self.model.set_scale(name, value))

    @Slot(str, str)
    def setTransform(self, name, value):
        self._edit(lambda: self.model.set_transform(name, value))

    @Slot(str, str)
    def setVrr(self, name, value):
        self._edit(lambda: self.model.set_vrr(name, value))

    @Slot(str, bool)
    def setEnabled(self, name, on):
        self._edit(lambda: self.model.set_enabled(name, on))

    @Slot(str, str)
    def setBackdrop(self, name, color):
        self._edit(lambda: self.model.set_backdrop(name, color))

    @Slot(str, int, int)
    def setPosition(self, name, x, y):
        d = self.model.draft(name)
        if (d["x"], d["y"]) != (x, y):
            self._edit(lambda: self.model.set_position(name, x, y))

    @Slot(str, float, float, result="QVariant")
    def snap(self, name, x, y):
        """Where a dragged output lands, in logical pixels, and the edge that snapped."""
        boxes = {o["name"]: o for o in self.outputs}
        others = [o for n, o in boxes.items() if n != name and o["enabled"] and o["connected"]]
        sx, sy, edge = snap_position(boxes[name], x, y, others)
        return {"x": sx, "y": sy, "edge": edge}

    # -- the timed trial

    @Property(bool, notify=trialChanged)
    def trialRunning(self):
        return self.model.trial_running

    @Property(int, notify=trialChanged)
    def trialSecondsLeft(self):
        return self._left

    @Property(str, notify=trialChanged)
    def trialError(self):
        return self.model.trial_error

    @Property(int, constant=True)
    def trialSeconds(self):
        return TRIAL_SECONDS

    @Slot()
    def tryNow(self):
        # The guard gets a little longer than the countdown, so the normal
        # path is this app reverting and the guard is only the backstop.
        if self.model.start_trial(TRIAL_SECONDS + 2):
            self._left = TRIAL_SECONDS
            self._tick.start()
        self.model.refresh()
        self.backend._touch()  # clears any stale notice; our handler recomputes the rest
        self.trialChanged.emit()

    def _end(self, keep: bool):
        self._tick.stop()
        self._left = 0
        self.model.end_trial(keep)
        self.model.refresh()
        self.backend._touch()
        self.trialChanged.emit()

    @Slot()
    def keep(self):
        self._end(True)

    @Slot()
    def revertNow(self):
        self._end(False)

    def _on_tick(self):
        self._left -= 1
        if self._left <= 0 or not self.model.trial_running:
            self._end(False)
        else:
            self.trialChanged.emit()

    # -- profiles

    def _profiles(self) -> dict:
        return _load_settings().get("display_profiles", {})

    @Property("QVariantList", notify=changed)
    def profiles(self):
        return [{"name": name, "active": self.model.matches_profile(p)}
                for name, p in self._profiles().items()]

    @Slot(str)
    def saveProfile(self, name):
        name = name.strip()
        if not name:
            return
        settings = _load_settings()
        settings.setdefault("display_profiles", {})[name] = self.model.snapshot_profile()
        _save_settings(settings)
        self.changed.emit()

    @Slot(str)
    def applyProfile(self, name):
        profile = self._profiles().get(name)
        if profile:
            self._edit(lambda: self.model.apply_profile(profile))

    @Slot(str)
    def deleteProfile(self, name):
        settings = _load_settings()
        if settings.get("display_profiles", {}).pop(name, None) is not None:
            _save_settings(settings)
            self.changed.emit()
