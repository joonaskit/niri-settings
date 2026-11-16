"""Window and layer rules as a model, without Qt: matching, merging and editing.

Both kinds of rule work the same way and differ only in their schema
(schema/window_rules.py, schema/layer_rules.py), which every function here
takes as `kind`, the window schema by default.

Matching follows niri: a rule applies when the window (or surface) matches any `match`
directive (or there are none) and no `exclude` directive. All matchers in
one directive must hold. `app-id` and `title` are Rust regexes searched
anywhere in the string (as is a layer's `namespace`); syntax Python's `re` lacks is handed to the `regex`
package when it is installed. A matcher that cannot be checked from IPC state
(or a regex neither can reproduce) gives "unknown" instead of a guess, so a
rule is shown as applying, not applying, or maybe applying.

Merging follows niri too: rules are applied top to bottom, a later rule
replaces each property it sets, and the blocks in MERGED_BLOCKS merge child
by child.

Rules are edited as a whole list through Config.set_rules, which keeps each
rule in its file and only rewrites the lines that changed.
"""

from __future__ import annotations

import copy
import difflib
import json
import os
import re
from dataclasses import dataclass

from . import niri_core
from .schema import layer_rules as LAYER
from .schema import window_rules as WINDOW

try:
    import regex as _regex      # optional: Unicode classes, class set operations, scoped flags
except ImportError:
    _regex = None

NAME = WINDOW.NAME
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


def _translate(p: str, rich: bool = False) -> str:
    """Rewrite the parts of Rust regex syntax that Python reads differently.

    Raises Unsupported for syntax Python has no equivalent for. With `rich`
    the result is for the `regex` package in V1 mode, which also reads
    Unicode classes, class set operations and flags in the middle of a
    pattern the way Rust does.
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
                if not rich:
                    raise Unsupported("unicode class")
                out.append(p[i:i + 2])
                i += 2
                continue
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
            cls, i = _class(p, i, rich)
            out.append(cls)
            continue
        if c == "(" and p.startswith("(?", i):
            if p.startswith("(?<", i) and p[i + 3:i + 4] not in ("=", "!"):
                out.append("(?P<")
                i += 3
                continue
            m = re.match(r"\(\?([a-zA-Z-]*)([):])", p[i:])
            if m and (m.group(2) == ")" or rich):
                flags = m.group(1)
                if not rich or set(flags) - set("imsxu-") or "m" in flags or "-u" in flags \
                        or (flags.startswith("-") and len(flags) == 1):
                    raise Unsupported("inline flags")
                kept = flags.replace("u", "")
                out.append(f"(?{kept}{m.group(2)}" if kept.strip("-") else ("(?:" if m.group(2) == ":" else ""))
                i += m.end()
                continue
        if c == "$" and not multiline:
            out.append("\\Z")
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _class(p: str, i: int, rich: bool) -> tuple[str, int]:
    """A bracketed class starting at p[i]; returns (translation, index after it)."""
    n, j, cls = len(p), i + 1, ["["]
    if p[j:j + 1] == "^":
        cls.append("^")
        j += 1
    if p[j:j + 1] == "]":
        cls.append("\\]")
        j += 1
    while j < n and p[j] != "]":
        if p.startswith("[:", j):
            end = p.find(":]", j)
            name = p[j + 2:end]
            negated = name.startswith("^")
            name = name[1:] if negated else name
            if end < 0 or name not in _POSIX or (negated and not rich):
                raise Unsupported("class")
            cls.append(f"[^{_POSIX[name]}]" if negated else _POSIX[name])
            j = end + 2
            continue
        if p[j] == "[":
            if not rich:
                raise Unsupported("class set")
            inner, j = _class(p, j, rich)
            cls.append(inner)
            continue
        if p[j:j + 2] in ("&&", "--", "~~"):
            if not rich:
                raise Unsupported("class set")
            cls.append(p[j:j + 2])
            j += 2
            continue
        if p[j] == "\\":
            if p[j + 1:j + 2] in ("p", "P") and not rich:
                raise Unsupported("unicode class")
            cls.append(p[j:j + 2])
            j += 2
            continue
        # `||` is a set operation for `regex` V1 but two literal bars for Rust.
        cls.append("\\|" if p[j] == "|" else p[j])
        j += 1
    return "".join(cls) + "]", j + 1


def _compile(pattern: str):
    try:
        return re.compile(_translate(pattern))
    except Unsupported:
        if _regex is None:
            raise
    # Rust folds case simply (`(?i)ß` does not match "SS"); V1 folds fully
    # unless told not to.
    return _regex.compile("(?-f)" + _translate(pattern, rich=True), _regex.V1)


def compile_regex(pattern: str):
    """A Python regex that behaves like niri's, or None if that is not possible."""
    if pattern not in _cache:
        errors = (Unsupported, re.error, ValueError, IndexError) + ((_regex.error,) if _regex else ())
        try:
            _cache[pattern] = _compile(pattern)
        except errors:
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


