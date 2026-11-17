"""Window rules: matchers, properties and templates, from niri's window-rules docs (26.04).

A property is addressed by a path inside the rule, such as `opacity` or
`focus-ring/width`. `state` is not a node: it stands for the `on` / `off`
flags of a block. `kind` picks the editor:

    bool      true / false             int, float   a number
    enum      one of `options`         text, color  a string
    onoff     the on / off flags       size         { proportion 0.5; } or { fixed 480; } or {}
    position  x= y= relative-to=       xy           x= y= (shadow offset)
    gradient  from= to= angle= relative-to= in=
    kdl       anything else, edited as the KDL after the node name

Matcher kinds: regex, bool, and enum (one of `options`).

`when` is "open" for properties niri reads once, when the window opens, and
"always" for those it keeps applying.
"""

NAME = "window-rule"
SUBJECT = "window"           # what a rule matches, for messages
SUBJECTS = "windows"

MATCHERS = [
    {"key": "app-id", "label": "app-id", "kind": "regex", "example": "^firefox$"},
    {"key": "title", "label": "title", "kind": "regex", "example": "^Picture-in-Picture$"},
    {"key": "is-active", "label": "is active", "kind": "bool"},
    {"key": "is-focused", "label": "is focused", "kind": "bool"},
    {"key": "is-active-in-column", "label": "is active in column", "kind": "bool"},
    {"key": "is-floating", "label": "is floating", "kind": "bool"},
    {"key": "is-window-cast-target", "label": "is being screencast", "kind": "bool"},
    {"key": "is-urgent", "label": "is urgent", "kind": "bool"},
    {"key": "at-startup", "label": "at niri startup", "kind": "bool"},
]
MATCHER_KEYS = {m["key"]: m for m in MATCHERS}

_RELATIVE = ["top-left", "top-right", "bottom-left", "bottom-right", "top", "bottom", "left", "right"]


def _ring(prefix: str, label: str, since: str = "") -> list[dict]:
    return [
        {"path": f"{prefix}/state", "label": f"{label}", "kind": "onoff", "default": "on"},
        {"path": f"{prefix}/width", "label": f"{label} width", "kind": "int", "default": 4, "min": 0},
        {"path": f"{prefix}/active-color", "label": f"{label} active color", "kind": "color", "default": "#7fc8ff"},
        {"path": f"{prefix}/inactive-color", "label": f"{label} inactive color", "kind": "color", "default": "#505050"},
        {"path": f"{prefix}/urgent-color", "label": f"{label} urgent color", "kind": "color", "default": "#9b0000"},
        *_gradients(prefix, label),
    ]


# Colour spaces a gradient can blend through (`in=`); srgb is niri's default.
GRADIENT_SPACES = ["srgb", "srgb-linear", "oklab", "oklch shorter hue", "oklch longer hue",
                   "oklch increasing hue", "oklch decreasing hue"]
GRADIENT_RELATIVE = ["window", "workspace-view"]   # `window` is niri's default: no relative-to


def _gradients(prefix: str, label: str) -> list[dict]:
    """active-, inactive- and urgent-gradient, which win over the colours of the same block."""
    starts = {"active": ("#80c8ff", "#bbddff"), "inactive": ("#505050", "#808080"), "urgent": ("#880000", "#aa3333")}
    return [{"path": f"{prefix}/{state}-gradient", "label": f"{label} {state} gradient", "kind": "gradient",
             "default": {"from": a, "to": b, "angle": 45, "rel": "window", "in": "srgb"},
             "overrides": f"{prefix}/{state}-color"}
            for state, (a, b) in starts.items()]


def _effect(prefix: str, label: str) -> list[dict]:
    return [
        {"path": f"{prefix}/blur", "label": f"{label}blur", "kind": "bool", "default": True},
        {"path": f"{prefix}/xray", "label": f"{label}xray", "kind": "bool", "default": True},
        {"path": f"{prefix}/noise", "label": f"{label}noise", "kind": "float", "default": 0.05, "min": 0, "max": 1},
        {"path": f"{prefix}/saturation", "label": f"{label}saturation", "kind": "float", "default": 1.0, "min": 0, "max": 10},
    ]


