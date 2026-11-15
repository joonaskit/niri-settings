# niri settings — implementation plan

Nov 15, 2026 · @Joonas

## Stack and key decisions

Recommendation: the UI in **Python + PySide6 (QML)**, with a small **Rust core** loaded as a Python module for the parts that need to be exact: editing KDL without losing comments. This matches the Python/Qt stack of your file manager, and the core uses the same libraries niri's own tools use.

| Decision | Choice | Why |
| --- | --- | --- |
| UI toolkit | PySide6 + QML | Fluid layouts, animation and custom drawing (preview, keyboard, displays canvas) are much easier in QML than in widgets |
| App logic | Python view-models exposed to QML | Fast to iterate; same skills as the file manager |
| KDL editing | Rust `kdl` crate 6.x via PyO3 + maturin | [Parses and edits KDL while keeping formatting, whitespace and comments](https://docs.rs/crate/kdl/6.7.0/source/Cargo.toml) — like `toml_edit`, but for KDL. Python KDL libraries don't do this reliably |
| niri IPC | Python, plain JSON over `$NIRI_SOCKET` | One JSON message per line; the [niri-ipc docs](https://niri-wm.github.io/niri/IPC.html) list every request and event. No Rust needed |
| Validation | Run `niri validate -c <staged copy>` | Always matches the installed niri version, with niri's own error messages |
| Applying changes | Write files; niri live-reloads | [niri watches the config and every included file and reloads on change](https://niri-wm.github.io/niri/Configuration%3A-Include.html) |
| Style | Tokens from the GUI style rules doc in one `Theme.qml` singleton | One place for colours, type and spacing |

Alternative if you'd rather avoid two languages: all Rust with GTK4/libadwaita (relm4). It reuses the same crates directly but drops the Python/Qt code you already know.

Sources: [kdl crate](https://docs.rs/crate/kdl/6.7.0/source/Cargo.toml) · [niri IPC](https://niri-wm.github.io/niri/IPC.html) · [niri includes](https://niri-wm.github.io/niri/Configuration%3A-Include.html) · [niri config intro](https://niri-wm.github.io/niri/Configuration%3A-Introduction.html)

## Architecture

&#91;embedded content: architecture · app, config files, niri\]

The UI never touches files or niri directly. Every write goes through the Rust core, which validates a staged copy first. niri picks up changes by watching the files; IPC is only used to read live state and for temporary display tries.

## Config model

The core loads the whole include tree into editable KDL documents, one per file. The UI reads one merged view of it, and every edit goes back into the file that owns the value.

1. **Load.** Start from `$NIRI_CONFIG` or `~/.config/niri/config.kdl` and follow `include` lines in order, recursively. Optional includes may be missing. Keep each file as its own document.
2. **Merge for display.** Build the effective value of each setting the way niri does: [most sections merge, so a later file only changes the properties it sets](https://mintlify.wiki/niri-wm/niri/configuration/include), while repeated nodes such as window rules add up. For every value, record its source (file, line, and whether an output or workspace override replaces it). This feeds the `file:line` hints and the "why" view in window rules.
3. **Edit.** Each setting maps to a path in a schema such as `layout › focus-ring › width`. An edit changes only that node in its owning file. A new setting goes to the target file chosen by the write mode.
4. **Two write modes.**
   - **In place:** edit the user's own files. Needed when changing an existing bind or window rule, because an overlay can add rules but not remove one.
   - **Managed include:** the user's files stay read-only and changes go into `niri-gui.kdl`. Once, with the user's consent, the app appends `include optional=true "niri-gui.kdl"` as the last line of `config.kdl`. This fits NixOS and dotfile repos.
5. **Validate before write.** Copy the tree to a temp directory, apply the pending edits there and run `niri validate -c` on the copy. Only a clean result is written to the real files.
6. **Snapshots.** Before each save, copy the touched files to `~/.local/state/niri-settings/snapshots/<timestamp>/`. Keep the last 50 plus any the user names. Restore is a normal save, so it is validated too.
7. **Outside edits.** Watch the files. If the user edits one in their text editor while the app is open, reload it and rebase pending changes onto it, or ask when the same node changed on both sides.

The schema (every section, key, type, default and the niri version it arrived in) is hand-written from niri's config docs at first. It drives the forms, search and validation hints, and is updated with each niri release.

## Rust core API

The Rust part is one small module, `niri_core`, that only loads, merges and edits KDL text. Python does everything else, so day-to-day work never touches Rust. It is built with `maturin develop` and used as `import niri_core`.

| Call | Returns | What it does |
| --- | --- | --- |
| `load_tree(main_path)` | `Tree` | Reads `config.kdl` and every include, in order. Raises `KdlError` with file, line and message on a parse error |
| `tree.get(path)` | value or `None` | The effective, merged value niri would use |
| `tree.source_of(path)` | `{file, line, overridden_by}` | Where a value is set, and which output or workspace override replaces it |
| `tree.list(path)` | list of paths | Children of a section, e.g. every `window-rule` or `output` |
| `tree.set(path, value, file)` | — | Changes or adds one node in one file, in memory only |
| `tree.remove(path, file)` | — | Deletes one node in one file, in memory only |
| `tree.render(file)` | `str` | The full edited text of that file, with untouched parts byte-for-byte the same |
| `tree.dirty_files()` | list of paths | Files with unsaved edits |
| `tree.reload_file(file)` | — | Re-reads one file after an outside edit |

**Paths** are plain strings: `layout/focus-ring/width`, `output[DP-1]/scale`, `window-rule#3/open-floating`, `binds/Mod+H`. **Values** cross as Python `int`, `float`, `str`, `bool`, `None`, or a dict `{"args": [...], "props": {...}}` for nodes with several values.

**What stays in Python:** writing files to disk, running `niri validate`, snapshots, file watching, the niri IPC socket and event stream, the schema, and all UI.

Project layout:

```
niri-settings/
  core/            Rust crate niri_core (kdl + pyo3), about 300 lines
    src/lib.rs
    tests/roundtrip.rs
  app/             Python package
    ipc.py         niri socket + event stream
    config.py      wraps niri_core, validate, snapshots
    schema/        settings definitions
    qml/           screens + Theme.qml
  tests/corpus/    real configs for round-trip tests
```

## Talking to niri

The app keeps two IPC connections and a preview file. Every change you make is visible in niri within about a fifth of a second and is undone if you leave without saving.

- **Event stream (socket 1).** A background thread requests the event stream on `$NIRI_SOCKET`. [It sends the full current state first, then updates](https://niri-wm.github.io/niri/IPC.html): windows, workspaces, outputs and keyboard layouts. That state powers the layout preview, the open-windows list and rule matching.
- **Requests (socket 2).** Requests go on a second socket, because [a socket that is streaming events can't take new requests](https://niri-wm.github.io/niri/niri_ipc/). These are output queries, `focus-window` when you click a window in a list, and similar.
- **Live preview.** Unsaved changes are written, debounced by about 150 ms, to `niri-gui-preview.kdl`, which is included after everything else. niri reloads it, so dragging the gaps slider really changes your desktop. Save moves the changes to their target file and empties the preview file. Revert, or closing the app, just empties it.
- **Risky changes.** Display mode, scale and position are first tried with `niri msg output`, which [changes an output temporarily without saving to the config](https://www.mintlify.com/niri-wm/niri/features/ipc). If you don't press Keep within 15 s, the old values are restored and nothing is written. Binds that could lock you out (removing the only `quit` or terminal bind) get a confirm step.
- **When a reload fails.** [niri keeps the last valid config and shows a notification](https://deepwiki.com/YaLTeR/niri/3.1-configuration-basics). The app also runs validation first, so this should only happen through outside edits. Validation errors are shown inline on the setting that caused them.
- **niri not running** (editing from a TTY or another session). The app works offline: it skips live preview and IPC, and just validates and writes files.

## Screens

The app shell (sidebar, top bar, footer) and setting cards are shared. Most screens are forms generated from the schema; four need custom-drawn parts.

| Screen | Built from | Needs from niri | Hard part |
| --- | --- | --- | --- |
| App shell + search | Sidebar, top bar, footer with validation and Save | IPC status, niri version | Search across every schema key, bind and rule; pending-change count and diff |
| Layout | Setting cards + custom preview | Windows and columns of the focused workspace | Drawing the scrolling preview from real window sizes; showing per-output overrides |
| Displays | Custom canvas + form panel | Outputs, modes, make/model/serial | Drag-to-arrange with snapping in logical pixels; the 15 s try-and-revert; display profiles |
| Key bindings | Custom keyboard map + detail panel | List of actions (from the niri-ipc action types) | Physical layout from the xkb keymap; finding conflicts across include files; recording a shortcut while niri itself grabs the keys |
| Window rules | Rule list + match/apply builder | Open windows (app-id, title) | Regex matching identical to niri's; the merged "why" view per window |
| Config files | Include tree + source editor + diff | — | Two-way link between source lines and controls; editing raw KDL with validation as you type |
| Simple forms | Schema-driven cards | — | Appearance & blur, animations, input devices, startup apps, environment, layer rules, gestures |

Recording a shortcut needs niri to stop handling keys while the dialog is open. Check whether the `toggle-keyboard-shortcuts-inhibit` approach works for this, or the app may have to read keys some other way.

## Milestones

Build the risky core first: a settings app that can damage a config is worse than none. No dates are set yet, so each phase ends on an exit check rather than a deadline.

1. **Core spike.** Write niri\_core with the API above (Rust, kdl + PyO3, built with maturin); from Python load the tree, change one value, write it back and run `niri validate`.
   - Exit check: round-tripping 20 real configs (yours plus public dotfiles) without editing leaves every file byte-for-byte unchanged.
2. **Shell + Layout screen.** QML shell from the style rules, the schema for `layout`, setting cards, the preview file, the event stream and the live layout preview.
   - Exit check: dragging gaps changes the desktop live; Revert restores it exactly; Save writes only the changed lines.
3. **Safety net.** Snapshots, diff view, write modes (in place / managed include), watching for outside edits, inline validation errors.
   - Exit check: a bad edit can never reach the real files; any save can be undone from Snapshots.
4. **Displays.** Output canvas, try-and-revert with `niri msg output`, profiles.
   - Exit check: a wrong scale or mode is reverted after 15 s without touching the config.
5. **Key bindings.** Keyboard map, action picker, conflict detection, recording.
   - Exit check: the map matches `binds {}` exactly for your config and the default config.
6. **Window rules.** Builder, live matching, per-window "why" view, templates.
   - Exit check: for each open window the app's matches agree with what niri actually applies.
7. **Remaining forms + config files screen.** Schema-driven pages for every other section; source editor with two-way linking.
   - Exit check: every top-level section in niri's config docs has a page or is listed as source-only.
8. **Release.** Packaging, first-run flow (pick a write mode, add the include line), docs.
   - Exit check: a fresh install on Fedora works from the app menu with no terminal steps.

## Testing and packaging

The core gets most of the tests because it is the part that can break a config. The UI is checked against the style rules and by hand.

**Testing**

- **Round-trip corpus:** a folder of real `config.kdl` trees. Each test loads a tree, saves it without changes and checks it is byte-identical, then makes a set of edits and checks that `niri validate` passes and that the diff touches only the expected lines.
- **Schema check:** for each schema key, write its default into a blank config and validate it. This catches keys niri renamed or removed.
- **IPC fakes:** recorded event-stream logs replayed into the view-models, so the preview and window lists can be tested without a running niri.
- **Nested niri:** for end-to-end runs, start niri as a window inside your current session with its own config and socket, and drive the app against it.
- **UI:** QML tests for the custom components (preview, keyboard, canvas); a checklist against the style rules doc for each screen.

**Packaging**

- Build the Rust module as a wheel with maturin; the app itself is a normal Python package.
- Fedora: an RPM through COPR, next to [niri's own COPR builds](https://niri-wm.github.io/niri/Development%3A-Releasing-niri.html). Arch: AUR. NixOS: a flake, defaulting to managed-include mode.
- Flatpak is a poor fit: the app needs your real config folder, the niri socket and the `niri` binary on the host.

## Risks and open questions

| Risk | Effect | Mitigation |
| --- | --- | --- |
| KDL version mismatch | The kdl crate defaults to KDL v2; niri's config may still be parsed as KDL v1 | Confirm in the core spike; enable the crate's `v1` / `v1-fallback` feature and write back in the version the file uses |
| Schema falls behind niri | New keys show as "unknown" and can't be edited in forms | Unknown nodes are always kept and editable in source view; check the schema against each niri release |
| Merge rules are subtle | The UI shows a value that niri doesn't actually use | Test the merged view against niri's behaviour in nested niri; show the source of every value |
| Live preview writes often | Many reloads while dragging; notification spam on errors | Debounce, validate before writing the preview file, write only on value change |
| Two languages to build | Harder setup and packaging | Keep the Rust module small (KDL editing and merge only) behind one Python API |

Open questions

- [ ] Do you want the app to target only your own setup first (Fedora, your config), or other people's configs from day one?
- [ ] Name and icon for the app.
- [ ] Should the Quickshell shell or Orbit get quick toggles (gaps, blur, VRR) that talk to this app's core?
- [ ] Is a command-line mode wanted (`niri-settings set layout.gaps 20`) using the same core?