STARTUP = 60.0      # at-startup holds for niri's first minute
_MARGIN = 1.0       # too close to call either way


def _within_startup(t: float, start: float) -> bool | None:
    since = t - start
    return None if abs(since - STARTUP) < _MARGIN else since < STARTUP


def startup(wid, clock: dict | None) -> tuple[bool | None, bool | None]:
    """(at-startup now, at-startup when the window opened); None for unknown.

    `clock` has niri's start time `niri_start`, the time `now`, `opened` (window
    id -> when it was seen opening) and `client_start` (window id -> when the
    window's process started, which is before the window opened).
    """
    start = (clock or {}).get("niri_start")
    if start is None:
        return None, None
    now = _within_startup(clock["now"], start)
    opened = clock.get("opened", {}).get(wid)
    if opened is not None:
        return now, _within_startup(opened, start)
    if now:
        return now, True            # niri is still in its first minute
    client = clock.get("client_start", {}).get(wid)
    if client is not None and _within_startup(client, start) is False:
        return now, False           # its process started after the first minute
    return now, None


def facts(window: dict, workspaces: dict, cast_targets: set | None, focused_output: str | None,
          column_sizes: dict | None = None, clock: dict | None = None) -> dict:
    """What matchers can know about an open window. None means unknown.

    `column_sizes` maps (workspace id, column) to its number of tiled windows:
    the only window of a column is always the active one in it. `clock` is
    described in `startup`.
    """
    at_startup, opened_at_startup = startup(window.get("id"), clock)
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
        "at-startup": at_startup,
        OPENED_AT_STARTUP: opened_at_startup,
    }


# What niri sees when it settles a window's open-* properties: the window is
# not mapped yet, so it is not focused, active, floating, urgent or cast, and it
# is a column of its own. Checked against real niri in tests/test_nested.py.
OPEN_STATE = {
    "is-focused": False,
    "is-active": False,
    "is-floating": False,
    "is-urgent": False,
    "is-window-cast-target": False,
    "is-active-in-column": True,
}
OPENED_AT_STARTUP = "_opened-at-startup"    # not a matcher: at-startup as it was at open


def at_open(f: dict) -> dict:
    """The facts as niri saw them when the window opened.

    app-id and title are taken as they are now; a window that changed its
    title since opening may have matched differently.
    """
    return dict(f, **OPEN_STATE, **{"at-startup": f.get(OPENED_AT_STARTUP)})


def window_facts(windows: dict, workspaces: dict, cast_targets: set | None,
                 clock: dict | None = None) -> dict:
    """id -> facts for every open window; `clock` is described in `startup`."""
    sizes: dict[tuple, int] = {}
    for w in windows.values():
        pos = (w.get("layout") or {}).get("pos_in_scrolling_layout")
        if pos and not w.get("is_floating"):
            key = (w.get("workspace_id"), pos[0])
            sizes[key] = sizes.get(key, 0) + 1
    focused = next((w for w in workspaces.values() if w.get("is_focused")), None)
    output = focused.get("output") if focused else None
    return {wid: facts(w, workspaces, cast_targets, output, sizes, clock) for wid, w in windows.items()}


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


def layer_facts(layers, clock: dict | None = None) -> dict:
    """key -> facts for every open layer surface, from a `Layers` reply list.

    niri gives layer surfaces no id, so the key is `namespace@output:layer`,
    with `#2`, `#3` added for repeats. at-startup is taken as it is now, which
    assumes niri rechecks layer rules when its first minute ends.
    """
    at_startup = startup(None, clock)[0]
    out: dict[str, dict] = {}
    for layer in layers if isinstance(layers, list) else []:
        if not isinstance(layer, dict):
            continue
        ns, level = layer.get("namespace") or "", str(layer.get("layer") or "").lower() or None
        key = base = f"{ns}@{layer.get('output') or '?'}:{level or '?'}"
        n = 1
        while key in out:
            n += 1
            key = f"{base}#{n}"
        out[key] = {"namespace": ns, "layer": level, "at-startup": at_startup,
                    "_output": layer.get("output") or ""}
    return out


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


def _regex_keys(kind) -> set[str]:
    return {m["key"] for m in kind.MATCHERS if m["kind"] == "regex"}


