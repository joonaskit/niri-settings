import QtQuick
import QtQuick.Layouts
import "."

// Setting card: surface, 1 px line, 12 px radius, 16 px padding, 10 px rows.
// Flat: a borderless tile on a group panel; it shows a border only when set.
Rectangle {
    default property alias content: column.data
    property bool flat: false
    Layout.fillWidth: true
    Layout.alignment: Qt.AlignTop
    implicitHeight: column.implicitHeight + 32
    radius: flat ? Theme.radiusBlock : Theme.radiusCard
    color: flat ? Theme.raised : Theme.surface
    border.width: 1
    border.color: flat ? "transparent" : Theme.line
    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10
    }
}
