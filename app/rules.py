"""Window rules as a model, without Qt: matching, merging and editing.

Matching follows niri: a rule applies when the window matches any `match`
directive (or there are none) and no `exclude` directive. All matchers in
one directive must hold. `app-id` and `title` are Rust regexes searched
anywhere in the string. A matcher that cannot be checked from IPC state (or a
regex Python cannot reproduce) gives "unknown" instead of a guess, so a rule
is shown as applying, not applying, or maybe applying.

Merging follows niri too: rules are applied top to bottom, a later rule
replaces each property it sets, and the blocks in MERGED_BLOCKS merge child
by child.

Rules are edited as a whole list through Config.set_rules, which keeps each
rule in its file and only rewrites the lines that changed.
"""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass

from . import niri_core
from .schema import window_rules as schema

NAME = "window-rule"
YES, NO, MAYBE = "yes", "no", "maybe"

# --------------------------------------------------------------------------
# Rust regex -> Python re

_POSIX = {"alnum": "0-9A-Za-z", "alpha": "A-Za-z", "ascii": "\\x00-\\x7F", "blank": "\\t ",
          "cntrl": "\\x00-\\x1F\\x7F", "digit": "0-9", "graph": "!-~", "lower": "a-z",
          "print": " -~", "punct": "!-/:-@\\[-`{-~", "space": "\\t\\n\\v\\f\\r ",
          "upper": "A-Z", "word": "0-9A-Za-z_", "xdigit": "0-9A-Fa-f"}
_cache: dict[str, object] = {}


class Unsupported(Exception):
    pass


def _translate(p: str) -> str:
    """Rewrite the parts of Rust regex syntax that Python reads differently.

    Raises Unsupported for syntax Python has no equivalent for (Unicode
    classes, class set operations, flags in the middle of a pattern).
    """
    out, i, n = [], 0, len(p)
    multiline = False
    m = re.match(r"\(\?([a-zA-Z]+)\)", p)
    if m:
        flags = m.group(1)
        if set(flags) - set("imsxuU") or "U" in flags:
            raise Unsupported("flag")
        multiline = "m" in flags
        kept = flags.replace("u", "")
        out.append(f"(?{kept})" if kept else "")
        i = m.end()
    while i < n:
        c = p[i]
        if c == "\\":
            e = p[i + 1:i + 2]
            if e in ("p", "P"):
                raise Unsupported("unicode class")
            if e == "z":
                out.append("\\Z")
            elif e == "x" and p[i + 2:i + 3] == "{":
                close = p.index("}", i)
                out.append("\\U%08x" % int(p[i + 3:close], 16))
                i = close + 1
                continue
            elif e in ("<", ">"):
                out.append("\\b(?=\\w)" if e == "<" else "\\b(?<=\\w)")
            else:
                out.append(p[i:i + 2])
            i += 2
            continue
        if c == "[":
            j, cls = i + 1, ["["]
            if p[j:j + 1] == "^":
                cls.append("^")
                j += 1
            if p[j:j + 1] == "]":
                cls.append("\\]")
                j += 1
            while j < n and p[j] != "]":
                if p.startswith("[:", j):
                    end = p.find(":]", j)
                    name = p[j + 2:end].lstrip("^")
                    if end < 0 or name not in _POSIX or p[j + 2] == "^":
                        raise Unsupported("class")
                    cls.append(_POSIX[name])
                    j = end + 2
                    continue
                if p[j] == "[" or p[j:j + 2] in ("&&", "--", "~~"):
                    raise Unsupported("class set")
                if p[j] == "\\":
                    if p[j + 1:j + 2] in ("p", "P"):
                        raise Unsupported("unicode class")
                    cls.append(p[j:j + 2])
                    j += 2
                    continue
                cls.append(p[j])
                j += 1
            out.append("".join(cls) + "]")
            i = j + 1
            continue
        if c == "(" and p.startswith("(?", i):
            if p.startswith("(?<", i) and p[i + 3:i + 4] not in ("=", "!"):
                out.append("(?P<")
                i += 3
                continue
            m = re.match(r"\(\?[a-zA-Z-]*\)", p[i:])
            if m:
                raise Unsupported("inline flags")
        if c == "$" and not multiline:
            out.append("\\Z")
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def compile_regex(pattern: str):
    """A Python regex that behaves like niri's, or None if that is not possible."""
    if pattern not in _cache:
        try:
            _cache[pattern] = re.compile(_translate(pattern))
        except (Unsupported, re.error, ValueError, IndexError):
            _cache[pattern] = None
    return _cache[pattern]


