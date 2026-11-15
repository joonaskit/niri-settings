"""Actions a key can be bound to.

`SNAPSHOT` was generated from `niri msg action --help` (niri 26.04). At run
time `load()` asks the installed niri instead, so newer actions show up; the
snapshot is the fallback when niri is not on the PATH.
"""

from __future__ import annotations

import re
import shutil
import subprocess

# (name, description, arguments as the CLI shows them)
SNAPSHOT = [
    ('quit', 'Exit niri', ''),
    ('power-off-monitors', 'Power off all monitors via DPMS', ''),
    ('power-on-monitors', 'Power on all monitors via DPMS', ''),
    ('spawn', 'Spawn a command', '-- <COMMAND>...'),
    ('spawn-sh', 'Spawn a command through the shell', '-- <COMMAND>'),
    ('do-screen-transition', 'Do a screen transition', ''),
    ('screenshot', 'Open the screenshot UI', ''),
    ('screenshot-screen', 'Screenshot the focused screen', ''),
    ('screenshot-window', 'Screenshot the focused window', ''),
    ('toggle-keyboard-shortcuts-inhibit', 'Enable or disable the keyboard shortcuts inhibitor (if any) for the focused surface', ''),
    ('close-window', 'Close the focused window', ''),
    ('fullscreen-window', 'Toggle fullscreen on the focused window', ''),
    ('toggle-windowed-fullscreen', 'Toggle windowed (fake) fullscreen on the focused window', ''),
    ('focus-window', 'Focus a window by id', '--id <ID>'),
    ('focus-window-in-column', 'Focus a window in the focused column by index', '<INDEX>'),
    ('focus-window-previous', 'Focus the previously focused window', ''),
    ('focus-column-left', 'Focus the column to the left', ''),
    ('focus-column-right', 'Focus the column to the right', ''),
    ('focus-column-first', 'Focus the first column', ''),
    ('focus-column-last', 'Focus the last column', ''),
    ('focus-column-right-or-first', 'Focus the next column to the right, looping if at end', ''),
    ('focus-column-left-or-last', 'Focus the next column to the left, looping if at start', ''),
    ('focus-column', 'Focus a column by index', '<INDEX>'),
    ('focus-window-or-monitor-up', 'Focus the window or the monitor above', ''),
    ('focus-window-or-monitor-down', 'Focus the window or the monitor below', ''),
    ('focus-column-or-monitor-left', 'Focus the column or the monitor to the left', ''),
    ('focus-column-or-monitor-right', 'Focus the column or the monitor to the right', ''),
    ('focus-window-down', 'Focus the window below', ''),
    ('focus-window-up', 'Focus the window above', ''),
    ('focus-window-down-or-column-left', 'Focus the window below or the column to the left', ''),
    ('focus-window-down-or-column-right', 'Focus the window below or the column to the right', ''),
    ('focus-window-up-or-column-left', 'Focus the window above or the column to the left', ''),
    ('focus-window-up-or-column-right', 'Focus the window above or the column to the right', ''),
    ('focus-window-or-workspace-down', 'Focus the window or the workspace below', ''),
    ('focus-window-or-workspace-up', 'Focus the window or the workspace above', ''),
    ('focus-window-top', 'Focus the topmost window', ''),
    ('focus-window-bottom', 'Focus the bottommost window', ''),
    ('focus-window-down-or-top', 'Focus the window below or the topmost window', ''),
    ('focus-window-up-or-bottom', 'Focus the window above or the bottommost window', ''),
    ('move-column-left', 'Move the focused column to the left', ''),
    ('move-column-right', 'Move the focused column to the right', ''),
    ('move-column-to-first', 'Move the focused column to the start of the workspace', ''),
    ('move-column-to-last', 'Move the focused column to the end of the workspace', ''),
    ('move-column-left-or-to-monitor-left', 'Move the focused column to the left or to the monitor to the left', ''),
    ('move-column-right-or-to-monitor-right', 'Move the focused column to the right or to the monitor to the right', ''),
    ('move-column-to-index', 'Move the focused column to a specific index on its workspace', '<INDEX>'),
    ('move-window-down', 'Move the focused window down in a column', ''),
    ('move-window-up', 'Move the focused window up in a column', ''),
    ('move-window-down-or-to-workspace-down', 'Move the focused window down in a column or to the workspace below', ''),
    ('move-window-up-or-to-workspace-up', 'Move the focused window up in a column or to the workspace above', ''),
    ('consume-or-expel-window-left', 'Consume or expel the focused window left', ''),
    ('consume-or-expel-window-right', 'Consume or expel the focused window right', ''),
    ('consume-window-into-column', 'Consume the window to the right into the focused column', ''),
    ('expel-window-from-column', 'Expel the bottom window from the focused column', ''),
    ('swap-window-right', 'Swap focused window with one to the right', ''),
    ('swap-window-left', 'Swap focused window with one to the left', ''),
    ('toggle-column-tabbed-display', 'Toggle the focused column between normal and tabbed display', ''),
    ('set-column-display', 'Set the display mode of the focused column', '<DISPLAY>'),
    ('center-column', 'Center the focused column on the screen', ''),
    ('center-window', 'Center the focused window on the screen', ''),
    ('center-visible-columns', 'Center all fully visible columns on the screen', ''),
    ('focus-workspace-down', 'Focus the workspace below', ''),
    ('focus-workspace-up', 'Focus the workspace above', ''),
    ('focus-workspace', 'Focus a workspace by reference (index or name)', '<REFERENCE>'),
    ('focus-workspace-previous', 'Focus the previous workspace', ''),
    ('move-window-to-workspace-down', 'Move the focused window to the workspace below', ''),
    ('move-window-to-workspace-up', 'Move the focused window to the workspace above', ''),
    ('move-window-to-workspace', 'Move the focused window to a workspace by reference (index or name)', '<REFERENCE>'),
    ('move-column-to-workspace-down', 'Move the focused column to the workspace below', ''),
    ('move-column-to-workspace-up', 'Move the focused column to the workspace above', ''),
    ('move-column-to-workspace', 'Move the focused column to a workspace by reference (index or name)', '<REFERENCE>'),
    ('move-workspace-down', 'Move the focused workspace down', ''),
    ('move-workspace-up', 'Move the focused workspace up', ''),
    ('move-workspace-to-index', 'Move the focused workspace to a specific index on its monitor', '<INDEX>'),
    ('set-workspace-name', 'Set the name of the focused workspace', '<NAME>'),
    ('unset-workspace-name', 'Unset the name of the focused workspace', '[REFERENCE]'),
    ('focus-monitor-left', 'Focus the monitor to the left', ''),
    ('focus-monitor-right', 'Focus the monitor to the right', ''),
    ('focus-monitor-down', 'Focus the monitor below', ''),
    ('focus-monitor-up', 'Focus the monitor above', ''),
    ('focus-monitor-previous', 'Focus the previous monitor', ''),
    ('focus-monitor-next', 'Focus the next monitor', ''),
    ('focus-monitor', 'Focus a monitor by name', '<OUTPUT>'),
    ('move-window-to-monitor-left', 'Move the focused window to the monitor to the left', ''),
    ('move-window-to-monitor-right', 'Move the focused window to the monitor to the right', ''),
    ('move-window-to-monitor-down', 'Move the focused window to the monitor below', ''),
    ('move-window-to-monitor-up', 'Move the focused window to the monitor above', ''),
    ('move-window-to-monitor-previous', 'Move the focused window to the previous monitor', ''),
    ('move-window-to-monitor-next', 'Move the focused window to the next monitor', ''),
    ('move-window-to-monitor', 'Move the focused window to a specific monitor', '<OUTPUT>'),
    ('move-column-to-monitor-left', 'Move the focused column to the monitor to the left', ''),
    ('move-column-to-monitor-right', 'Move the focused column to the monitor to the right', ''),
    ('move-column-to-monitor-down', 'Move the focused column to the monitor below', ''),
    ('move-column-to-monitor-up', 'Move the focused column to the monitor above', ''),
    ('move-column-to-monitor-previous', 'Move the focused column to the previous monitor', ''),
    ('move-column-to-monitor-next', 'Move the focused column to the next monitor', ''),
    ('move-column-to-monitor', 'Move the focused column to a specific monitor', '<OUTPUT>'),
    ('set-window-width', 'Change the width of the focused window', '<CHANGE>'),
    ('set-window-height', 'Change the height of the focused window', '<CHANGE>'),
    ('reset-window-height', 'Reset the height of the focused window back to automatic', ''),
    ('switch-preset-column-width', 'Switch between preset column widths', ''),
    ('switch-preset-column-width-back', 'Switch between preset column widths backwards', ''),
    ('switch-preset-window-width', 'Switch between preset window widths', ''),
    ('switch-preset-window-width-back', 'Switch between preset window widths backwards', ''),
    ('switch-preset-window-height', 'Switch between preset window heights', ''),
    ('switch-preset-window-height-back', 'Switch between preset window heights backwards', ''),
    ('maximize-column', 'Toggle the maximized state of the focused column', ''),
    ('maximize-window-to-edges', 'Toggle the maximized-to-edges state of the focused window', ''),
    ('set-column-width', 'Change the width of the focused column', '<CHANGE>'),
    ('expand-column-to-available-width', 'Expand the focused column to space not taken up by other fully visible columns', ''),
    ('switch-layout', 'Switch between keyboard layouts', '<LAYOUT>'),
    ('show-hotkey-overlay', 'Show the hotkey overlay', ''),
    ('move-workspace-to-monitor-left', 'Move the focused workspace to the monitor to the left', ''),
    ('move-workspace-to-monitor-right', 'Move the focused workspace to the monitor to the right', ''),
    ('move-workspace-to-monitor-down', 'Move the focused workspace to the monitor below', ''),
    ('move-workspace-to-monitor-up', 'Move the focused workspace to the monitor above', ''),
    ('move-workspace-to-monitor-previous', 'Move the focused workspace to the previous monitor', ''),
    ('move-workspace-to-monitor-next', 'Move the focused workspace to the next monitor', ''),
    ('move-workspace-to-monitor', 'Move the focused workspace to a specific monitor', '<OUTPUT>'),
    ('toggle-debug-tint', 'Toggle a debug tint on windows', ''),
    ('debug-toggle-opaque-regions', 'Toggle visualization of render element opaque regions', ''),
    ('debug-toggle-damage', 'Toggle visualization of output damage', ''),
    ('toggle-window-floating', 'Move the focused window between the floating and the tiling layout', ''),
    ('move-window-to-floating', 'Move the focused window to the floating layout', ''),
    ('move-window-to-tiling', 'Move the focused window to the tiling layout', ''),
    ('focus-floating', 'Switches focus to the floating layout', ''),
    ('focus-tiling', 'Switches focus to the tiling layout', ''),
    ('switch-focus-between-floating-and-tiling', 'Toggles the focus between the floating and the tiling layout', ''),
    ('move-floating-window', 'Move the floating window on screen', ''),
    ('toggle-window-rule-opacity', 'Toggle the opacity of the focused window', ''),
    ('set-dynamic-cast-window', 'Set the dynamic cast target to the focused window', ''),
    ('set-dynamic-cast-monitor', 'Set the dynamic cast target to the focused monitor', '[OUTPUT]'),
    ('clear-dynamic-cast-target', 'Clear the dynamic cast target, making it show nothing', ''),
    ('stop-cast', 'Stop a PipeWire screencast', '--session-id <SESSION_ID>'),
    ('toggle-overview', 'Toggle (open/close) the Overview', ''),
    ('open-overview', 'Open the Overview', ''),
    ('close-overview', 'Close the Overview', ''),
    ('toggle-window-urgent', 'Toggle urgent status of a window', '--id <ID>'),
    ('set-window-urgent', 'Set urgent status of a window', '--id <ID>'),
    ('unset-window-urgent', 'Unset urgent status of a window', '--id <ID>'),
    ('load-config-file', 'Reload the config file', ''),
]

