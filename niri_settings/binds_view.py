"""The Key bindings page's object in QML: a thin Qt layer over BindsModel."""

from __future__ import annotations

import re

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot

from . import keymap as km
from .binds import (MOD_LABELS, POINTER, PROP_DEFAULTS, BindsModel, action_text, layer_label,
                    layer_name, parse_action, short_label)
from .schema import actions

COLORS = {c["id"]: c["color"] for c in actions.CATEGORIES}
_NONE = "none"   # the layer value for "no modifier"


def _layer_value(mods) -> str:
    return layer_name(mods) or _NONE


def _usage(text: str) -> str:
    """CLI usage (`--id <ID> <INDEX>`) in the form a bind takes (`id=<ID> <INDEX>`)."""
    text = text.replace("-- ", "")
    return re.sub(r"--([a-z-]+) ", r"\1=", text).strip()


class BindsView(QObject):
    changed = Signal()

    def __init__(self, backend, model: BindsModel | None = None):
        super().__init__(backend)
        self.backend = backend
        self.model = model or BindsModel(lambda: backend.config)
        self._layer = frozenset({"Mod"})
        self._key = ""          # selected key: canonical name or pointer trigger
        self._recording = ""    # "", "select" or "move"
        self._error = ""        # why the last action text was refused
        self._confirm = None    # {"text", "label", "run"}
        self._cache = {}
        self._xkb = self._xkb_names()
        backend.changed.connect(self._on_backend_changed)

    def _xkb_names(self):
        return tuple(self.backend.config.get(f"input/keyboard/xkb/{k}") for k in
                     ("layout", "variant", "model", "options"))

    def _on_backend_changed(self):
        if self._xkb_names() != self._xkb:
            self._xkb = self._xkb_names()
            self.model.reset_keymap()
        self._refresh()

    def _refresh(self):
        self._cache = {}
        self.changed.emit()

    def _cached(self, name, build):
        if name not in self._cache:
            self._cache[name] = build()
        return self._cache[name]

    def _binds(self) -> dict:
        """Effective binds of the current layer, by canonical key."""
        return self._cached("binds", lambda: {b.key: b for b in self.model.effective()
                                              if b.mods == self._layer})

    def _selected(self):
        return self._binds().get(self._key) if self._key else None

    # -- layers

    @Property("QVariantList", notify=changed)
    def layers(self):
        def build():
            found = self.model.layers()
            if self._layer not in [m for m, _ in found]:
                found.append((self._layer, 0))
            return [{"label": layer_label(m), "value": _layer_value(m), "count": n} for m, n in found]
        return self._cached("layers", build)

    @Property(str, notify=changed)
    def layer(self):
        return _layer_value(self._layer)

    @Slot(str)
    def setLayer(self, value):
        self._layer = frozenset() if value == _NONE else frozenset(value.split("+"))
        self._confirm = None
        self._error = ""
        self._refresh()

    @Slot(str)
    def toggleMod(self, mod):
        self.setLayer(_layer_value(self._layer ^ {mod}))

    # -- the map

    def _cap(self, code, width):
        if code is None:
            return {"gap": True, "w": width}
        keymap = self.model.keymap
        sym = keymap.sym(code)
        if sym is None:
            return {"gap": True, "w": width}
        cap = {"gap": False, "w": width, "code": code, "key": sym, "label": keymap.label(code),
               "short": "", "color": "", "bound": False, "modifier": "", "held": False,
               "selected": False, "aria": keymap.label(code)}
        mod = km.MODIFIER_KEYS.get(sym)
        if mod:
            held = mod in self._layer or (mod == "Mod" and "Super" in self._layer)
            cap.update(modifier=mod, held=held,
                       aria=f"{cap['label']} modifier, {'held' if held else 'not held'}")
            return cap
        bind = self._binds().get(sym)
        cap["selected"] = sym == self._key
        if bind:
            text = action_text(bind.action)
            cap.update(bound=True, short=short_label(bind.action), color=COLORS[bind.category],
                       aria=f"{bind.name}: {text}")
        else:
            cap["aria"] = f"{cap['label']}, free"
        return cap

    @Property("QVariantList", notify=changed)
    def rows(self):
        return self._cached("rows", lambda: [[self._cap(c, w) for c, w in row]
                                             for row in self.model.keymap.rows()])

    @Property("QVariantList", notify=changed)
    def navRows(self):
        return self._cached("nav", lambda: [[self._cap(c, w) for c, w in row] for row in km.NAV])

    def _on_map(self) -> set:
        return {cap["key"] for rows in (self.rows, self.navRows) for row in rows for cap in row
                if not cap["gap"]}

    @Property("QVariantList", notify=changed)
    def extras(self):
        """Binds of this layer that have no cap on the map: media keys, wheel, mouse."""
        def build():
            on_map, keymap, out = self._on_map(), self.model.keymap, []
            for key, bind in self._binds().items():
                if key in on_map:
                    continue
                missing = not bind.pointer and keymap.keycode(key) is None
                out.append({"key": key, "label": bind.name.rpartition("+")[2],
                            "short": short_label(bind.action), "color": COLORS[bind.category],
                            "selected": key == self._key, "missing": missing,
                            "aria": f"{bind.name}: {action_text(bind.action)}"})
            if self._key and self._key not in on_map and self._key not in self._binds():
                out.append({"key": self._key, "label": self._key, "short": "", "color": "",
                            "selected": True, "missing": False, "aria": f"{self._key}, free"})
            return out
        return self._cached("extras", build)

    @Property("QVariantList", constant=True)
    def categories(self):
        return actions.CATEGORIES

    @Property("QVariantList", constant=True)
    def pointerTriggers(self):
        return [{"label": p, "value": p} for p in POINTER]

    @Property(int, notify=changed)
    def count(self):
        return self._cached("count", lambda: len(self.model.effective()))

    @Slot(str)
    def selectKey(self, key):
        self._key = key
        self._confirm = None
        self._error = ""
        self._refresh()

    # -- conflicts

    @Property("QVariantList", notify=changed)
    def conflicts(self):
        def build():
            out = []
            for c in self.model.conflicts():
                winner, loser = c["winner"], c["losers"][-1]
                both = (f"<span style=\"font-family:'JetBrains Mono'\">{action_text(loser.action)}</span>"
                        f" ({loser.where}) and "
                        f"<span style=\"font-family:'JetBrains Mono'\">{action_text(winner.action)}</span>"
                        f" ({winner.where})")
                if c["kind"] == "override":
                    text = f"{c['combo']} is bound to both {both}. The later one wins."
                elif c["kind"] == "duplicate":
                    text = f"{c['combo']} is bound twice in one file: {both}. niri will not load this."
                else:
                    text = (f"{loser.name} and {winner.name} are the same shortcut while Mod is "
                            f"Super: {both}.")
                out.append({"lead": "Conflict:", "text": text, "layer": _layer_value(winner.mods),
                            "key": winner.key})
            return out
        return self._cached("conflicts", build)

    # -- the selected key

    @Property("QVariantMap", notify=changed)
    def detail(self):
        def build():
            if not self._key:
                return {"has": False}
            bind, keymap = self._selected(), self.model.keymap
            pointer = self.model.key_id(self._key)[1]
            name = bind.name if bind else self.model.combo_name(self._layer, self._key)
            combo = [MOD_LABELS.get(m, m) for m in layer_name(self._layer).split("+") if m]
            combo.append(name.rpartition("+")[2])
            action = bind.action if bind else None
            known = {a["name"]: a for a in actions.load(self.backend.config.niri_bin)}
            info = known.get(action["name"]) if action else None
            title = bind.props.get("hotkey-overlay-title", "") if bind else ""
            return {
                "has": True, "bound": bind is not None, "name": name, "combo": combo,
                "path": "binds/" + name,
                "status": bind.where if bind else "free",
                "actionText": action_text(action),
                "actionName": action["name"] if action else "",
                "description": (info["description"] if info else
                                "Not an action this niri knows" if action else
                                "Not bound. Type to search all niri actions, or pick spawn to run a command."),
                "usage": _usage(info["usage"]) if info else "",
                "isSpawn": bool(action) and action["name"] in ("spawn", "spawn-sh"),
                "title": title if isinstance(title, str) else "",
                "titleHidden": bind is not None and "hotkey-overlay-title" in bind.props and title is None,
                "repeat": bool(bind.props.get("repeat", True)) if bind else True,
                "allowWhenLocked": bool(bind.props.get("allow-when-locked", False)) if bind else False,
                "allowInhibiting": bool(bind.props.get("allow-inhibiting", True)) if bind else True,
                "cooldown": int(bind.props.get("cooldown-ms", 0) or 0) if bind else 0,
                "pointer": pointer,
                "missing": not pointer and keymap.keycode(self._key) is None,
                "overridden": [f"{action_text(b.action)} · {b.where}" for b in self.model.all()
                               if bind and not b.effective and b.ident == bind.ident],
                "error": self._error,
            }
        return self._cached("detail", build)

    @Slot(str, result="QVariantList")
    def actionMatches(self, text):
        """Actions for the picker: those matching what is typed, else related ones."""
        words = text.strip().split()
        typed = words[0].lower() if words else ""
        known = actions.load(self.backend.config.niri_bin)
        bind = self._selected()
        current = bind.action["name"] if bind and bind.action else ""
        if typed and typed != current:
            found = [a for a in known if a["name"].startswith(typed)]
            found += [a for a in known if typed in a["name"] and a not in found]
            found += [a for a in known if typed in a["description"].lower() and a not in found]
        elif current:
            cat = actions.category(current)
            stem = current.rsplit("-", 1)[0]
            found = [a for a in known if a["name"] != current and a["name"].startswith(stem)]
            found += [a for a in known if a["category"] == cat and a["name"] != current and a not in found]
        else:
            first = ["spawn", "close-window", "focus-column-left", "toggle-overview", "screenshot"]
            found = [a for a in known if a["name"] in first]
        return [{"name": a["name"], "description": a["description"],
                 "color": COLORS[a["category"]]} for a in found[:8]]

    def _edit(self, fn) -> bool:
        ok = self.backend._edit(fn)
        if ok:
            self.backend._touch()
        return ok

    def _ask(self, text, label, run):
        self._confirm = {"text": text, "label": label, "run": run}
        self._refresh()

    @Slot(str)
    def setActionText(self, text):
        """Bind the selected key to the action typed as KDL."""
        if not self._key:
            return
        bind = self._selected()
        if bind and text.strip() == action_text(bind.action):
            return
        try:
            action = parse_action(text)
        except ValueError as e:
            self._error = str(e)
            self._refresh()
            return
        self._error = ""
        layer, key = self._layer, self._key
        run = lambda: self._edit(lambda: self.model.set_action(layer, key, action))
        reason = self.model.lockout(bind, action) if bind else ""
        if reason:
            self._ask(reason, "Change anyway", run)
        else:
            run()

    @Slot(str)
    def pickAction(self, name):
        """Take an action from the picker; ones that need arguments get a starting value."""
        usage = {a["name"]: a["usage"] for a in actions.load(self.backend.config.niri_bin)}.get(name, "")
        starter = {"spawn": 'spawn "alacritty"', "spawn-sh": 'spawn-sh "notify-send hello"'}.get(name)
        if starter is None:
            needs = re.sub(r"(--[a-z-]+ <[^>]+>|\[[^\]]*\]|--)", "", usage).strip()
            starter = name + (" 1" if needs else "")
        self.setActionText(starter)

    @Slot(str, "QVariant")
    def setProp(self, name, value):
        bind = self._selected()
        if bind is None:
            return
        if name == "cooldown-ms":
            value = max(0, int(value))
        elif name in PROP_DEFAULTS:
            value = bool(value)
        self._edit(lambda: self.model.set_prop(bind, name, value))

    @Slot(bool)
    def setTitleHidden(self, hidden):
        bind = self._selected()
        if bind is not None:
            self._edit(lambda: self.model.set_prop(bind, "hotkey-overlay-title", None if hidden else ""))

    @Slot()
    def removeBind(self):
        bind = self._selected()
        if bind is None:
            return
        run = lambda: self._edit(lambda: self.model.remove(bind))
        reason = self.model.lockout(bind)
        if reason:
            self._ask(reason, "Remove anyway", run)
        else:
            run()

    # -- confirm step for binds that can lock you out

    @Property(str, notify=changed)
    def confirmText(self):
        return self._confirm["text"] if self._confirm else ""

    @Property(str, notify=changed)
    def confirmLabel(self):
        return self._confirm["label"] if self._confirm else ""

    @Slot(bool)
    def confirm(self, yes):
        pending, self._confirm = self._confirm, None
        if yes and pending:
            pending["run"]()
        self._refresh()

    # -- recording

    @Property(str, notify=changed)
    def recording(self):
        return self._recording

    @Slot(str)
    def startRecording(self, mode):
        self._recording = mode if mode in ("select", "move") else ""
        self._error = ""
        self._refresh()

    @Slot()
    def cancelRecording(self):
        self._recording = ""
        self._refresh()

    @Slot(int, int, str, result=bool)
    def recorded(self, scan_code, modifiers, text):
        """A key press while recording. Returns False while only modifiers are down."""
        if not self._recording:
            return False
        keymap = self.model.keymap
        sym = keymap.sym(scan_code)
        if sym is None and len(text) == 1 and text.isprintable() and text.strip():
            sym = keymap.canonical(text)       # no scan code (some platforms): go by the character
        if sym is None or sym in km.MODIFIER_KEYS:
            return False
        mods = set()
        flags = Qt.KeyboardModifier(modifiers)
        for flag, mod in ((Qt.KeyboardModifier.MetaModifier, "Mod"), (Qt.KeyboardModifier.ControlModifier, "Ctrl"),
                          (Qt.KeyboardModifier.ShiftModifier, "Shift"), (Qt.KeyboardModifier.AltModifier, "Alt")):
            if flags & flag:
                mods.add(mod)
        mode, self._recording = self._recording, ""
        if sym == "Escape" and not mods:
            self._refresh()
            return True
        if mode == "move":
            bind = self._selected()
            if bind is not None:
                try:
                    if not self._edit(lambda: self.model.move(bind, mods, sym)):
                        self._refresh()
                        return True
                except ValueError as e:
                    self._error = str(e)
                    self._refresh()
                    return True
        self._layer, self._key = frozenset(mods), sym
        self._refresh()
        return True