def regex_error(pattern: str) -> str:
    """Why a regex is not valid, for an inline hint; "" when it looks fine."""
    try:
        re.compile(_translate(pattern))
    except Unsupported:
        return ""          # valid for Rust perhaps; niri validate decides on save
    except re.error as e:
        return f"Not a valid regex: {e.msg}"
    return ""


def exact(text: str) -> str:
    """A regex that matches exactly this string."""
    return "^" + re.sub(r"([\\.^$|?*+()\[\]{}])", r"\\\1", text) + "$"


def readable(pattern: str) -> str:
    """A regex shortened for a summary line: `^org\\.foo$` -> `org.foo`."""
    return re.sub(r"\\(.)", r"\1", pattern.strip("^$")) or pattern


# --------------------------------------------------------------------------
# Windows


def facts(window: dict, workspaces: dict, cast_targets: set | None, focused_output: str | None,
          column_sizes: dict | None = None) -> dict:
    """What matchers can know about an open window. None means unknown.

    `column_sizes` maps (workspace id, column) to its number of tiled windows:
    the only window of a column is always the active one in it.
    """
    ws = workspaces.get(window.get("workspace_id")) or {}
    floating = bool(window.get("is_floating"))
    active = None
    if ws:
        active = ws.get("active_window_id") == window.get("id") and ws.get("output") == focused_output
    in_column = None
    if not floating and ws:
        pos = (window.get("layout") or {}).get("pos_in_scrolling_layout")
        if ws.get("active_window_id") == window.get("id"):
            in_column = True
        elif pos and (column_sizes or {}).get((window.get("workspace_id"), pos[0])) == 1:
            in_column = True
    return {
        "app-id": window.get("app_id"),
        "title": window.get("title"),
        "is-focused": bool(window.get("is_focused")),
        "is-floating": floating,
        "is-urgent": bool(window.get("is_urgent")),
        "is-active": active,
        "is-active-in-column": in_column,
        "is-window-cast-target": None if cast_targets is None else window.get("id") in cast_targets,
        "at-startup": None,
    }


def window_facts(windows: dict, workspaces: dict, cast_targets: set | None) -> dict:
    """id -> facts for every open window."""
    sizes: dict[tuple, int] = {}
    for w in windows.values():
        pos = (w.get("layout") or {}).get("pos_in_scrolling_layout")
        if pos and not w.get("is_floating"):
            key = (w.get("workspace_id"), pos[0])
            sizes[key] = sizes.get(key, 0) + 1
    focused = next((w for w in workspaces.values() if w.get("is_focused")), None)
    output = focused.get("output") if focused else None
    return {wid: facts(w, workspaces, cast_targets, output, sizes) for wid, w in windows.items()}


def cast_targets(reply) -> set | None:
    """Window ids being screencast, from a `Casts` reply; None if unreadable."""
    if not isinstance(reply, dict) or not isinstance(reply.get("Casts"), list):
        return None
    found = set()
    for cast in reply["Casts"]:
        target = cast.get("target") if isinstance(cast, dict) else None
        if isinstance(target, dict) and "Window" in target:
            inner = target["Window"]
            wid = inner.get("id", inner.get("window_id")) if isinstance(inner, dict) else inner
            if isinstance(wid, int):
                found.add(wid)
                continue
            return None
        if target is None and cast:
            return None
    return found


# --------------------------------------------------------------------------
# Matching


def _and(results):
    results = list(results)
    if NO in results:
        return NO
    return MAYBE if MAYBE in results else YES


def _or(results):
    results = list(results)
    if YES in results:
        return YES
    return MAYBE if MAYBE in results else NO


