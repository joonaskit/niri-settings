import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// 18 px checkbox with its label on the right.
AbstractButton {
    id: control
    property bool on: false
    property real radius: 4
    implicitHeight: Math.max(Theme.control, label.implicitHeight + 8)
    checkable: true
    checked: on
    opacity: enabled ? 1 : 0.45
    Accessible.role: Accessible.CheckBox
    Accessible.name: text
    Accessible.checked: on
    contentItem: RowLayout {
        spacing: 10
        Rectangle {
            implicitWidth: 18; implicitHeight: 18
            radius: control.radius
            color: control.on ? Theme.accent : Theme.raised
            border.width: 1
            border.color: control.on ? Theme.accent : Theme.lineStrong
            Text {
                anchors.centerIn: parent
                visible: control.on
                text: "✓"
                font.pixelSize: 13
                font.weight: Font.Bold
                color: Theme.accentInk
            }
            FocusRing { target: control }
        }
        Text {
            id: label
            Layout.fillWidth: true
            text: control.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.body
            color: Theme.text
        }
    }
    background: Item {}
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
