import QtQuick
import QtQuick.Controls.Basic
import "."

Slider {
    id: control
    property real radius: 4
    implicitHeight: 24
    stepSize: 1
    snapMode: Slider.SnapAlways
    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: control.availableWidth
        height: 4
        radius: 2
        color: Theme.line
        Rectangle {
            width: control.visualPosition * parent.width
            height: parent.height
            radius: 2
            color: Theme.accent
        }
    }
    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: 16; height: 16; radius: 8
        color: Theme.accent
        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: 11
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            visible: control.visualFocus
        }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