def check_matcher(key: str, wanted, f: dict) -> tuple[str, str]:
    """(yes/no/maybe, a short explanation) for one matcher against one window."""
    have = f.get(key)
    if key in ("app-id", "title"):
        if have is None:
            return NO, f"the window has no {key}"
        rx = compile_regex(str(wanted))
        if rx is None:
            return MAYBE, f"{key} regex {wanted} cannot be checked here"
        hit = rx.search(have) is not None
        return (YES, f"{key} matches {wanted}") if hit else (NO, f"{key} {have} does not match {wanted}")
    label = schema.MATCHER_KEYS.get(key, {"label": key})["label"]
    if key not in f:
        return MAYBE, f"{key} is not known to this app"
    if have is None:
        when = "when the window opened" if key == "at-startup" else "from niri IPC"
        return MAYBE, f"whether it {label} is not known {when}"
    hit = bool(have) == bool(wanted)
    state = label if have else label.replace("is ", "is not ", 1) if label.startswith("is ") else "not " + label
    return (YES if hit else NO), state


def check_directive(props: dict, f: dict) -> tuple[str, list[str]]:
    """A match or exclude line: all its matchers must hold."""
    results = [check_matcher(k, v, f) for k, v in props.items()]
    return _and(r for r, _ in results), [why for _, why in results]


@dataclass
class Verdict:
    status: str      # yes / no / maybe
    reason: str


def check_rule(rule: dict, f: dict) -> Verdict:
    matches = [c["props"] for c in rule.get("children", []) if c["name"] == "match"]
    excludes = [c["props"] for c in rule.get("children", []) if c["name"] == "exclude"]
    m_results = [check_directive(p, f) for p in matches]
    e_results = [check_directive(p, f) for p in excludes]
    m = _or(r for r, _ in m_results) if matches else YES
    e = _or(r for r, _ in e_results) if excludes else NO
    if m == NO:
        first = next(w for r, w in m_results if r == NO)
        failed = [x for x in first if " not " in x or "does not" in x or "has no" in x] or first
        return Verdict(NO, failed[0] if len(matches) == 1 else "matches none of its match lines")
    if e == YES:
        hit = next(w for r, w in e_results if r == YES)
        return Verdict(NO, "excluded: " + ", ".join(hit))
    if m == YES and e == NO:
        why = next(w for r, w in m_results if r == YES) if matches else ["applies to every window"]
        return Verdict(YES, ", ".join(why))
    unknown = [x for r, w in m_results + e_results if r == MAYBE for x in w if "not known" in x or "cannot" in x]
    return Verdict(MAYBE, unknown[0] if unknown else "depends on state this app cannot see")


# --------------------------------------------------------------------------
# Properties of a rule


def tail(child: dict) -> str:
    """What follows the node name, e.g. `0.5` or `{ proportion 0.5; }`."""
    text = niri_core._format_child(dict(child, name="x"))
    return text[1:].strip()


def leaves(children: list[dict], prefix: str = "") -> list[tuple[str, dict]]:
    """(path, node) for each property a rule sets, blocks merged as niri does."""
    out = []
    for c in children:
        if not prefix and c["name"] in ("match", "exclude"):
            continue
        path = prefix + c["name"]
        if path in schema.MERGED_BLOCKS and "children" in c:
            flags = [k["name"] for k in c["children"] if k["name"] in ("on", "off") and not k.get("args")]
            if flags:
                state = "on" if "on" in flags else "off"
                out.append((path + "/state", {"name": "state", "args": [state], "props": {}}))
            rest = [k for k in c["children"] if not (k["name"] in ("on", "off") and not k.get("args"))]
            out += leaves(rest, path + "/")
            continue
        out.append((path, c))
    return out


def label_of(path: str) -> str:
    known = schema.PROP_PATHS.get(path)
    return known["label"] if known else path.replace("/", " › ")


def when_of(path: str) -> str:
    known = schema.PROP_PATHS.get(path)
    return known["when"] if known else "always"


