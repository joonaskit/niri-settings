"""Key bindings: the `binds {}` section as a model, without Qt.

A bind is addressed by its config path `binds/<name as written>`. Two binds
are the same key when their modifiers and key match after normalising the
spelling (`Mod+Shift+H`, `shift+mod+h`), which is how niri compares them.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field

from . import niri_core
from .keymap import Keymap
from .schema import actions

MOD_ORDER = ["Mod", "Super", "Ctrl", "Shift", "Alt", "ISO_Level3_Shift", "ISO_Level5_Shift"]
MOD_LABELS = {"ISO_Level3_Shift": "AltGr", "ISO_Level5_Shift": "Lv5"}
_MOD_ALIASES = {
    "mod": "Mod", "super": "Super", "win": "Super", "ctrl": "Ctrl", "control": "Ctrl",
    "shift": "Shift", "alt": "Alt", "iso_level3_shift": "ISO_Level3_Shift",
    "mod5": "ISO_Level3_Shift", "iso_level5_shift": "ISO_Level5_Shift",
}

# Triggers that are not keyboard keys.
POINTER = ["WheelScrollDown", "WheelScrollUp", "WheelScrollLeft", "WheelScrollRight",
           "TouchpadScrollDown", "TouchpadScrollUp", "TouchpadScrollLeft", "TouchpadScrollRight",
           "MouseLeft", "MouseRight", "MouseMiddle", "MouseBack", "MouseForward"]
_POINTER = {p.lower(): p for p in POINTER}

# Bind properties and the value niri uses when one is left out.
PROP_DEFAULTS = {"repeat": True, "allow-when-locked": False, "allow-inhibiting": True,
                 "cooldown-ms": 0}

TERMINALS = {"alacritty", "foot", "footclient", "kitty", "wezterm", "ghostty", "konsole",
             "gnome-terminal", "kgx", "ptyxis", "xterm", "st", "urxvt", "tilix", "terminator",
             "rio", "contour", "cosmic-term", "xfce4-terminal", "blackbox", "warp-terminal"}

_SHORT = [("left", "←"), ("right", "→"), ("up", "↑"), ("down", "↓"), ("workspace", "ws"),
          ("monitor", "mon"), ("column", "col"), ("columns", "cols"), ("window", "win"),
          ("toggle", "tgl"), ("preset", "pre"), ("switch", "sw"), ("screenshot", "shot"),
          ("maximize", "max"), ("fullscreen", "full"), ("floating", "float"),
          ("keyboard", "kbd"), ("shortcuts", "keys"), ("available", "free")]
_DROP = re.compile(r"\b(to|or|the|into|from|display)\b")


def parse_combo(name: str) -> tuple[frozenset, str]:
    """`Mod+Shift+H` -> ({"Mod", "Shift"}, "H"). Unknown modifiers are kept as written."""
    *mods, key = name.split("+") if name else [""]
    if not key and mods:      # the key is "+" itself is not valid; keep the text
        key = mods.pop()
    return frozenset(_MOD_ALIASES.get(m.lower(), m) for m in mods), key


def layer_name(mods) -> str:
    known = [m for m in MOD_ORDER if m in mods]
    return "+".join(known + sorted(m for m in mods if m not in MOD_ORDER))


def layer_label(mods) -> str:
    return "+".join(MOD_LABELS.get(m, m) for m in layer_name(mods).split("+")) if mods else "No modifier"


def action_text(child: dict | None) -> str:
    """One action as KDL, e.g. `spawn "alacritty"`."""
    if not child:
        return ""
    return niri_core.format_node(child["name"], {"args": child.get("args", []),
                                                 "props": child.get("props", {})})


def parse_action(text: str) -> dict:
    """KDL for one action -> {name, args, props}. Raises ValueError with a reason."""
    text = text.strip().rstrip(";").strip()
    if not text:
        raise ValueError("Type an action, for example close-window")
    try:
        tree = niri_core.load_string("binds {\n k {\n" + text + "\n }\n}\n")
    except niri_core.KdlError as e:
        raise ValueError(e.message) from None
    children = tree.get("binds/k")["children"]
    if len(children) != 1:
        raise ValueError("A key runs one action")
    return children[0]


def short_label(child: dict | None) -> str:
    """A few characters for the second line of a key cap."""
    if not child:
        return ""
    name, args = child["name"], child.get("args", [])
    if name in ("spawn", "spawn-sh") and args:
        words = shlex.split(str(args[0])) if name == "spawn-sh" else [str(a) for a in args]
        if words and os.path.basename(words[0]) in ("sh", "bash") and "-c" in words:
            rest = words[words.index("-c") + 1:]
            words = shlex.split(rest[0]) if rest else words
        return os.path.basename(words[0]) if words else name
    text = name
    for long, short in _SHORT:
        text = re.sub(rf"\b{long}\b", short, text)
    text = " ".join(_DROP.sub("", text.replace("-", " ")).split())
    return text + (" " + " ".join(str(a) for a in args) if args else "")


def role(child: dict | None, props: dict | None = None) -> str | None:
    """`quit` or `terminal` for the binds you need to get out of trouble."""
    if not child:
        return None
    if child["name"] == "quit":
        return "quit"
    if child["name"] in ("spawn", "spawn-sh") and child.get("args"):
        try:
            words = shlex.split(" ".join(str(a) for a in child["args"]))
        except ValueError:
            words = [str(child["args"][0])]
        if words and os.path.basename(words[0]) in TERMINALS:
            return "terminal"
        if "terminal" in str((props or {}).get("hotkey-overlay-title") or "").lower():
            return "terminal"
    return None


@dataclass
class Bind:
    name: str                 # as written in the file
    mods: frozenset
    key: str                  # canonical key name, or a POINTER trigger
    file: str
    line: int
    props: dict
    action: dict | None       # {name, args, props}; None for an empty block
    effective: bool = True    # False when a later definition replaces it
    pointer: bool = False
    extra: list = field(default_factory=list)   # further actions, which niri rejects

    @property
    def path(self) -> str:
        return "binds/" + self.name

    @property
    def ident(self) -> tuple:
        return (self.mods, self.key)

    @property
    def category(self) -> str:
        return actions.category(self.action["name"]) if self.action else actions.SYSTEM

    @property
    def where(self) -> str:
        return f"{os.path.basename(self.file)}:{self.line}"


class BindsModel:
    def __init__(self, config_fn, keymap: Keymap | None = None):
        self._config = config_fn
        self._keymap = keymap

    @property
    def config(self):
        return self._config()

    @property
    def keymap(self) -> Keymap:
        if self._keymap is None:
            self._keymap = Keymap.for_config(self.config)
        return self._keymap

    def reset_keymap(self):
        self._keymap = None

    # -- reading

    def key_id(self, key: str) -> tuple[str, bool]:
        """(canonical key, is a pointer trigger)"""
        if key.lower() in _POINTER:
            return _POINTER[key.lower()], True
        return self.keymap.canonical(key), False

    def all(self) -> list[Bind]:
        """Every bind in every file, in the order niri reads them."""
        out: list[Bind] = []
        for e in self.config.tree.entries("binds"):
            mods, key = parse_combo(e["name"])
            key, pointer = self.key_id(key)
            children = e["value"]["children"]
            out.append(Bind(e["name"], mods, key, e["file"], e["line"], e["value"]["props"],
                            children[0] if children else None, pointer=pointer,
                            extra=children[1:]))
        last = {b.ident: i for i, b in enumerate(out)}
        for i, b in enumerate(out):
            b.effective = last[b.ident] == i
        return out

    def effective(self) -> list[Bind]:
        return [b for b in self.all() if b.effective]

    def at(self, mods, key: str) -> Bind | None:
        ident = (frozenset(mods), self.key_id(key)[0])
        return next((b for b in self.all() if b.effective and b.ident == ident), None)

    def layers(self) -> list[tuple[frozenset, int]]:
        """Modifier combinations in use, most binds first; Mod and no modifier always."""
        counts: dict[frozenset, int] = {frozenset({"Mod"}): 0, frozenset(): 0}
        for b in self.effective():
            counts[b.mods] = counts.get(b.mods, 0) + 1
        ordered = sorted(counts, key=lambda m: (m != frozenset({"Mod"}), not m, -counts[m], layer_name(m)))
        return [(m, counts[m]) for m in ordered]

    def combo_name(self, mods, key: str) -> str:
        """How a new bind for this key is written."""
        key, pointer = self.key_id(key)
        written = key if pointer else self.keymap.written(key)
        return "+".join([p for p in [layer_name(mods), written] if p])

    def conflicts(self) -> list[dict]:
        """Keys defined more than once: {combo, kind, winner, losers}.

        `override`: a later file replaces an earlier one, as niri's includes do.
        `duplicate`: twice in one file, which niri refuses to load.
        `shadow`: Mod+key and Super+key, the same shortcut while Mod is Super.
        """
        binds = self.all()
        groups: dict[tuple, list[Bind]] = {}
        for b in binds:
            groups.setdefault(b.ident, []).append(b)
        out = []
        for group in groups.values():
            if len(group) < 2:
                continue
            winner, losers = group[-1], group[:-1]
            same_file = any(b.file == winner.file for b in losers)
            out.append({"combo": winner.name, "kind": "duplicate" if same_file else "override",
                        "winner": winner, "losers": losers})
        mod_key = str(self.config.get("input/mod-key", "Super")).lower()
        if mod_key in ("super", "win"):
            for ident, group in groups.items():
                mods, key = ident
                if "Mod" not in mods:
                    continue
                twin = groups.get((frozenset(mods - {"Mod"} | {"Super"}), key))
                if twin and "Super" not in mods:
                    out.append({"combo": group[-1].name, "kind": "shadow",
                                "winner": group[-1], "losers": [twin[-1]]})
        return out

    # -- editing

    def _value(self, props: dict, action: dict | None) -> dict:
        return {"args": [], "props": props, "children": [action] if action else []}

    def set_action(self, mods, key: str, action: dict) -> str:
        """Bind a key (new or existing) to an action. Returns the bind's path."""
        bind = self.at(mods, key)
        if bind is None:
            path = "binds/" + self.combo_name(mods, key)
            self.config.set(path, self._value({}, action))
            return path
        props = dict(bind.props)
        if action["name"] not in ("spawn", "spawn-sh"):
            props.pop("allow-when-locked", None)   # niri only accepts it on spawn binds
        self.config.set(bind.path, self._value(props, action))
        return bind.path

    def set_prop(self, bind: Bind, name: str, value):
        """Set a bind property; a value equal to niri's default removes it."""
        props = dict(bind.props)
        if name == "hotkey-overlay-title":
            if value == "":
                props.pop(name, None)
            else:
                props[name] = value            # a title, or None to hide the bind
        elif value == PROP_DEFAULTS.get(name):
            props.pop(name, None)
        else:
            props[name] = value
        self.config.set(bind.path, self._value(props, bind.action))

    def remove(self, bind: Bind):
        self.config.remove(bind.path)

    def move(self, bind: Bind, mods, key: str) -> str:
        """Put a bind on another key. Returns the new path."""
        new_name = self.combo_name(mods, key)
        target = self.at(mods, key)
        if target is not None and target.ident != bind.ident:
            raise ValueError(f"{target.name} is already bound to {action_text(target.action)}")
        self.config.rename(bind.path, new_name)
        return "binds/" + new_name

    # -- lockout

    def lockout(self, bind: Bind, new_action: dict | None = None) -> str:
        """Why changing or removing this bind needs a confirm, or ""."""
        kind = role(bind.action, bind.props)
        if kind is None or role(new_action) == kind:
            return ""
        others = [b for b in self.effective()
                  if b.ident != bind.ident and role(b.action, b.props) == kind]
        if others:
            return ""
        if kind == "quit":
            return (f"{bind.name} is your only key for quit. Without it you can only leave "
                    "niri from a terminal or another TTY.")
        return (f"{bind.name} is your only key that opens a terminal. Without it you may have "
                "no way to fix the config from inside niri.")
