# niri settings — GUI style rules

Nov 15, 2026 · @Joonas

## Principles

The app is a calm, dark, tool-like surface where only one blue accent marks what is active. These rules are taken from the five concept screens and apply to every new screen.

- **One accent.** Blue `#8fb0ff` marks the current selection, the primary action and links. Use nothing else for emphasis.
- **Color always carries a meaning.** The other hues are reserved for status (ok, warning) and for action categories in the keybind map. They are never decoration.
- **Flat layers, no shadows.** Depth comes from four steps of background lightness plus 1 px borders.
- **Show the config.** Values that map to KDL (keys, paths, file:line, actions) are always set in monospace, so the user can see what will be written.
- **No gradients, no emoji, no left-border accent cards.**

## Color

The palette has 4 background steps, 2 border tones, 2 text tones, 1 accent and 2 status families. Contrast is measured against the darkest background the color sits on.

### Backgrounds and lines

| Token | Hex | Used for |
| --- | --- | --- |
| `ground` | `#0f1115` | App background, segmented-control track, code blocks, text on accent fills |
| `chrome` | `#13161c` | Top bar, sidebar, side panels, footer, keyboard plate |
| `surface` | `#161920` | Cards and setting groups |
| `raised` | `#1d212a` | Inputs, selects, tag chips, list rows, free keys |
| `selected` | `#1f2633` | Selected list item, focused window in the preview, current file |
| `line` | `#2a2f3a` | Every border and divider (1 px) |
| `line-strong` | `#505868` | Inactive focus ring, window border in the preview, unpinned monitor |

### Text and accent

| Token | Hex | Used for | Contrast |
| --- | --- | --- | --- |
| `text` | `#e7e9ee` | Body text, headings, controls | 15.6:1 on ground, 13.3:1 on raised |
| `muted` | `#a0a7b4` | Labels, hints, metadata, KDL comments | 7.8:1 on ground, 6.7:1 on raised |
| `accent` | `#8fb0ff` | Active nav item, pressed segment, primary button, slider and checkbox fill, links, focus ring | 8.5:1 on chrome |
| `accent-hover` | `#b9ccff` | Link hover | — |
| `on-accent` | `#0f1115` | Text on any accent or category fill | 8.8:1 on accent |

### Status

| Token | Text | Fill | Border | Used for |
| --- | --- | --- | --- | --- |
| `ok` | `#a8e6c6` (dot/inline: `#7fd1a8`) | `#16261f` | `#3f7a5d` | Validation passed, matching window, added diff line |
| `warn` | `#f6c896` (inline: `#f2a65a`) | `#2a2116` | `#6b4a24` | Conflicts, removed diff line, unsaved marker, urgent ring |

### Keybind categories

These four colors appear only in the keybind map and its legend, always with `on-accent` text.

| Category | Hex |
| --- | --- |
| Focus and navigation | `#8fb0ff` |
| Columns and windows | `#c4a7ff` |
| Workspaces and monitors | `#7fd1a8` |
| Spawn and system | `#f2a65a` |

## Typography

There are two families: **Inter** for all interface text and **JetBrains Mono** for anything that is config. Use only the weights 400, 600 and 700.

| Role | Family | Size / line | Weight | Notes |
| --- | --- | --- | --- | --- |
| Page title | Inter | 22 px | 700 | Letter-spacing −0.02em. Screen 1 uses 24 px; align it to 22 |
| Section title | Inter | 18 px | 700 | E.g. the selected rule's name |
| App name, panel title | Inter | 16 px | 700 | “niri settings”, “DP-1”, “Open windows” |
| Body, controls | Inter | 14 px | 400 | Default for the whole app |
| Setting label | Inter | 14 px | 600 | The bold name above a control |
| Secondary | Inter | 13 px | 400 | Segmented buttons, chips, panel text, banners |
| Hint, metadata | Inter | 12 px | 400 | Always `muted` |
| Group label | Inter | 11 px | 600 | Uppercase, letter-spacing 0.08em, `muted` |
| Key cap | Inter | 11 px | 600 | Action line under it: 9 px |
| Config value | JetBrains Mono | 13 px | 400 | Actions, regexes, key chips, slider readouts, file tree |
| Code block | JetBrains Mono | 12–13 px / 1.6–1.75 | 400 | Generated KDL, source view |
| Small config ref | JetBrains Mono | 11 px | 400 | app-id and workspace under a window name |

- Use monospace for: KDL nodes and values, action names, file names with line numbers, regexes, key combos, and numbers with units shown as readouts (`16 px`).
- Never use monospace for labels or explanations.
- Write sentence case everywhere except group labels. Never set body text in bold.

## Spacing, layout and sizing

Spacing runs on a 4 px grid. Use 8, 12, 16 and 24 most of the time; 2, 6, 10 and 14 are only for tight spots inside a control.

### Spacing

| Where | Value |
| --- | --- |
| App top bar | 14 px vertical, 20 px horizontal, 16 px between items |
| Page header (inside content) | 18 px vertical, 28 px horizontal, 12 px between items |
| Main content area | 24–32 px padding, 16–24 px between blocks |
| Side panel | 20–24 px padding, 14–16 px between groups |
| Card | 16 px padding, 10 px between its rows |
| Grid of cards | 16 px gap; 12 px for dense info cards |
| Sidebar | 16 px × 12 px padding; items 8 × 10 px, 2 px apart; 14 px above each group label |
| Footer | 12 px × 20 px, 12 px between items, 8 px between buttons |

### Layout

