import QtQuick
import QtQuick.Controls.Basic
import "."

// A colour square that opens the colour picker. `value` is the config
// colour; `fallback` is shown dimmed when there is none (niri's default).
AbstractButton {
    id: swatch
    property string value: ""
    property string fallback: ""
    property string label: "colour"
    property int size: 18
    signal picked(string value)

    implicitWidth: size
    implicitHeight: size
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: "Pick " + label
    onClicked: picker.open()

    background: Rectangle {
        radius: swatch.size > 20 ? Theme.radiusSmall : 4
        color: Theme.cssColor(swatch.value || swatch.fallback)
        opacity: swatch.value ? 1 : 0.5
        border.width: swatch.hovered || swatch.visualFocus ? 2 : 1
        border.color: swatch.hovered || swatch.visualFocus ? Theme.accent : Theme.lineStrong
    }

    ColorPicker {
        id: picker
        y: swatch.height + 6
        value: swatch.value || swatch.fallback
        onPicked: v => swatch.picked(v)
    }
}
