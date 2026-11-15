"""niri_core: load, merge and edit a niri KDL config tree without losing formatting.

This is a Python stand-in for the Rust module described in the implementation
plan, with the same API (load_tree, get, source_of, list, set, remove, render,
dirty_files, reload_file). It never re-serialises a document: the parser only
records where each node and value sits in the text, and every edit is a splice
of the original text. Untouched parts therefore stay byte-for-byte the same.

It does no disk writes; that is the caller's job (see config.py).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

__all__ = ["KdlError", "Tree", "load_tree", "load_string", "format_node", "format_value"]

# Sections whose contents niri treats as one combined value: a later
# occurrence replaces the earlier one instead of merging into it.
NON_MERGING = {
    "layout/struts",
    "layout/preset-column-widths",
    "layout/preset-window-heights",
    "layout/default-column-width",
}

# Nodes that may repeat. `list()` addresses these by argument or by index.
# Sections whose children are read and written as whole nodes, block included.
WHOLE = {"binds"}
KEYED = {"output", "workspace"}
REPEATED = {
    "window-rule", "layer-rule", "spawn-at-startup", "spawn-sh-at-startup",
    "match", "exclude", "proportion", "fixed", "include", "environment",
}

_NON_IDENT = set('\\/(){}<>;[]=,"')
_NEWLINES = "\n\r\x0c\x85  "
_SPACES = " \t﻿ 　"


class KdlError(Exception):
    def __init__(self, file: str, line: int, message: str):
        super().__init__(f"{file}:{line}: {message}")
        self.file = file
        self.line = line
        self.message = message


@dataclass
class Entry:
    name: str | None  # None for a positional argument
    value: object
    start: int
    end: int


@dataclass
class Node:
    name: str
    start: int
    name_end: int
    end: int = 0                      # after the last token of the node
    entries: list[Entry] = field(default_factory=list)
    children: list["Node"] | None = None
    block_start: int = -1             # offset of "{"
    block_end: int = -1               # offset of "}"

    @property
    def args(self) -> list:
        return [e.value for e in self.entries if e.name is None]

    @property
    def props(self) -> dict:
        return {e.name: e.value for e in self.entries if e.name is not None}


# --------------------------------------------------------------------------
# Parser


class _Parser:
    def __init__(self, text: str, file: str):
        self.t = text
        self.n = len(text)
        self.file = file

    def fail(self, pos: int, message: str):
        raise KdlError(self.file, self.t.count("\n", 0, pos) + 1, message)

    def parse(self) -> list[Node]:
        nodes, pos = self.nodes(0, False)
        return nodes

    def skip_block_comment(self, pos: int) -> int:
        depth, i = 1, pos + 2
        while i < self.n and depth:
            if self.t.startswith("/*", i):
                depth, i = depth + 1, i + 2
            elif self.t.startswith("*/", i):
                depth, i = depth - 1, i + 2
            else:
                i += 1
        if depth:
            self.fail(pos, "unclosed /* comment")
        return i

    def skip_line_comment(self, pos: int) -> int:
        i = pos
        while i < self.n and self.t[i] not in _NEWLINES:
            i += 1
        return i

    def skip_filler(self, pos: int) -> int:
        """Skip everything that can sit between nodes."""
        t = self.t
        while pos < self.n:
            c = t[pos]
            if c in _SPACES or c in _NEWLINES or c == ";":
                pos += 1
            elif t.startswith("//", pos):
                pos = self.skip_line_comment(pos)
            elif t.startswith("/*", pos):
                pos = self.skip_block_comment(pos)
            else:
                break
        return pos

    def skip_node_space(self, pos: int) -> int:
        """Skip spaces inside a node: blanks, /* */ and line continuations."""
        t = self.t
        while pos < self.n:
            c = t[pos]
            if c in _SPACES:
                pos += 1
            elif t.startswith("/*", pos):
                pos = self.skip_block_comment(pos)
            elif c == "\\":
                i = pos + 1
                while i < self.n and t[i] in _SPACES:
                    i += 1
                if t.startswith("//", i):
                    i = self.skip_line_comment(i)
                if i < self.n and t[i] in _NEWLINES:
                    if t.startswith("\r\n", i):
                        i += 1
                    pos = i + 1
                else:
                    self.fail(pos, "unexpected \\")
            else:
                break
        return pos

    def nodes(self, pos: int, in_block: bool) -> tuple[list[Node], int]:
        out: list[Node] = []
        while True:
            pos = self.skip_filler(pos)
            if pos >= self.n:
                if in_block:
                    self.fail(pos, "missing closing }")
                return out, pos
            if self.t[pos] == "}":
                if not in_block:
                    self.fail(pos, "unexpected }")
                return out, pos
            if self.t.startswith("/-", pos):
                _, pos = self.node(self.skip_node_space(pos + 2))
                continue
            node, pos = self.node(pos)
            out.append(node)

    def type_annotation(self, pos: int) -> int:
        if pos < self.n and self.t[pos] == "(":
            close = self.t.find(")", pos)
            if close < 0:
                self.fail(pos, "unclosed type annotation")
            return close + 1
        return pos

    def node(self, pos: int) -> tuple[Node, int]:
        start = pos
        pos = self.type_annotation(pos)
        name, pos = self.identifier_or_string(pos)
        node = Node(name=name, start=start, name_end=pos, end=pos)
        t = self.t
        while True:
            pos = self.skip_node_space(pos)
            if pos >= self.n:
                return node, pos
            c = t[pos]
            if c in _NEWLINES or c == ";" or c == "}" or t.startswith("//", pos):
                return node, pos
            if t.startswith("/-", pos):
                pos = self.skip_node_space(pos + 2)
                if pos < self.n and t[pos] == "{":
                    _, close = self.nodes(pos + 1, True)
                    pos = close + 1
                else:
                    _, pos = self.entry(pos)
                continue
            if c == "{":
                node.block_start = pos
                node.children, close = self.nodes(pos + 1, True)
                node.block_end = close
                node.end = close + 1
                return node, close + 1
            entry, pos = self.entry(pos)
            node.entries.append(entry)
            node.end = pos

    def identifier_or_string(self, pos: int) -> tuple[str, int]:
        if pos < self.n and (self.t[pos] == '"' or self.is_raw_string(pos)):
            return self.string(pos)
        end = self.ident_end(pos)
        if end == pos:
            self.fail(pos, f"unexpected {self.t[pos]!r}")
        return self.t[pos:end], end

    def ident_end(self, pos: int) -> int:
        t, i = self.t, pos
        while i < self.n and t[i] not in _NON_IDENT and t[i] not in _SPACES and t[i] not in _NEWLINES:
            i += 1
        return i

    def is_raw_string(self, pos: int) -> bool:
        return re.compile(r'r?#*"').match(self.t, pos) is not None and self.t[pos] in "r#"

    def string(self, pos: int) -> tuple[str, int]:
        t = self.t
        if t[pos] == '"':
            i, out = pos + 1, []
            while i < self.n and t[i] != '"':
                if t[i] == "\\":
                    i += 1
                    if i >= self.n:
                        break
                    e = t[i]
                    if e == "u":
                        close = t.find("}", i)
                        if t[i + 1:i + 2] != "{" or close < 0:
                            self.fail(i, "bad \\u escape")
                        out.append(chr(int(t[i + 2:close], 16)))
                        i = close + 1
                        continue
                    if e in _SPACES or e in _NEWLINES:  # KDL v2 whitespace escape
                        while i < self.n and (t[i] in _SPACES or t[i] in _NEWLINES):
                            i += 1
                        continue
                    simple = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", "/": "/",
                              '"': '"', "b": "\b", "f": "\f", "s": " "}
                    if e not in simple:
                        self.fail(i, f"unknown escape \\{e}")
                    out.append(simple[e])
                    i += 1
                else:
                    out.append(t[i])
                    i += 1
            if i >= self.n:
                self.fail(pos, "unclosed string")
            return "".join(out), i + 1
        m = re.compile(r'r?(#*)"').match(t, pos)
        closing = '"' + m.group(1)
        end = t.find(closing, m.end())
        if end < 0:
            self.fail(pos, "unclosed raw string")
        return t[m.end():end], end + len(closing)

    def value(self, pos: int) -> tuple[object, int]:
        t = self.t
        pos = self.type_annotation(pos)
        if pos < self.n and (t[pos] == '"' or self.is_raw_string(pos)):
            return self.string(pos)
        end = self.ident_end(pos)
        word = t[pos:end]
        if not word:
            self.fail(pos, f"unexpected {t[pos:pos + 1]!r}")
        keywords = {"true": True, "false": False, "null": None,
                    "#true": True, "#false": False, "#null": None}
        if word in keywords:
            return keywords[word], end
        number = _parse_number(word)
        if number is not None:
            return number, end
        return word, end  # bare word (KDL v2 style string)

    def entry(self, pos: int) -> tuple[Entry, int]:
        t = self.t
        start = pos
        # A property is `name=value`, where name is an identifier or a string.
        if t[pos] == '"' or self.is_raw_string(pos):
            name, after = self.string(pos)
        else:
            after = self.ident_end(self.type_annotation(pos))
            name = t[pos:after]
        if after < self.n and t[after] == "=" and after > pos:
            value, end = self.value(after + 1)
            return Entry(name, value, start, end), end
        value, end = self.value(pos)
        return Entry(None, value, start, end), end


def _parse_number(word: str) -> int | float | None:
    w = word.replace("_", "")
    if not w or not (w[0].isdigit() or (w[0] in "+-" and len(w) > 1 and w[1].isdigit())):
        return None
    try:
        sign = -1 if w[0] == "-" else 1
        body = w.lstrip("+-")
        for prefix, base in (("0x", 16), ("0o", 8), ("0b", 2)):
            if body.startswith(prefix):
                return sign * int(body[2:], base)
        if any(c in w for c in ".eE"):
            return float(w)
        return int(w)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Formatting values back to KDL


def format_value(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return repr(round(value, 6))
    text = str(value)
    escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    return '"' + "".join(escapes.get(c, c) for c in text) + '"'


def _format_entries(value: object) -> str:
    """Text that follows a node name for this value (no leading space)."""
    if value is True:
        return ""  # a flag: the bare node name
    if isinstance(value, dict):
        parts = [format_value(a) for a in value.get("args", [])]
        parts += [f"{k}={format_value(v)}" for k, v in value.get("props", {}).items()]
        return " ".join(parts)
    return format_value(value)


def _format_children(children: list[dict]) -> str:
    """A one-line block for the child nodes of a whole-node value."""
    parts = []
    for c in children:
        tail = _format_entries({"args": c.get("args", []), "props": c.get("props", {})})
        parts.append(_format_name(c["name"]) + (" " + tail if tail else "") + ";")
    return "{ " + " ".join(parts) + " }" if parts else "{ }"


def _format_name(name: str) -> str:
    plain = name and not any(c in _NON_IDENT or c in _SPACES or c in _NEWLINES for c in name)
    if plain and _parse_number(name) is None and name not in ("true", "false", "null"):
        return name
    return format_value(name)


def format_node(segment: str, value: object = True) -> str:
    """KDL text for one node addressed by a path segment, e.g. `output[DP-1]`."""
    seg = _Segment.parse(segment)
    head = _format_name(seg.name)
    if seg.key is not None:
        head += " " + format_value(seg.key)
    tail = _format_entries(value)
    text = f"{head} {tail}" if tail else head
    if isinstance(value, dict) and "children" in value:
        text += " " + _format_children(value["children"])
    return text


# --------------------------------------------------------------------------
# Paths


@dataclass
class _Segment:
    name: str
    key: str | None = None    # output[DP-1]
    index: int | None = None  # window-rule#3

    @staticmethod
    def parse(text: str) -> "_Segment":
        m = re.fullmatch(r"(.+?)\[(.*)\]", text)
        if m:
            return _Segment(m.group(1), key=m.group(2))
        m = re.fullmatch(r"(.+?)#(\d+)", text)
        if m:
            return _Segment(m.group(1), index=int(m.group(2)))
        return _Segment(text)

    def matches(self, node: Node) -> bool:
        if node.name != self.name:
            return False
        if self.key is not None:
            args = node.args
            return bool(args) and str(args[0]) == self.key
        return True


def _segments(path: str) -> list[_Segment]:
    if not path:
        return []
    # Split on "/" but not inside [..], so output[/dev/x] style keys survive.
    parts, depth, cur = [], 0, ""
    for c in path:
        if c == "[":
            depth += 1
        elif c == "]":
            depth = max(0, depth - 1)
        if c == "/" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    parts.append(cur)
    return [_Segment.parse(p) for p in parts if p]


def _node_value(node: Node) -> object:
    args, props = node.args, node.props
    if not props:
        if not args:
            return True
        if len(args) == 1:
            return args[0]
    return {"args": args, "props": props}


def _whole_value(node: Node) -> dict:
    """A node together with its children, for sections listed in WHOLE."""
    return {"args": node.args, "props": node.props,
            "children": [{"name": c.name, "args": c.args, "props": c.props}
                         for c in (node.children or [])]}


def _is_whole(path: str) -> bool:
    parent, _, name = path.rpartition("/")
    return bool(name) and parent in WHOLE


# --------------------------------------------------------------------------
# Tree


@dataclass
class _File:
    path: str
    text: str
    original: str
    nodes: list[Node]
    exists: bool


class Tree:
    """A main config file plus every file it includes, in niri's order."""

    def __init__(self, main: str, skip: tuple[str, ...] = ()):
        self.main = main
        # Files that stay in the tree but are read as empty (the live-preview
        # overlay: its content is unsaved changes, not config).
        self._skip = {os.path.normpath(p) for p in skip}
        self._files: dict[str, _File] = {}
        self._depth: dict[str, int] = {}

    # -- loading

    def _read(self, path: str, optional: bool, origin: tuple[str, int] | None) -> _File:
        if path in self._skip:
            return _File(path, "", "", [], False)
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                text = fh.read()
            exists = True
        except FileNotFoundError:
            if not optional:
                if origin:
                    raise KdlError(origin[0], origin[1], f"included file not found: {path}")
                raise KdlError(path, 0, "file not found")
            text, exists = "", False
        return _File(path, text, text, _Parser(text, path).parse(), exists)

    def _load(self, path: str, optional=False, origin=None, depth=0):
        if path in self._files:
            return
        f = self._read(path, optional, origin)
        self._files[path] = f
        self._depth[path] = depth
        for node in f.nodes:
            if node.name == "include":
                target = self._include_target(f, node)
                if target:
                    line = f.text.count("\n", 0, node.start) + 1
                    self._load(target, bool(node.props.get("optional")), (path, line), depth + 1)

    @staticmethod
    def _include_target(f: _File, node: Node) -> str | None:
        args = node.args
        if not args or not isinstance(args[0], str):
            return None
        target = os.path.expanduser(args[0])
        if not os.path.isabs(target):
            target = os.path.join(os.path.dirname(f.path), target)
        return os.path.normpath(target)

    def _file(self, file: str) -> _File:
        path = os.path.normpath(os.path.expanduser(file))
        if path not in self._files:
            raise KeyError(f"{file} is not part of this config tree")
        return self._files[path]

    # -- reading

    def files(self) -> list[str]:
        """Every file of the tree in load order, including missing optional ones."""
        return list(self._files)

    def exists(self, file: str) -> bool:
        return self._file(file).exists

    def depth(self, file: str) -> int:
        """How deep a file sits in the include tree (the main file is 0)."""
        return self._depth.get(self._file(file).path, 0)

    def path_at(self, file: str, line: int) -> str | None:
        """The path of the innermost node on a line, e.g. for a validation error."""
        f = self._file(file)

        def line_of(pos: int) -> int:
            return f.text.count("\n", 0, pos) + 1

        def segment(node: Node, siblings: list[Node]) -> str:
            if node.name in KEYED and node.args:
                return f"{node.name}[{node.args[0]}]"
            if node.name in REPEATED or node.name in KEYED:
                same = [n for n in siblings if n.name == node.name]
                return f"{node.name}#{next(i for i, n in enumerate(same) if n is node)}"
            return node.name

        parts: list[str] = []
        siblings = [n for _, n in self._top()]
        level = f.nodes
        while True:
            hit = next((n for n in level if line_of(n.start) <= line <= line_of(max(n.start, n.end - 1))), None)
            if hit is None:
                break
            parts.append(segment(hit, siblings if not parts else level))
            level = siblings = hit.children or []
        return "/".join(parts) or None

    def _top(self, f: _File | None = None, seen: set | None = None):
        """Top-level nodes in the order niri applies them."""
        f = f or self._files[self.main]
        seen = seen if seen is not None else set()
        if f.path in seen:
            return
        seen.add(f.path)
        for node in f.nodes:
            yield f, node
            if node.name == "include":
                target = self._include_target(f, node)
                if target in self._files:
                    yield from self._top(self._files[target], seen)

    def _resolve(self, path: str, only: _File | None = None) -> list[tuple[_File, Node]]:
        segs = _segments(path)
        cands = list(self._top())
        names: list[str] = []
        for i, seg in enumerate(segs):
            found = [(f, n) for f, n in cands if seg.matches(n)]
            if seg.index is not None:
                found = found[seg.index:seg.index + 1]
            if only is not None:
                found = [(f, n) for f, n in found if f is only]
            names.append(seg.name)
            if "/".join(names) in NON_MERGING:
                found = found[-1:]
            if i == len(segs) - 1:
                return found
            cands = [(f, c) for f, n in found for c in (n.children or [])]
        return []

    def get(self, path: str):
        """The effective, merged value niri would use, or None if unset."""
        found = self._resolve(path)
        if not found:
            return None
        node = found[-1][1]
        return _whole_value(node) if _is_whole(path) else _node_value(node)

    def entries(self, path: str) -> list[dict]:
        """Every child of a section, from every file, in the order niri reads them.

        Unlike `list`, repeated names are kept, so overridden definitions show up.
        """
        out = []
        for f, section in self._resolve(path):
            for c in section.children or []:
                out.append({"name": c.name, "file": f.path,
                            "line": f.text.count("\n", 0, c.start) + 1,
                            "value": _whole_value(c)})
        return out

    def source_of(self, path: str) -> dict | None:
        found = self._resolve(path)
        if not found:
            return None
        f, node = found[-1]
        overridden = []
        segs = path.split("/")
        if segs[0] == "layout":
            for kind in ("output", "workspace"):
                for p in self.list(""):
                    if p.startswith(kind + "[") and self._resolve(p + "/" + path):
                        overridden.append(p)
        return {"file": f.path, "line": f.text.count("\n", 0, node.start) + 1,
                "overridden_by": overridden}

    def node_text(self, path: str) -> str | None:
        """The source text of the effective node, exactly as written."""
        found = self._resolve(path)
        if not found:
            return None
        f, node = found[-1]
        return f.text[node.start:node.end]

    def list(self, path: str) -> list[str]:
        """Child paths of a section ("" lists the top level)."""
        if path:
            children = [c for _, n in self._resolve(path) for c in (n.children or [])]
        else:
            children = [n for _, n in self._top()]
        prefix = path + "/" if path else ""
        out, counts = [], {}
        for c in children:
            if c.name in KEYED and c.args:
                p = f"{prefix}{c.name}[{c.args[0]}]"
            elif c.name in REPEATED or c.name in KEYED:
                i = counts.get(c.name, 0)
                counts[c.name] = i + 1
                p = f"{prefix}{c.name}#{i}"
            else:
                p = prefix + c.name
            if p not in out:
                out.append(p)
        return out

    # -- editing (in memory only)

    def _splice(self, f: _File, start: int, end: int, new: str):
        text = f.text[:start] + new + f.text[end:]
        nodes = _Parser(text, f.path).parse()  # raises before anything changes
        f.text, f.nodes = text, nodes

    def _find_in_file(self, f: _File, path: str) -> Node | None:
        found = self._resolve(path, only=f)
        return found[-1][1] if found else None

    @staticmethod
    def _indent_of(text: str, pos: int) -> str:
        line_start = text.rfind("\n", 0, pos) + 1
        m = re.match(r"[ \t]*", text[line_start:pos])
        return m.group(0)

    def set(self, path: str, value, file: str):
        """Change or add one node in one file."""
        f = self._file(file)
        segs = path.split("/") if path else []
        if not segs:
            raise ValueError("empty path")
        node = self._find_in_file(f, path)
        if node is not None:
            self._set_existing(f, node, value)
            return
        # Find the deepest existing ancestor in this file, then create the rest.
        depth, parent = len(segs) - 1, None
        while depth > 0:
            parent = self._find_in_file(f, "/".join(segs[:depth]))
            if parent is not None:
                break
            depth -= 1
        for s in segs[depth:]:
            if _Segment.parse(s).index is not None:
                raise KeyError(f"{path}: cannot create a node by index")
        self._insert(f, parent, segs[depth:], value)

    def copy_node(self, path: str, file: str):
        """Copy the effective node, exactly as written, into another file.

        Does nothing if that file already has the node. Used for sections niri
        does not merge: an overlay file has to carry the whole section.
        """
        f = self._file(file)
        if self._find_in_file(f, path) is not None:
            return
        found = self._resolve(path)
        if not found:
            return
        src, node = found[-1]
        raw = (src.text[node.start:node.end], self._indent_of(src.text, node.start))
        segs = path.split("/")
        depth, parent = len(segs) - 1, None
        while depth > 0:
            parent = self._find_in_file(f, "/".join(segs[:depth]))
            if parent is not None:
                break
            depth -= 1
        self._insert(f, parent, segs[depth:], None, raw)

    def rename(self, path: str, new_name: str, file: str):
        """Change the name of one node in one file, leaving the rest as written."""
        f = self._file(file)
        node = self._find_in_file(f, path)
        if node is None:
            raise KeyError(path)
        self._splice(f, node.start, node.name_end, _format_name(new_name))

    def _set_existing(self, f: _File, node: Node, value):
        if isinstance(value, dict) and "children" in value:
            # Later text first, so the earlier offsets stay valid.
            if _whole_value(node)["children"] != value["children"]:
                block = _format_children(value["children"])
                if node.children is None:
                    self._splice(f, node.end, node.end, " " + block)
                else:
                    self._splice(f, node.block_start, node.block_end + 1, block)
            if (node.args, node.props) != (value.get("args", []), value.get("props", {})):
                entries_end = node.entries[-1].end if node.entries else node.name_end
                tail = _format_entries(value)
                self._splice(f, node.name_end, entries_end, " " + tail if tail else "")
            return
        positional = [e for e in node.entries if e.name is None]
        scalar = not isinstance(value, dict) and value is not True
        if scalar and len(node.entries) == 1 and len(positional) == 1:
            e = positional[0]
            self._splice(f, e.start, e.end, format_value(value))
            return
        entries_end = node.entries[-1].end if node.entries else node.name_end
        tail = _format_entries(value)
        self._splice(f, node.name_end, entries_end, " " + tail if tail else "")

    def _insert(self, f: _File, parent: Node | None, segs: list[str], value,
                raw: tuple[str, str] | None = None):
        def build(indent: str, parts: list[str]) -> str:
            if len(parts) == 1:
                if raw is None:
                    return format_node(parts[0], value)
                first, *rest = raw[0].split("\n")  # re-indent the copied text
                return "\n".join([first] + [indent + (l[len(raw[1]):] if l.startswith(raw[1]) else l.lstrip())
                                            for l in rest])
            inner = indent + "    "
            return f"{format_node(parts[0])} {{\n{inner}{build(inner, parts[1:])}\n{indent}}}"

        t = f.text
        if parent is None:
            # Includes at the end of a file are there to override what comes
            # before them, so a new section goes above them, not below.
            trailing = None
            for node in reversed(f.nodes):
                if node.name != "include":
                    break
                trailing = node
            if trailing is not None and not self._indent_of(t, trailing.start) \
                    and not t[t.rfind("\n", 0, trailing.start) + 1:trailing.start]:
                at = trailing.start
                while True:  # keep the comment lines right above the include with it
                    prev = t.rfind("\n", 0, at - 1) + 1 if at > 0 else 0
                    if at == 0 or not t[prev:at].startswith("//"):
                        break
                    at = prev
                self._splice(f, at, at, build("", segs) + "\n\n")
                return
            lead = "" if not t or t.endswith("\n") else "\n"
            self._splice(f, len(t), len(t), lead + build("", segs) + "\n")
            return
        own_indent = self._indent_of(t, parent.start)
        if parent.children is None:
            inner = own_indent + "    "
            block = f" {{\n{inner}{build(inner, segs)}\n{own_indent}}}"
            self._splice(f, parent.end, parent.end, block)
            return
        close = parent.block_end
        line_start = t.rfind("\n", 0, close) + 1
        multiline = "\n" in t[parent.block_start:close]
        if multiline and not t[line_start:close].strip():
            if parent.children:
                inner = self._indent_of(t, parent.children[-1].start)
                if "\n" not in t[parent.block_start:parent.children[-1].start]:
                    inner = own_indent + "    "
            else:
                inner = own_indent + "    "
            self._splice(f, line_start, line_start, f"{inner}{build(inner, segs)}\n")
            return
        # One-line block such as `{ proportion 0.5; }`.
        before = t[parent.block_start + 1:close].rstrip()
        sep = "" if not before or before.endswith(";") else ";"
        end_of_content = parent.block_start + 1 + len(before)
        self._splice(f, end_of_content, close, f"{sep} {build(own_indent, segs)}; ")

    def remove(self, path: str, file: str):
        """Delete one node in one file. Does nothing if it is not there."""
        f = self._file(file)
        node = self._find_in_file(f, path)
        if node is None:
            return
        t = f.text
        start, end = node.start, node.end
        line_start = t.rfind("\n", 0, start) + 1
        i = end
        while i < len(t) and t[i] in _SPACES:
            i += 1
        if i < len(t) and t[i] == ";":
            i += 1
            while i < len(t) and t[i] in _SPACES:
                i += 1
        alone_before = not t[line_start:start].strip()
        at_line_end = i >= len(t) or t[i] in _NEWLINES
        if alone_before and at_line_end:
            if t.startswith("\r\n", i):
                i += 2
            elif i < len(t):
                i += 1
            self._splice(f, line_start, i, "")
        elif alone_before:
            self._splice(f, start, i, "")
        else:
            self._splice(f, start, i if not at_line_end else end, "")

    # -- output and bookkeeping

    def render(self, file: str) -> str:
        return self._file(file).text

    def original(self, file: str) -> str:
        """The text as it was last read from disk."""
        return self._file(file).original

    def dirty_files(self) -> list[str]:
        return [p for p, f in self._files.items() if f.text != f.original]

    def reload_file(self, file: str):
        """Re-read one file from disk, dropping its in-memory edits."""
        old = self._file(file)
        new = self._read(old.path, True, None)
        self._files[old.path] = new
        for node in new.nodes:
            if node.name == "include":
                target = self._include_target(new, node)
                if target and target not in self._files:
                    self._load(target, bool(node.props.get("optional")), (old.path, 0),
                               self._depth.get(old.path, 0) + 1)


def load_tree(main_path: str, skip: tuple[str, ...] = ()) -> Tree:
    """Read a config file and every file it includes.

    Files in `skip` keep their place in the tree but are read as empty.
    """
    main = os.path.normpath(os.path.abspath(os.path.expanduser(main_path)))
    tree = Tree(main, skip)
    tree._load(main)
    return tree


def load_string(text: str, name: str = "<memory>") -> Tree:
    """A single in-memory document, for building or checking KDL text."""
    tree = Tree(name)
    tree._files[name] = _File(name, text, text, _Parser(text, name).parse(), False)
    return tree