def check_matcher(key: str, wanted, f: dict, kind=WINDOW) -> tuple[str, str]:
    """(yes/no/maybe, a short explanation) for one matcher against one window or surface."""
    have = f.get(key)
    known = kind.MATCHER_KEYS.get(key, {"label": key, "kind": ""})
    if known["kind"] == "regex":
        if have is None:
            return NO, f"the {kind.SUBJECT} has no {key}"
        rx = compile_regex(str(wanted))
        if rx is None:
            return MAYBE, f"{key} regex {wanted} cannot be checked here"
        hit = rx.search(have) is not None
        return (YES, f"{key} matches {wanted}") if hit else (NO, f"{key} {have} does not match {wanted}")
    label = known["label"]
    if key not in f:
        return MAYBE, f"{key} is not known to this app"
    if have is None:
        when = f"when the {kind.SUBJECT} opened" if OPENED_AT_STARTUP in f and key == "at-startup" \
            else "from niri IPC"
        return MAYBE, f"whether it {label} is not known {when}"
    if known["kind"] == "enum":
        hit = str(wanted) == str(have)
        return (YES, f"{label} is {have}") if hit else (NO, f"{label} is {have}, not {wanted}")
    hit = bool(have) == bool(wanted)
    state = label if have else label.replace("is ", "is not ", 1) if label.startswith("is ") else "not " + label
    return (YES if hit else NO), state


def check_directive(props: dict, f: dict, kind=WINDOW) -> tuple[str, list[str]]:
    """A match or exclude line: all its matchers must hold."""
    results = [check_matcher(k, v, f, kind) for k, v in props.items()]
    return _and(r for r, _ in results), [why for _, why in results]


@dataclass
class Verdict:
    status: str      # yes / no / maybe
    reason: str


def check_rule(rule: dict, f: dict, kind=WINDOW) -> Verdict:
    if rule.get("disabled"):
        return Verdict(NO, "turned off")
    matches = [c["props"] for c in rule.get("children", []) if c["name"] == "match"]
    excludes = [c["props"] for c in rule.get("children", []) if c["name"] == "exclude"]
    m_results = [check_directive(p, f, kind) for p in matches]
    e_results = [check_directive(p, f, kind) for p in excludes]
    m = _or(r for r, _ in m_results) if matches else YES
    e = _or(r for r, _ in e_results) if excludes else NO
    if m == NO:
        first = next(w for r, w in m_results if r == NO)
        failed = [x for x in first if " not " in x or "does not" in x or "has no" in x or ", not " in x] or first
        return Verdict(NO, failed[0] if len(matches) == 1 else "matches none of its match lines")
    if e == YES:
        hit = next(w for r, w in e_results if r == YES)
        return Verdict(NO, "excluded: " + ", ".join(hit))
    if m == YES and e == NO:
        why = next(w for r, w in m_results if r == YES) if matches else [f"applies to every {kind.SUBJECT}"]
        return Verdict(YES, ", ".join(why))
    unknown = [x for r, w in m_results + e_results if r == MAYBE for x in w if "not known" in x or "cannot" in x]
    return Verdict(MAYBE, unknown[0] if unknown else "depends on state this app cannot see")


# --------------------------------------------------------------------------
# Properties of a rule


def tail(child: dict) -> str:
    """What follows the node name, e.g. `0.5` or `{ proportion 0.5; }`."""
    text = niri_core._format_child(dict(child, name="x"))
    return text[1:].strip()


def leaves(children: list[dict], prefix: str = "", kind=WINDOW) -> list[tuple[str, dict]]:
    """(path, node) for each property a rule sets, blocks merged as niri does."""
    out = []
    for c in children:
        if not prefix and c["name"] in ("match", "exclude"):
            continue
        path = prefix + c["name"]
        if path in kind.MERGED_BLOCKS and "children" in c:
            flags = [k["name"] for k in c["children"] if k["name"] in ("on", "off") and not k.get("args")]
            if flags:
                state = "on" if "on" in flags else "off"
                out.append((path + "/state", {"name": "state", "args": [state], "props": {}}))
            rest = [k for k in c["children"] if not (k["name"] in ("on", "off") and not k.get("args"))]
            out += leaves(rest, path + "/", kind)
            continue
        out.append((path, c))
    return out


def label_of(path: str, kind=WINDOW) -> str:
    known = kind.PROP_PATHS.get(path)
    return known["label"] if known else path.replace("/", " › ")


def when_of(path: str, kind=WINDOW) -> str:
    known = kind.PROP_PATHS.get(path)
    return known["when"] if known else "always"