- The app window is designed at 1280 × 820 px.
- **Sidebar:** flex basis 220 px. **Content:** `flex: 999 1 560px; min-width: 0`.
- **Side panels** (details, open windows, validation): basis 240–280 px, separated by a 1 px `line` on the left.
- **Inner lists** (rule list, include tree): basis 190–200 px.
- Every row is `flex-wrap: wrap`, so on a narrow window panels stack under the content instead of shrinking.
- Wide content (keyboard map, code) scrolls sideways inside its own box; the page itself never scrolls sideways.
- Card grids use `repeat(N, minmax(0, 1fr))`: 2 columns for setting cards, 3 for info cards.

### Control sizes

| Control | Size |
| --- | --- |
| Button, input, select | 36 px tall, 12–16 px horizontal padding |
| Segment inside a segmented control | 32–36 px tall in a 4 px padded track |
| Width chip (pill) | 36 px tall, min-width 64 px |
| Tag chip | 4 × 10 px padding, 13 px text |
| Checkbox | 18 × 18 px |
| Toggle switch | 52 × 30 px, 22 px knob |
| Key cap | 40 px per unit, 48 px tall, 5 px gap |
| Layout preview | 560 × 300 px |

## Borders, radii and elevation

Every border is 1 px solid `line` (`#2a2f3a`). Thicker strokes are only for selection and focus. There are no drop shadows anywhere.

### Borders

| Element | Border |
| --- | --- |
| Cards, inputs, chips, panels, dividers | 1 px `line` |
| Selected list item, focused input | 1 px `accent` |
| Status banner | 1 px of its status border tone |
| Area you can drop or arrange things in (displays canvas) | 1 px dashed `line` |
| Selected monitor | 2 px `accent` plus a 6 px halo of accent at 15% opacity |
| Selected key cap | 2 px `ground` gap, then a 2 px `text` ring |

The `line` tone is only 1.4:1 on `chrome`, so a border never carries meaning on its own. A selected state always changes fill or text color as well.

### Radii

| Radius | Used for |
| --- | --- |
| 6 px | Sidebar items, segments, small key chips, compact selects |
| 7–8 px | Buttons, inputs, list rows, monitors, key caps |
| 10 px | Banners, code blocks, window tiles in the preview |
| 12 px | Cards and setting groups |
| 14 px | Large canvases (keyboard plate, displays area) |
| Full pill | Width chips, tag chips, toggles, status dots |

### Elevation

Elevation is shown only by background step, from back to front: `ground` → `chrome` → `surface` → `raised` / `selected`. Overlays such as menus and the command palette sit on `raised` with a 1 px `line` border. They are not designed yet.

## Components

Each component below is defined by the tokens above. A new screen should use only these components.

| Component | Default | Active / selected | Notes |
| --- | --- | --- | --- |
| Primary button | `accent` fill, `on-accent` 600 text, no border | — | At most one per view: Save, Try, New rule, Record |
| Secondary button | Transparent, 1 px `line`, `text` | — | Review diff, Revert, Import |
| Segmented control | `ground` track, 4 px padding, segments transparent with `text` | Segment filled `accent`, `on-accent` text | For 2–4 exclusive choices (center column, layer, view, profile) |
| Width chip | Pill, 1 px `line`, mono 13 px | `accent` fill and border | Choices that are config values (1/3, 1/2, 2/3) |
| Tag chip | Pill, `raised`, 1 px `line`, 13 px | — | Read-only values: workspaces, matches |
| Text input, select | `raised`, 1 px `line`, 36 px | Border turns `accent` on focus | Config values inside it are mono |
| Slider | Native range input with `accent-color` | — | Mono readout on the right of the label row: `16 px` |
| Checkbox | 18 px, `accent-color` | — | Label to the right, 10 px gap |
| Toggle switch | `line` track | `accent` track, knob slides right | On/off settings that apply right away |
| Setting card | `surface`, 1 px `line`, 12 px radius, 16 px padding | — | Order: bold label + readout, then the control, then a 12 px muted hint or `section › key · file:line` |
| Sidebar item | Transparent, `text` | `accent` fill, `on-accent` 600 text | Grouped under 11 px uppercase labels |
| List row | Transparent or `raised` | `selected` fill + 1 px `accent` | Title 600 + 12 px muted subline |
| Status banner | Status fill, border and text | — | Bold lead word (“Conflict:”), one sentence, link on the right |
| Code block | `ground` or `chrome`, 1 px `line`, 10 px radius | Diff: `ok` / `warn` fill per line | Mono 12–13 px, wraps |
| Key cap | Bound: category fill + `on-accent`; free: `raised` + `muted` | Ring as in Borders | Modifier caps held in the current layer: `text` fill |
| Status dot | 8 px circle | — | `ok` green = connected |

## Accessibility and interaction

These rules keep the app usable with a keyboard and a screen reader, and keep config changes safe.

- **Contrast:** text is at least 4.5:1 against its background. The current palette passes everywhere; the lowest pair is `muted` on `raised` at 6.7:1.
- **Not color alone:** every state shown by color also changes shape, fill or text, such as a ✓, a “free” label or a ring.
- **Targets:** anything clickable is at least 36 px tall; aim for 44 px on touch screens.
- **Real controls:** use `button`, `a`, `input`, `select` and `label`, never clickable divs. Buttons that toggle set `aria-pressed`, the current nav item sets `aria-current`, and icon-only buttons get an `aria-label`.
- **Focus:** every control shows a 2 px `accent` focus ring when it has keyboard focus.
- **Motion:** transitions are 0.2–0.3 s ease, and only for moving or resizing (preview tiles, the toggle knob). Respect reduced-motion.
- **Applying changes:** live-apply settings that are safe; anything that can lock you out (display mode, quit binds) needs a timed confirm. Changes are saved only from the footer, after validation.
- **Where a value comes from:** each setting can show which file and line sets it, and whether a per-output or per-workspace override replaces it.