PROPS = [
    # Read once, when the window opens
    {"path": "open-floating", "label": "Open floating", "kind": "bool", "default": True, "when": "open"},
    {"path": "open-maximized", "label": "Open maximized", "kind": "bool", "default": True, "when": "open"},
    {"path": "open-maximized-to-edges", "label": "Open maximized to edges", "kind": "bool", "default": True, "when": "open"},
    {"path": "open-fullscreen", "label": "Open fullscreen", "kind": "bool", "default": True, "when": "open"},
    {"path": "open-focused", "label": "Focus on open", "kind": "bool", "default": False, "when": "open"},
    {"path": "default-column-width", "label": "Width", "kind": "size", "default": {"kind": "proportion", "value": 0.5}, "when": "open"},
    {"path": "default-window-height", "label": "Height", "kind": "size", "default": {"kind": "proportion", "value": 0.5}, "when": "open"},
    {"path": "open-on-output", "label": "Open on output", "kind": "text", "default": "", "when": "open", "suggest": "outputs"},
    {"path": "open-on-workspace", "label": "Open on workspace", "kind": "text", "default": "", "when": "open", "suggest": "workspaces"},
    # Applied continuously
    {"path": "default-floating-position", "label": "Floating position", "kind": "position",
     "default": {"x": 32, "y": 32, "relative-to": "bottom-right"}, "options": _RELATIVE},
    {"path": "opacity", "label": "Opacity", "kind": "float", "default": 0.95, "min": 0, "max": 1},
    {"path": "block-out-from", "label": "Block out from", "kind": "enum", "default": "screencast",
     "options": ["screencast", "screen-capture"]},
    {"path": "geometry-corner-radius", "label": "Corner radius", "kind": "kdl", "default": "12"},
    {"path": "clip-to-geometry", "label": "Clip to geometry", "kind": "bool", "default": True},
    {"path": "draw-border-with-background", "label": "Border with background", "kind": "bool", "default": False},
    {"path": "variable-refresh-rate", "label": "Variable refresh rate", "kind": "bool", "default": True},
    {"path": "default-column-display", "label": "Column display", "kind": "enum", "default": "tabbed",
     "options": ["normal", "tabbed"]},
    {"path": "scroll-factor", "label": "Scroll factor", "kind": "float", "default": 0.75, "min": 0, "max": 100},
    {"path": "tiled-state", "label": "Tiled state", "kind": "bool", "default": True},
    {"path": "min-width", "label": "Minimum width", "kind": "int", "default": 400, "min": 0},
    {"path": "max-width", "label": "Maximum width", "kind": "int", "default": 1200, "min": 0},
    {"path": "min-height", "label": "Minimum height", "kind": "int", "default": 300, "min": 0},
    {"path": "max-height", "label": "Maximum height", "kind": "int", "default": 900, "min": 0},
    *_ring("focus-ring", "Focus ring"),
    *_ring("border", "Border"),
    {"path": "shadow/state", "label": "Shadow", "kind": "onoff", "default": "on"},
    {"path": "shadow/softness", "label": "Shadow softness", "kind": "int", "default": 30, "min": 0},
    {"path": "shadow/spread", "label": "Shadow spread", "kind": "int", "default": 5},
    {"path": "shadow/offset", "label": "Shadow offset", "kind": "xy", "default": {"x": 0, "y": 5}},
    {"path": "shadow/color", "label": "Shadow color", "kind": "color", "default": "#0007"},
    {"path": "shadow/draw-behind-window", "label": "Shadow behind window", "kind": "bool", "default": True},
    {"path": "tab-indicator/active-color", "label": "Tab active color", "kind": "color", "default": "#7fc8ff"},
    {"path": "tab-indicator/inactive-color", "label": "Tab inactive color", "kind": "color", "default": "#505050"},
    {"path": "tab-indicator/urgent-color", "label": "Tab urgent color", "kind": "color", "default": "#9b0000"},
    *_gradients("tab-indicator", "Tab"),
    *_effect("background-effect", "Background "),
    {"path": "popups/opacity", "label": "Pop-up opacity", "kind": "float", "default": 0.9, "min": 0, "max": 1},
    {"path": "popups/geometry-corner-radius", "label": "Pop-up corner radius", "kind": "kdl", "default": "15"},
    *_effect("popups/background-effect", "Pop-up "),
    {"path": "baba-is-float", "label": "Baba is float", "kind": "bool", "default": True},
]
for _p in PROPS:
    _p.setdefault("when", "always")
