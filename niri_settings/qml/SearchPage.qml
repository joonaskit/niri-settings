import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Every setting whose name, path or hint matches the search, by page.
ScrollView {
    id: page
    property string query: ""
    signal openPage(string id)
    readonly property var results: backend.searchSettings(query)
    contentWidth: availableWidth
    clip: true

    ColumnLayout {
        width: page.availableWidth
        spacing: 0
        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 28
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            spacing: 16
            Text {
                text: page.results.length + (page.results.length === 1 ? " setting matches " : " settings match ")
                      + "“" + page.query.trim() + "”"
                font.pixelSize: Theme.pageTitle
                font.weight: Font.Bold
                font.letterSpacing: -0.44
                color: Theme.text
                Accessible.role: Accessible.Heading
            }
            Text {
                visible: page.results.length === 0
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                font.pixelSize: Theme.secondary
                color: Theme.muted
                text: "Displays, key bindings and window rules have their own pages; anything else is in Config files."
            }
            GridLayout {
                Layout.fillWidth: true
                columns: width >= 640 ? 2 : 1
                columnSpacing: 16
                rowSpacing: 16
                Repeater {
                    model: page.results
                    ColumnLayout {
                        id: hit
                        required property var modelData
                        Layout.preferredWidth: 1
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        spacing: 4
                        LinkButton {
                            text: hit.modelData.pageTitle
                            Accessible.name: "Open the " + hit.modelData.pageTitle + " page"
                            onClicked: page.openPage(hit.modelData.page)
                        }
                        SettingCard { setting: hit.modelData.setting }
                    }
                }
            }
        }
    }
}
