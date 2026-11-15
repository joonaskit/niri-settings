# niri settings

A settings app for the [niri](https://github.com/YaLTeR/niri) compositor. It edits your
KDL config in place, keeps comments and formatting, and never writes a file that
`niri validate` rejects.

The plan, style rules and concept screens are in `desing/`.

## Run

Needs Python 3 with PySide6 (Fedora: `python3-pyside6`) and `niri` on the PATH.

```
python3 -m app                      # edits $NIRI_CONFIG or ~/.config/niri/config.kdl
python3 -m app --config some.kdl    # edit another config tree
python3 -m app --offline            # do not talk to niri over IPC
```

## Test

```
python3 -m unittest discover -s tests -t .
```

## Displays

Mode, scale, rotation, position and on/off are never applied by saving alone. "Try for
15 s" sends them to niri with `niri msg output`, which does not touch the config, and
`app/output_guard.py` (a separate process) reverts them unless you press Keep. Save is
refused while there are display changes that have not been tried and kept.

## Key bindings

The map shows `binds {}` for one modifier layer at a time. Keys are placed with the xkb
keymap niri uses (the `xkb {}` section, else the system setting from `localectl`), read
through libxkbcommon; without the library a US layout is drawn. Binds with no key on the
map (media keys, wheel, mouse, or a key your layout does not have) are listed under it.

- A bind is edited as a whole node: `binds/Mod+T`. Only the changed part of its line is
  rewritten.
- Bind changes apply on save. They are never sent through the live-preview file.
- Removing or re-purposing your only `quit` bind or only terminal bind asks first.
- "Record shortcut" reads the key press from the window. niri handles its own shortcuts
  before the app sees them, and this Qt build has no shortcuts-inhibit support, so a
  combination niri already uses must be picked on the map instead.

## Layout

```
app/
  niri_core.py   load, merge and edit the KDL include tree (text splices, no re-serialising)
  config.py      pending changes, staged validation, snapshots, save, live-preview file
  ipc.py         niri socket requests and the event stream
  viewmodel.py   the one object QML talks to
  displays.py    outputs: drafts vs live state, the timed trial, profiles (no Qt)
  displays_view.py  the Displays page's object in QML
  output_guard.py   reverts a display trial even if the app dies
  keymap.py      xkb keymap (libxkbcommon via ctypes) and the physical key layout
  binds.py       key bindings: conflicts, edits, the lockout check (no Qt)
  binds_view.py  the Key bindings page's object in QML
  schema/        settings definitions that drive the forms; the action catalogue
  qml/           Theme.qml (style tokens), shared controls, pages
tests/
  corpus/        config trees used by the round-trip tests
```

## Safety net

- Every save is validated on a staged copy with `niri validate` first.
- The touched files are copied to `~/.local/state/niri-settings/snapshots/` before each
  save. Restore one from Config files; a restore is validated and snapshotted too.
- Write mode (Config files page): `in-place` edits the file that sets each value;
  `managed` leaves your files read-only and writes only to an included `niri-gui.kdl`.
- If a file changes on disk while you have unsaved changes, they are re-applied on top.
  A setting changed on both sides is shown as a conflict to resolve before saving.