PROP_PATHS = {p["path"]: p for p in PROPS}

# Blocks whose children niri merges one by one across rules.
MERGED_BLOCKS = {"focus-ring", "border", "shadow", "tab-indicator", "background-effect",
                 "popups", "popups/background-effect"}

APP = "__APP__"   # replaced by the picked window's app-id, as an exact regex

TEMPLATES = [
    {"id": "float", "title": "Float this app", "needs_app": True,
     "description": "Open the picked app as a floating window.",
     "children": [{"name": "match", "args": [], "props": {"app-id": APP}},
                  {"name": "open-floating", "args": [True], "props": {}}]},
    {"id": "dialogs", "title": "Dialogs float",
     "description": "File pickers and other common dialogs open floating.",
     "children": [{"name": "match", "args": [], "props": {"title": r"^(Open|Save|Choose|Select)( |$)"}},
                  {"name": "open-floating", "args": [True], "props": {}}]},
    {"id": "pip", "title": "Picture-in-picture",
     "description": "Firefox's video player floats in the bottom-right corner.",
     "children": [{"name": "match", "args": [], "props": {"app-id": "firefox$", "title": "^Picture-in-Picture$"}},
                  {"name": "open-floating", "args": [True], "props": {}},
                  {"name": "default-floating-position", "args": [],
                   "props": {"x": 32, "y": 32, "relative-to": "bottom-right"}}]},
    {"id": "games", "title": "Games fullscreen",
     "description": "Steam games open fullscreen and turn on VRR.",
     "children": [{"name": "match", "args": [], "props": {"app-id": r"^steam_app_"}},
                  {"name": "open-fullscreen", "args": [True], "props": {}},
                  {"name": "variable-refresh-rate", "args": [True], "props": {}}]},
    {"id": "screencast", "title": "Screen-share safe",
     "description": "Password managers show as black boxes in screencasts.",
     "children": [{"name": "match", "args": [], "props": {"app-id": r"^org\.keepassxc\.KeePassXC$"}},
                  {"name": "match", "args": [], "props": {"app-id": r"^org\.gnome\.World\.Secrets$"}},
                  {"name": "match", "args": [], "props": {"app-id": r"^(Bitwarden|1Password)$"}},
                  {"name": "block-out-from", "args": ["screencast"], "props": {}}]},
    {"id": "opacity", "title": "App opacity", "needs_app": True,
     "description": "Make the picked app slightly see-through.",
     "children": [{"name": "match", "args": [], "props": {"app-id": APP}},
                  {"name": "opacity", "args": [0.92], "props": {}}]},
    {"id": "inactive", "title": "Dim inactive windows",
     "description": "Windows other than the active one are slightly see-through.",
     "children": [{"name": "match", "args": [], "props": {"is-active": False}},
                  {"name": "opacity", "args": [0.95], "props": {}}]},
    {"id": "rounded", "title": "Rounded corners",
     "description": "Round every window and clip it to that shape.",
     "children": [{"name": "geometry-corner-radius", "args": [12], "props": {}},
                  {"name": "clip-to-geometry", "args": [True], "props": {}}]},
    {"id": "blank", "title": "Empty rule",
     "description": "Start from nothing. Without a match it applies to every window.",
     "children": []},
]
