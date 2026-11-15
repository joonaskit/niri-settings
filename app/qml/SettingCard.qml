import QtQuick
import QtQuick.Layouts
import "."

// One schema entry drawn as a card. The control depends on `setting.kind`.
Card {
    id: card
    required property var setting
    readonly property int rev: backend.revision
    readonly property string path: setting.path

    function read(p, fallback) {
        rev
        var v = backend.value(p)
        return v === undefined || v === null ? fallback : v
    }
    function sourceHint(p) {
        rev
        return backend.hint(p)
    }

    readonly property string error: { rev; return backend.errorFor(path, setting.kind) }
    border.color: error ? Theme.warnBorder : Theme.line

    Loader {
        Layout.fillWidth: true
        sourceComponent: ({ slider: slider, segmented: segmented, flag: flag, onoff: onoff,
                            widths: widths, struts: struts })[card.setting.kind]
    }
    Text {  // niri's own message, on the setting that caused it
        Layout.fillWidth: true
        visible: card.error !== ""
        text: "✕ " + card.error
        wrapMode: Text.Wrap
        font.pixelSize: Theme.hint
        color: Theme.warnText
        Accessible.role: Accessible.AlertMessage
    }

    component Title: Text {
        font.pixelSize: Theme.body
        font.weight: Font.DemiBold
        color: Theme.text
        wrapMode: Text.Wrap
    }
    component SourceHint: Hint {
        property string of: card.path
        readonly property var parts: card.sourceHint(of).split(" · ")
        config: parts[0]
        plain: parts.slice(1).join(" · ")
    }

    Component {
        id: slider
        ColumnLayout {
            spacing: 10
            RowLayout {
                Title { text: card.setting.label; Layout.fillWidth: true }
                Text {
                    text: range.value + " " + card.setting.unit
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    color: Theme.muted
                }
            }
            RangeSlider {
                id: range
                Layout.fillWidth: true
                from: card.setting.min
                to: Math.max(card.setting.max, stored)
                readonly property real stored: Number(card.read(card.path, card.setting["default"]))
                value: stored
                onMoved: backend.setValue(card.path, value)
                Accessible.name: card.setting.label
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                visible: card.setting.swatches !== undefined
                Repeater {
                    model: card.setting.swatches || []
                    Row {
                        required property var modelData
                        spacing: 6
                        Text {
                            text: modelData[0]
                            font.pixelSize: Theme.hint
                            color: Theme.muted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Rectangle {
                            width: 18; height: 18; radius: 4
                            color: card.read(modelData[1], modelData[2])
                            border.width: 1
                            border.color: Theme.line
                        }
                    }
                }
            }
            SourceHint {}
        }
    }

    Component {
        id: segmented
        ColumnLayout {
            spacing: 10
            Title { text: card.setting.label; Layout.fillWidth: true }
            Segmented {
                Layout.fillWidth: true
                label: card.setting.label
                options: card.setting.options
                current: String(card.read(card.path, card.setting["default"]))
                onPicked: value => backend.setValue(card.path, value)
            }
            SourceHint {}
        }
    }

    Component {
        id: flag
        RowLayout {
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Title { text: card.setting.label; Layout.fillWidth: true }
                Hint { plain: card.setting.hint || "" }
                SourceHint {}
            }
            Toggle {
                on: card.read(card.path, false) === true
                onClicked: backend.setFlag(card.path, !on)
                Accessible.name: card.setting.label
            }
        }
    }

    Component {
        id: onoff
        RowLayout {
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Title { text: card.setting.label; Layout.fillWidth: true }
                Hint { plain: card.setting.hint || "" }
                SourceHint {}
            }
            Toggle {
                on: { card.rev; return backend.isOn(card.path, card.setting["default"]) }
                onClicked: backend.setOn(card.path, !on, card.setting["default"])
                Accessible.name: card.setting.label
            }
        }
    }

    Component {
        id: widths
        ColumnLayout {
            id: w
            spacing: 10
            readonly property var current: { card.rev; return backend.widthCurrent(card.path) }
            readonly property var presets: { card.rev; return backend.widthPresets(card.setting.presets) }
            Title { text: card.setting.label; Layout.fillWidth: true }
            Flow {
                Layout.fillWidth: true
                spacing: 6
                Accessible.role: Accessible.Grouping
                Accessible.name: card.setting.label
                Repeater {
                    model: w.presets
                    Chip {
                        required property var modelData
                        text: modelData.label
                        on: modelData.kind === w.current.kind
                            && Math.abs(modelData.value - w.current.value) < 0.002
                        onClicked: backend.setWidth(card.path, modelData.kind, modelData.value)
                    }
                }
            }
            Hint { plain: card.setting.hint || "" }
            SourceHint {}
        }
    }

    Component {
        id: struts
        ColumnLayout {
            spacing: 10
            Title { text: card.setting.label; Layout.fillWidth: true }
            Flow {
                Layout.fillWidth: true
                spacing: 12
                Repeater {
                    model: card.setting.sides
                    Row {
                        required property string modelData
                        spacing: 8
                        Text {
                            id: sideLabel
                            text: modelData
                            font.family: Theme.mono
                            font.pixelSize: Theme.config
                            color: Theme.muted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        NumberField {
                            from: card.setting.min
                            to: card.setting.max
                            number: Number(card.read(card.path + "/" + modelData, 0))
                            onCommitted: value => backend.setValue(card.path + "/" + modelData, value)
                            Accessible.name: card.setting.label + " " + modelData
                        }
                    }
                }
            }
            Hint { plain: card.setting.hint || "" }
            SourceHint {}
        }
    }
}
