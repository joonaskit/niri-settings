"""Config: the safe way to change a niri config.

Wraps niri_core with everything that touches the disk or niri itself:
pending changes, the two write modes, validation of a staged copy, snapshots,
saving, rebasing onto outside edits, and the live-preview file. Nothing
reaches the real files unless `niri validate` accepts a staged copy first.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

from . import niri_core

# Repeated top-level sections tracked as one ordered list each: removing or
# moving one entry shifts the index of every entry after it.
RULES = ("window-rule", "layer-rule", "spawn-at-startup", "spawn-sh-at-startup")
# A raw edit of a whole file in the source editor is tracked as "file:<path>".
FILE = "file:"
PREVIEW_NAME = "niri-gui-preview.kdl"
MANAGED_NAME = "niri-gui.kdl"
IN_PLACE, MANAGED = "in-place", "managed"
SNAPSHOT_KEEP = 50
# Where distributions put niri's default config; used when config.kdl is missing.
DEFAULT_CONFIGS = ("/usr/share/doc/niri/default-config.kdl",
                   "/usr/share/niri/default-config.kdl",
                   "/usr/local/share/doc/niri/default-config.kdl")


class ReadOnlyError(Exception):
    """The change needs an edit to a file that managed mode keeps read-only."""


def default_config_path() -> str:
    env = os.environ.get("NIRI_CONFIG")
    if env:
        return env
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "niri", "config.kdl")


def snapshot_dir() -> str:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, "niri-settings", "snapshots")


def _settings_file() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "niri-settings", "settings.json")


def _load_settings() -> dict:
    try:
        with open(_settings_file(), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_settings(settings: dict):
    try:
        os.makedirs(os.path.dirname(_settings_file()), exist_ok=True)
        with open(_settings_file(), "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=1)
    except OSError:
        pass


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def _write_atomic(path: str, text: str):
    """Replace a file's content in one step, following symlinks (dotfile repos)."""
    real = os.path.realpath(path)
    os.makedirs(os.path.dirname(real), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(real), prefix=".niri-settings-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        if os.path.exists(real):
            shutil.copymode(real, tmp)
        os.replace(tmp, real)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class Config:
    def __init__(self, main_path: str | None = None, niri_bin: str = "niri",
                 write_mode: str | None = None):
        self.main = os.path.abspath(os.path.expanduser(main_path or default_config_path()))
        self.niri_bin = niri_bin
        self.tree = self._load()
        self._preview_written = ""
        self.clear_preview()  # left over if the app was killed with unsaved changes
        mode = write_mode or _load_settings().get("write_mode", {}).get(self.main, IN_PLACE)
        # Managed mode only works once config.kdl includes the managed file.
        self.write_mode = mode if mode == MANAGED and self.managed_enabled else IN_PLACE
        # path -> value before the first unsaved edit (None when it was unset)
        self._baseline: dict[str, object] = {}
        self.last_error: dict | None = None
        # path -> {"mine": value, "disk": value} after an outside edit
        self.conflicts: dict[str, dict] = {}

    def _load(self) -> niri_core.Tree:
        # The preview overlay holds unsaved changes; reading it back as config
        # would make them look saved.
        # A missing config.kdl loads empty: first run creates it.
        return niri_core.load_tree(self.main, skip=(self.preview_file,), missing_ok=True)

    # -- reading

    def get(self, path: str, default=None):
        value = self.tree.get(path)
        return default if value is None else value

    def _value(self, path: str):
        """What a tracked path holds now: a value, a list of rules, or a file's text."""
        if path in RULES:
            return self.rules(path)
        if path.startswith(FILE):
            return self.tree.render(path[len(FILE):])
        return self.tree.get(path)

    def rules(self, name: str) -> list[dict]:
        """Every rule of one kind, in niri's order: {args, props, children, comment}."""
        return [dict(n["value"], comment=n["comment"]) for n in self.tree.top_nodes(name)]

    def source(self, path: str) -> dict | None:
        return self.tree.source_of(path)

    @property
    def pending(self) -> dict[str, object]:
        """Unsaved changes: path -> new value (None means removed)."""
        return {p: self._value(p) for p in self._baseline}

    def pending_count(self) -> int:
        """Unsaved changes, counting each changed rule once."""
        count = 0
        for path, old in self._baseline.items():
            if path not in RULES:
                count += 1
                continue
            new = self._value(path)
            for tag, i1, i2, j1, j2 in _rule_ops(old or [], new):
                if tag != "equal":
                    count += max(i2 - i1, j2 - j1)
        return count

    @property
    def preview_file(self) -> str:
        return os.path.join(os.path.dirname(self.main), PREVIEW_NAME)

    @property
    def managed_file(self) -> str:
        return os.path.join(os.path.dirname(self.main), MANAGED_NAME)

    @property
    def preview_enabled(self) -> bool:
        """True when config.kdl includes the preview file, so niri follows it."""
        return self.preview_file in self.tree.files()

    @property
    def managed_enabled(self) -> bool:
        return self.managed_file in self.tree.files()

    # -- editing (in memory)

    def _owner(self, path: str) -> str:
        """The file an edit goes to.

        Managed mode: always niri-gui.kdl. In place: where the value is set
        now, else the main file.
        """
        if self.write_mode == MANAGED:
            return self.managed_file
        parts = path.split("/")
        for depth in range(len(parts), 0, -1):
            src = self.tree.source_of("/".join(parts[:depth]))
            if src and src["file"] != self.preview_file:
                return src["file"]
        return self.main

    def _track(self, path: str):
        if path not in self._baseline:
            self._baseline[path] = self._value(path)

    def _settle(self):
        """Forget edits that ended up back at their saved value."""
        for path in [p for p, old in self._baseline.items() if self._value(p) == old]:
            del self._baseline[path]
        if not self._baseline:
            # Nothing pending: drop any leftover formatting differences too.
            for f in self.tree.dirty_files():
                self.tree.reload_file(f)

    def _guard_multipart(self, path: str):
        """Managed mode cannot override part of an `output` section.

        niri does not merge repeated output sections, so an overlay section
        would not add to the user's one. Refuse instead of guessing.
        """
        head = path.split("/")[0]
        if self.write_mode != MANAGED or not head.startswith("output["):
            return
        src = self.tree.source_of(head)
        if src and src["file"] != self.managed_file:
            raise ReadOnlyError(
                f"{head[7:-1]} is configured in {os.path.basename(src['file'])}, which managed "
                "mode keeps read-only. Switch to in-place mode to change this display.")

    def _set(self, path: str, value):
        self._guard_multipart(path)
        self._track(path)
        owner = self._owner(path)
        if self.write_mode == MANAGED:
            # A section niri does not merge must be carried whole by the overlay.
            parts = path.split("/")
            for i in range(1, len(parts)):
                section = "/".join(parts[:i])
                if section in niri_core.NON_MERGING:
                    self.tree.copy_node(section, owner)
        self.tree.set(path, value, owner)

    def set(self, path: str, value):
        self._set(path, value)
        self._settle()

    def remove(self, path: str):
        self._guard_multipart(path)
        self._track(path)
        try:
            if self.write_mode == MANAGED:
                self._remove_managed(path)
            else:
                for _ in range(len(self.tree.files()) + 1):
                    src = self.tree.source_of(path)
                    if not src:
                        break
                    self.tree.remove(path, src["file"])
        finally:
            self._settle()

    def _remove_managed(self, path: str):
        """Unset a value without touching the user's files."""
        self.tree.remove(path, self.managed_file)
        value = self.tree.get(path)
        if value is None:
            return
        parent, _, name = path.rpartition("/")
        if name in ("on", "off") and parent:
            self._set(f"{parent}/{'off' if name == 'on' else 'on'}", True)
        elif value is True:
            self._set(path, False)  # most flags accept `false`; validation checks it
        else:
            where = os.path.basename(self.tree.source_of(path)["file"])
            raise ReadOnlyError(
                f"{path.replace('/', ' › ')} is set in {where}, which managed mode keeps "
                "read-only. Switch to in-place mode to remove it.")

    def rename(self, path: str, new_name: str):
        """Move a node to a new name, in place when one file holds it."""
        parent = path.rpartition("/")[0]
        new_path = f"{parent}/{new_name}" if parent else new_name
        if new_path == path:
            return
        value = self.tree.get(path)
        files = {e["file"] for e in self.tree.entries(parent) if e["name"] == path.rpartition("/")[2]}
        if self.write_mode == MANAGED or len(files) != 1 or self.tree.get(new_path) is not None:
            self.remove(path)      # raises ReadOnlyError before anything changes
            self.set(new_path, value)
            return
        self._track(path)
        self._track(new_path)
        self.tree.rename(path, new_name, files.pop())
        self._settle()

    def set_text(self, file: str, text: str):
        """Replace one file's text from the source editor. Raises KdlError if
        it does not parse, and ReadOnlyError for a file managed mode protects."""
        file = os.path.normpath(file)
        if not self._writable(file):
            raise ReadOnlyError(f"{os.path.basename(file)} is read-only in managed mode. "
                                "Switch to in-place mode to edit it here.")
        if self.tree.render(file) == text:
            return
        self._track(FILE + file)
        try:
            self.tree.set_text(file, text)
        finally:
            self._settle()

    def _apply(self, path: str, value):
        if path.startswith(FILE):
            self.set_text(path[len(FILE):], value)
        elif path in RULES:
            self.set_rules(path, value or [])
        elif value is None:
            self.remove(path)
        else:
            self.set(path, value)

    # -- rules

    def set_rules(self, name: str, new: list[dict]):
        """Make the rules of one kind equal `new`, editing as little text as possible.

        Rules keep their file. New rules go next to their neighbours in the
        list; in managed mode only after your own rules, in niri-gui.kdl.
        Raises ReadOnlyError, changing nothing, if managed mode forbids it.
        """
        self._track(name)
        try:
            self._write_rules(name, new)
        finally:
            self._moving = {}
            self._settle()

    def _writable(self, file: str) -> bool:
        return self.write_mode != MANAGED or file == self.managed_file

    def _write_rules(self, name: str, new: list[dict]):
        old = self.rules(name)
        nodes = self.tree.top_nodes(name)
        files = [n["file"] for n in nodes]
        key = lambda r: json.dumps(r, sort_keys=True, default=str)
        # Text of rules that are removed here, so a rule that only moves is
        # written back exactly as it was.
        self._moving = {}
        label = name.replace("-", " ")
        plan = []
        for tag, i1, i2, j1, j2 in _rule_ops(old, new):
            if tag == "equal":
                continue
            paired = min(i2 - i1, j2 - j1)
            plan += [("set", i1 + k, new[j1 + k]) for k in range(paired)]
            plan += [("remove", k, None) for k in range(i1 + paired, i2)]
            for k in range(i1 + paired, i2):
                self._moving.setdefault(key(old[k]), []).append(nodes[k]["full_text"])
            if j2 - j1 > paired:
                plan.append(("insert", i1 + paired, new[j1 + paired:j2]))
        for op, i, _ in plan:
            if op in ("set", "remove") and not self._writable(files[i]):
                raise ReadOnlyError(
                    f"This {label} is in {os.path.basename(files[i])}, which managed mode keeps "
                    "read-only. Switch to in-place mode to change or remove it.")
            if op == "insert" and self.write_mode == MANAGED and i < len(old) \
                    and not (i and self._writable(files[i - 1])) and not self._writable(files[i]):
                raise ReadOnlyError(
                    f"Managed mode can add a {label} only after your own ones. "
                    "Switch to in-place mode to put it in between.")
        # Highest position first, so lower indexes stay valid. An insert at
        # position i goes after everything at i and above is done.
        plan.sort(key=lambda p: p[1] - (0.5 if p[0] == "insert" else 0), reverse=True)
        for op, i, value in plan:
            if op == "set":
                body = {k: v for k, v in value.items() if k != "comment"}
                self.tree.replace_top(name, i, body, value.get("comment", ""))
            elif op == "remove":
                self.tree.remove_top(name, i)
            else:
                for k, rule in enumerate(value):
                    self._insert_rule(name, i + k, rule)

    def _insert_rule(self, name: str, i: int, rule: dict):
        """Put a rule at position i of the current list."""
        nodes = self.tree.top_nodes(name)
        body = {k: v for k, v in rule.items() if k != "comment"}
        comment = rule.get("comment", "")
        moved = getattr(self, "_moving", {}).get(json.dumps(rule, sort_keys=True, default=str))
        text = moved.pop(0) if moved else None
        if i and self._writable(nodes[i - 1]["file"]):
            self.tree.insert_top(name, body, nodes[i - 1]["file"], i - 1, True, comment, text)
        elif i < len(nodes) and self._writable(nodes[i]["file"]):
            self.tree.insert_top(name, body, nodes[i]["file"], i, False, comment, text)
        else:
            target = self.managed_file if self.write_mode == MANAGED else self.main
            self.tree.insert_top(name, body, target, comment=comment, text=text)

    def revert(self):
        self._baseline.clear()
        for f in self.tree.dirty_files():
            self.tree.reload_file(f)

    def reload(self):
        """Re-read everything from disk, dropping unsaved changes."""
        self.tree = self._load()
        self._baseline.clear()
        self.conflicts = {}
        if self.write_mode == MANAGED and not self.managed_enabled:
            self.write_mode = IN_PLACE

    # -- outside edits

    def changed_on_disk(self) -> bool:
        for f in self.tree.files():
            if f == self.preview_file:
                continue
            if (_read(f) or "") != self.tree.original(f):
                return True
        return False

    def rebase(self) -> list[str]:
        """Reload from disk and put unsaved changes back on top.

        A change is re-applied when the file still has the value it was based
        on. If the same setting changed on both sides it becomes a conflict
        and is left at the file's value until `resolve_conflicts`. Raises
        KdlError, changing nothing, if the files on disk do not parse.
        """
        mine, base = self.pending, dict(self._baseline)
        tree = self._load()
        self.tree = tree
        self._baseline = {}
        self.conflicts = {}
        if self.write_mode == MANAGED and not self.managed_enabled:
            self.write_mode = IN_PLACE
        for path, value in mine.items():
            disk = self._value(path)
            if disk == value:
                continue
            if disk == base[path]:
                self._apply(path, value)
            else:
                self.conflicts[path] = {"mine": value, "disk": disk}
        return list(self.conflicts)

    def resolve_conflicts(self, keep_mine: bool):
        conflicts, self.conflicts = self.conflicts, {}
        if keep_mine:
            for path, sides in conflicts.items():
                self._apply(path, sides["mine"])

    # -- validation

    def _validate_stage(self, overrides: dict[str, str]) -> tuple[bool, str]:
        """Run `niri validate` on a copy of the tree with some files replaced."""
        self.last_error = None
        files = [f for f in self.tree.files() if self.tree.exists(f) or f in overrides]
        files += [f for f in overrides if f not in files]
        root = os.path.commonpath([os.path.dirname(f) for f in files])
        if shutil.which(self.niri_bin) is None:
            try:
                for f, text in overrides.items():
                    niri_core.load_string(text, f)
            except niri_core.KdlError as e:
                self.last_error = {"file": e.file, "line": e.line, "path": None,
                                   "summary": e.message, "text": str(e)}
                return False, str(e)
            return True, "niri not found: syntax checked only"

        def text_of(f: str) -> str:
            return overrides[f] if f in overrides else self.tree.original(f)

        with tempfile.TemporaryDirectory(prefix="niri-settings-") as tmp:
            for f in files:
                dest = os.path.join(tmp, os.path.relpath(f, root))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text_of(f))
            staged_main = os.path.join(tmp, os.path.relpath(self.main, root))
            try:
                run = subprocess.run([self.niri_bin, "validate", "-c", staged_main],
                                     capture_output=True, text=True, timeout=10,
                                     env={**os.environ, "NO_COLOR": "1"})
            except (OSError, subprocess.TimeoutExpired) as e:
                return False, f"could not run niri validate: {e}"
            if run.returncode == 0:
                return True, ""
            message = _clean_error(run.stderr, tmp)
        self.last_error = _parse_error(message)
        rel = self.last_error["file"]
        if rel:
            f = os.path.normpath(os.path.join(root, rel))
            self.last_error["file"] = f
            if f in files and self.last_error["line"]:
                try:
                    doc = niri_core.load_string(text_of(f), f)
                    self.last_error["path"] = doc.path_at(f, self.last_error["line"])
                except niri_core.KdlError:
                    pass
        return False, message

    def _pending_overrides(self) -> dict[str, str]:
        overrides = {f: self.tree.render(f) for f in self.tree.dirty_files()}
        if self.preview_enabled:
            overrides[self.preview_file] = ""  # it is emptied on save
        return overrides

    def validate(self) -> tuple[bool, str]:
        """Check the config as it would be after saving."""
        return self._validate_stage(self._pending_overrides())

    # -- diff

    def diff(self) -> str:
        out = []
        for f in self.tree.dirty_files():
            name = os.path.relpath(f, os.path.dirname(self.main))
            out += difflib.unified_diff(
                self.tree.original(f).splitlines(), self.tree.render(f).splitlines(),
                f"a/{name}", f"b/{name}", lineterm="", n=2)
        return "\n".join(out)

    def file_lines(self, file: str) -> list[dict]:
        """A file's text line by line, with unsaved changes marked added/removed."""
        old = self.tree.original(file).splitlines()
        new = self.tree.render(file).splitlines()
        out = []
        for line in difflib.ndiff(old, new):
            tag, text = line[:2], line[2:]
            if tag == "? ":
                continue
            out.append({"text": text, "kind": {"+ ": "added", "- ": "removed"}.get(tag, "")})
        return out

    # -- snapshots

    def _snapshot(self, files: list[str], reason: str) -> str:
        """Copy the current on-disk state of some files aside before a write."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base, n = os.path.join(snapshot_dir(), stamp), 1
        dest = base
        while os.path.exists(dest):
            n += 1
            dest = f"{base}-{n}"
        root = os.path.dirname(self.main)
        meta = {"main": self.main, "name": "", "reason": reason, "files": {}, "absent": []}
        os.makedirs(dest)
        for i, f in enumerate(files):
            if not os.path.exists(f):
                meta["absent"].append(f)
                continue
            rel = os.path.relpath(f, root)
            if rel.startswith(".."):
                rel = os.path.join("_outside", str(i), os.path.basename(f))
            target = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(f, target)
            meta["files"][rel] = f
        with open(os.path.join(dest, "snapshot.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=1)
        self._prune_snapshots()
        return os.path.basename(dest)

    def _snapshot_meta(self, snap_id: str) -> dict | None:
        folder = os.path.join(snapshot_dir(), snap_id)
        try:
            with open(os.path.join(folder, "snapshot.json"), encoding="utf-8") as fh:
                return json.load(fh)
        except ValueError:
            return None
        except OSError:
            pass
        # Snapshots from before snapshot.json existed: plain copies, laid out
        # relative to the config folder.
        files = {}
        for base, _, names in os.walk(folder):
            for name in names:
                rel = os.path.relpath(os.path.join(base, name), folder)
                files[rel] = os.path.join(os.path.dirname(self.main), rel)
        if not files:
            return None
        return {"main": self.main, "name": "", "reason": "before save", "files": files, "absent": []}

    def _prune_snapshots(self):
        """Keep the newest SNAPSHOT_KEEP automatic snapshots and every named one."""
        auto = [s["id"] for s in self.snapshots(all_configs=True) if not s["name"]]
        for old in auto[SNAPSHOT_KEEP:]:
            shutil.rmtree(os.path.join(snapshot_dir(), old), ignore_errors=True)

    def snapshots(self, all_configs: bool = False) -> list[dict]:
        """Snapshots of this config, newest first."""
        try:
            ids = sorted(os.listdir(snapshot_dir()), reverse=True)
        except FileNotFoundError:
            return []
        out = []
        for snap_id in ids:
            meta = self._snapshot_meta(snap_id)
            if not meta or (not all_configs and meta.get("main") != self.main):
                continue
            try:
                when = time.mktime(time.strptime(snap_id[:15], "%Y%m%d-%H%M%S"))
            except ValueError:
                when = 0
            out.append({"id": snap_id, "name": meta.get("name", ""), "time": when,
                        "reason": meta.get("reason", ""),
                        "files": [os.path.basename(f) for f in meta.get("files", {}).values()]})
        return out

    def name_snapshot(self, snap_id: str, name: str):
        """Named snapshots are never pruned."""
        meta = self._snapshot_meta(snap_id)
        if meta is None:
            return
        meta["name"] = name.strip()
        with open(os.path.join(snapshot_dir(), snap_id, "snapshot.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=1)

    def restore_snapshot(self, snap_id: str) -> tuple[bool, str]:
        """Put snapshotted files back. A normal save: validated and snapshotted."""
        meta = self._snapshot_meta(snap_id)
        if meta is None or meta.get("main") != self.main:
            return False, "Snapshot not found"
        if self._baseline:
            return False, "Save or revert your unsaved changes first."
        folder = os.path.join(snapshot_dir(), snap_id)
        wanted: dict[str, str] = {}
        for rel, f in meta["files"].items():
            text = _read(os.path.join(folder, rel))
            if text is None:
                return False, f"Snapshot is incomplete: {rel} is missing"
            wanted[f] = text
        for f in meta.get("absent", []):
            wanted[f] = ""  # the file did not exist then; an empty one means the same to niri
        changed = {f: t for f, t in wanted.items() if (_read(f) or "") != t}
        if not changed:
            return True, "The config already matches this snapshot"
        try:
            self.reload()  # validate against what is on disk right now
        except niri_core.KdlError:
            pass  # the current files are broken; restoring is the way out
        ok, message = self._validate_stage(changed)
        if not ok:
            return False, message
        self._snapshot(list(changed), "before restore")
        self._write_all(changed)
        self.clear_preview()
        self.reload()
        return True, f"Restored {len(changed)} file{'s' if len(changed) != 1 else ''}"

    # -- save

    def _write_all(self, texts: dict[str, str]):
        """Write several files; if one fails, put the others back."""
        before = {f: _read(f) for f in texts}
        done = []
        try:
            for f, text in texts.items():
                _write_atomic(f, text)
                done.append(f)
        except BaseException:
            for f in done:
                if before[f] is None:
                    os.unlink(f)
                else:
                    _write_atomic(f, before[f])
            raise

    def save(self) -> tuple[bool, str]:
        """Validate, snapshot the touched files, then write them."""
        dirty = self.tree.dirty_files()
        if not dirty:
            return True, "Nothing to save"
        if self.conflicts:
            return False, "Resolve the conflict with the file on disk first."
        if self.changed_on_disk():
            return False, "The config changed on disk. Reload it before saving."
        ok, message = self.validate()
        if not ok:
            return False, message
        self._snapshot(dirty, "before save")
        try:
            self._write_all({f: self.tree.render(f) for f in dirty})
        except OSError as e:
            return False, f"Could not write: {e}"
        self.clear_preview()
        self.reload()
        return True, f"Saved {len(dirty)} file{'s' if len(dirty) != 1 else ''}"

    # -- include lines for the managed and preview files

    def _add_include(self, name: str, comment: str) -> tuple[bool, str]:
        """Add `include optional=true "<name>"` to the main config.

        Its own validated, snapshotted write, separate from unsaved changes.
        The preview include always stays last so it can override everything.
        """
        if self.changed_on_disk():
            return False, "The config changed on disk. Reload it first."
        current = self.tree.original(self.main)
        block = f'// {comment}\ninclude optional=true "{name}"\n'
        marker = re.search(r'^(//[^\n]*\n)?include optional=true "%s"[^\n]*\n?' % re.escape(PREVIEW_NAME),
                           current, re.M)
        if marker and name != PREVIEW_NAME:
            new = current[:marker.start()] + block + "\n" + current[marker.start():]
        else:
            lead = "" if current.endswith("\n") or not current else "\n"
            new = current + lead + "\n" + block
        ok, message = self._validate_stage({self.main: new})
        if not ok:
            return False, message
        self._snapshot([self.main], f"before adding {name}")
        _write_atomic(self.main, new)
        self.reload()
        return True, ""

    def _reapply(self, pending: dict[str, object]) -> str:
        """Put unsaved changes back after the tree was reloaded."""
        try:
            for path, value in pending.items():
                self._apply(path, value)
        except ReadOnlyError as e:
            return str(e)
        return ""

    def enable_preview(self) -> tuple[bool, str]:
        if self.preview_enabled:
            return True, ""
        pending = self.pending
        ok, message = self._add_include(PREVIEW_NAME, "Live preview of unsaved changes from niri settings.")
        if not ok:
            return False, message
        return True, self._reapply(pending) or "Live preview enabled"

    def set_write_mode(self, mode: str) -> tuple[bool, str]:
        """Switch between editing in place and writing only to niri-gui.kdl.

        The first switch to managed mode adds the include line to config.kdl.
        Unsaved changes are kept and retargeted to the new mode's file.
        """
        if mode == self.write_mode:
            return True, ""
        pending = self.pending
        if mode == MANAGED and not self.managed_enabled:
            ok, message = self._add_include(MANAGED_NAME, "Settings written by niri settings (managed mode).")
            if not ok:
                return False, message
        else:
            self.revert()
        self.write_mode = mode
        note = self._reapply(pending)
        settings = _load_settings()
        settings.setdefault("write_mode", {})[self.main] = mode
        _save_settings(settings)
        return True, note

    # -- first run

    @property
    def setup_done(self) -> bool:
        """True once the first-run choices were made (or skipped) for this config.

        A config that already has a write mode on record set up an earlier version.
        """
        settings = _load_settings()
        return self.main in settings.get("setup_done", []) or self.main in settings.get("write_mode", {})

    def mark_setup_done(self):
        settings = _load_settings()
        done = settings.setdefault("setup_done", [])
        if self.main not in done:
            done.append(self.main)
        _save_settings(settings)

    def default_source(self) -> str | None:
        """niri's own default config, to start from when config.kdl is missing."""
        return next((p for p in DEFAULT_CONFIGS if os.path.isfile(p)), None)

    def suggested_mode(self) -> tuple[str, str]:
        """The write mode to suggest first, and why.

        Managed when the config looks generated or version-controlled: a symlink
        (home-manager, stow), the Nix store, or a git work tree.
        """
        if os.path.islink(self.main):
            return MANAGED, "config.kdl is a symlink, as dotfile managers make it"
        real = os.path.realpath(self.main)
        if real.startswith("/nix/store/"):
            return MANAGED, "config.kdl is in the Nix store"
        stop = os.path.expanduser("~")
        d = os.path.dirname(real)
        while d and d != os.path.dirname(d):
            if os.path.exists(os.path.join(d, ".git")):
                return MANAGED, "config.kdl is in a git repository"
            if d == stop:
                break
            d = os.path.dirname(d)
        return IN_PLACE, ""

    def create_main(self) -> tuple[bool, str]:
        """Write config.kdl from niri's default config when it does not exist."""
        if os.path.exists(self.main):
            return True, ""
        source = self.default_source()
        text = (_read(source) or "") if source else ""
        if not text:
            text = "// niri config. See https://niri-wm.github.io/niri/Configuration%3A-Introduction.html\n"
        try:
            _write_atomic(self.main, text)
        except OSError as e:
            return False, f"Could not create {self.main}: {e.strerror or e}"
        self.reload()
        return True, ""

    def first_run(self, mode: str, preview: bool) -> tuple[bool, str]:
        """Apply the first-run choices: create config.kdl if needed, pick the
        write mode and optionally include the live-preview file. Each include
        line is its own validated, snapshotted write."""
        steps = [self.create_main]
        if mode != self.write_mode:
            steps.append(lambda: self.set_write_mode(mode))
        if preview:
            steps.append(self.enable_preview)
        for step in steps:
            try:
                ok, message = step()
            except OSError as e:
                ok, message = False, f"Could not write the config: {e.strerror or e}"
            if not ok:
                return False, message
        settings = _load_settings()
        settings.setdefault("write_mode", {})[self.main] = self.write_mode
        _save_settings(settings)
        self.mark_setup_done()
        return True, ""

    # -- live preview

    def preview_text(self) -> str:
        """The pending changes as a small KDL overlay that niri merges last."""
        root: dict = {}
        for path, value in self.pending.items():
            parts = path.split("/")
            if parts[0] in RULES or path.startswith(FILE):
                # Rules apply on save: an overlay can add a rule but not
                # change or remove one, so it cannot show an edit faithfully.
                continue
            if parts[0].startswith("output[") or parts[0] == "binds":
                # Display changes are never previewed through the overlay: they
                # can lock the user out and go through a timed trial instead.
                # Key bindings apply on save, so a half-edited bind never fires.
                continue
            # Sections niri does not merge must be written out whole.
            whole = next((i for i in range(1, len(parts) + 1)
                          if "/".join(parts[:i]) in niri_core.NON_MERGING), None)
            if whole is not None:
                section = "/".join(parts[:whole])
                text = self.tree.node_text(section)
                if text is None:
                    text = niri_core.format_node(parts[whole - 1]) + " {}"
                parts, leaf = parts[:whole], text
            elif value is None:
                # A removal cannot be expressed in an overlay, except for flags.
                if parts[-1] == "off":
                    parts, leaf = parts[:-1] + ["on"], "on"
                elif parts[-1] == "on":
                    parts, leaf = parts[:-1] + ["off"], "off"
                elif self._baseline.get(path) is True:
                    leaf = niri_core.format_node(parts[-1], False)
                else:
                    continue
            else:
                leaf = niri_core.format_node(parts[-1], value)
            level = root
            for p in parts[:-1]:
                nxt = level.setdefault(p, {})
                if not isinstance(nxt, dict):
                    break
                level = nxt
            else:
                level[parts[-1]] = leaf

        def emit(level: dict, indent: str) -> list[str]:
            lines = []
            for key, val in level.items():
                if isinstance(val, dict):
                    lines.append(f"{indent}{niri_core.format_node(key)} {{")
                    lines += emit(val, indent + "    ")
                    lines.append(indent + "}")
                else:
                    lines += [indent + line.strip() if i == 0 else line
                              for i, line in enumerate(val.split("\n"))]
            return lines

        if not root:
            return ""
        head = "// Unsaved changes from niri settings. This file is emptied on save or revert.\n"
        return head + "\n".join(emit(root, "")) + "\n"

    def write_preview(self) -> tuple[bool, str]:
        """Show unsaved changes on the running niri. Does nothing unless enabled."""
        if not self.preview_enabled:
            return True, ""
        text = self.preview_text()
        if text == self._preview_written:
            return True, ""
        if text:
            ok, message = self._validate_stage({self.preview_file: text})
            if not ok:
                return False, message
        _write_atomic(self.preview_file, text)
        self._preview_written = text
        return True, ""

    def clear_preview(self):
        if os.path.exists(self.preview_file) and os.path.getsize(self.preview_file):
            _write_atomic(self.preview_file, "")
        self._preview_written = ""


