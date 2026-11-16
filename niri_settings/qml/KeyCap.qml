import QtQuick
import QtQuick.Controls.Basic
import "."

// One key of the keyboard map. Bound keys take their category colour, free
// keys sit on `raised`, and modifiers held in the current layer turn `text`.
AbstractButton {
    id: control
    property var cap: ({})
    property real radius: 7
    readonly property bool filled: cap.bound === true || cap.held === true
    readonly property color ink: filled ? Theme.accentInk : Theme.muted

    implicitWidth: cap.w ? cap.w * 45 - 5 : 40
    implicitHeight: 48
    checkable: true
    checked: cap.selected === true || cap.held === true
    Accessible.name: cap.aria || ""
    Accessible.checked: checked

    background: Rectangle {
        radius: control.radius
        color: control.cap.held ? Theme.text : control.cap.bound ? control.cap.color
             : control.hovered ? Theme.selected : Theme.raised
        border.width: 1
        border.color: control.filled ? color : Theme.line
        // Selected: a 2 px gap, then a 2 px `text` ring
        Rectangle {
            visible: control.cap.selected === true
            anchors.fill: parent
            anchors.margins: -4
            radius: control.radius + 4
            color: "transparent"
            border.width: 2
            border.color: Theme.text
        }
        FocusRing { target: control; anchors.margins: control.cap.selected ? -7 : -3 }
    }
    contentItem: Item {
        Text {
            x: 4; y: 4
            width: parent.width - 6
            text: control.cap.label || ""
            elide: Text.ElideRight
            font.pixelSize: 11
            font.weight: Font.DemiBold
            color: control.ink
        }
        Text {
            x: 5
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 4
            width: parent.width - 10
            text: control.cap.short || ""
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            lineHeight: 0.95
            elide: Text.ElideRight
            font.pixelSize: 9
            color: control.ink
        }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
    ToolTip {
        id: tip
        visible: control.hovered && (control.cap.aria || "") !== ""
        delay: 500
        text: control.cap.aria || ""
        contentItem: Text { text: tip.text; font.family: Theme.mono; font.pixelSize: Theme.hint; color: Theme.text }
        background: Rectangle { radius: Theme.radiusSmall; color: Theme.raised; border.width: 1; border.color: Theme.line }
    }
}
