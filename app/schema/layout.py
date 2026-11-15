"""Settings of the `layout` section. Drives the Layout page, hints and search.

Hand-written from niri's Configuration: Layout docs. `since` is the niri
version a key arrived in. Kinds:
  slider     number at `path`
  segmented  one of `options` at `path`
  flag       a bare node: present = on, absent = off
  onoff      a section with `off` / `on` children (focus-ring, border)
  widths     default-column-width, chosen from preset-column-widths
  struts     four numbers under `path`
"""

SETTINGS = [
    {"kind": "slider", "path": "layout/gaps", "label": "Gaps",
     "min": 0, "max": 48, "unit": "px", "default": 16},
    {"kind": "slider", "path": "layout/focus-ring/width", "label": "Focus ring width",
     "min": 0, "max": 12, "unit": "px", "default": 4,
     "swatches": [["Active", "layout/focus-ring/active-color", "#7fc8ff"],
                  ["Inactive", "layout/focus-ring/inactive-color", "#505050"],
                  ["Urgent", "layout/focus-ring/urgent-color", "#9b0000"]]},
    {"kind": "segmented", "path": "layout/center-focused-column",
     "label": "Center focused column",
     "options": ["never", "on-overflow", "always"], "default": "never"},
    {"kind": "widths", "path": "layout/default-column-width",
     "label": "Default column width",
     "presets": "layout/preset-column-widths", "default": 0.5,
     "hint": "Chips are your preset-column-widths."},
    {"kind": "onoff", "path": "layout/focus-ring", "label": "Focus ring",
     "default": True, "hint": "Drawn around the focused window only"},
    {"kind": "onoff", "path": "layout/border", "label": "Window border",
     "default": False, "hint": "Drawn inside the gaps, unlike the focus ring"},
    {"kind": "slider", "path": "layout/border/width", "label": "Border width",
     "min": 0, "max": 12, "unit": "px", "default": 4,
     "swatches": [["Active", "layout/border/active-color", "#ffc87f"],
                  ["Inactive", "layout/border/inactive-color", "#505050"],
                  ["Urgent", "layout/border/urgent-color", "#9b0000"]]},
    {"kind": "struts", "path": "layout/struts", "label": "Struts",
     "sides": ["left", "right", "top", "bottom"], "min": -64, "max": 256,
     "hint": "Reserve space at the screen edges, like outer gaps."},
    {"kind": "flag", "path": "layout/always-center-single-column",
     "label": "Always center a single column", "since": "0.1.9",
     "hint": "Centers a lone column whatever the centering mode"},
    {"kind": "flag", "path": "layout/empty-workspace-above-first",
     "label": "Empty workspace above first", "since": "25.01",
     "hint": "Keeps an empty workspace at the very start too"},
    {"kind": "segmented", "path": "layout/default-column-display",
     "label": "Default column display", "since": "25.02",
     "options": ["normal", "tabbed"], "default": "normal"},
]
