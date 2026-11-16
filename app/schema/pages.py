"""Settings pages drawn from the schema, from niri's config docs (26.04).

Each page is a list of groups, each a list of settings drawn as cards by
SettingCard.qml. A setting has a `kind` (the control), a config `path`,
a `label`, and the `default` niri uses when the setting is not written.

Kinds, besides the ones in layout.py:
  number     whole number at `path` (`unit`, `min`, `max`)
  decimal    number written with a decimal point
  text       a string; color: a string with a swatch
  select     one of `options` (many choices); segmented: 2-4 choices
  bool       a node with true / false: `drag false`
  offflag    a section that is on unless it has an `off` child
  xy         `offset x=0 y=5`
  animation  one entry of `animations {}`: default, off, spring or easing
  workspaces, startup, environment   lists edited in place

COVERAGE says where each top-level section of the config is edited: a page,
or "source" for sections only the Config files editor covers.
"""

from . import layout

_ACCEL = ["adaptive", "flat"]
_SCROLL = ["no-scroll", "two-finger", "edge", "on-button-down"]


def _pointer(device: str, label: str, touchpad: bool = False) -> list[dict]:
    p = f"input/{device}"
    out = [{"kind": "offflag", "path": p, "label": f"{label} enabled", "default": True,
            "hint": f"Off ignores every {label.lower()}"}]
    if touchpad:
        out += [
            {"kind": "flag", "path": f"{p}/tap", "label": "Tap to click"},
            {"kind": "bool", "path": f"{p}/drag", "label": "Tap and drag", "default": True},
            {"kind": "flag", "path": f"{p}/drag-lock", "label": "Drag lock",
             "hint": "Lifting the finger briefly does not end a drag"},
            {"kind": "flag", "path": f"{p}/dwt", "label": "Disable while typing"},
            {"kind": "flag", "path": f"{p}/dwtp", "label": "Disable while the trackpoint is used"},
            {"kind": "select", "path": f"{p}/tap-button-map", "label": "Two- and three-finger tap",
             "options": ["left-right-middle", "left-middle-right"], "default": "left-right-middle"},
            {"kind": "select", "path": f"{p}/click-method", "label": "Click method",
             "options": ["button-areas", "clickfinger"], "default": ""},
            {"kind": "flag", "path": f"{p}/disabled-on-external-mouse", "label": "Off when a mouse is plugged in"},
        ]
    out += [
        {"kind": "flag", "path": f"{p}/natural-scroll", "label": "Natural scrolling"},
        {"kind": "decimal", "path": f"{p}/accel-speed", "label": "Pointer speed", "min": -1, "max": 1,
         "default": 0.0, "hint": "From -1 (slowest) to 1 (fastest)"},
        {"kind": "segmented", "path": f"{p}/accel-profile", "label": "Acceleration", "options": _ACCEL,
         "default": "adaptive"},
    ]
    if device in ("touchpad", "mouse"):
        out.append({"kind": "decimal", "path": f"{p}/scroll-factor", "label": "Scroll speed", "min": 0, "max": 100,
                    "default": 1.0})
    out += [
        {"kind": "select", "path": f"{p}/scroll-method", "label": "Scroll method", "options": _SCROLL,
         "default": ""},
        {"kind": "number", "path": f"{p}/scroll-button", "label": "Scroll button", "min": 0, "max": 1000,
         "default": 274, "hint": "Evdev code of the button for on-button-down scrolling, e.g. 274 (middle)"},
        {"kind": "flag", "path": f"{p}/scroll-button-lock", "label": "Scroll button lock",
         "hint": "Press once to start scrolling, again to stop"},
        {"kind": "flag", "path": f"{p}/left-handed", "label": "Left-handed"},
        {"kind": "flag", "path": f"{p}/middle-emulation", "label": "Middle-click emulation",
         "hint": "Pressing left and right together clicks middle"},
    ]
    return out


