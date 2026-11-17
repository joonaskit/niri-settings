import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// One property of a window rule: label, an editor for its kind, and remove.
// `item` comes from RulesView.detail: {path, label, kind, value, text, options, note, …}.
Rectangle {
    id: row
    property var item: ({})
    signal edited(var value)
    signal removed()

    implicitHeight: content.implicitHeight + 20
    radius: Theme.radius
    color: Theme.raised

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 6
        anchors.topMargin: 10
        anchors.bottomMargin: 10
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 72
                text: row.item.label || ""
                wrapMode: Text.Wrap
                font.pixelSize: Theme.body
                color: Theme.text
            }

            // bool
            Toggle {
                visible: row.item.kind === "bool"
                on: row.item.value === true
                Accessible.name: row.item.label
                onClicked: row.edited(!on)
            }

            // int
            NumberField {
                visible: row.item.kind === "int"
                number: row.item.kind === "int" ? row.item.value : 0
                from: -99999; to: 99999
                Accessible.name: row.item.label
                onCommitted: function(value) { row.edited(value) }
            }

            // float, text, color
            Field {
                id: textField
                visible: ["float", "text", "color"].indexOf(row.item.kind) >= 0 && !row.item.suggest
                implicitWidth: row.item.kind === "float" ? 80 : 160
                font.family: Theme.mono
                font.pixelSize: Theme.config
                text: visible ? String(row.item.text === undefined ? "" : (row.item.kind === "float" ? row.item.text : row.item.value)) : ""
                Accessible.name: row.item.label
                onEditingFinished: {
                    var current = row.item.kind === "float" ? row.item.text : row.item.value
                    if (text !== String(current)) row.edited(text)
                }
            }
            // output or workspace name, with a list of the ones niri knows
            SuggestField {
                visible: row.item.kind === "text" && !!row.item.suggest
                implicitWidth: 200
                font.family: Theme.mono
                font.pixelSize: Theme.config
                kind: row.item.suggest || ""
                stored: visible ? String(row.item.value || "") : ""
                placeholderText: kind === "outputs" ? "DP-1" : "name"
                Accessible.name: row.item.label
                onCommitted: v => row.edited(v)
            }
            ColorSwatch {
                visible: row.item.kind === "color"
                value: visible ? String(row.item.value || "") : ""
                label: row.item.label || "colour"
                onPicked: v => row.edited(v)
            }

            // enum
            Select {
                visible: row.item.kind === "enum"
                implicitWidth: 160
                model: row.item.kind === "enum" ? row.item.options : []
                current: row.item.kind === "enum" ? row.item.value : ""
                Accessible.name: row.item.label
                onPicked: function(value) { row.edited(value) }
            }

            // on / off flags of a block
            Segmented {
                visible: row.item.kind === "onoff"
                implicitWidth: 120
                options: ["on", "off"]
                current: row.item.kind === "onoff" ? row.item.value : ""
                label: row.item.label
                onPicked: function(value) { row.edited(value) }
            }

            // size: proportion / fixed / app decides
            Select {
                id: sizeKind
                visible: row.item.kind === "size"
                implicitWidth: 140
                model: row.item.kind === "size" ? row.item.options : []
                current: row.item.kind === "size" ? row.item.sizeKind : ""
                Accessible.name: row.item.label + " kind"
                onPicked: function(value) {
                    var start = value === "fixed" ? "800" : value === "proportion" ? "0.5" : ""
                    row.edited({ kind: value, value: value === row.item.sizeKind ? row.item.sizeValue : start })
                }
            }
            Field {
                visible: row.item.kind === "size" && row.item.sizeKind !== ""
                implicitWidth: 80
                font.family: Theme.mono
                font.pixelSize: Theme.config
                text: row.item.kind === "size" ? row.item.sizeValue : ""
                Accessible.name: row.item.label + (row.item.sizeKind === "fixed" ? " in pixels" : " as a share of the screen")
                onEditingFinished: if (text !== row.item.sizeValue) row.edited({ kind: row.item.sizeKind, value: text })
            }

            // position: x, y, relative-to; xy: x, y
            Text {
                visible: row.item.kind === "position" || row.item.kind === "xy"
                text: "x"; font.family: Theme.mono; font.pixelSize: Theme.config; color: Theme.muted
            }
            NumberField {
                implicitWidth: 64
                visible: row.item.kind === "position" || row.item.kind === "xy"
                number: visible ? row.item.x : 0
                Accessible.name: row.item.label + " x"
                onCommitted: function(value) { row.edited({ x: value, y: row.item.y, rel: row.item.rel }) }
            }
            Text {
                visible: row.item.kind === "position" || row.item.kind === "xy"
                text: "y"; font.family: Theme.mono; font.pixelSize: Theme.config; color: Theme.muted
            }
            NumberField {
                implicitWidth: 64
                visible: row.item.kind === "position" || row.item.kind === "xy"
                number: visible ? row.item.y : 0
                Accessible.name: row.item.label + " y"
                onCommitted: function(value) { row.edited({ x: row.item.x, y: value, rel: row.item.rel }) }
            }
            Select {
                visible: row.item.kind === "position"
                implicitWidth: 138
                model: row.item.kind === "position" ? row.item.options : []
                current: row.item.kind === "position" ? row.item.rel : ""
                Accessible.name: row.item.label + " relative to"
                onPicked: function(value) { row.edited({ x: row.item.x, y: row.item.y, rel: value }) }
            }

            // anything else, as KDL
            Field {
                visible: row.item.kind === "kdl"
                Layout.preferredWidth: 220
                Layout.minimumWidth: 100
                font.family: Theme.mono
                font.pixelSize: Theme.config
                text: row.item.kind === "kdl" ? row.item.text : ""
                Accessible.name: row.item.label + " as KDL"
                onEditingFinished: if (text !== row.item.text) row.edited(text)
            }

            Btn {
                implicitWidth: 36
                leftPadding: 0; rightPadding: 0
                text: "×"
                font.pixelSize: Theme.body
                Accessible.name: "Remove " + (row.item.label || "")
                onClicked: row.removed()
            }
        }

        // gradient: its own row under the label, it has five fields
        GradientField {
            visible: row.item.kind === "gradient"
            Layout.fillWidth: true
            Layout.rightMargin: 6
            label: row.item.label || ""
            value: row.item.kind === "gradient" ? row.item.value : ({})
            relOptions: row.item.relOptions || []
            inOptions: row.item.inOptions || []
            onEdited: function(value) { row.edited(value) }
        }

        // e.g. a colour that a gradient in the same block wins over, or an unknown output
        Text {
            readonly property string unknown: row.item.suggest
                ? backend.suggestionNote(row.item.suggest, String(row.item.value || "")) : ""
            visible: text !== ""
            Layout.fillWidth: true
            text: [row.item.note || "", unknown].filter(function (t) { return t }).join(". ")
            wrapMode: Text.Wrap
            font.pixelSize: Theme.secondary
            color: Theme.muted
        }
    }
}
