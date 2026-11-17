import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes
import "."

// A niri gradient: from and to colours, angle, what it is relative to, and
// the colour space it blends in. `value` is {from, to, angle, rel, in};
// `edited` hands back the whole value with one field changed.
// The preview blends in sRGB, so it is close but not exact for other spaces.
ColumnLayout {
    id: root
    property var value: ({})
    property var relOptions: []
    property var inOptions: []
    property string label: ""
    signal edited(var value)

    spacing: 8

    function changed(key, v) {
        var next = { from: value.from, to: value.to, angle: value.angle, rel: value.rel, "in": value["in"] }
        next[key] = v
        edited(next)
    }

    // CSS linear-gradient geometry: the line runs through the centre at
    // `angle` (0 = upwards, clockwise) and is long enough that the corners
    // get the end colours.
    Rectangle {
        id: preview
        Layout.fillWidth: true
        implicitHeight: 22
        radius: 4
        color: "transparent"
        border.width: 1
        border.color: Theme.lineStrong
        clip: true
        Accessible.ignored: true

        readonly property real rad: (root.value.angle === undefined ? 180 : root.value.angle) * Math.PI / 180
        readonly property real half: (Math.abs(width * Math.sin(rad)) + Math.abs(height * Math.cos(rad))) / 2

        Shape {
            anchors.fill: parent
            anchors.margins: 1
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeWidth: -1
                fillGradient: LinearGradient {
                    x1: preview.width / 2 - Math.sin(preview.rad) * preview.half
                    y1: preview.height / 2 + Math.cos(preview.rad) * preview.half
                    x2: preview.width / 2 + Math.sin(preview.rad) * preview.half
                    y2: preview.height / 2 - Math.cos(preview.rad) * preview.half
                    GradientStop { position: 0; color: Theme.cssColor(root.value.from) }
                    GradientStop { position: 1; color: Theme.cssColor(root.value.to) }
                }
                startX: 0; startY: 0
                PathLine { x: preview.width - 2; y: 0 }
                PathLine { x: preview.width - 2; y: preview.height - 2 }
                PathLine { x: 0; y: preview.height - 2 }
                PathLine { x: 0; y: 0 }
            }
        }
    }

    Flow {
        Layout.fillWidth: true
        spacing: 8

        Repeater {
            model: [{ key: "from", name: "from" }, { key: "to", name: "to" }]
            Row {
                required property var modelData
                spacing: 6
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.name
                    font.family: Theme.mono; font.pixelSize: Theme.config; color: Theme.muted
                }
                Field {
                    id: colourField
                    width: 112
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    text: root.value[modelData.key] || ""
                    Accessible.name: root.label + " " + modelData.name + " colour"
                    onEditingFinished: if (text !== root.value[modelData.key]) root.changed(modelData.key, text)
                }
                ColorSwatch {
                    anchors.verticalCenter: parent.verticalCenter
                    value: root.value[modelData.key] || ""
                    label: root.label + " " + modelData.name + " colour"
                    onPicked: v => root.changed(modelData.key, v)
                }
            }
        }

        Row {
            spacing: 6
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "angle"
                font.family: Theme.mono; font.pixelSize: Theme.config; color: Theme.muted
            }
            NumberField {
                width: 64
                from: -360; to: 720
                number: root.value.angle === undefined ? 180 : root.value.angle
                Accessible.name: root.label + " angle in degrees"
                onCommitted: function(v) { if (v !== root.value.angle) root.changed("angle", v) }
            }
        }

        Row {
            spacing: 6
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "relative to"
                font.family: Theme.mono; font.pixelSize: Theme.config; color: Theme.muted
            }
            Select {
                width: 150
                model: root.relOptions
                current: root.value.rel || "window"
                Accessible.name: root.label + " relative to"
                onPicked: function(v) { if (v !== root.value.rel) root.changed("rel", v) }
            }
        }

        Row {
            spacing: 6
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "in"
                font.family: Theme.mono; font.pixelSize: Theme.config; color: Theme.muted
            }
            Select {
                width: 190
                model: root.inOptions
                current: root.value["in"] || "srgb"
                Accessible.name: root.label + " blend colour space"
                onPicked: function(v) { if (v !== root.value["in"]) root.changed("in", v) }
            }
        }
    }
}
