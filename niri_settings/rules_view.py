"""The Window rules and Layer rules pages' objects in QML: thin Qt layers over RulesModel.

RuleListView holds what the two pages share; RulesView (windows) and
LayerRulesView (layer surfaces) say what there is to match against. Both pages
are drawn by RulesPage.qml, which takes its wording from `words`.
"""

from __future__ import annotations

import os
import threading
import time

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import QJSValue

from . import gradients, ipc, niri_core
from . import rules as rl
from .rules import RulesModel

_SIZE_KINDS = [{"label": "proportion", "value": "proportion"}, {"label": "fixed px", "value": "fixed"},
               {"label": "app decides", "value": ""}]
_WIDE = {"size", "position", "kdl", "xy", "gradient"}
_LAYOUT_ONOFF = {"focus-ring": True, "border": False}   # niri's defaults


def _options(values) -> list[dict]:
    return [{"label": v, "value": v} for v in values]


def _number(text, kind: str):
    value = float(str(text).strip().replace(",", "."))
    if kind == "int":
        if value != int(value):
            raise ValueError
        return int(value)
    return value


class RuleListView(QObject):
    changed = Signal()
    kind = rl.WINDOW               # the rule schema
    WORDS: dict = {}               # wording for RulesPage.qml

    def __init__(self, backend, model: RulesModel | None = None):
        super().__init__(backend)
        self.backend = backend
        self.model = model or RulesModel(lambda: backend.config, self.kind)
        self._index = 0
        self._target = None        # the selected window or surface
        self._error = ""           # why the last edit was refused
        self._niri_start = None    # Unix time; 0.0 when it cannot be found
        self._cache = {}
        backend.changed.connect(self._refresh)
        backend.stateChanged.connect(self._refresh)

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

    def _niri_started(self) -> float | None:
        if not self.backend.connected:
            return None
        if self._niri_start is None:
            self._niri_start = ipc.niri_started() or 0.0
        return self._niri_start or None

    # What a subclass provides: facts per target, and how to show a target.

    def _facts(self) -> dict:
        raise NotImplementedError

    def _target_rows(self) -> list[dict]:
        """{id, title, subtitle} for each target, in display order."""
        raise NotImplementedError

    def _open_facts(self, f: dict) -> dict | None:
        """Facts as they were when the target opened, for open-time properties."""
        return None

    def _target_value(self, key: str) -> str | None:
        f = self._facts().get(self._target) if self._target is not None else None
        value = (f or {}).get(key)
        return value if isinstance(value, str) else None

    def _first_regex(self) -> str:
        return next(m["key"] for m in self.kind.MATCHERS if m["kind"] == "regex")

    def _verdicts(self, target) -> list:
        f = self._facts().get(target)
        if f is None:
            return []
        return self._cached(f"v{target}", lambda: [rl.check_rule(r, f, self.kind) for r in self._rules()])

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
            verdicts = self._verdicts(self._target) if self._target is not None else []
            out = []
            for i, rule in enumerate(self._rules()):
                out.append({"index": i, "title": rl.title(rule, self.kind), "subtitle": rl.summary(rule, self.kind),
                            "where": f"{os.path.basename(sources[i]['file'])}:{sources[i]['line']}",
                            "status": verdicts[i].status if verdicts else "",
                            "disabled": bool(rule.get("disabled")),
                            "error": self._rule_error(i) != ""})
            return out
        return self._cached("list", build)

    @Property("QVariantList", constant=True)
    def templates(self):
        return [{"id": t["id"], "title": t["title"], "description": t["description"],
                 "needsApp": bool(t.get("needs_app"))} for t in self.kind.TEMPLATES]

    @Property("QVariantMap", constant=True)
    def words(self):
        return self.WORDS

    @Property(bool, constant=True)
    def canPick(self):
        return False

    @Slot(int)
    def select(self, index):
        self._index = index
        self._error = ""
        self._refresh()

    @Slot(str)
    def newRule(self, template_id):
        templates = self.kind.TEMPLATES
        template = next((t for t in templates if t["id"] == template_id), templates[-1])
        key = self._first_regex()
        app = self._target_value(key)
        rule = rl.from_template(template, app, self.kind)
        if template["id"] == "blank" and app:
            rule["children"] = [{"name": "match", "args": [], "props": {key: niri_core.Raw(rl.exact(app))}}]
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

    @Slot(int, bool)
    def setEnabled(self, index, on):
        """Turn the rule at `index` on, or off (commented out with /-)."""
        rules = self._rules()
        if 0 <= index < len(rules) and bool(on) == bool(rules[index].get("disabled")):
            self._edit(lambda: self.model.set_enabled(index, bool(on)))

    @Slot(str)
    def rename(self, name):
        i = self._current()
        if i >= 0 and " ".join(name.split()) != self._rules()[i].get("comment", ""):
            self._edit(lambda: self.model.rename(i, name))

    # -- the selected rule

    def _prop_item(self, path: str, node: dict) -> dict:
        known = self.kind.PROP_PATHS.get(path)
        kind = known["kind"] if known else "kdl"
        args, props, kids = node.get("args", []), node.get("props", {}), node.get("children")
        item = {"path": path, "label": rl.label_of(path, self.kind), "when": rl.when_of(path, self.kind),
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
            elif kind == "gradient":
                item["value"] = gradients.read(node)
                if item["value"] is None:
                    raise TypeError
                item["relOptions"] = gradients.options(gradients.RELATIVE)
                item["inOptions"] = gradients.options(gradients.SPACES)
        except (TypeError, IndexError, KeyError):
            kind = "kdl"
        item["kind"] = kind
        item["wide"] = kind in _WIDE
        return item

    def _block_shown(self, rule: dict, block: str) -> bool:
        """Whether a focus-ring or border block is drawn: the rule turns it on, or the layout has it on."""
        state = rl.get_prop(rule, f"{block}/state")
        if state is not None:
            return state.get("args") == ["on"]
        return self.backend.config.is_on(f"layout/{block}", _LAYOUT_ONOFF[block])

    def _directive_items(self, rule: dict, f: dict | None) -> list[dict]:
        out = []
        for kind, d, props in rl.directives(rule):
            fields = []
            for key, value in props.items():
                known = self.kind.MATCHER_KEYS.get(key)
                mkind = known["kind"] if known else "regex"
                status = rl.check_matcher(key, value, f, self.kind)[0] if f else ""
                fields.append({"key": key, "label": known["label"] if known else key, "kind": mkind,
                               "value": value if mkind == "bool" else str(value),
                               "options": _options(known.get("options", [])) if known else [],
                               "example": known.get("example", "") if known else "",
                               "error": rl.regex_error(str(value)) if mkind == "regex" else "",
                               "status": status})
            free = [{"label": m["label"], "value": m["key"]} for m in self.kind.MATCHERS if m["key"] not in props]
            warn = ""
            regex = {m["key"] for m in self.kind.MATCHERS if m["kind"] == "regex"}
            if kind == "exclude" and all(k in regex and str(v) == "" for k, v in props.items()):
                warn = f"This exclude line matches every {self.kind.SUBJECT}, so the rule applies to none."
            out.append({"kind": kind, "index": d, "fields": fields, "free": free, "warn": warn,
                        "status": rl.check_directive(props, f, self.kind)[0] if f else ""})
        return out

    @Property("QVariantMap", notify=changed)
    def detail(self):
        def build():
            i = self._current()
            if i < 0:
                return {"has": False, "error": self._error}
            rule, src = self._rules()[i], self._sources()[i]
            f = self._facts().get(self._target) if self._target is not None else None
            items = [self._prop_item(p, n) for p, n in rl.leaves(rule.get("children", []), kind=self.kind)]
            used = {it["path"] for it in items}
            beaten = {self.kind.PROP_PATHS[it["path"]]["overrides"]: it["label"] for it in items
                      if it["path"] in self.kind.PROP_PATHS and "overrides" in self.kind.PROP_PATHS[it["path"]]}
            for it in items:
                notes = [f"{beaten[it['path']]} wins over this"] if it["path"] in beaten else []
                block = it["path"].split("/", 1)[0]
                if block in _LAYOUT_ONOFF and "/" in it["path"] and not it["path"].endswith("/state") \
                        and not self._block_shown(rule, block):
                    name = rl.label_of(f"{block}/state", self.kind)
                    notes.append(f"{name} is off in your layout: add {name} set to on to this rule to show it")
                if notes:
                    it["note"] = ". ".join(notes)
            addable = [{"label": ("At open: " if p["when"] == "open" else "") + p["label"], "value": p["path"]}
                       for p in self.kind.PROPS if p["path"] not in used]
            text = src["text"]
            if src["comment"]:
                text = f"// {src['comment']}\n" + text
            matches = [d for d in rl.directives(rule) if d[0] == "match"]
            return {
                "has": True, "index": i, "title": rl.title(rule, self.kind), "comment": rule.get("comment", ""),
                "disabled": bool(rule.get("disabled")),
                "where": f"{os.path.basename(src['file'])}:{src['line']}",
                "first": i == 0, "last": i == len(self._rules()) - 1,
                "directives": self._directive_items(rule, f),
                "matchesAll": not matches,
                "globalNote": "The Layout page sets the focus ring and border for every window."
                              if not matches and items and all(it["path"].split("/", 1)[0] in _LAYOUT_ONOFF
                                                               for it in items) else "",
                "open": [it for it in items if it["when"] == "open"],
                "always": [it for it in items if it["when"] != "open"],
                "addable": addable,
                "kdl": text,
                "saved": self._preview_hint(),
                "error": self._error or self._rule_error(i),
            }
        return self._cached("detail", build)

    def _preview_hint(self) -> str:
        """When unsaved rule edits reach niri: now, through the preview, or on save."""
        cfg = self.backend.config
        if not getattr(cfg, "preview_enabled", False):
            return self.WORDS["saved"]
        extra, why = cfg.rule_preview(self.kind.NAME)
        if extra is None:
            return f"unsaved changes show after Save: {why}"
        if not extra:
            return "edits that add rules or properties are previewed live; others apply when you save"
        return "unsaved changes are previewed live" + (
            "; open-time settings affect windows opened from now on" if self.WORDS["hasOpen"] else "")

    @Property("QVariantList", constant=True)
    def matchers(self):
        return [{"label": m["label"], "value": m["key"]} for m in self.kind.MATCHERS]

    @Slot(str)
    def addDirective(self, kind):
        i = self._current()
        if i < 0:
            return
        key = self._first_regex()
        app = self._target_value(key)
        props = {key: niri_core.Raw(rl.exact(app) if app else "")}
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
        if self.kind.MATCHER_KEYS.get(key, {}).get("kind") == "bool":
            value = bool(value)
        else:
            value = str(value)
        self._edit(lambda: self.model.set_matcher(i, kind, d, key, value))

    @Slot(str, int, str)
    def addMatcher(self, kind, d, key):
        known = self.kind.MATCHER_KEYS.get(key)
        if not known:
            return
        have = self._target_value(key)
        if known["kind"] == "bool":
            self.setMatcher(kind, d, key, True)
        elif known["kind"] == "enum":
            self.setMatcher(kind, d, key, have if have in known["options"] else known["options"][0])
        else:
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
    def fillFromTarget(self, key):
        """Put the selected window's app-id or title (or surface's namespace) into the first match line."""
        i = self._current()
        have = self._target_value(key)
        if i < 0 or have is None:
            return
        if any(k == "match" for k, _, _ in rl.directives(self._rules()[i])):
            self.setMatcher("match", 0, key, rl.exact(have))
        else:
            self._edit(lambda: self.model.add_directive(i, "match", {key: niri_core.Raw(rl.exact(have))}))

    # -- properties

    def _node_for(self, path: str, value) -> dict:
        known = self.kind.PROP_PATHS.get(path)
        kind = known["kind"] if known else "kdl"
        if kind == "bool":
            return {"args": [bool(value)], "props": {}}
        if kind in ("int", "float"):
            try:
                number = _number(value, kind)
            except (TypeError, ValueError):
                raise ValueError(f"{rl.label_of(path, self.kind)} needs {'a whole number' if kind == 'int' else 'a number'}")
            lo, hi = known.get("min"), known.get("max")
            if (lo is not None and number < lo) or (hi is not None and number > hi):
                raise ValueError(f"{rl.label_of(path, self.kind)} goes from {lo} to {hi}")
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
        if kind == "gradient":
            return {"args": [], "props": gradients.props_of(value)}
        text = str(value).strip()
        name = path.rsplit("/", 1)[-1]
        try:
            doc = niri_core.load_string(f"{self.kind.NAME} {{\n{niri_core._format_name(name)} {text}\n}}\n")
        except niri_core.KdlError as e:
            raise ValueError(f"Not valid KDL: {e.message}")
        kids = doc.top_nodes(self.kind.NAME)[0]["value"]["children"]
        if len(kids) != 1:
            raise ValueError("Type the value of one property")
        return {k: v for k, v in kids[0].items() if k != "name"}

    @Slot(str, "QVariant")
    def setProp(self, path, value):
        i = self._current()
        if i < 0:
            return
        if isinstance(value, QJSValue):
            value = value.toVariant()
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
        known = self.kind.PROP_PATHS.get(path)
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

    # -- open windows or surfaces, and the "why" view

    @Property("QVariantList", notify=changed)
    def targets(self):
        def build():
            i = self._current()
            rule = self._rules()[i] if i >= 0 else None
            facts = self._facts()
            out = []
            for row in self._target_rows():
                verdict = rl.check_rule(rule, facts[row["id"]], self.kind) if rule else None
                out.append(dict(row, status=verdict.status if verdict else "",
                                reason=verdict.reason if verdict else "",
                                selected=row["id"] == self._target))
            return out
        return self._cached("targets", build)

    @Slot("QVariant")
    def selectTarget(self, target):
        self._target = None if target == self._target or target in (None, -1, "") else target
        self._refresh()

    @Property("QVariantMap", notify=changed)
    def why(self):
        def build():
            f = self._facts().get(self._target) if self._target is not None else None
            row = next((r for r in self._target_rows() if r["id"] == self._target), None)
            if f is None or row is None:
                return {"has": False}
            rules = self._rules()
            verdicts = self._verdicts(self._target)
            touching = [{"index": i, "title": rl.title(r, self.kind), "status": v.status, "reason": v.reason}
                        for i, (r, v) in enumerate(zip(rules, verdicts))]
            values = []
            at_open = self._open_facts(f)
            opened = [rl.check_rule(r, at_open, self.kind) for r in rules] if at_open else None
            for m in rl.merged(rules, verdicts, opened, self.kind):
                values.append({"label": rl.label_of(m["path"], self.kind), "value": m["value"],
                               "rule": rl.title(rules[m["rule"]], self.kind), "ruleIndex": m["rule"],
                               "when": rl.when_of(m["path"], self.kind), "maybe": m["maybe"],
                               "replaces": len(m["earlier"])})
            return {"has": True, "title": row["title"], "subtitle": row["detail"],
                    "rules": touching, "values": values,
                    "applies": sum(1 for v in verdicts if v.status == rl.YES)}
        return self._cached("why", build)

    # -- picking with the mouse

    @Property(bool, notify=changed)
    def picking(self):
        return False

    @Slot()
    def pickWindow(self):
        pass

    @Slot()
    def poll(self):
        """Called every few seconds while the page is shown, for state niri does not stream."""


class RulesView(RuleListView):
    """Window rules, matched against the windows niri streams over IPC."""
    _picked = Signal(object)       # from the pick-window thread
    kind = rl.WINDOW
    WORDS = {
        "title": "Window rules",
        "one": "window",
        "many": "windows",
        "intro": "Window rules change how particular windows open and look: floating, size, "
                 "the workspace or output they open on, opacity, borders and more.",
        "saved": "applies when you save; open-time settings affect windows opened after that",
        "hasOpen": True,
        "fill": [{"key": "app-id", "label": "Use window's app-id"}, {"key": "title", "label": "Use window's title"}],
        "fillHint": "The buttons copy the selected window's real values into the first match line as exact regexes.",
        "matchHint": "app-id and title are regexes matched anywhere in the text. "
                     "Select a window on the right to fill them from its real values.",
        "listTitle": "Open windows",
        "offline": "niri is not running, so there are no windows to match against.",
        "none": "No windows are open.",
        "noValues": "No rule sets anything for this window; it follows the layout settings.",
    }

    def __init__(self, backend, model: RulesModel | None = None):
        super().__init__(backend, model)
        self._picking = False
        self._casts = (0.0, None)  # (when, window ids being cast)
        self._pid_start = {}       # client pid -> Unix time its process started
        self._picked.connect(self._on_picked)

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

    def _clock(self, windows: dict) -> dict | None:
        """Times for the at-startup matcher (see rules.startup)."""
        start = self._niri_started()
        if start is None:
            return None
        stream = getattr(self.backend, "_stream", None)
        opened = getattr(self.backend.state, "opened", {})
        if stream is not None:
            with stream.lock:
                opened = dict(opened)
        client = {}
        for wid, w in windows.items():
            pid = w.get("pid")
            if pid and wid not in opened:
                if pid not in self._pid_start:
                    self._pid_start[pid] = ipc.process_started(pid)
                client[wid] = self._pid_start[pid]
        return {"niri_start": start, "now": time.time(), "opened": dict(opened),
                "client_start": {k: v for k, v in client.items() if v is not None}}

    def _facts(self) -> dict:
        def build():
            windows, workspaces = self._windows()
            return rl.window_facts(windows, workspaces, self._cast_targets() if windows else set(),
                                   self._clock(windows))
        return self._cached("facts", build)

    def _target_rows(self) -> list[dict]:
        def build():
            windows, workspaces = self._windows()
            out = []
            for wid, w in sorted(windows.items(), key=lambda kv: (kv[1].get("workspace_id") or 0, kv[0])):
                ws = workspaces.get(w.get("workspace_id")) or {}
                app = w.get("app_id") or "(no app-id)"
                out.append({"id": wid, "title": w.get("title") or "(no title)", "detail": app,
                            "subtitle": app + " · ws " + str(ws.get("name") or ws.get("idx") or "?")})
            return out
        return self._cached("rows", build)

    def _open_facts(self, f: dict) -> dict | None:
        return rl.at_open(f)

    @Property(bool, constant=True)
    def canPick(self):
        return True

    @Property(bool, notify=RuleListView.changed)
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
            self._target = w["id"]
        self._refresh()


class LayerRulesView(RuleListView):
    """Layer rules, matched against the layer surfaces `niri msg layers` lists.

    niri does not stream layer surfaces, so the page polls for them.
    """
    kind = rl.LAYER
    WORDS = {
        "title": "Layer rules",
        "one": "surface",
        "many": "layer surfaces",
        "intro": "Layer rules change how layer-shell surfaces look: bars, docks, launchers, notifications "
                 "and wallpapers. Set opacity, shadows, blur, or hide them from screencasts.",
        "saved": "applies when you save",
        "hasOpen": False,
        "fill": [{"key": "namespace", "label": "Use surface's namespace"}],
        "fillHint": "The button copies the selected surface's namespace into the first match line as an exact regex.",
        "matchHint": "namespace is a regex matched anywhere in the surface's namespace. "
                     "Select a surface on the right to fill it from its real value.",
        "listTitle": "Open layer surfaces",
        "offline": "niri is not running, so there are no layer surfaces to match against.",
        "none": "No layer surfaces are open.",
        "noValues": "No rule sets anything for this surface; it uses niri's defaults.",
    }

    def __init__(self, backend, model: RulesModel | None = None):
        super().__init__(backend, model)
        self._layers = None        # the last `Layers` reply list

    def _fetch(self):
        reply = ipc.request("Layers") if self.backend.connected else None
        return reply.get("Layers") if isinstance(reply, dict) and isinstance(reply.get("Layers"), list) else []

    def _layer_list(self) -> list:
        if self._layers is None:
            self._layers = self._fetch()
        return self._layers

    @Slot()
    def poll(self):
        layers = self._fetch()
        if layers != self._layers:
            self._layers = layers
            self._refresh()

    def _facts(self) -> dict:
        def build():
            start = self._niri_started()
            clock = {"niri_start": start, "now": time.time()} if start else None
            return rl.layer_facts(self._layer_list(), clock)
        return self._cached("facts", build)

    def _target_rows(self) -> list[dict]:
        order = {name: i for i, name in enumerate(reversed(rl.LAYER.LAYERS))}
        rows = [{"id": key, "title": f["namespace"] or "(no namespace)",
                 "subtitle": f"{f['layer'] or '?'} · {f['_output'] or '?'}",
                 "detail": f"{f['layer'] or '?'} layer on {f['_output'] or '?'}"}
                for key, f in self._facts().items()]
        return sorted(rows, key=lambda r: (order.get(self._facts()[r["id"]]["layer"], 9), r["title"]))
