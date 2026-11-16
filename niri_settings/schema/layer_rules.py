"""Layer rules: matchers, properties and templates, from niri's layer-rules docs (26.04).

Layer rules work like window rules (see window_rules.py for paths and kinds)
but match layer-shell surfaces: bars, docks, launchers, notifications and
wallpapers. Every property applies continuously; none is read only at open.
"""

from .window_rules import APP, _effect

NAME = "layer-rule"
SUBJECT = "surface"
SUBJECTS = "layer surfaces"

LAYERS = ["background", "bottom", "top", "overlay"]

MATCHERS = [
    {"key": "namespace", "label": "namespace", "kind": "regex", "example": "^waybar$"},
    {"key": "layer", "label": "layer", "kind": "enum", "options": LAYERS},
    {"key": "at-startup", "label": "at niri startup", "kind": "bool"},
]
MATCHER_KEYS = {m["key"]: m for m in MATCHERS}

PROPS = [
    {"path": "opacity", "label": "Opacity", "kind": "float", "default": 0.95, "min": 0, "max": 1},
    {"path": "block-out-from", "label": "Block out from", "kind": "enum", "default": "screencast",
     "options": ["screencast", "screen-capture"]},
    {"path": "geometry-corner-radius", "label": "Corner radius", "kind": "kdl", "default": "12"},
    {"path": "place-within-backdrop", "label": "Place within backdrop", "kind": "bool", "default": True},
    {"path": "shadow/state", "label": "Shadow", "kind": "onoff", "default": "on"},
    {"path": "shadow/softness", "label": "Shadow softness", "kind": "int", "default": 40, "min": 0},
    {"path": "shadow/spread", "label": "Shadow spread", "kind": "int", "default": 5},
    {"path": "shadow/offset", "label": "Shadow offset", "kind": "xy", "default": {"x": 0, "y": 5}},
    {"path": "shadow/color", "label": "Shadow color", "kind": "color", "default": "#00000064"},
    {"path": "shadow/draw-behind-window", "label": "Shadow behind surface", "kind": "bool", "default": True},
    *_effect("background-effect", "Background "),
    {"path": "popups/opacity", "label": "Pop-up opacity", "kind": "float", "default": 0.9, "min": 0, "max": 1},
    {"path": "popups/geometry-corner-radius", "label": "Pop-up corner radius", "kind": "kdl", "default": "6"},
    *_effect("popups/background-effect", "Pop-up "),
    {"path": "baba-is-float", "label": "Baba is float", "kind": "bool", "default": True},
]
for _p in PROPS:
    _p.setdefault("when", "always")
PROP_PATHS = {p["path"]: p for p in PROPS}

MERGED_BLOCKS = {"shadow", "background-effect", "popups", "popups/background-effect"}

TEMPLATES = [
    {"id": "blur", "title": "Blur behind this surface", "needs_app": True,
     "description": "Blur what is behind the selected surface (blur must be on in Appearance & blur).",
     "children": [{"name": "match", "args": [], "props": {"namespace": APP}},
                  {"name": "background-effect", "args": [], "props": {},
                   "children": [{"name": "blur", "args": [True], "props": {}}]}]},
    {"id": "opacity", "title": "Surface opacity", "needs_app": True,
     "description": "Make the selected surface slightly see-through.",
     "children": [{"name": "match", "args": [], "props": {"namespace": APP}},
                  {"name": "opacity", "args": [0.95], "props": {}}]},
    {"id": "notifications", "title": "Hide notifications in screencasts",
     "description": "mako and similar notification daemons show as black boxes in screencasts.",
     "children": [{"name": "match", "args": [], "props": {"namespace": "^notifications$"}},
                  {"name": "block-out-from", "args": ["screencast"], "props": {}}]},
    {"id": "launcher", "title": "Launcher shadow",
     "description": "A shadow with rounded corners behind fuzzel.",
     "children": [{"name": "match", "args": [], "props": {"namespace": "^launcher$"}},
                  {"name": "shadow", "args": [], "props": {}, "children": [{"name": "on", "args": [], "props": {}}]},
                  {"name": "geometry-corner-radius", "args": [10], "props": {}}]},
    {"id": "backdrop", "title": "Wallpaper in the overview",
     "description": "Put swaybg's wallpaper into the backdrop seen in the overview and between workspaces.",
     "children": [{"name": "match", "args": [], "props": {"namespace": "^wallpaper$"}},
                  {"name": "place-within-backdrop", "args": [True], "props": {}}]},
    {"id": "blank", "title": "Empty rule",
     "description": "Start from nothing. Without a match it applies to every layer surface.",
     "children": []},
]
