"""Which key is where: the xkb keymap and the physical layout of the map.

niri binds name keys by XKB keysym (`Mod+H`, `Mod+Page_Down`). To draw them on
a keyboard, each physical key (an xkb keycode) is resolved to the keysym it
produces without modifiers in the user's layout. libxkbcommon does that; when
the library is missing, a built-in US table is used.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import re
import subprocess

# -- physical layout: rows of (xkb keycode or None for a gap, width in key units)

_F_ROW = [(9, 1), (None, 1), (67, 1), (68, 1), (69, 1), (70, 1), (None, .5),
          (71, 1), (72, 1), (73, 1), (74, 1), (None, .5), (75, 1), (76, 1), (95, 1), (96, 1)]
_NUM_ROW = [(49, 1)] + [(c, 1) for c in range(10, 22)] + [(22, 2)]
_TOP = [(c, 1) for c in range(24, 36)]
_HOME = [(c, 1) for c in range(38, 49)]
_BOTTOM = [(c, 1) for c in range(52, 62)]
_SPACE_ROW = [(37, 1.25), (133, 1.25), (64, 1.25), (65, 6.25), (108, 1.25), (134, 1.25),
              (135, 1.25), (105, 1.25)]

ANSI = [
    _F_ROW,
    _NUM_ROW,
    [(23, 1.5)] + _TOP + [(51, 1.5)],
    [(66, 1.75)] + _HOME + [(36, 2.25)],
    [(50, 2.25)] + _BOTTOM + [(62, 2.75)],
    _SPACE_ROW,
]
# The ISO Enter key is drawn as one cap in the home row; the gap above it is
# where its upper half would be.
ISO = [
    _F_ROW,
    _NUM_ROW,
    [(23, 1.5)] + _TOP + [(None, 1.5)],
    [(66, 1.75)] + _HOME + [(51, 1), (36, 1.25)],
    [(50, 1.25), (94, 1)] + _BOTTOM + [(62, 2.75)],
    _SPACE_ROW,
]
NAV = [
    [(107, 1), (78, 1), (127, 1)],
    [(118, 1), (110, 1), (112, 1)],
    [(119, 1), (115, 1), (117, 1)],
    [(None, 3)],
    [(None, 1), (111, 1), (None, 1)],
    [(113, 1), (116, 1), (114, 1)],
]

# Keys that switch the modifier layer instead of being bound.
MODIFIER_KEYS = {
    "Shift_L": "Shift", "Shift_R": "Shift", "Control_L": "Ctrl", "Control_R": "Ctrl",
    "Alt_L": "Alt", "Alt_R": "Alt", "Meta_L": "Alt", "Meta_R": "Alt",
    "Super_L": "Mod", "Super_R": "Mod",
    "ISO_Level3_Shift": "ISO_Level3_Shift", "ISO_Level5_Shift": "ISO_Level5_Shift",
}

_LABELS = {
    "Escape": "Esc", "Return": "Enter", "BackSpace": "Bksp", "Caps_Lock": "Caps",
    "Shift_L": "Shift", "Shift_R": "Shift", "Control_L": "Ctrl", "Control_R": "Ctrl",
    "Alt_L": "Alt", "Alt_R": "Alt", "Super_L": "Mod", "Super_R": "Mod",
    "ISO_Level3_Shift": "AltGr", "ISO_Level5_Shift": "Lv5", "space": "Space",
    "Left": "←", "Right": "→", "Up": "↑", "Down": "↓", "Print": "PrtSc",
    "Scroll_Lock": "ScrLk", "Pause": "Pause", "Insert": "Ins", "Delete": "Del",
    "Prior": "PgUp", "Next": "PgDn", "Home": "Home", "End": "End", "Menu": "Menu",
    "Tab": "Tab",
}

_DEAD = {"acute": "´", "grave": "`", "diaeresis": "¨", "circumflex": "^", "tilde": "~",
         "cedilla": "¸", "caron": "ˇ", "abovering": "°"}

# Names to write for keys whose xkb name is not the one people use.
_WRITTEN = {"Prior": "Page_Up", "Next": "Page_Down"}

_US = {
    9: "Escape", 67: "F1", 68: "F2", 69: "F3", 70: "F4", 71: "F5", 72: "F6", 73: "F7",
    74: "F8", 75: "F9", 76: "F10", 95: "F11", 96: "F12",
    49: "grave", 10: "1", 11: "2", 12: "3", 13: "4", 14: "5", 15: "6", 16: "7", 17: "8",
    18: "9", 19: "0", 20: "minus", 21: "equal", 22: "BackSpace",
    23: "Tab", 24: "q", 25: "w", 26: "e", 27: "r", 28: "t", 29: "y", 30: "u", 31: "i",
    32: "o", 33: "p", 34: "bracketleft", 35: "bracketright", 51: "backslash",
    66: "Caps_Lock", 38: "a", 39: "s", 40: "d", 41: "f", 42: "g", 43: "h", 44: "j",
    45: "k", 46: "l", 47: "semicolon", 48: "apostrophe", 36: "Return",
    50: "Shift_L", 94: "less", 52: "z", 53: "x", 54: "c", 55: "v", 56: "b", 57: "n",
    58: "m", 59: "comma", 60: "period", 61: "slash", 62: "Shift_R",
    37: "Control_L", 133: "Super_L", 64: "Alt_L", 65: "space", 108: "Alt_R",
    134: "Super_R", 135: "Menu", 105: "Control_R",
    107: "Print", 78: "Scroll_Lock", 127: "Pause", 118: "Insert", 110: "Home",
    112: "Prior", 119: "Delete", 115: "End", 117: "Next",
    111: "Up", 113: "Left", 116: "Down", 114: "Right",
    121: "XF86AudioMute", 122: "XF86AudioLowerVolume", 123: "XF86AudioRaiseVolume",
    171: "XF86AudioNext", 172: "XF86AudioPlay", 173: "XF86AudioPrev", 174: "XF86AudioStop",
    198: "XF86AudioMicMute", 232: "XF86MonBrightnessDown", 233: "XF86MonBrightnessUp",
}
_US_SYMBOLS = {
    "grave": "`", "minus": "-", "equal": "=", "bracketleft": "[", "bracketright": "]",
    "backslash": "\\", "semicolon": ";", "apostrophe": "'", "comma": ",", "period": ".",
    "slash": "/", "less": "<",
}


class _RuleNames(ctypes.Structure):
    _fields_ = [(n, ctypes.c_char_p) for n in ("rules", "model", "layout", "variant", "options")]


def _load_xkb():
    name = ctypes.util.find_library("xkbcommon") or "libxkbcommon.so.0"
    try:
        lib = ctypes.CDLL(name)
    except OSError:
        return None
    p, u32 = ctypes.c_void_p, ctypes.c_uint32
    lib.xkb_context_new.restype, lib.xkb_context_new.argtypes = p, [ctypes.c_int]
    lib.xkb_context_unref.argtypes = [p]
    lib.xkb_keymap_new_from_names.restype = p
    lib.xkb_keymap_new_from_names.argtypes = [p, ctypes.POINTER(_RuleNames), ctypes.c_int]
    lib.xkb_keymap_unref.argtypes = [p]
    lib.xkb_keymap_num_layouts.restype, lib.xkb_keymap_num_layouts.argtypes = u32, [p]
    lib.xkb_keymap_key_get_syms_by_level.restype = ctypes.c_int
    lib.xkb_keymap_key_get_syms_by_level.argtypes = [
        p, u32, u32, u32, ctypes.POINTER(ctypes.POINTER(u32))]
    lib.xkb_keysym_get_name.restype = ctypes.c_int
    lib.xkb_keysym_get_name.argtypes = [u32, ctypes.c_char_p, ctypes.c_size_t]
    lib.xkb_keysym_from_name.restype, lib.xkb_keysym_from_name.argtypes = u32, [ctypes.c_char_p, ctypes.c_int]
    lib.xkb_keysym_to_utf32.restype, lib.xkb_keysym_to_utf32.argtypes = u32, [u32]
    return lib


_xkb = _load_xkb()
_CASE_INSENSITIVE = 1


def _sym_name(sym: int) -> str | None:
    buf = ctypes.create_string_buffer(64)
    return buf.value.decode() if _xkb.xkb_keysym_get_name(sym, buf, 64) > 0 else None


def system_names() -> dict:
    """The system keyboard settings (what niri uses when `xkb {}` is empty)."""
    try:
        out = subprocess.run(["localectl", "status"], capture_output=True, text=True,
                             timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    found = {}
    for key, field in (("layout", "Layout"), ("model", "Model"), ("variant", "Variant"),
                       ("options", "Options")):
        m = re.search(rf"X11 {field}:\s*(\S.*)$", out, re.M)
        if m and m.group(1).strip() not in ("", "(unset)", "n/a"):
            found[key] = m.group(1).strip()
    return found


class Keymap:
    """Keys of one xkb configuration, by keycode and by name."""

    def __init__(self, layout: str = "us", variant: str = "", model: str = "",
                 options: str = "", rules: str = ""):
        self.layout = layout or "us"
        self._by_code: dict[int, str] = {}     # keycode -> keysym name, first layout
        self._by_name: dict[str, int] = {}     # keysym name -> keycode, first layout that has it
        self.native = False
        if _xkb is not None:
            self._compile(rules, model, self.layout, variant, options)
        if not self._by_code:
            self._by_code = dict(_US)
            for code, name in _US.items():
                self._by_name.setdefault(name, code)

    @classmethod
    def for_config(cls, config, system=system_names) -> "Keymap":
        """The keymap niri builds for this config."""
        names = {k: config.get(f"input/keyboard/xkb/{k}") for k in
                 ("layout", "variant", "model", "options", "rules")}
        names = {k: v for k, v in names.items() if isinstance(v, str) and v}
        if "layout" not in names:
            names = system() or {}
        return cls(**names)

    def _compile(self, rules, model, layout, variant, options):
        ctx = _xkb.xkb_context_new(0)
        if not ctx:
            return
        names = _RuleNames(*(s.encode() if s else None for s in (rules, model, layout, variant, options)))
        keymap = _xkb.xkb_keymap_new_from_names(ctx, ctypes.byref(names), 0)
        if keymap:
            syms = ctypes.POINTER(ctypes.c_uint32)()
            for group in range(_xkb.xkb_keymap_num_layouts(keymap)):
                for code in range(8, 256):
                    if _xkb.xkb_keymap_key_get_syms_by_level(keymap, code, group, 0, ctypes.byref(syms)) < 1:
                        continue
                    name = _sym_name(syms[0])
                    if not name or name == "NoSymbol":
                        continue
                    if group == 0:
                        self._by_code[code] = name
                    self._by_name.setdefault(name, code)
            self.native = bool(self._by_code)
            _xkb.xkb_keymap_unref(keymap)
        _xkb.xkb_context_unref(ctx)

    # -- names

    def canonical(self, name: str) -> str:
        """One spelling per key: niri looks key names up without regard to case."""
        if _xkb is not None:
            sym = _xkb.xkb_keysym_from_name(name.encode(), _CASE_INSENSITIVE)
            found = _sym_name(sym) if sym else None
            if found:
                return found
        lowered = name.lower()
        for known in self._by_name:
            if known.lower() == lowered:
                return known
        return {"page_up": "Prior", "page_down": "Next"}.get(lowered, name)

    def sym(self, keycode: int) -> str | None:
        return self._by_code.get(keycode)

    def keycode(self, name: str) -> int | None:
        return self._by_name.get(self.canonical(name))

    def written(self, canonical: str) -> str:
        """How a key is spelled in a new bind, in the style of niri's default config."""
        if canonical in _WRITTEN:
            return _WRITTEN[canonical]
        if len(canonical) == 1 and canonical.isascii():
            return canonical.upper()
        if canonical.isascii() and canonical.islower() and self.canonical(canonical.capitalize()) == canonical:
            return canonical.capitalize()
        return canonical

    def label(self, keycode: int) -> str:
        name = self._by_code.get(keycode)
        if name is None:
            return ""
        if name in _LABELS:
            return _LABELS[name]
        if len(name) == 1:
            return name.upper()
        if name.startswith("dead_"):
            return _DEAD.get(name[5:], name[5:])
        if _xkb is not None:
            sym = _xkb.xkb_keysym_from_name(name.encode(), 0)
            char = chr(_xkb.xkb_keysym_to_utf32(sym)) if sym and _xkb.xkb_keysym_to_utf32(sym) else ""
            if char.isprintable() and char.strip():
                return char.upper() if len(char.upper()) == 1 else char
        return _US_SYMBOLS.get(name, name)

    # -- geometry

    @property
    def iso(self) -> bool:
        """ISO has an extra key next to left Shift; US-style layouts are drawn as ANSI."""
        return self.layout.split(",")[0].strip() not in ("us", "kr", "th", "cn", "tw", "ph")

    def rows(self) -> list[list[tuple[int | None, float]]]:
        return ISO if self.iso else ANSI