def merged(rules: list[dict], verdicts: list[Verdict]) -> list[dict]:
    """The values a window ends up with: {path, value, rule, earlier, maybe}."""
    out: dict[str, dict] = {}
    for i, (rule, v) in enumerate(zip(rules, verdicts)):
        if v.status == NO:
            continue
        for path, node in leaves(rule.get("children", [])):
            value = node["args"][0] if path.endswith("/state") else tail(node)
            prev = out.get(path)
            earlier = (prev["earlier"] + [prev["rule"]]) if prev else []
            out[path] = {"path": path, "value": value, "rule": i, "earlier": earlier,
                         "maybe": v.status == MAYBE}
    return list(out.values())


def summary(rule: dict) -> str:
    """One line for the rule list: what it matches, then what it does."""
    parts = []
    matches = [c["props"] for c in rule.get("children", []) if c["name"] == "match"]
    if not matches:
        parts.append("all windows")
    else:
        bits = []
        for props in matches[:2]:
            words = [readable(str(v)) for k, v in props.items() if k in ("app-id", "title")]
            words += [(k.replace("is-", "") if v else "not " + k.replace("is-", "")) for k, v in props.items()
                      if k not in ("app-id", "title")]
            bits.append(" ".join(words) or "all windows")
        parts.append(", ".join(bits) + (f" +{len(matches) - 2}" if len(matches) > 2 else ""))
    for path, node in leaves(rule.get("children", []))[:2]:
        if path.endswith("/state"):
            parts.append(f"{label_of(path).lower()} {node['args'][0]}")
            continue
        known = schema.PROP_PATHS.get(path)
        args = node.get("args", [])
        if known and known["kind"] == "bool" and args:
            parts.append(known["label"].lower() if args[0] else "not " + known["label"].lower())
        else:
            parts.append(f"{path.rsplit('/', 1)[-1]} {tail(node)}".strip())
    return " · ".join(parts)


def title(rule: dict) -> str:
    if rule.get("comment"):
        return rule["comment"]
    matches = [c["props"] for c in rule.get("children", []) if c["name"] == "match"]
    for props in matches:
        for key in ("app-id", "title"):
            if key in props:
                return readable(str(props[key]))
    return "All windows" if not matches else "Rule"


# --------------------------------------------------------------------------
# Editing helpers on one rule's children


def _find(children: list[dict], name: str) -> dict | None:
    found = [c for c in children if c["name"] == name]
    return found[-1] if found else None


def get_prop(rule: dict, path: str) -> dict | None:
    """The node a property path points at (for `…/state`: {args: ["on"|"off"]})."""
    parts = path.split("/")
    children = rule.get("children", [])
    for p in parts[:-1]:
        block = _find(children, p)
        if block is None or "children" not in block:
            return None
        children = block["children"]
    if parts[-1] == "state":
        flags = [c["name"] for c in children if c["name"] in ("on", "off") and not c.get("args")]
        if not flags:
            return None
        return {"name": "state", "args": ["on" if "on" in flags else "off"], "props": {}}
    return _find(children, parts[-1])


def set_prop(rule: dict, path: str, node: dict | None):
    """Set (or with None remove) a property in place, creating blocks as needed.

    For `…/state`, node is {args: ["on"|"off"]}. Emptied blocks are removed.
    """
    parts = path.split("/")
    chain = [rule]
    children = rule.setdefault("children", [])
    for p in parts[:-1]:
        block = _find(children, p)
        if block is None:
            if node is None:
                return
            block = {"name": p, "args": [], "props": {}, "children": []}
            children.append(block)
        block.setdefault("children", [])
        chain.append(block)
        children = block["children"]
    leaf = parts[-1]
    if leaf == "state":
        keep = [c for c in children if not (c["name"] in ("on", "off") and not c.get("args"))]
        if node is not None:
            keep.insert(0, {"name": node["args"][0], "args": [], "props": {}})
        children[:] = keep
    else:
        at = [i for i, c in enumerate(children) if c["name"] == leaf]
        if node is None:
            for i in reversed(at):
                del children[i]
        else:
            new = dict(node, name=leaf)
            if at:
                children[at[-1]] = new
            else:
                children.append(new)
    # Drop blocks this left empty, innermost first.
    for parent, block in reversed(list(zip(chain[:-1], chain[1:]))):
        if not block["children"] and node is None:
            parent["children"] = [c for c in parent["children"] if c is not block]


