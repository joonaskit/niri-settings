import QtQuick
import QtQuick.Controls.Basic
import "."

// Pill for a choice that is a config value, such as 1/3 or 1/2.
AbstractButton {
    id: control
    property bool on: false
    property real radius: 18
    implicitHeight: Theme.control
    implicitWidth: Math.max(64, label.implicitWidth + 24)
    checkable: true
    checked: on
    Accessible.checked: on
    contentItem: Text {
        id: label
        text: control.text
        font.family: Theme.mono
        font.pixelSize: Theme.config
        color: control.on ? Theme.accentInk : Theme.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 18
        color: control.on ? Theme.accent : (control.hovered ? Theme.raised : "transparent")
        border.width: 1
        border.color: control.on ? Theme.accent : Theme.line
        FocusRing { target: control }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
