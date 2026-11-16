import QtQuick
import QtQuick.Layouts
import "."

// Setting card: surface, 1 px line, 12 px radius, 16 px padding, 10 px rows.
Rectangle {
    default property alias content: column.data
    Layout.fillWidth: true
    Layout.alignment: Qt.AlignTop
    implicitHeight: column.implicitHeight + 32
    radius: Theme.radiusCard
    color: Theme.surface
    border.width: 1
    border.color: Theme.line
    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10
    }
}
