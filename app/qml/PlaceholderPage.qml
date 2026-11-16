import QtQuick
import QtQuick.Layouts
import "."

Item {
    property string title: ""
    ColumnLayout {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 28
        anchors.leftMargin: 32
        spacing: 12
        Text {
            text: title
            font.pixelSize: Theme.pageTitle
            font.weight: Font.Bold
            font.letterSpacing: -0.44
            color: Theme.text
        }
        Text {
            font.pixelSize: Theme.secondary
            color: Theme.muted
            text: "This page is not built yet. Edit these settings in Config files for now."
        }
    }
}