FOCUS, WINDOWS, WORKSPACES, SYSTEM = "focus", "windows", "workspaces", "system"

CATEGORIES = [
    {"id": FOCUS, "label": "Focus and navigation", "color": "#8fb0ff"},
    {"id": WINDOWS, "label": "Columns and windows", "color": "#c4a7ff"},
    {"id": WORKSPACES, "label": "Workspaces and monitors", "color": "#7fd1a8"},
    {"id": SYSTEM, "label": "Spawn and system", "color": "#f2a65a"},
]

_SYSTEM = re.compile(
    r"^(spawn|spawn-sh|quit|power-|screenshot|do-screen-transition|show-hotkey-overlay"
    r"|switch-layout|toggle-keyboard-shortcuts-inhibit|load-config-file|suspend"
    r"|toggle-debug|debug-|.*cast)")


def category(action: str) -> str:
    """Which of the four keybind-map colours an action gets."""
    if _SYSTEM.match(action):
        return SYSTEM
    if "workspace" in action or "monitor" in action or "overview" in action:
        return WORKSPACES
    if action.startswith("focus-") or action.startswith("switch-focus"):
        return FOCUS
    return WINDOWS


def _from_niri(niri_bin: str) -> list[tuple[str, str, str]]:
    if shutil.which(niri_bin) is None:
        return []
    try:
        out = subprocess.run([niri_bin, "msg", "action", "--help"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    known = {name: usage for name, _, usage in SNAPSHOT}
    found, lines = [], out.splitlines()
    for i, line in enumerate(lines[:-1]):
        m = re.match(r"^  ([a-z][a-z0-9-]*)$", line)
        if m and lines[i + 1].startswith("      ") and m.group(1) != "help":
            found.append((m.group(1), lines[i + 1].strip(), known.get(m.group(1), "")))
    return found


_cache: dict[str, list[dict]] = {}


def load(niri_bin: str = "niri") -> list[dict]:
    """All actions as {name, description, usage, category}."""
    if niri_bin not in _cache:
        rows = _from_niri(niri_bin) or SNAPSHOT
        _cache[niri_bin] = [{"name": n, "description": d, "usage": u, "category": category(n)}
                            for n, d, u in rows]
    return _cache[niri_bin]
