"""Displays: outputs as niri reports them, the drafts in the config, and the
timed trial that keeps a wrong mode or scale from locking the user out.

`DisplayModel` has no Qt and takes its I/O as functions, so it runs in tests
without niri. A draft value is what the config (with unsaved changes) says;
where the config says nothing, it is what niri is doing now.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from . import ipc

TRIAL_SECONDS = 15
TRANSFORMS = ["normal", "90", "180", "270", "flipped", "flipped-90", "flipped-180", "flipped-270"]
# Keys that go through the timed trial before they may be saved.
RISKY = ("off", "mode", "scale", "transform", "position", "variable-refresh-rate")
SNAP = 24  # logical pixels


def _transform_name(live: str) -> str:
    """IPC spelling (Normal, 90, Flipped90) to config spelling (normal, flipped-90)."""
    t = str(live).lower().replace("_", "").replace("-", "")
    if t.startswith("flipped") and t != "flipped":
        return "flipped-" + t[7:]
    return t if t in TRANSFORMS else "normal"


def mode_value(mode: dict) -> str:
    return f"{mode['width']}x{mode['height']}@{mode['refresh_rate'] / 1000:.3f}"


def mode_label(mode: dict) -> str:
    star = "  (preferred)" if mode.get("is_preferred") else ""
    return f"{mode['width']}×{mode['height']} @ {mode['refresh_rate'] / 1000:.3f} Hz{star}"


def _parse_mode(value: str) -> tuple[int, int] | None:
    try:
        size = str(value).split("@")[0]
        w, h = size.lower().split("x")
        return int(w), int(h)
    except ValueError:
        return None


def snap_position(moving: dict, x: float, y: float, others: list[dict]) -> tuple[int, int, str]:
    """Snap a dragged output to the edges of the others.

    Returns the position and which of the moving output's edges snapped
    ("left", "right", "top", "bottom", or "").
    """
    w, h = moving["w"], moving["h"]
    best_x = best_y = None
    edge = ""
    for o in others:
        ox, oy, ow, oh = o["x"], o["y"], o["w"], o["h"]
        for target, name in ((ox + ow, "left"), (ox - w, "right"), (ox, ""), (ox + ow - w, "")):
            d = abs(x - target)
            if d <= SNAP and (best_x is None or d < best_x[0]):
                best_x = (d, target, name)
        for target, name in ((oy + oh, "top"), (oy - h, "bottom"), (oy, ""), (oy + oh - h, "")):
            d = abs(y - target)
            if d <= SNAP and (best_y is None or d < best_y[0]):
                best_y = (d, target, name)
    if best_x:
        x, edge = best_x[1], best_x[2]
    if best_y:
        y, edge = best_y[1], edge or best_y[2]
    return round(x), round(y), edge


class DisplayModel:
    def __init__(self, config_fn, outputs_fn=ipc.outputs, run_fn=None, niri_bin="niri"):
        self._config = config_fn      # callable: the Config can be replaced on reload
        self._outputs_fn = outputs_fn
        self._run = run_fn or (lambda argv: subprocess.run(argv, capture_output=True, text=True))
        self.niri_bin = niri_bin
        self.live: dict[str, dict] = {}
        self._guard: subprocess.Popen | None = None
        self.trial_error = ""

    @property
    def config(self):
        return self._config()

    def refresh(self) -> bool:
        live = self._outputs_fn() or {}
        changed = live != self.live
        self.live = live
        return changed

    # -- matching config sections to outputs

    def _config_keys(self) -> list[str]:
        return [p[7:-1] for p in self.config.tree.list("") if p.startswith("output[")]

    def key_for(self, name: str) -> str:
        """The name the config uses for this output: connector or "make model serial"."""
        out = self.live.get(name, {})
        ident = " ".join(str(out.get(k) or "") for k in ("make", "model", "serial")).strip().lower()
        for key in self._config_keys():
            if key.lower() == name.lower() or (ident and key.lower() == ident):
                return key
        return name

    def path(self, name: str, key: str = "") -> str:
        base = f"output[{self.key_for(name)}]"
        return f"{base}/{key}" if key else base

    def names(self) -> list[str]:
        """Connected outputs first, then ones that are only in the config."""
        names = sorted(self.live)
        known = {self.key_for(n).lower() for n in names}
        return names + [k for k in self._config_keys() if k.lower() not in known]

    # -- live state, in config terms

    def live_state(self, name: str) -> dict | None:
        out = self.live.get(name)
        if not out:
            return None
        logical = out.get("logical")
        modes = out.get("modes") or []
        current = out.get("current_mode")
        mode = mode_value(modes[current]) if current is not None and current < len(modes) else ""
        state = {"enabled": logical is not None, "mode": mode,
                 "vrr": "on" if out.get("vrr_enabled") else "off"}
        if logical:
            state.update(scale=float(logical["scale"]), transform=_transform_name(logical["transform"]),
                         x=int(logical["x"]), y=int(logical["y"]))
        return state

    # -- drafts

    def draft(self, name: str) -> dict:
        cfg = self.config
        live = self.live_state(name) or {}
        get = lambda key: cfg.get(self.path(name, key))
        vrr_node = get("variable-refresh-rate")
        if vrr_node is None or vrr_node is False:
            vrr = "off"
        elif isinstance(vrr_node, dict) and vrr_node.get("props", {}).get("on-demand"):
            vrr = "on-demand"
        else:
            vrr = "on"
        pos = get("position")
        pos = pos.get("props", {}) if isinstance(pos, dict) else {}
        mode = get("mode")
        mode = mode if isinstance(mode, str) else None
        scale = get("scale")
        return {
            "enabled": get("off") is None,
            "mode": mode or live.get("mode", ""),
            "scale": float(scale) if isinstance(scale, (int, float)) and not isinstance(scale, bool)
                     else live.get("scale", 1.0),
            "transform": get("transform") or live.get("transform", "normal"),
            "x": int(pos["x"]) if "x" in pos else live.get("x", 0),
            "y": int(pos["y"]) if "y" in pos else live.get("y", 0),
            "vrr": vrr,
        }

    def logical_size(self, name: str, draft: dict) -> tuple[int, int]:
        size = _parse_mode(draft["mode"])
        if size is None:
            logical = (self.live.get(name) or {}).get("logical") or {}
            return int(logical.get("width", 1920)), int(logical.get("height", 1080))
        w, h = size[0] / (draft["scale"] or 1), size[1] / (draft["scale"] or 1)
        if draft["transform"] in ("90", "270", "flipped-90", "flipped-270"):
            w, h = h, w
        return round(w), round(h)

    def describe(self, name: str) -> dict:
        """Everything the page shows for one output."""
        out = self.live.get(name) or {}
        d = self.draft(name)
        w, h = self.logical_size(name, d)
        modes = out.get("modes") or []
        mode_list = [{"label": mode_label(m), "value": mode_value(m)} for m in modes]
        if d["mode"] and all(m["value"] != d["mode"] for m in mode_list):
            mode_list.insert(0, {"label": d["mode"].replace("x", "×").replace("@", " @ ") + "  (from config)",
                                 "value": d["mode"]})
        model = out.get("model") or ""
        cfg = self.config
        kdl = cfg.tree.node_text(self.path(name))
        overrides = [p.rsplit("/", 1)[1] for p in cfg.tree.list(self.path(name, "layout"))]
        key = self.key_for(name).lower()
        ident = " ".join(str(out.get(k) or "") for k in ("make", "model", "serial")).strip().lower()
        workspaces = []
        for p in cfg.tree.list(""):
            if p.startswith("workspace["):
                target = str(cfg.get(p + "/open-on-output") or "").lower()
                if target and target in (name.lower(), key, ident):
                    workspaces.append(p[10:-1])
        return {
            "name": name, "connected": bool(out), "model": model,
            "title": f"{name} · {model}" if model else name,
            "key": self.key_for(name), "w": w, "h": h, **d,
            "modes": mode_list, "vrrSupported": bool(out.get("vrr_supported")),
            "backdrop": str(cfg.get(self.path(name, "backdrop-color")) or ""),
            "kdl": kdl or f'// nothing set for {self.key_for(name)} yet; niri picks mode, scale and position',
            "overrides": overrides, "workspaces": workspaces,
            "needsTry": name in self.untried(),
        }

    # -- editing the draft (pending config changes; nothing reaches niri yet)

    def set_mode(self, name: str, value: str):
        self.config.set(self.path(name, "mode"), value)

    def set_scale(self, name: str, value: float):
        self.config.set(self.path(name, "scale"), round(float(value), 3))

    def set_transform(self, name: str, value: str):
        if value in TRANSFORMS:
            self.config.set(self.path(name, "transform"), value)

    def set_position(self, name: str, x: int, y: int):
        self.config.set(self.path(name, "position"), {"args": [], "props": {"x": int(x), "y": int(y)}})

    def set_vrr(self, name: str, value: str):
        path = self.path(name, "variable-refresh-rate")
        if value == "off":
            self.config.remove(path)
        elif value == "on-demand":
            self.config.set(path, {"args": [], "props": {"on-demand": True}})
        else:
            self.config.set(path, True)

    def set_enabled(self, name: str, on: bool):
        path = self.path(name, "off")
        if on:
            self.config.remove(path)
        else:
            self.config.set(path, True)

    def set_backdrop(self, name: str, color: str):
        path = self.path(name, "backdrop-color")
        if color.strip():
            self.config.set(path, color.strip())
        else:
            self.config.remove(path)

    # -- the timed trial

    def _differences(self, name: str) -> list[str]:
        """Risky properties where the draft differs from what niri is doing."""
        live = self.live_state(name)
        if live is None:
            return []
        d = self.draft(name)
        if not d["enabled"]:
            return ["enabled"] if live["enabled"] else []
        if not live["enabled"]:
            return ["enabled"]
        diffs = []
        if d["mode"] != live["mode"]:
            diffs.append("mode")
        if abs(d["scale"] - live["scale"]) > 0.001:
            diffs.append("scale")
        if d["transform"] != live["transform"]:
            diffs.append("transform")
        if (d["x"], d["y"]) != (live["x"], live["y"]):
            diffs.append("position")
        if d["vrr"] != "on-demand" and d["vrr"] != live["vrr"]:
            diffs.append("vrr")  # on-demand cannot be read back from niri
        return diffs

    def untried(self) -> list[str]:
        """Connected outputs with unsaved risky changes that niri is not showing yet.

        Empty once a trial was kept: niri then already runs the draft.
        """
        pending = self.config.pending
        out = []
        for name in self.live:
            base = self.path(name)
            touched = any(p == f"{base}/{k}" for p in pending for k in RISKY)
            if touched and self._differences(name):
                out.append(name)
        return out

    def _commands(self, name: str, state: dict, keys: list[str]) -> list[list[str]]:
        """`niri msg output` commands that put the given properties of an output at `state`."""
        head = [self.niri_bin, "msg", "output", name]
        if "enabled" in keys:
            if not state["enabled"]:
                return [head + ["off"]]
            # Coming back on: niri restores the rest from its own state.
            return [head + ["on"]]
        cmds = []
        if "mode" in keys and state.get("mode"):
            cmds.append(head + ["mode", state["mode"]])
        if "scale" in keys:
            cmds.append(head + ["scale", f"{state['scale']:g}"])
        if "transform" in keys:
            cmds.append(head + ["transform", state["transform"]])
        if "position" in keys:
            cmds.append(head + ["position", "set", str(state["x"]), str(state["y"])])
        if "vrr" in keys:
            cmds.append(head + ["vrr"] + (["--on-demand"] if state["vrr"] == "on-demand" else [])
                        + ["off" if state["vrr"] == "off" else "on"])
        return cmds

    def trial_plan(self) -> tuple[list[list[str]], list[list[str]]]:
        """(commands to apply the drafts, commands that undo them)."""
        apply, undo = [], []
        for name in self.untried():
            keys = self._differences(name)
            apply += self._commands(name, self.draft(name), keys)
            undo = self._commands(name, self.live_state(name), keys) + undo
        return apply, undo

    @property
    def trial_running(self) -> bool:
        return self._guard is not None and self._guard.poll() is None

    def start_trial(self, seconds: float = TRIAL_SECONDS) -> bool:
        """Apply the drafts to niri for a while. The config is not touched.

        The undo commands are handed to a separate guard process first, so the
        revert happens even if this app dies.
        """
        self.trial_error = ""
        if self.trial_running:
            return False
        apply, undo = self.trial_plan()
        if not apply:
            return False
        self._guard = subprocess.Popen(
            [sys.executable, "-m", "niri_settings.output_guard", str(seconds), json.dumps(undo)],
            stdin=subprocess.PIPE, text=True, start_new_session=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for argv in apply:
            result = self._run(argv)
            if getattr(result, "returncode", 0) != 0:
                self.trial_error = (getattr(result, "stderr", "") or "niri refused the change").strip()
                self.end_trial(keep=False)
                return False
        return True

    def end_trial(self, keep: bool):
        """Keep: niri stays as tried and the drafts wait for Save. Otherwise undo now."""
        guard, self._guard = self._guard, None
        if guard is None or guard.poll() is not None:
            return
        try:
            guard.stdin.write("keep\n" if keep else "revert\n")
            guard.stdin.close()
            guard.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass

    # -- profiles: named sets of drafts, kept in the app's own settings

    def snapshot_profile(self) -> dict:
        return {name: self.draft(name) for name in self.live}

    def apply_profile(self, profile: dict):
        for name, d in profile.items():
            if name not in self.live:
                continue
            now = self.draft(name)
            if d["enabled"] != now["enabled"]:
                self.set_enabled(name, d["enabled"])
            if d["mode"] and d["mode"] != now["mode"]:
                self.set_mode(name, d["mode"])
            if abs(d["scale"] - now["scale"]) > 0.001:
                self.set_scale(name, d["scale"])
            if d["transform"] != now["transform"]:
                self.set_transform(name, d["transform"])
            if (d["x"], d["y"]) != (now["x"], now["y"]):
                self.set_position(name, d["x"], d["y"])
            if d["vrr"] != now["vrr"]:
                self.set_vrr(name, d["vrr"])

    def matches_profile(self, profile: dict) -> bool:
        if set(profile) != set(self.live):
            return False
        for name, d in profile.items():
            now = self.draft(name)
            if any(now[k] != d[k] for k in ("enabled", "mode", "transform", "x", "y", "vrr")):
                return False
            if abs(now["scale"] - d["scale"]) > 0.001:
                return False
        return True