ANIMATIONS = [
    ("workspace-switch", "Workspace switch"), ("window-open", "Window open"),
    ("window-close", "Window close"), ("horizontal-view-movement", "Scrolling the view"),
    ("window-movement", "Window movement"), ("window-resize", "Window resize"),
    ("config-notification-open-close", "Config notification"),
    ("exit-confirmation-open-close", "Exit confirmation"), ("screenshot-ui-open", "Screenshot UI"),
    ("overview-open-close", "Overview"), ("recent-windows-close", "Alt-Tab close"),
]
CURVES = ["ease-out-quad", "ease-out-cubic", "ease-out-expo", "linear"]

PAGES = {
    "appearance": {
        "title": "Appearance & blur",
        "intro": "Shadows, tabs, blur and the cursor. Focus ring and border are on the Layout page.",
        "groups": [
            {"title": "Windows", "settings": [
                {"kind": "flag", "path": "prefer-no-csd", "label": "Prefer server-side decorations",
                 "hint": "Asks apps to drop their own title bars and shadows"},
                {"kind": "color", "path": "layout/background-color", "label": "Workspace background",
                 "default": ""},
                {"kind": "onoff", "path": "layout/shadow", "label": "Window shadows", "default": False},
                {"kind": "number", "path": "layout/shadow/softness", "label": "Shadow softness",
                 "unit": "px", "min": 0, "max": 200, "default": 30},
                {"kind": "number", "path": "layout/shadow/spread", "label": "Shadow spread",
                 "unit": "px", "min": -100, "max": 200, "default": 5},
                {"kind": "xy", "path": "layout/shadow/offset", "label": "Shadow offset", "default": [0, 5]},
                {"kind": "color", "path": "layout/shadow/color", "label": "Shadow color", "default": "#0007"},
                {"kind": "bool", "path": "layout/shadow/draw-behind-window", "label": "Shadow behind window",
                 "default": False, "hint": "For windows that are see-through or have rounded corners"},
                {"kind": "onoff", "path": "layout/insert-hint", "label": "Insert hint", "default": True,
                 "hint": "Shows where a dragged window will land"},
                {"kind": "color", "path": "layout/insert-hint/color", "label": "Insert hint color",
                 "default": "#ffc87f80"},
            ]},
            {"title": "Tabs", "settings": [
                {"kind": "onoff", "path": "layout/tab-indicator", "label": "Tab indicator", "default": True},
                {"kind": "flag", "path": "layout/tab-indicator/hide-when-single-tab", "label": "Hide with one tab"},
                {"kind": "flag", "path": "layout/tab-indicator/place-within-column", "label": "Inside the column"},
                {"kind": "segmented", "path": "layout/tab-indicator/position", "label": "Position",
                 "options": ["left", "right", "top", "bottom"], "default": "left"},
                {"kind": "number", "path": "layout/tab-indicator/width", "label": "Width", "unit": "px",
                 "min": 0, "max": 64, "default": 4},
                {"kind": "number", "path": "layout/tab-indicator/gap", "label": "Gap to the window", "unit": "px",
                 "min": -64, "max": 64, "default": 5},
                {"kind": "number", "path": "layout/tab-indicator/gaps-between-tabs", "label": "Gap between tabs",
                 "unit": "px", "min": 0, "max": 64, "default": 0},
                {"kind": "number", "path": "layout/tab-indicator/corner-radius", "label": "Corner radius",
                 "unit": "px", "min": 0, "max": 64, "default": 0},
            ]},
            {"title": "Blur", "settings": [
                {"kind": "offflag", "path": "blur", "label": "Blur", "default": True,
                 "hint": "Windows and layers ask for blur with background-effect rules"},
                {"kind": "number", "path": "blur/passes", "label": "Passes", "min": 1, "max": 31, "default": 3,
                 "hint": "More passes blur more and cost more"},
                {"kind": "decimal", "path": "blur/offset", "label": "Offset", "min": 0, "max": 100, "default": 3.0},
                {"kind": "decimal", "path": "blur/noise", "label": "Noise", "min": 0, "max": 1, "default": 0.02,
                 "hint": "Hides banding in smooth gradients"},
                {"kind": "decimal", "path": "blur/saturation", "label": "Saturation", "min": 0, "max": 10,
                 "default": 1.5},
            ]},
            {"title": "Cursor", "settings": [
                {"kind": "text", "path": "cursor/xcursor-theme", "label": "Cursor theme", "default": "default"},
                {"kind": "number", "path": "cursor/xcursor-size", "label": "Cursor size", "unit": "px",
                 "min": 8, "max": 256, "default": 24},
                {"kind": "flag", "path": "cursor/hide-when-typing", "label": "Hide while typing"},
                {"kind": "number", "path": "cursor/hide-after-inactive-ms", "label": "Hide after no movement",
                 "unit": "ms", "min": 0, "max": 600000, "default": 0, "hint": "0 or not set: never"},
            ]},
        ],
    },
    "animations": {
        "title": "Animations",
        "intro": "Each animation is a spring or an easing curve. Default keeps niri's own.",
        "groups": [
            {"title": "All animations", "settings": [
                {"kind": "flag", "path": "animations/off", "label": "Turn off all animations"},
                {"kind": "decimal", "path": "animations/slowdown", "label": "Slowdown", "min": 0.01, "max": 100,
                 "default": 1.0, "hint": "Above 1 slows every animation down, below 1 speeds it up"},
            ]},
            {"title": "Individual animations", "settings": [
                {"kind": "animation", "path": f"animations/{name}", "label": label} for name, label in ANIMATIONS
            ]},
        ],
    },
    "workspaces": {
        "title": "Workspaces",
        "intro": "Named workspaces always exist, in this order, even when empty.",
        "groups": [
            {"title": "Named workspaces", "settings": [
                {"kind": "workspaces", "path": "workspace", "label": "Named workspaces"},
            ]},
            {"title": "Behaviour", "settings": [
                {"kind": "flag", "path": "input/workspace-auto-back-and-forth",
                 "label": "Back and forth", "hint": "Switching to the current workspace goes to the previous one"},
                {"kind": "flag", "path": "layout/empty-workspace-above-first",
                 "label": "Empty workspace above first", "hint": "Keeps an empty workspace at the very start too"},
            ]},
        ],
    },
    "overview": {
        "title": "Overview & Alt-Tab",
        "intro": "The zoomed-out overview, and the recent-windows switcher. Its keys are in recent-windows › binds.",
        "groups": [
            {"title": "Overview", "settings": [
                {"kind": "decimal", "path": "overview/zoom", "label": "Zoom", "min": 0.0001, "max": 0.75,
                 "default": 0.5, "hint": "How small workspaces get"},
                {"kind": "color", "path": "overview/backdrop-color", "label": "Backdrop", "default": "#262626"},
                {"kind": "offflag", "path": "overview/workspace-shadow", "label": "Workspace shadows",
                 "default": True},
                {"kind": "number", "path": "overview/workspace-shadow/softness", "label": "Shadow softness",
                 "unit": "px", "min": 0, "max": 200, "default": 40},
                {"kind": "number", "path": "overview/workspace-shadow/spread", "label": "Shadow spread",
                 "unit": "px", "min": -100, "max": 200, "default": 10},
                {"kind": "xy", "path": "overview/workspace-shadow/offset", "label": "Shadow offset",
                 "default": [0, 10]},
                {"kind": "color", "path": "overview/workspace-shadow/color", "label": "Shadow color",
                 "default": "#00000050"},
            ]},
            {"title": "Alt-Tab", "settings": [
                {"kind": "offflag", "path": "recent-windows", "label": "Recent-windows switcher", "default": True},
                {"kind": "number", "path": "recent-windows/debounce-ms", "label": "Count as visited after",
                 "unit": "ms", "min": 0, "max": 10000, "default": 750,
                 "hint": "A window focused for less time does not move up the list"},
                {"kind": "number", "path": "recent-windows/open-delay-ms", "label": "Show the switcher after",
                 "unit": "ms", "min": 0, "max": 10000, "default": 150,
                 "hint": "A quick Alt-Tab switches without showing it"},
                {"kind": "color", "path": "recent-windows/highlight/active-color", "label": "Highlight",
                 "default": "#999999ff"},
                {"kind": "color", "path": "recent-windows/highlight/urgent-color", "label": "Urgent highlight",
                 "default": "#ff9999ff"},
                {"kind": "number", "path": "recent-windows/highlight/padding", "label": "Highlight padding",
                 "unit": "px", "min": 0, "max": 200, "default": 30},
                {"kind": "number", "path": "recent-windows/highlight/corner-radius", "label": "Highlight corners",
                 "unit": "px", "min": 0, "max": 200, "default": 0},
                {"kind": "number", "path": "recent-windows/previews/max-height", "label": "Preview height",
                 "unit": "px", "min": 1, "max": 4000, "default": 480},
                {"kind": "decimal", "path": "recent-windows/previews/max-scale", "label": "Preview scale",
                 "min": 0.01, "max": 1, "default": 0.5},
            ]},
        ],
    },
    "keyboard": {
        "title": "Keyboard",
        "intro": "Layouts come from xkb. Leave them empty to follow the system setting (localectl).",
        "groups": [
            {"title": "Layout", "settings": [
                {"kind": "text", "path": "input/keyboard/xkb/layout", "label": "Layouts", "default": "",
                 "hint": "Comma-separated, e.g. us,fi"},
                {"kind": "text", "path": "input/keyboard/xkb/variant", "label": "Variants", "default": ""},
                {"kind": "text", "path": "input/keyboard/xkb/options", "label": "Options", "default": "",
                 "hint": "e.g. grp:win_space_toggle,ctrl:nocaps"},
                {"kind": "text", "path": "input/keyboard/xkb/model", "label": "Model", "default": ""},
                {"kind": "text", "path": "input/keyboard/xkb/file", "label": "Keymap file", "default": "",
                 "hint": "A .xkb file used instead of everything above"},
                {"kind": "segmented", "path": "input/keyboard/track-layout", "label": "Remember layout",
                 "options": ["global", "window"], "default": "global"},
            ]},
            {"title": "Typing", "settings": [
                {"kind": "number", "path": "input/keyboard/repeat-delay", "label": "Repeat delay", "unit": "ms",
                 "min": 1, "max": 5000, "default": 600},
                {"kind": "number", "path": "input/keyboard/repeat-rate", "label": "Repeat rate", "unit": "/s",
                 "min": 0, "max": 255, "default": 25},
                {"kind": "flag", "path": "input/keyboard/numlock", "label": "Num Lock on at startup"},
            ]},
            {"title": "Modifier", "settings": [
                {"kind": "select", "path": "input/mod-key", "label": "Mod key",
                 "options": ["Super", "Alt", "Ctrl", "Shift", "ISO_Level3_Shift", "ISO_Level5_Shift"],
                 "default": "Super", "hint": "What Mod means in key bindings"},
                {"kind": "select", "path": "input/mod-key-nested", "label": "Mod key when nested",
                 "options": ["Super", "Alt", "Ctrl", "Shift", "ISO_Level3_Shift", "ISO_Level5_Shift"],
                 "default": "Alt", "hint": "When niri runs as a window inside another session"},
                {"kind": "flag", "path": "input/disable-power-key-handling", "label": "Ignore the power key",
                 "hint": "Leave it to systemd-logind"},
            ]},
        ],
    },
    "pointer": {
        "title": "Touchpad & mouse",
        "intro": "Settings per kind of pointing device, and how focus follows the pointer.",
        "groups": [
            {"title": "Behaviour", "settings": [
                {"kind": "flag", "path": "input/focus-follows-mouse", "label": "Focus follows mouse"},
                {"kind": "flag", "path": "input/warp-mouse-to-focus", "label": "Move pointer to focused window"},
            ]},
            {"title": "Touchpad", "settings": _pointer("touchpad", "Touchpad", touchpad=True)},
            {"title": "Mouse", "settings": _pointer("mouse", "Mouse")},
            {"title": "Trackpoint", "settings": _pointer("trackpoint", "Trackpoint")},
            {"title": "Trackball", "settings": _pointer("trackball", "Trackball")},
        ],
    },
    "tablet": {
        "title": "Tablet & touch",
        "intro": "Drawing tablets and touch screens. Map each to one output so it lines up.",
        "groups": [
            {"title": "Tablet", "settings": [
                {"kind": "offflag", "path": "input/tablet", "label": "Tablet enabled", "default": True},
                {"kind": "text", "path": "input/tablet/map-to-output", "label": "Map to output", "default": "",
                 "suggest": "outputs"},
                {"kind": "flag", "path": "input/tablet/map-to-focused-output", "label": "Map to the focused output"},
                {"kind": "flag", "path": "input/tablet/left-handed", "label": "Left-handed"},
                {"kind": "text", "path": "input/tablet/calibration-matrix", "label": "Calibration matrix",
                 "numbers": 6, "default": "", "hint": "Six numbers, e.g. 1 0 0 0 1 0"},
            ]},
            {"title": "Touch screen", "settings": [
                {"kind": "offflag", "path": "input/touch", "label": "Touch enabled", "default": True},
                {"kind": "text", "path": "input/touch/map-to-output", "label": "Map to output", "default": "",
                 "suggest": "outputs"},
                {"kind": "text", "path": "input/touch/calibration-matrix", "label": "Calibration matrix",
                 "numbers": 6, "default": "", "hint": "Six numbers, e.g. 1 0 0 0 1 0"},
            ]},
        ],
    },
    "gestures": {
        "title": "Gestures & hot corners",
        "intro": "Scrolling while dragging near an edge, and corners that open the overview.",
        "groups": [
            {"title": "Hot corners", "settings": [
                {"kind": "offflag", "path": "gestures/hot-corners", "label": "Hot corners", "default": True,
                 "hint": "With no corner picked below, the top-left corner is used"},
                {"kind": "flag", "path": "gestures/hot-corners/top-left", "label": "Top left"},
                {"kind": "flag", "path": "gestures/hot-corners/top-right", "label": "Top right"},
                {"kind": "flag", "path": "gestures/hot-corners/bottom-left", "label": "Bottom left"},
                {"kind": "flag", "path": "gestures/hot-corners/bottom-right", "label": "Bottom right"},
            ]},
            {"title": "Drag near the side edges", "settings": [
                {"kind": "number", "path": "gestures/dnd-edge-view-scroll/trigger-width", "label": "Edge width",
                 "unit": "px", "min": 0, "max": 1000, "default": 30},
                {"kind": "number", "path": "gestures/dnd-edge-view-scroll/delay-ms", "label": "Delay",
                 "unit": "ms", "min": 0, "max": 10000, "default": 100},
                {"kind": "number", "path": "gestures/dnd-edge-view-scroll/max-speed", "label": "Top speed",
                 "unit": "px/s", "min": 0, "max": 100000, "default": 1500},
            ]},
            {"title": "Drag near the top and bottom edges", "settings": [
                {"kind": "number", "path": "gestures/dnd-edge-workspace-switch/trigger-height",
                 "label": "Edge height", "unit": "px", "min": 0, "max": 1000, "default": 50},
                {"kind": "number", "path": "gestures/dnd-edge-workspace-switch/delay-ms", "label": "Delay",
                 "unit": "ms", "min": 0, "max": 10000, "default": 100},
                {"kind": "number", "path": "gestures/dnd-edge-workspace-switch/max-speed", "label": "Top speed",
                 "unit": "px/s", "min": 0, "max": 100000, "default": 1500},
            ]},
        ],
    },
    "startup": {
        "title": "Startup apps",
        "intro": "Run once when niri starts. Changes apply the next time niri starts.",
        "groups": [
            {"title": "Commands", "settings": [
                {"kind": "startup", "path": "spawn-at-startup", "label": "Programs",
                 "hint": "A program and its arguments, run directly"},
                {"kind": "startup", "path": "spawn-sh-at-startup", "label": "Shell commands",
                 "hint": "Run with sh -c, so pipes and ~ work"},
            ]},
            {"title": "Xwayland", "settings": [
                {"kind": "offflag", "path": "xwayland-satellite", "label": "Xwayland for X11 apps",
                 "default": True, "hint": "niri starts xwayland-satellite when an X11 app connects"},
                {"kind": "text", "path": "xwayland-satellite/path", "label": "xwayland-satellite path",
                 "default": "xwayland-satellite"},
            ]},
        ],
    },
    "environment": {
        "title": "Environment",
        "intro": "Variables set for every program niri starts, including startup apps.",
        "groups": [
            {"title": "Variables", "settings": [
                {"kind": "environment", "path": "environment", "label": "Variables"},
            ]},
        ],
    },
    "misc": {
        "title": "Miscellaneous",
        "intro": "Screenshots, clipboard, the hotkey overlay and config notifications.",
        "groups": [
            {"title": "Session", "settings": [
                {"kind": "text", "path": "screenshot-path", "label": "Screenshot file",
                 "default": "~/Pictures/Screenshots/Screenshot from %Y-%m-%d %H-%M-%S.png",
                 "hint": "strftime codes like %Y are filled in"},
                {"kind": "flag", "path": "clipboard/disable-primary", "label": "No middle-click paste",
                 "hint": "Turns off the primary selection"},
                {"kind": "flag", "path": "hotkey-overlay/skip-at-startup", "label": "No hotkey overlay at startup"},
                {"kind": "flag", "path": "hotkey-overlay/hide-not-bound", "label": "Hide unbound actions in the overlay"},
                {"kind": "flag", "path": "config-notification/disable-failed",
                 "label": "No notification when the config fails to load"},
            ]},
        ],
    },
}
PAGES["layout"] = {"title": "Layout", "intro": "", "groups": [{"title": "", "settings": layout.SETTINGS}]}