def merged(rules: list[dict], verdicts: list[Verdict],
           open_verdicts: list[Verdict] | None = None, kind=WINDOW) -> list[dict]:
    """The values a window ends up with: {path, value, rule, earlier, maybe}.

    Properties niri applies when the window opens are judged by
    `open_verdicts` (rules checked against `at_open` facts) when given.
    """
    out: dict[str, dict] = {}
    open_verdicts = open_verdicts or verdicts
    for i, (rule, now, then) in enumerate(zip(rules, verdicts, open_verdicts)):
        for path, node in leaves(rule.get("children", []), kind=kind):
            v = then if when_of(path, kind) == "open" else now
            if v.status == NO:
                continue
            value = node["args"][0] if path.endswith("/state") else tail(node)
            prev = out.get(path)
            earlier = (prev["earlier"] + [prev["rule"]]) if prev else []
            out[path] = {"path": path, "value": value, "rule": i, "earlier": earlier,
                         "maybe": v.status == MAYBE}
    return list(out.values())


def summary(rule: dict, kind=WINDOW) -> str:
    """One line for the rule list: what it matches, then what it does."""
    parts = []
    regex = _regex_keys(kind)
    matches = [c["props"] for c in rule.get("children", []) if c["name"] == "match"]
    if not matches:
        parts.append("all " + kind.SUBJECTS)
    else:
        bits = []
        for props in matches[:2]:
            words = [readable(str(v)) for k, v in props.items() if k in regex]
            for k, v in props.items():
                if k in regex:
                    continue
                if not isinstance(v, bool):
                    words.append(f"{v} {k}")
                else:
                    words.append(k.replace("is-", "") if v else "not " + k.replace("is-", ""))
            bits.append(" ".join(words) or "all " + kind.SUBJECTS)
        parts.append(", ".join(bits) + (f" +{len(matches) - 2}" if len(matches) > 2 else ""))
    for path, node in leaves(rule.get("children", []), kind=kind)[:2]:
        if path.endswith("/state"):
            parts.append(f"{label_of(path, kind).lower()} {node['args'][0]}")
            continue
        known = kind.PROP_PATHS.get(path)
        args = node.get("args", [])
        if known and known["kind"] == "bool" and args:
            parts.append(known["label"].lower() if args[0] else "not " + known["label"].lower())
        else:
            parts.append(f"{path.rsplit('/', 1)[-1]} {tail(node)}".strip())
    return " · ".join(parts)


def title(rule: dict, kind=WINDOW) -> str:
    if rule.get("comment"):
        return rule["comment"]
    matches = [c["props"] for c in rule.get("children", []) if c["name"] == "match"]
    for props in matches:
        for key in [m["key"] for m in kind.MATCHERS if m["kind"] == "regex"]:
            if key in props:
                return readable(str(props[key]))
    return "All " + kind.SUBJECTS if not matches else "Rule"


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


def from_template(template: dict, app_id: str | None, kind=WINDOW) -> dict:
    """A new rule from a template; `app_id` is the selected window's app-id
    (or surface's namespace) and fills the templates that need one."""
    regex = _regex_keys(kind)
    rule = {"args": [], "props": {}, "children": copy.deepcopy(template["children"]),
            "comment": template["title"] if template["id"] != "blank" else "New rule"}
    for c in rule["children"]:
        for k, v in list(c["props"].items()):
            if v == WINDOW.APP:
                c["props"][k] = niri_core.Raw(exact(app_id or k))
            elif k in regex:
                c["props"][k] = niri_core.Raw(v)
    if template.get("needs_app") and app_id:
        rule["comment"] = template["title"].replace("this app", app_id).replace("this surface", app_id) \
            .replace("App", app_id).replace("Surface", app_id)
    return rule


# --------------------------------------------------------------------------
# Live preview: unsaved rule edits as rules added after all others