def _rule_ops(old: list[dict], new: list[dict]):
    key = lambda r: json.dumps(r, sort_keys=True, default=str)
    return difflib.SequenceMatcher(None, [key(r) for r in old], [key(r) for r in new],
                                   autojunk=False).get_opcodes()


def _clean_error(stderr: str, tmp: str) -> str:
    """niri's error text without log noise or the temp folder name."""
    lines = []
    for line in stderr.replace(tmp + os.sep, "").splitlines():
        if " WARN " in line or " INFO " in line or " DEBUG " in line:
            continue
        lines.append(line.rstrip())
    text = "\n".join(lines).strip()
    # niri prints a generic "error loading config" block first; keep the specific one.
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if len(blocks) > 1 and "error loading config" in blocks[0]:
        text = "\n\n".join(blocks[1:])
    return text or "niri validate failed"


def _parse_error(text: str) -> dict:
    """Pull the file, line and one-line summary out of niri's error report.

    The `[file:line:col]` header names the first line of the quoted snippet,
    not the faulty one, so the line is read from the snippet: it is the
    numbered line just above the first `──┬──` marker.
    """
    error = {"file": None, "line": None, "path": None, "summary": "", "text": text}
    # With includes niri reports the include line first; the last block is the cause.
    text = text[max(0, text.rfind("Error:")):]
    summaries = re.findall(r"×\s*(.+)", text)
    if summaries:
        error["summary"] = summaries[-1].strip()
    header = re.search(r"\[(.+?):(\d+):\d+\]", text)
    if not header:
        return error
    error["file"], error["line"] = header.group(1), int(header.group(2))
    last = None
    for line in text[header.end():].splitlines():
        numbered = re.match(r"\s*(\d+)\s*│", line)
        if numbered:
            last = int(numbered.group(1))
        elif last is not None and re.match(r"\s*[·•]", line) and ("┬" in line or "─" in line):
            error["line"] = last
            break
    label = re.search(r"╰──\s*(.+)", text[header.end():])
    if label and label.group(1).strip() not in error["summary"]:
        error["summary"] = f"{error['summary']}: {label.group(1).strip()}".lstrip(": ")
    return error
