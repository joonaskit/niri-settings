"""niri IPC: one JSON message per line over $NIRI_SOCKET.

`request()` opens a short-lived socket per request. `EventStream` keeps a
second socket open on a background thread, because a socket that is streaming
events cannot take new requests. `NiriState` folds events into the current
state and has no I/O, so recorded event logs can be replayed into it in tests.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time


def socket_path() -> str | None:
    path = os.environ.get("NIRI_SOCKET")
    return path if path and os.path.exists(path) else None


def request(message, timeout: float = 2.0):
    """Send one request; return the Ok payload, or None if niri is unreachable."""
    path = socket_path()
    if not path:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(path)
            s.sendall((json.dumps(message) + "\n").encode())
            line = s.makefile("r", encoding="utf-8").readline()
        reply = json.loads(line)
    except (OSError, ValueError):
        return None
    return reply.get("Ok") if isinstance(reply, dict) else None


def process_started(pid) -> float | None:
    """When a process started, as a Unix time; None if unknown."""
    try:
        with open(f"/proc/{int(pid)}/stat", encoding="ascii") as fh:
            # The command name may hold spaces and parentheses: split after the last ")".
            fields = fh.read().rsplit(")", 1)[1].split()
        ticks = int(fields[19])     # field 22, starttime, in clock ticks since boot
        with open("/proc/stat", encoding="ascii") as fh:
            boot = next(int(line.split()[1]) for line in fh if line.startswith("btime "))
        return boot + ticks / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError, StopIteration, TypeError):
        return None


def niri_pid() -> int | None:
    """niri's pid, from the socket name `niri.<display>.<pid>.sock`."""
    path = socket_path()
    name = os.path.basename(path or "")
    parts = name.split(".")
    if len(parts) >= 4 and parts[0] == "niri" and parts[-1] == "sock" and parts[-2].isdigit():
        return int(parts[-2])
    return None


def niri_started() -> float | None:
    """When the running niri started, as a Unix time; None if unknown."""
    pid = niri_pid()
    return process_started(pid) if pid else None


def version() -> str | None:
    reply = request("Version")
    return reply.get("Version") if isinstance(reply, dict) else None


def outputs() -> dict:
    reply = request("Outputs")
    return reply.get("Outputs", {}) if isinstance(reply, dict) else {}


class NiriState:
    """Windows and workspaces, kept current from event-stream events."""

    def __init__(self, clock=time.time):
        self.windows: dict[int, dict] = {}
        self.workspaces: dict[int, dict] = {}
        self.opened: dict[int, float] = {}   # window id -> Unix time it was seen opening
        self._clock = clock

    def apply(self, event: dict) -> bool:
        """Fold one event in. Returns True if the state changed."""
        if not isinstance(event, dict) or len(event) != 1:
            return False
        (kind, data), = event.items()
        if kind == "WindowsChanged":
            self.windows = {w["id"]: w for w in data["windows"]}
            self.opened = {k: v for k, v in self.opened.items() if k in self.windows}
        elif kind == "WindowOpenedOrChanged":
            w = data["window"]
            if w["id"] not in self.windows:
                self.opened[w["id"]] = self._clock()
            if w.get("is_focused"):
                for other in self.windows.values():
                    other["is_focused"] = False
            self.windows[w["id"]] = w
        elif kind == "WindowClosed":
            self.windows.pop(data["id"], None)
            self.opened.pop(data["id"], None)
        elif kind == "WindowFocusChanged":
            for w in self.windows.values():
                w["is_focused"] = w["id"] == data["id"]
        elif kind == "WindowLayoutsChanged":
            for wid, layout in data["changes"]:
                if wid in self.windows:
                    self.windows[wid]["layout"] = layout
        elif kind == "WorkspacesChanged":
            self.workspaces = {w["id"]: w for w in data["workspaces"]}
        elif kind == "WorkspaceActivated":
            target = self.workspaces.get(data["id"])
            if target:
                for w in self.workspaces.values():
                    if w["output"] == target["output"]:
                        w["is_active"] = w["id"] == data["id"]
                    if data.get("focused"):
                        w["is_focused"] = w["id"] == data["id"]
        elif kind == "WorkspaceActiveWindowChanged":
            if data["workspace_id"] in self.workspaces:
                self.workspaces[data["workspace_id"]]["active_window_id"] = data["active_window_id"]
        else:
            return False
        return True

    def focused_workspace(self) -> dict | None:
        return next((w for w in self.workspaces.values() if w.get("is_focused")), None)

    def columns(self, workspace_id: int) -> list[list[dict]]:
        """Tiled windows of a workspace as columns, left to right, top to bottom."""
        cols: dict[int, list[tuple[int, dict]]] = {}
        for w in self.windows.values():
            pos = (w.get("layout") or {}).get("pos_in_scrolling_layout")
            if w.get("workspace_id") != workspace_id or w.get("is_floating") or not pos:
                continue
            cols.setdefault(pos[0], []).append((pos[1], w))
        return [[w for _, w in sorted(cols[c], key=lambda t: t[0])] for c in sorted(cols)]


class EventStream(threading.Thread):
    """Reads the event stream and calls `on_change()` after each state change."""

    def __init__(self, state: NiriState, on_change):
        super().__init__(daemon=True, name="niri-event-stream")
        self.state = state
        self.on_change = on_change
        self.lock = threading.Lock()
        self._sock: socket.socket | None = None

    def run(self):
        path = socket_path()
        if not path:
            return
        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.connect(path)
            self._sock.sendall(b'"EventStream"\n')
            for line in self._sock.makefile("r", encoding="utf-8"):
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                with self.lock:
                    changed = self.state.apply(event)
                if changed:
                    self.on_change()
        except (OSError, RuntimeError):
            pass  # socket closed, or the app is shutting down

    def stop(self):
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
