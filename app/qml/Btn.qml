import QtQuick
import QtQuick.Controls.Basic
import "."

Button {
    id: control
    property bool primary: false
    property real radius: Theme.radius
    implicitHeight: Theme.control
    leftPadding: primary ? 16 : 14
    rightPadding: leftPadding
    font.pixelSize: Theme.secondary
    font.weight: primary ? Font.DemiBold : Font.Normal
    opacity: enabled ? 1 : 0.45
    contentItem: Text {
        text: control.text
        font: control.font
        color: control.primary ? Theme.accentInk : Theme.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: control.radius
        color: control.primary ? (control.hovered ? Theme.accentHover : Theme.accent)
                               : (control.hovered ? Theme.raised : "transparent")
        border.width: control.primary ? 0 : 1
        border.color: Theme.line
        FocusRing { target: control }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
