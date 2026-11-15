import QtQuick
import QtQuick.Controls.Basic
import "."

// On/off switch, 52 × 30 with a 22 px knob.
AbstractButton {
    id: control
    property bool on: false
    property real radius: 15
    implicitWidth: 52
    implicitHeight: 30
    checkable: true
    checked: on
    Accessible.role: Accessible.CheckBox
    Accessible.checked: on
    background: Rectangle {
        radius: 15
        color: control.on ? Theme.accent : Theme.line
        FocusRing { target: control }
    }
    contentItem: Item {
        Rectangle {
            width: 22; height: 22; radius: 11
            y: 4
            x: control.on ? 26 : 4
            color: Theme.text
            Behavior on x { NumberAnimation { duration: Theme.motion; easing.type: Easing.InOutQuad } }
        }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
