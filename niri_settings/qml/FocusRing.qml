import QtQuick
import "."

// 2 px accent ring around the parent (a control's background) while the
// control `target` has keyboard focus.
Rectangle {
    property Item target
    anchors.fill: parent
    anchors.margins: -3
    radius: parent.radius + 3
    color: "transparent"
    border.width: 2
    border.color: Theme.accent
    visible: target !== null && target.visualFocus === true
}
