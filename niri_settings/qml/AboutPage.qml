import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// About: what the app is, where it lives, its license, and the versions a
// bug report needs (with a button that copies them as plain text).
Item {
    id: page
    readonly property var info: backend.about

    ScrollView {
        id: scroll
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
            width: Math.min(scroll.availableWidth, 760)
            spacing: 0

            ColumnLayout {
                Layout.fillWidth: true
                Layout.margins: 28
                Layout.leftMargin: 32
                Layout.rightMargin: 32
                spacing: 16

                Text {
                    text: "About"
                    font.pixelSize: Theme.pageTitle
                    font.weight: Font.Bold
                    font.letterSpacing: -0.44
                    color: Theme.text
                }

                // Identity
                Card {
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 16
                        Image {
                            visible: page.info.icon !== ""
                            source: page.info.icon
                            sourceSize.width: 64
                            sourceSize.height: 64
                            Layout.preferredWidth: 64
                            Layout.preferredHeight: 64
                            Layout.alignment: Qt.AlignTop
                            Accessible.ignored: true
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            RowLayout {
                                spacing: 10
                                Text {
                                    text: "niri settings"
                                    font.pixelSize: Theme.sectionTitle
                                    font.weight: Font.Bold
                                    color: Theme.text
                                }
                                Text {
                                    text: "Version " + page.info.version
                                    font.pixelSize: Theme.secondary
                                    color: Theme.muted
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                font.pixelSize: Theme.body
                                color: Theme.text
                                text: "Change the niri compositor's settings without breaking its config. "
                                    + "It edits your KDL files in place, keeps comments and formatting, "
                                    + "and never writes a file that niri validate rejects."
                            }
                            RowLayout {
                                Layout.topMargin: 6
                                spacing: 12
                                LinkButton { text: "Source code"; onClicked: Qt.openUrlExternally(page.info.repo) }
                                LinkButton { text: "Report a bug"; onClicked: Qt.openUrlExternally(page.info.issues) }
                                LinkButton { text: "Release notes"; onClicked: Qt.openUrlExternally(page.info.releases) }
                            }
                        }
                    }
                }

                // Versions for bug reports
                Card {
                    RowLayout {
                        Layout.fillWidth: true
                        GroupLabel { text: "System info"; Layout.fillWidth: true }
                        Btn { text: "Copy"; onClicked: backend.copySystemInfo() }
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 24
                        rowSpacing: 6
                        Repeater {
                            model: backend.systemInfo
                            delegate: Text {
                                required property var modelData
                                required property int index
                                Layout.row: index
                                Layout.column: 0
                                text: modelData.label
                                font.pixelSize: Theme.secondary
                                color: Theme.muted
                            }
                        }
                        Repeater {
                            model: backend.systemInfo
                            delegate: Text {
                                required property var modelData
                                required property int index
                                Layout.row: index
                                Layout.column: 1
                                Layout.fillWidth: true
                                text: modelData.value
                                font.family: Theme.mono
                                font.pixelSize: Theme.secondary
                                color: Theme.text
                                elide: Text.ElideMiddle
                            }
                        }
                    }
                    Hint {
                        Layout.fillWidth: true
                        plain: "Paste this into a bug report so it is clear which versions you run."
                    }
                }

                // License and credits
                Card {
                    GroupLabel { text: "License" }
                    RowLayout {
                        spacing: 6
                        Text {
                            text: "Free software under the GNU General Public License, version 3 or later."
                            font.pixelSize: Theme.secondary
                            color: Theme.text
                        }
                        LinkButton { text: "Read it"; onClicked: Qt.openUrlExternally(page.info.license) }
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        font.pixelSize: Theme.secondary
                        color: Theme.muted
                        text: "Uses the Inter and JetBrains Mono fonts, © 2020 their project authors, "
                            + "under the SIL Open Font License 1.1."
                    }
                }
            }
        }
    }
}