def _key(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _body(rule: dict) -> dict:
    return {k: v for k, v in rule.items() if k not in ("comment", "disabled")}


def _matchers(rule: dict) -> list[dict]:
    return [c for c in rule.get("children", []) if c["name"] in ("match", "exclude")]


def _leaf_map(rule: dict, kind) -> dict[str, dict]:
    """path -> node of what an enabled rule sets; nothing for a rule that is off."""
    if rule.get("disabled"):
        return {}
    return {path: node for path, node in leaves(rule.get("children", []), kind=kind)}


def overlay(old: list[dict], new: list[dict], kind=WINDOW) -> tuple[list[dict] | None, str]:
    """Rules that, added after the saved ones, make niri behave as `new` does.

    niri can be shown unsaved rule edits only by adding rules at the end, so
    this works when every edit adds: a new rule, a rule turned on, or new or
    changed properties on a rule whose match lines stay the same. Each added
    property must also be the last word: no later rule may set it, or the
    added rule would win where that later rule should.

    Returns (rules to add, "") or (None, why the edits cannot be shown).
    """
    old_keys, new_keys = [_key(_body(r)) + str(bool(r.get("disabled"))) for r in old], \
                         [_key(_body(r)) + str(bool(r.get("disabled"))) for r in new]
    if sorted(old_keys) == sorted(new_keys) and old_keys != new_keys:
        return None, "rules were moved"
    # (index in new, the rule before the edit or None) for each rule that changed
    changed: list[tuple[int, dict | None]] = []
    ops = difflib.SequenceMatcher(None, old_keys, new_keys, autojunk=False).get_opcodes()
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        if tag == "delete" or (tag == "replace" and i2 - i1 != j2 - j1):
            return None, "a rule was moved or removed"
        changed += [(j, None if tag == "insert" else old[i1 + j - j1]) for j in range(j1, j2)]

    later = [_leaf_map(r, kind) for r in new]
    out = []
    for j, before in changed:
        rule = new[j]
        if rule.get("disabled"):
            if before is not None and not before.get("disabled"):
                return None, "a rule was turned off"
            continue                                 # edits to a rule that is off do nothing
        was = _leaf_map(before, kind) if before is not None else {}
        if was and _key(_matchers(before)) != _key(_matchers(rule)):
            return None, "a match or exclude line changed"
        if before is not None and _key({k: v for k, v in _body(before).items() if k != "children"}) \
                != _key({k: v for k, v in _body(rule).items() if k != "children"}):
            return None, "a rule changed"
        now = later[j]
        if set(was) - set(now):
            return None, f"{label_of(sorted(set(was) - set(now))[0], kind)} was removed from a rule"
        paths = [p for p, node in now.items() if p not in was or _key(was[p]) != _key(node)]
        for p in paths:
            if any(p in later[k] for k in range(j + 1, len(new))):
                return None, f"a later rule also sets {label_of(p, kind).lower()}"
        if not paths:
            continue
        added = {"args": [], "props": {}, "children": copy.deepcopy(_matchers(rule))}
        for p in paths:
            node = now[p]
            set_prop(added, p, {k: v for k, v in node.items() if k != "name"} if not p.endswith("/state")
                     else {"args": node["args"], "props": {}})
        out.append(added)
    return out, ""


# --------------------------------------------------------------------------
# The model


class RulesModel:
    def __init__(self, config_fn, kind=WINDOW):
        self._config = config_fn
        self.kind = kind
        self.name = kind.NAME

    @property
    def config(self):
        return self._config()

    def rules(self) -> list[dict]:
        return self.config.rules(self.name)

    def sources(self) -> list[dict]:
        return self.config.tree.top_nodes(self.name)

    def where(self, index: int) -> str:
        src = self.sources()[index]
        return f"{os.path.basename(src['file'])}:{src['line']}"

    def _change(self, index: int, fn):
        rules = self.rules()
        rule = copy.deepcopy(rules[index])
        fn(rule)
        rules[index] = rule
        self.config.set_rules(self.name, rules)

    # -- whole rules

    def add(self, rule: dict, at: int | None = None) -> int:
        rules = self.rules()
        at = len(rules) if at is None else at
        rules.insert(at, rule)
        self.config.set_rules(self.name, rules)
        return at

    def remove(self, index: int):
        rules = self.rules()
        del rules[index]
        self.config.set_rules(self.name, rules)

    def move(self, index: int, delta: int) -> int:
        rules = self.rules()
        to = max(0, min(len(rules) - 1, index + delta))
        if to == index:
            return index
        rules.insert(to, rules.pop(index))
        self.config.set_rules(self.name, rules)
        return to

    def set_enabled(self, index: int, on: bool):
        """Turn a rule on or off: off comments it out with /- in front."""
        def fn(rule):
            if on:
                rule.pop("disabled", None)
            else:
                rule["disabled"] = True
        self._change(index, fn)

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
                props[key] = niri_core.Raw(value) if key in _regex_keys(self.kind) else value
            node["props"] = props
        self._change(index, fn)

    # -- properties

    def set_prop(self, index: int, path: str, node: dict | None):
        self._change(index, lambda r: set_prop(r, path, node))

    # -- matching

    def verdicts(self, f: dict) -> list[Verdict]:
        return [check_rule(r, f, self.kind) for r in self.rules()]
