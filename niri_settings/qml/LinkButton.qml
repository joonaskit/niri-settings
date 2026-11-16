import QtQuick
import QtQuick.Controls.Basic
import "."

// A link-styled button for small inline actions: file:line, Reset.
AbstractButton {
    id: control
    property bool mono: false
    property real radius: 4
    implicitHeight: 24
    leftPadding: 2
    rightPadding: 2
    contentItem: Text {
        text: control.text
        font.family: control.mono ? Theme.mono : Theme.sans
        font.pixelSize: Theme.hint
        font.underline: control.hovered
        color: control.hovered ? Theme.accentHover : Theme.accent
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: control.radius
        color: "transparent"
        FocusRing { target: control }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
