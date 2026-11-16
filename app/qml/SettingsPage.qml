import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// A page drawn from app/schema/pages.py: groups of setting cards.
ScrollView {
    id: page
    property string pageId: ""
    readonly property var spec: backend.pages[pageId] || ({ title: "", intro: "", groups: [] })
    readonly property var wide: ["animation", "workspaces", "startup", "environment"]
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
                text: page.spec.title
                font.pixelSize: Theme.pageTitle
                font.weight: Font.Bold
                font.letterSpacing: -0.44
                color: Theme.text
                Accessible.role: Accessible.Heading
            }
            Text {
                Layout.fillWidth: true
                Layout.topMargin: -8
                visible: page.spec.intro !== ""
                text: page.spec.intro
                wrapMode: Text.Wrap
                font.pixelSize: Theme.secondary
                color: Theme.muted
            }

            Repeater {
                model: page.spec.groups
                ColumnLayout {
                    id: group
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    spacing: 10
                    GroupLabel { visible: group.modelData.title !== ""; text: group.modelData.title }
                    GridLayout {
                        id: grid
                        Layout.fillWidth: true
                        columns: width >= 640 ? 2 : 1
                        columnSpacing: 16
                        rowSpacing: 16
                        Repeater {
                            model: group.modelData.settings
                            SettingCard {
                                required property var modelData
                                setting: modelData
                                Layout.preferredWidth: 1
                                Layout.columnSpan: page.wide.indexOf(modelData.kind) >= 0 && grid.columns > 1
                                                   && modelData.kind !== "animation" ? 2 : 1
                            }
                        }
                    }
                }
            }
        }
    }
}
