import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

Popup {
    id: dialog
    property string diff: ""
    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(820, Overlay.overlay ? Overlay.overlay.width - 48 : 820)
    height: Math.min(560, Overlay.overlay ? Overlay.overlay.height - 48 : 560)
    padding: 20
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: "#b30f1115" }
    background: Rectangle {
        radius: Theme.radiusCard
        color: Theme.raised
        border.width: 1
        border.color: Theme.line
    }
    contentItem: ColumnLayout {
        spacing: 14
        Text {
            text: "Unsaved changes"
            font.pixelSize: Theme.panelTitle
            font.weight: Font.Bold
            color: Theme.text
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radiusBlock
            color: Theme.ground
            border.width: 1
            border.color: Theme.line
            ListView {
                anchors.fill: parent
                anchors.margins: 8
                clip: true
                model: dialog.diff ? dialog.diff.split("\n") : ["No unsaved changes."]
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    required property string modelData
                    readonly property bool added: modelData.startsWith("+") && !modelData.startsWith("+++")
                    readonly property bool removed: modelData.startsWith("-") && !modelData.startsWith("---")
                    width: ListView.view.width
                    height: line.implicitHeight + 4
                    radius: 3
                    color: added ? Theme.okFill : removed ? Theme.warnFill : "transparent"
                    Text {
                        id: line
                        x: 8; y: 2
                        width: parent.width - 16
                        text: modelData
                        wrapMode: Text.WrapAnywhere
                        font.family: Theme.mono
                        font.pixelSize: Theme.hint
                        color: added ? Theme.okText : removed ? Theme.warnText : Theme.muted
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Close"; onClicked: dialog.close() }
        }
    }
}