# Top-level sections: (section, page id or "source", what covers it)
COVERAGE = [
    ("input", "keyboard", "Keyboard; Touchpad & mouse; Tablet & touch; Workspaces"),
    ("output", "displays", "Displays"),
    ("binds", "binds", "Key bindings"),
    ("switch-events", "source", "Lid and tablet-mode actions: edit in Config files"),
    ("layout", "layout", "Layout; Appearance & blur"),
    ("window-rule", "window-rules", "Window rules"),
    ("layer-rule", "source", "Layer rules page not built yet (issue #8)"),
    ("animations", "animations", "Animations"),
    ("gestures", "gestures", "Gestures & hot corners"),
    ("recent-windows", "overview", "Overview & Alt-Tab; its binds in Config files"),
    ("overview", "overview", "Overview & Alt-Tab"),
    ("workspace", "workspaces", "Workspaces"),
    ("spawn-at-startup", "startup", "Startup apps"),
    ("spawn-sh-at-startup", "startup", "Startup apps"),
    ("xwayland-satellite", "startup", "Startup apps"),
    ("environment", "environment", "Environment"),
    ("cursor", "appearance", "Appearance & blur"),
    ("blur", "appearance", "Appearance & blur"),
    ("prefer-no-csd", "appearance", "Appearance & blur"),
    ("screenshot-path", "misc", "Miscellaneous"),
    ("clipboard", "misc", "Miscellaneous"),
    ("hotkey-overlay", "misc", "Miscellaneous"),
    ("config-notification", "misc", "Miscellaneous"),
    ("include", "files", "Config files"),
    ("debug", "source", "Debug options: edit in Config files"),
]


def page_for(path: str) -> str | None:
    """The page that edits a config path, for the source editor's link."""
    if not path:
        return None
    head = path.split("/")[0]
    name = head.split("[")[0].split("#")[0]
    best, size = None, -1
    for page_id, page in PAGES.items():
        for group in page["groups"]:
            for s in group["settings"]:
                p = s["path"]
                if (path == p or path.startswith(p + "/")) and len(p) > size:
                    best, size = page_id, len(p)
    if best:
        return best
    if name == "layout":
        return "layout"
    if name == "input":
        sub = path.split("/")[1] if "/" in path else ""
        return {"keyboard": "keyboard", "touchpad": "pointer", "mouse": "pointer", "trackpoint": "pointer",
                "trackball": "pointer", "tablet": "tablet", "touch": "tablet"}.get(sub, "keyboard")
    page = next((p for s, p, _ in COVERAGE if s == name), None)
    return None if page == "source" else page
