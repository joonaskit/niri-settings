pragma Singleton
import QtQuick

// Every colour, size and font of the app. Values come from the GUI style rules.
QtObject {
    // Backgrounds and lines
    readonly property color ground: "#0f1115"
    readonly property color chrome: "#13161c"
    readonly property color surface: "#161920"
    readonly property color raised: "#1d212a"
    readonly property color selected: "#1f2633"
    readonly property color line: "#2a2f3a"
    readonly property color lineStrong: "#505868"
    readonly property color previewGround: "#1a1e27"
    readonly property color tile: "#232833"
    readonly property color tileFocused: "#2a3140"

    // Text and accent
    readonly property color text: "#e7e9ee"
    readonly property color muted: "#a0a7b4"
    readonly property color accent: "#8fb0ff"
    readonly property color accentHover: "#b9ccff"
    readonly property color accentInk: "#0f1115"  // the `on-accent` token; "on…" is reserved in QML

    // Status
    readonly property color okText: "#a8e6c6"
    readonly property color okInline: "#7fd1a8"
    readonly property color okFill: "#16261f"
    readonly property color okBorder: "#3f7a5d"
    readonly property color warnText: "#f6c896"
    readonly property color warnInline: "#f2a65a"
    readonly property color warnFill: "#2a2116"
    readonly property color warnBorder: "#6b4a24"

    // Type
    readonly property string sans: "Inter"
    readonly property string mono: "JetBrains Mono"
    readonly property int pageTitle: 22
    readonly property int sectionTitle: 18
    readonly property int panelTitle: 16
    readonly property int body: 14
    readonly property int secondary: 13
    readonly property int hint: 12
    readonly property int groupLabel: 11
    readonly property int config: 13

    // Sizes
    readonly property int control: 36
    readonly property int radiusSmall: 6
    readonly property int radius: 8
    readonly property int radiusBlock: 10
    readonly property int radiusCard: 12
    readonly property int sidebar: 220

    // Motion: only for things that move or resize
    readonly property int motion: 200
}