def directives(rule: dict) -> list[tuple[str, int, dict]]:
    """(kind, index among that kind, props) for each match / exclude line."""
    out, counts = [], {"match": 0, "exclude": 0}
    for c in rule.get("children", []):
        if c["name"] in counts:
            out.append((c["name"], counts[c["name"]], c["props"]))
            counts[c["name"]] += 1
    return out


def _directive_node(rule: dict, kind: str, index: int) -> dict | None:
    found = [c for c in rule.get("children", []) if c["name"] == kind]
    return found[index] if 0 <= index < len(found) else None


def from_template(template: dict, app_id: str | None) -> dict:
    rule = {"args": [], "props": {}, "children": copy.deepcopy(template["children"]),
            "comment": template["title"] if template["id"] != "blank" else "New rule"}
    for c in rule["children"]:
        for k, v in list(c["props"].items()):
            if v == schema.APP:
                c["props"][k] = niri_core.Raw(exact(app_id or "app-id"))
            elif k in ("app-id", "title"):
                c["props"][k] = niri_core.Raw(v)
    if template.get("needs_app") and app_id:
        rule["comment"] = f"{template['title'].replace('this app', app_id).replace('App', app_id)}"
    return rule


# --------------------------------------------------------------------------
# The model


class RulesModel:
    def __init__(self, config_fn):
        self._config = config_fn

    @property
    def config(self):
        return self._config()

    def rules(self) -> list[dict]:
        return self.config.rules(NAME)

    def sources(self) -> list[dict]:
        return self.config.tree.top_nodes(NAME)

    def where(self, index: int) -> str:
        src = self.sources()[index]
        return f"{os.path.basename(src['file'])}:{src['line']}"

    def _change(self, index: int, fn):
        rules = self.rules()
        rule = copy.deepcopy(rules[index])
        fn(rule)
        rules[index] = rule
        self.config.set_rules(NAME, rules)

    # -- whole rules

    def add(self, rule: dict, at: int | None = None) -> int:
        rules = self.rules()
        at = len(rules) if at is None else at
        rules.insert(at, rule)
        self.config.set_rules(NAME, rules)
        return at

    def remove(self, index: int):
        rules = self.rules()
        del rules[index]
        self.config.set_rules(NAME, rules)

    def move(self, index: int, delta: int) -> int:
        rules = self.rules()
        to = max(0, min(len(rules) - 1, index + delta))
        if to == index:
            return index
        rules.insert(to, rules.pop(index))
        self.config.set_rules(NAME, rules)
        return to

    def rename(self, index: int, name: str):
        self._change(index, lambda r: r.__setitem__("comment", " ".join(name.split())))

    # -- match and exclude lines

    def add_directive(self, index: int, kind: str, props: dict | None = None):
        def fn(rule):
            node = {"name": kind, "args": [], "props": props or {}}
            kids = rule.setdefault("children", [])
            last = max((i for i, c in enumerate(kids) if c["name"] in ("match", "exclude")), default=-1)
            kids.insert(last + 1, node)
        self._change(index, fn)

    def remove_directive(self, index: int, kind: str, d: int):
        def fn(rule):
            node = _directive_node(rule, kind, d)
            rule["children"] = [c for c in rule["children"] if c is not node]
        self._change(index, fn)

    def set_matcher(self, index: int, kind: str, d: int, key: str, value):
        """Set one matcher of a match / exclude line; None removes it."""
        def fn(rule):
            node = _directive_node(rule, kind, d)
            if node is None:
                return
            props = dict(node["props"])
            if value is None:
                props.pop(key, None)
            else:
                props[key] = niri_core.Raw(value) if key in ("app-id", "title") else value
            node["props"] = props
        self._change(index, fn)

    # -- properties

    def set_prop(self, index: int, path: str, node: dict | None):
        self._change(index, lambda r: set_prop(r, path, node))

    # -- matching

    def verdicts(self, f: dict) -> list[Verdict]:
        return [check_rule(r, f) for r in self.rules()]
