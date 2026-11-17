import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Picks a colour without typing hex: a saturation/brightness square, hue and
// opacity bars, a hex field and a few niri colours. `value` is the colour as
// written in the config (CSS order, #rrggbbaa); "Use" emits `picked` with
// the new one, written as #rrggbb, or #rrggbbaa when it is see-through.
// Nothing is written while dragging: an edit rebuilds the cards, which
// would close the picker.
Popup {
    id: picker
    property string value: ""
    signal picked(string value)

    property real hue: 0
    property real sat: 0
    property real val: 1
    property real alpha: 1
    readonly property color current: Qt.hsva(hue, sat, val, alpha)
    readonly property string css: toCss(current)

    // niri's own defaults and a few common accents.
    readonly property var presets: ["#7fc8ff", "#ffc87f", "#505050", "#9b0000", "#80c8ff", "#bbddff",
                                    "#e5989b", "#c7ff7f", "#ffffff", "#000000", "#00000070", "#ffc87f80"]

    padding: 14
    modal: false
    focus: true
    margins: 8
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle {
        radius: Theme.radiusCard
        color: Theme.raised
        border.width: 1
        border.color: Theme.lineStrong
    }

    function hex2(n) {
        var s = Math.round(Math.max(0, Math.min(1, n)) * 255).toString(16)
        return s.length < 2 ? "0" + s : s
    }
    function toCss(c) {
        return "#" + hex2(c.r) + hex2(c.g) + hex2(c.b) + (c.a < 0.999 ? hex2(c.a) : "")
    }
    // Take a config colour (CSS hex or a name) as the starting point.
    property color parsed
    function load(text) {
        var t = String(text || "").trim()
        if (!t) return false
        parsed = "transparent"
        parsed = Theme.cssColor(t)
        var c = parsed
        if (!c.valid || (c.a === 0 && t !== "transparent" && !/^#(?:[0-9a-f]{3}0|[0-9a-f]{6}00)$/i.test(t))) return false
        alpha = c.a
        val = c.hsvValue
        sat = c.hsvSaturation
        if (c.hsvHue >= 0) hue = c.hsvHue      // greys have no hue: keep the last one
        return true
    }
    // Close before emitting: the write rebuilds the card this picker lives in.
    function use(text) {
        load(text)
        var v = css
        close()
        picked(v)
    }
    onAboutToShow: { load(value); hexField.text = css }
    onCssChanged: if (!hexField.activeFocus) hexField.text = css

    contentItem: ColumnLayout {
        spacing: 10

        // saturation left to right, brightness bottom to top
        Rectangle {
            id: square
            Layout.preferredWidth: 232
            Layout.preferredHeight: 150
            radius: 4
            color: Qt.hsva(picker.hue, 1, 1, 1)
            Rectangle {
                anchors.fill: parent
                radius: 4
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "#ffffffff" }
                    GradientStop { position: 1; color: "#00ffffff" }
                }
            }
            Rectangle {
                anchors.fill: parent
                radius: 4
                gradient: Gradient {
                    GradientStop { position: 0; color: "#00000000" }
                    GradientStop { position: 1; color: "#ff000000" }
                }
            }
            Rectangle {
                x: picker.sat * square.width - 7
                y: (1 - picker.val) * square.height - 7
                width: 14; height: 14; radius: 7
                color: "transparent"
                border.width: 2
                border.color: picker.val > 0.5 && picker.sat < 0.5 ? "black" : "white"
            }
            MouseArea {
                anchors.fill: parent
                function set(m) {
                    picker.sat = Math.max(0, Math.min(1, m.x / width))
                    picker.val = 1 - Math.max(0, Math.min(1, m.y / height))
                }
                onPressed: m => set(m)
                onPositionChanged: m => set(m)
            }
            Accessible.role: Accessible.Slider
            Accessible.name: "Saturation and brightness"
        }

        // hue
        Bar {
            id: hueBar
            position: picker.hue
            Accessible.name: "Hue"
            onMoved: p => picker.hue = Math.min(p, 0.999)
            Rectangle {
                anchors.fill: parent
                radius: 4
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0 / 6; color: "#ff0000" }
                    GradientStop { position: 1 / 6; color: "#ffff00" }
                    GradientStop { position: 2 / 6; color: "#00ff00" }
                    GradientStop { position: 3 / 6; color: "#00ffff" }
                    GradientStop { position: 4 / 6; color: "#0000ff" }
                    GradientStop { position: 5 / 6; color: "#ff00ff" }
                    GradientStop { position: 1;     color: "#ff0000" }
                }
            }
        }

        // opacity, over a checkerboard so see-through shows
        Bar {
            position: picker.alpha
            Accessible.name: "Opacity"
            onMoved: p => picker.alpha = p
            Grid {
                anchors.fill: parent
                columns: Math.ceil(width / 6)
                clip: true
                Repeater {
                    model: Math.ceil(parent.width / 6) * 2
                    Rectangle {
                        required property int index
                        readonly property int cols: Math.ceil(parent.width / 6)
                        width: 6; height: 6
                        color: (index % cols + Math.floor(index / cols)) % 2 ? "#9a9a9a" : "#e6e6e6"
                    }
                }
            }
            Rectangle {
                anchors.fill: parent
                radius: 4
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.hsva(picker.hue, picker.sat, picker.val, 0) }
                    GradientStop { position: 1; color: Qt.hsva(picker.hue, picker.sat, picker.val, 1) }
                }
            }
        }

        Flow {
            Layout.preferredWidth: 232
            spacing: 6
            Repeater {
                model: picker.presets
                Rectangle {
                    required property string modelData
                    width: 14; height: 14; radius: 3
                    color: Theme.cssColor(modelData)
                    border.width: 1
                    border.color: Theme.lineStrong
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: picker.load(modelData)
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Preset " + modelData
                }
            }
        }

        RowLayout {
            spacing: 8
            Rectangle {
                implicitWidth: 28; implicitHeight: 28
                radius: Theme.radiusSmall
                color: picker.current
                border.width: 1
                border.color: Theme.lineStrong
                Accessible.ignored: true
            }
            Field {
                id: hexField
                Layout.fillWidth: true
                font.family: Theme.mono
                font.pixelSize: Theme.config
                Accessible.name: "Colour as hex"
                onEditingFinished: if (!picker.load(text)) text = picker.css
                onAccepted: picker.use(text)
            }
        }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8
            Btn { text: "Cancel"; onClicked: picker.close() }
            Btn {
                text: "Use"
                onClicked: picker.use(hexField.text)
            }
        }
    }

    // A horizontal bar with a handle; `moved` gives 0..1.
    component Bar: Item {
        id: bar
        property real position: 0
        signal moved(real p)
        Layout.preferredWidth: 232
        Layout.preferredHeight: 14
        Accessible.role: Accessible.Slider
        Rectangle {
            z: 2
            x: bar.position * bar.width - 4
            y: -2
            width: 8; height: bar.height + 4; radius: 3
            color: "transparent"
            border.width: 2
            border.color: "white"
        }
        MouseArea {
            z: 3
            anchors.fill: parent
            function set(m) { bar.moved(Math.max(0, Math.min(1, m.x / width))) }
            onPressed: m => set(m)
            onPositionChanged: m => set(m)
        }
        Keys.onLeftPressed: bar.moved(Math.max(0, bar.position - 0.02))
        Keys.onRightPressed: bar.moved(Math.min(1, bar.position + 0.02))
    }
}
