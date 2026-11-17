"""niri gradients (`active-gradient from=… to=… angle=… relative-to=… in=…`).

Shared by the window rules editor and the Layout and Appearance pages. In the
app a gradient is {from, to, angle, rel, in}; in the file it is the props of
one node, with niri's defaults left out.
"""

from __future__ import annotations

# Colour spaces a gradient can blend through (`in=`); srgb is niri's default.
SPACES = ["srgb", "srgb-linear", "oklab", "oklch shorter hue", "oklch longer hue",
          "oklch increasing hue", "oklch decreasing hue"]
RELATIVE = ["window", "workspace-view"]   # `window` is niri's default: no relative-to
KEYS = {"from", "to", "angle", "relative-to", "in"}
STATES = ["active", "inactive", "urgent"]


def options(values) -> list[dict]:
    return [{"label": v, "value": v} for v in values]


def read(node) -> dict | None:
    """The app's value for a gradient node, or None when the editor cannot show it."""
    if not isinstance(node, dict) or node.get("args") or node.get("children"):
        return None
    props = node.get("props", {})
    angle = props.get("angle", 180)
    if (set(props) - KEYS or not {"from", "to"} <= set(props)
            or isinstance(angle, bool) or not isinstance(angle, int)):
        return None
    rel, space = str(props.get("relative-to", "window")), str(props.get("in", "srgb"))
    if rel not in RELATIVE or space not in SPACES:
        return None
    return {"from": str(props["from"]), "to": str(props["to"]), "angle": angle, "rel": rel, "in": space}


def props_of(value: dict) -> dict:
    """niri's props for a gradient, leaving out what niri does by default.

    Raises ValueError with a message for the user.
    """
    start, end = str(value.get("from", "")).strip(), str(value.get("to", "")).strip()
    if not start or not end:
        raise ValueError("A gradient needs a from and a to colour")
    try:
        number = float(str(value.get("angle", 180)).strip().replace(",", "."))
    except ValueError:
        number = None
    if number is None or number != int(number):          # niri takes whole degrees only
        raise ValueError("The gradient angle needs a whole number of degrees")
    props = {"from": start, "to": end}
    if int(number) != 180:
        props["angle"] = int(number)
    if value.get("rel", "window") != "window":
        props["relative-to"] = value["rel"]
    if value.get("in", "srgb") != "srgb":
        props["in"] = value["in"]
    return props


def default(state: str) -> dict:
    """A starting gradient for a new active, inactive or urgent gradient."""
    a, b = {"active": ("#80c8ff", "#bbddff"), "inactive": ("#505050", "#808080"),
            "urgent": ("#880000", "#aa3333")}[state]
    return {"from": a, "to": b, "angle": 45, "rel": "window", "in": "srgb"}
