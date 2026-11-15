import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// 2–4 exclusive choices on a ground track.
Rectangle {
    id: root
    property var options: []
    property string current: ""
    property string label: ""
    signal picked(string value)

    implicitHeight: 44
    radius: Theme.radius
    color: Theme.ground
    Accessible.role: Accessible.Grouping
    Accessible.name: label

    RowLayout {
        anchors.fill: parent
        anchors.margins: 4
        spacing: 4
        Repeater {
            model: root.options
            AbstractButton {
                id: seg
                required property string modelData
                readonly property bool on: modelData === root.current
                property real radius: Theme.radiusSmall
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                checkable: true
                checked: on
                text: modelData
                onClicked: root.picked(modelData)
                Accessible.checked: on
                contentItem: Text {
                    text: seg.text
                    font.pixelSize: Theme.secondary
                    font.weight: seg.on ? Font.DemiBold : Font.Normal
                    color: seg.on ? Theme.accentInk : Theme.text
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    radius: seg.radius
                    color: seg.on ? Theme.accent : (seg.hovered ? Theme.raised : "transparent")
                    FocusRing { target: seg }
                }
                HoverHandler { cursorShape: Qt.PointingHandCursor }
            }
        }
    }
}
