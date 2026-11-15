import QtQuick
import QtQuick.Controls.Basic
import "."

// Small numeric input for a config value. Commits on Enter or focus loss.
TextField {
    id: control
    property real number: 0
    property real from: -9999
    property real to: 9999
    signal committed(real value)

    implicitHeight: Theme.control
    implicitWidth: 72
    leftPadding: 12
    rightPadding: 12
    font.family: Theme.mono
    font.pixelSize: Theme.config
    color: Theme.text
    selectionColor: Theme.accent
    selectedTextColor: Theme.accentInk
    selectByMouse: true
    validator: IntValidator { bottom: control.from; top: control.to }
    text: String(number)
    onNumberChanged: if (!activeFocus) text = String(number)
    onEditingFinished: {
        var v = parseInt(text)
        if (isNaN(v)) { text = String(number); return }
        v = Math.max(from, Math.min(to, v))
        text = String(v)
        if (v !== number) committed(v)
    }
    background: Rectangle {
        radius: Theme.radius
        color: Theme.raised
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.accent : Theme.line
    }
}
