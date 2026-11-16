"""The Window rules page's object in QML: a thin Qt layer over RulesModel."""

from __future__ import annotations

import os
import threading
import time

from PySide6.QtCore import Property, QObject, Signal, Slot

from . import ipc, niri_core
from . import rules as rl
from .rules import NAME, RulesModel
from .schema import window_rules as schema

_SIZE_KINDS = [{"label": "proportion", "value": "proportion"}, {"label": "fixed px", "value": "fixed"},
               {"label": "app decides", "value": ""}]
_WIDE = {"size", "position", "kdl", "xy"}


def _options(values) -> list[dict]:
    return [{"label": v, "value": v} for v in values]


def _number(text, kind: str):
    value = float(str(text).strip().replace(",", "."))
    if kind == "int":
        if value != int(value):
            raise ValueError
        return int(value)
    return value


class RulesView(QObject):
    changed = Signal()
    _picked = Signal(object)       # from the pick-window thread

    def __init__(self, backend, model: RulesModel | None = None):
        super().__init__(backend)
        self.backend = backend
        self.model = model or RulesModel(lambda: backend.config)
        self._index = 0
        self._window = None        # selected window id
        self._picking = False
        self._error = ""           # why the last edit was refused
        self._casts = (0.0, None)  # (when, window ids being cast)
        self._cache = {}
        backend.changed.connect(self._refresh)
        backend.stateChanged.connect(self._refresh)
        self._picked.connect(self._on_picked)

    def _refresh(self):
        self._cache = {}
        self.changed.emit()

    def _cached(self, name, build):
        if name not in self._cache:
            self._cache[name] = build()
        return self._cache[name]

    # -- data

    def _rules(self) -> list[dict]:
        return self._cached("rules", self.model.rules)

    def _sources(self) -> list[dict]:
        return self._cached("sources", self.model.sources)

    def _current(self) -> int:
        n = len(self._rules())
        return max(0, min(self._index, n - 1)) if n else -1

    def _windows(self) -> dict:
        def build():
            stream = getattr(self.backend, "_stream", None)
            state = self.backend.state
            if stream is not None:
                with stream.lock:
                    return {k: dict(v) for k, v in state.windows.items()}, \
                           {k: dict(v) for k, v in state.workspaces.items()}
            return {k: dict(v) for k, v in state.windows.items()}, dict(state.workspaces)
        return self._cached("windows", build)

    def _cast_targets(self):
        when, targets = self._casts
        if self.backend.connected and time.monotonic() - when > 2:
            targets = rl.cast_targets(ipc.request("Casts"))
            self._casts = (time.monotonic(), targets)
        return targets

    def _facts(self) -> dict:
        def build():
            windows, workspaces = self._windows()
            return rl.window_facts(windows, workspaces, self._cast_targets() if windows else set())
        return self._cached("facts", build)

    def _verdicts(self, wid) -> list:
        f = self._facts().get(wid)
        if f is None:
            return []
        return self._cached(f"v{wid}", lambda: [rl.check_rule(r, f) for r in self._rules()])

    def _rule_error(self, index: int) -> str:
        """niri's validation error when it points into this rule."""
        e = getattr(self.backend, "_error", None)
        if not e or not e.get("file") or not e.get("line") or index < 0:
            return ""
        src = self._sources()[index]
        first = src["line"] - (1 if src["comment"] else 0)
        if os.path.normpath(e["file"]) == os.path.normpath(src["file"]) and first <= e["line"] <= src["end_line"]:
            return e.get("summary") or "niri rejected this rule"
        return ""

    def _edit(self, fn) -> bool:
        self._error = ""
        try:
            ok = self.backend._edit(fn)
        except (ValueError, niri_core.KdlError) as e:
            self._error = getattr(e, "message", None) or str(e)
            self._refresh()
            return False
        if ok:
            self.backend._touch()
        return ok

    # -- the rule list

    @Property(bool, constant=True)
    def connected(self):
        return bool(self.backend.connected)

    @Property(int, notify=changed)
    def selected(self):
        return self._current()

    @Property("QVariantList", notify=changed)
    def rules(self):
        def build():
            sources = self._sources()
            verdicts = self._verdicts(self._window) if self._window is not None else []
            out = []
            for i, rule in enumerate(self._rules()):
                out.append({"index": i, "title": rl.title(rule), "subtitle": rl.summary(rule),
                            "where": f"{os.path.basename(sources[i]['file'])}:{sources[i]['line']}",
                            "status": verdicts[i].status if verdicts else "",
                            "error": self._rule_error(i) != ""})
            return out
        return self._cached("list", build)

    @Property("QVariantList", constant=True)
    def templates(self):
        return [{"id": t["id"], "title": t["title"], "description": t["description"],
                 "needsApp": bool(t.get("needs_app"))} for t in schema.TEMPLATES]

    @Slot(int)
    def select(self, index):
        self._index = index
        self._error = ""
        self._refresh()

    @Slot(str)
    def newRule(self, template_id):
        template = next((t for t in schema.TEMPLATES if t["id"] == template_id), schema.TEMPLATES[-1])
        app = None
        if self._window is not None:
            app = (self._windows()[0].get(self._window) or {}).get("app_id")
        rule = rl.from_template(template, app)
        if template["id"] == "blank" and app:
            rule["children"] = [{"name": "match", "args": [], "props": {"app-id": niri_core.Raw(rl.exact(app))}}]
            rule["comment"] = f"Rule for {app}"
        holder = {}
        if self._edit(lambda: holder.setdefault("at", self.model.add(rule))):
            self._index = holder["at"]
            self._refresh()

    @Slot()
    def removeRule(self):
        i = self._current()
        if i >= 0 and self._edit(lambda: self.model.remove(i)):
            self._index = max(0, i - 1) if i >= len(self._rules()) else i
            self._refresh()

    @Slot(int)
    def moveRule(self, delta):
        i = self._current()
        holder = {}
        if i >= 0 and self._edit(lambda: holder.setdefault("to", self.model.move(i, delta))):
            self._index = holder["to"]
            self._refresh()

    @Slot(str)
    def rename(self, name):
        i = self._current()
        if i >= 0 and " ".join(name.split()) != self._rules()[i].get("comment", ""):
            self._edit(lambda: self.model.rename(i, name))

    # -- the selected rule

    def _prop_item(self, path: str, node: dict) -> dict:
        known = schema.PROP_PATHS.get(path)
        kind = known["kind"] if known else "kdl"
        args, props, kids = node.get("args", []), node.get("props", {}), node.get("children")
        item = {"path": path, "label": rl.label_of(path), "when": rl.when_of(path),
                "text": rl.tail(node) if not path.endswith("/state") else str(args[0]),
                "options": [], "value": None, "wide": False}
        try:
            if kind == "bool":
                value = args[0] if args else True
                if not isinstance(value, bool):
                    raise TypeError
                item["value"] = value
            elif kind in ("int", "float"):
                if len(args) != 1 or isinstance(args[0], bool) or not isinstance(args[0], (int, float)):
                    raise TypeError
                item["value"] = args[0]
                item["text"] = niri_core.format_value(args[0])
            elif kind in ("enum", "text", "color", "onoff"):
                if len(args) != 1 or props or kids:
                    raise TypeError
                item["value"] = str(args[0])
                if kind == "enum":
                    item["options"] = _options(known["options"])
                elif kind == "onoff":
                    item["options"] = ["on", "off"]
            elif kind == "size":
                kids = kids or []
                if args or props or len(kids) > 1:
                    raise TypeError
                item["options"] = _SIZE_KINDS
                item["sizeKind"] = kids[0]["name"] if kids else ""
                item["sizeValue"] = niri_core.format_value(kids[0]["args"][0]) if kids and kids[0]["args"] else ""
                if item["sizeKind"] not in ("", "proportion", "fixed"):
                    raise TypeError
            elif kind in ("position", "xy"):
                if args or kids or set(props) - {"x", "y", "relative-to"}:
                    raise TypeError
                item["x"] = props.get("x", 0)
                item["y"] = props.get("y", 0)
                item["rel"] = props.get("relative-to", "top-left")
                if kind == "position":
                    item["options"] = _options(known["options"])
        except (TypeError, IndexError, KeyError):
            kind = "kdl"
        item["kind"] = kind
        item["wide"] = kind in _WIDE
        return item

    def _directive_items(self, rule: dict, f: dict | None) -> list[dict]:
        out = []
        for kind, d, props in rl.directives(rule):
            fields = []
            for key, value in props.items():
                known = schema.MATCHER_KEYS.get(key)
                mkind = known["kind"] if known else "regex"
                status = rl.check_matcher(key, value, f)[0] if f else ""
                fields.append({"key": key, "label": known["label"] if known else key, "kind": mkind,
                               "value": value if mkind == "bool" else str(value),
                               "error": rl.regex_error(str(value)) if mkind == "regex" else "",
                               "status": status})
            free = [{"label": m["label"], "value": m["key"]} for m in schema.MATCHERS if m["key"] not in props]
            warn = ""
            if kind == "exclude" and all(k in ("app-id", "title") and str(v) == "" for k, v in props.items()):
                warn = "This exclude line matches every window, so the rule applies to none."
            out.append({"kind": kind, "index": d, "fields": fields, "free": free, "warn": warn,
                        "status": rl.check_directive(props, f)[0] if f else ""})
        return out

    @Property("QVariantMap", notify=changed)
    def detail(self):
        def build():
            i = self._current()
            if i < 0:
                return {"has": False, "error": self._error}
            rule, src = self._rules()[i], self._sources()[i]
            f = self._facts().get(self._window) if self._window is not None else None
            items = [self._prop_item(p, n) for p, n in rl.leaves(rule.get("children", []))]
            used = {it["path"] for it in items}
            addable = [{"label": ("At open: " if p["when"] == "open" else "") + p["label"], "value": p["path"]}
                       for p in schema.PROPS if p["path"] not in used]
            text = src["text"]
            if src["comment"]:
                text = f"// {src['comment']}\n" + text
            matches = [d for d in rl.directives(rule) if d[0] == "match"]
            return {
                "has": True, "index": i, "title": rl.title(rule), "comment": rule.get("comment", ""),
                "where": f"{os.path.basename(src['file'])}:{src['line']}",
                "first": i == 0, "last": i == len(self._rules()) - 1,
                "directives": self._directive_items(rule, f),
                "allWindows": not matches,
                "open": [it for it in items if it["when"] == "open"],
                "always": [it for it in items if it["when"] != "open"],
                "addable": addable,
                "kdl": text,
                "error": self._error or self._rule_error(i),
            }
        return self._cached("detail", build)

    @Property("QVariantList", constant=True)
    def matchers(self):
        return [{"label": m["label"], "value": m["key"]} for m in schema.MATCHERS]

    def _window_value(self, key: str) -> str | None:
        w = self._windows()[0].get(self._window) if self._window is not None else None
        if not w:
            return None
        return w.get("app_id" if key == "app-id" else "title")

    @Slot(str)
    def addDirective(self, kind):
        i = self._current()
        if i < 0:
            return
        app = self._window_value("app-id")
        props = {"app-id": niri_core.Raw(rl.exact(app) if app else "")}
        self._edit(lambda: self.model.add_directive(i, kind, props))

    @Slot(str, int)
    def removeDirective(self, kind, d):
        i = self._current()
        if i >= 0:
            self._edit(lambda: self.model.remove_directive(i, kind, d))

    @Slot(str, int, str, "QVariant")
    def setMatcher(self, kind, d, key, value):
        i = self._current()
        if i < 0:
            return
        if schema.MATCHER_KEYS.get(key, {}).get("kind") == "bool":
            value = bool(value)
        else:
            value = str(value)
        self._edit(lambda: self.model.set_matcher(i, kind, d, key, value))

    @Slot(str, int, str)
    def addMatcher(self, kind, d, key):
        known = schema.MATCHER_KEYS.get(key)
        if not known:
            return
        if known["kind"] == "bool":
            self.setMatcher(kind, d, key, True)
        else:
            have = self._window_value(key)
            self.setMatcher(kind, d, key, rl.exact(have) if have else "")

    @Slot(str, int, str)
    def removeMatcher(self, kind, d, key):
        i = self._current()
        if i < 0:
            return
        props = next((p for k, n, p in rl.directives(self._rules()[i]) if k == kind and n == d), {})
        if set(props) <= {key}:
            self.removeDirective(kind, d)
        else:
            self._edit(lambda: self.model.set_matcher(i, kind, d, key, None))

    @Slot(str)
    def fillFromWindow(self, key):
        """Put the selected window's app-id or title into the first match line."""
        i = self._current()
        have = self._window_value(key)
        if i < 0 or have is None:
            return
        if any(k == "match" for k, _, _ in rl.directives(self._rules()[i])):
            self.setMatcher("match", 0, key, rl.exact(have))
        else:
            self._edit(lambda: self.model.add_directive(i, "match", {key: niri_core.Raw(rl.exact(have))}))

    # -- properties

    def _node_for(self, path: str, value) -> dict:
        known = schema.PROP_PATHS.get(path)
        kind = known["kind"] if known else "kdl"
        if kind == "bool":
            return {"args": [bool(value)], "props": {}}
        if kind in ("int", "float"):
            try:
                number = _number(value, kind)
            except (TypeError, ValueError):
                raise ValueError(f"{rl.label_of(path)} needs {'a whole number' if kind == 'int' else 'a number'}")
            lo, hi = known.get("min"), known.get("max")
            if (lo is not None and number < lo) or (hi is not None and number > hi):
                raise ValueError(f"{rl.label_of(path)} goes from {lo} to {hi}")
            return {"args": [number], "props": {}}
        if kind in ("enum", "text", "color", "onoff"):
            return {"args": [str(value)], "props": {}}
        if kind == "size":
            size_kind, number = value.get("kind", ""), value.get("value", "")
            if not size_kind:
                return {"args": [], "props": {}, "children": []}
            try:
                number = float(str(number).replace(",", "."))
            except ValueError:
                raise ValueError("Type a number: a share of the screen like 0.5, or pixels like 480")
            if size_kind == "fixed":
                number = int(number) if number == int(number) else number
            return {"args": [], "props": {}, "children": [{"name": size_kind, "args": [number], "props": {}}]}
        if kind in ("position", "xy"):
            props = {"x": int(value.get("x", 0)), "y": int(value.get("y", 0))}
            if kind == "position" and value.get("rel", "top-left") != "top-left":
                props["relative-to"] = value["rel"]
            return {"args": [], "props": props}
        text = str(value).strip()
        name = path.rsplit("/", 1)[-1]
        try:
            doc = niri_core.load_string(f"window-rule {{\n{niri_core._format_name(name)} {text}\n}}\n")
        except niri_core.KdlError as e:
            raise ValueError(f"Not valid KDL: {e.message}")
        kids = doc.top_nodes("window-rule")[0]["value"]["children"]
        if len(kids) != 1:
            raise ValueError("Type the value of one property")
        return {k: v for k, v in kids[0].items() if k != "name"}

    @Slot(str, "QVariant")
    def setProp(self, path, value):
        i = self._current()
        if i < 0:
            return
        if isinstance(value, dict) or hasattr(value, "keys"):
            value = dict(value)
        try:
            node = self._node_for(path, value)
        except ValueError as e:
            self._error = str(e)
            self._refresh()
            return
        if path.endswith("/state"):
            node = {"args": [str(value)], "props": {}}
        current = rl.get_prop(self._rules()[i], path)
        if current is not None and {k: v for k, v in current.items() if k != "name"} == node:
            if self._error:
                self._error = ""
                self._refresh()
            return
        self._edit(lambda: self.model.set_prop(i, path, node))

    @Slot(str)
    def addProp(self, path):
        known = schema.PROP_PATHS.get(path)
        if known is None:
            return
        default = known["default"]
        if known["kind"] == "size":
            default = {"kind": default["kind"], "value": default["value"]}
        elif known["kind"] == "position":
            default = {"x": default["x"], "y": default["y"], "rel": default["relative-to"]}
        self.setProp(path, default)

    @Slot(str)
    def removeProp(self, path):
        i = self._current()
        if i >= 0:
            self._edit(lambda: self.model.set_prop(i, path, None))

    # -- open windows and the "why" view

    @Property("QVariantList", notify=changed)
    def windows(self):
        def build():
            windows, workspaces = self._windows()
            i = self._current()
            rule = self._rules()[i] if i >= 0 else None
            facts = self._facts()
            out = []
            for wid, w in sorted(windows.items(), key=lambda kv: (kv[1].get("workspace_id") or 0, kv[0])):
                ws = workspaces.get(w.get("workspace_id")) or {}
                verdict = rl.check_rule(rule, facts[wid]) if rule else None
                out.append({"id": wid, "title": w.get("title") or "(no title)",
                            "appId": w.get("app_id") or "(no app-id)",
                            "workspace": "ws " + str(ws.get("name") or ws.get("idx") or "?"),
                            "status": verdict.status if verdict else "",
                            "reason": verdict.reason if verdict else "",
                            "selected": wid == self._window})
            return out
        return self._cached("windowList", build)

    @Slot(int)
    def selectWindow(self, wid):
        self._window = None if wid == self._window or wid < 0 else wid
        self._refresh()

    @Property("QVariantMap", notify=changed)
    def why(self):
        def build():
            windows = self._windows()[0]
            w = windows.get(self._window) if self._window is not None else None
            if w is None:
                return {"has": False}
            rules = self._rules()
            verdicts = self._verdicts(self._window)
            touching = [{"index": i, "title": rl.title(r), "status": v.status, "reason": v.reason}
                        for i, (r, v) in enumerate(zip(rules, verdicts))]
            values = []
            for m in rl.merged(rules, verdicts):
                values.append({"label": rl.label_of(m["path"]), "value": m["value"],
                               "rule": rl.title(rules[m["rule"]]), "ruleIndex": m["rule"],
                               "when": rl.when_of(m["path"]), "maybe": m["maybe"],
                               "replaces": len(m["earlier"])})
            return {"has": True, "title": w.get("title") or "", "appId": w.get("app_id") or "",
                    "rules": touching, "values": values,
                    "applies": sum(1 for v in verdicts if v.status == rl.YES)}
        return self._cached("why", build)

    # -- picking a window with the mouse

    @Property(bool, notify=changed)
    def picking(self):
        return self._picking

    @Slot()
    def pickWindow(self):
        if self._picking or not self.backend.connected:
            return
        self._picking = True
        self._refresh()

        def run():
            reply = ipc.request("PickWindow", timeout=120)
            self._picked.emit(reply)
        threading.Thread(target=run, daemon=True, name="niri-pick-window").start()

    def _on_picked(self, reply):
        self._picking = False
        w = reply.get("PickedWindow") if isinstance(reply, dict) else None
        if isinstance(w, dict) and "id" in w:
            self._window = w["id"]
        self._refresh()
