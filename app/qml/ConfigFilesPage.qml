import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Include tree, the selected file with unsaved changes marked, and the
// safety net: validation state and snapshots.
Item {
    id: page
    readonly property int rev: backend.revision
    property string currentFile: ""
    property string selectedSnapshot: ""
    readonly property var tree: backend.includeTree
    readonly property var current: {
        for (var i = 0; i < tree.length; i++)
            if (tree[i].path === currentFile) return tree[i]
        return tree.length ? tree[0] : null
    }
    readonly property var lines: { rev; return current ? backend.fileLines(current.path) : [] }
    readonly property int firstChange: {
        for (var i = 0; i < lines.length; i++)
            if (lines[i].kind) return i
        return -1
    }
    // Open a file at its first unsaved change.
    function showFirstChange() {
        if (firstChange >= 0) source.positionViewAtIndex(firstChange, ListView.Center)
        else source.positionViewAtBeginning()
    }
    onCurrentChanged: Qt.callLater(showFirstChange)
    Component.onCompleted: Qt.callLater(showFirstChange)

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 64
            color: Theme.chrome
            Text {
                anchors.verticalCenter: parent.verticalCenter
                x: 28
                text: "Config files"
                font.pixelSize: Theme.pageTitle
                font.weight: Font.Bold
                font.letterSpacing: -0.44
                color: Theme.text
                Accessible.role: Accessible.Heading
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Include tree and write mode
            Rectangle {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                color: Theme.chrome
                Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    anchors.topMargin: 16
                    spacing: 2
                    GroupLabel { text: "Include tree"; Layout.leftMargin: 10; Layout.bottomMargin: 6 }
                    Repeater {
                        model: page.tree
                        AbstractButton {
                            id: row
                            required property var modelData
                            readonly property bool on: page.current !== null && page.current.path === modelData.path
                            property real radius: Theme.radiusSmall
                            Layout.fillWidth: true
                            implicitHeight: Theme.control
                            onClicked: page.currentFile = modelData.path
                            Accessible.name: modelData.name + (modelData.dirty ? ", unsaved changes" : "")
                            Accessible.selected: on
                            contentItem: RowLayout {
                                spacing: 6
                                Item { implicitWidth: 4 + 16 * row.modelData.depth }
                                Text {
                                    text: row.modelData.name
                                    font.family: Theme.mono
                                    font.pixelSize: Theme.config
                                    color: row.modelData.missing ? Theme.muted : Theme.text
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                Text {
                                    visible: row.modelData.dirty
                                    text: "●"
                                    font.pixelSize: Theme.hint
                                    color: Theme.warnInline
                                }
                                Text {
                                    visible: text !== ""
                                    text: row.modelData.tag
                                    font.pixelSize: Theme.groupLabel
                                    color: Theme.muted
                                }
                            }
                            background: Rectangle {
                                radius: row.radius
                                color: row.on ? Theme.selected : row.hovered ? Theme.raised : "transparent"
                                border.width: row.on ? 1 : 0
                                border.color: Theme.accent
                                FocusRing { target: row }
                            }
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                        }
                    }

                    GroupLabel { text: "Write mode"; Layout.leftMargin: 10; Layout.topMargin: 14; Layout.bottomMargin: 6 }
                    Segmented {
                        Layout.fillWidth: true
                        label: "Write mode"
                        options: ["in-place", "managed"]
                        current: backend.writeMode
                        onPicked: value => backend.setWriteMode(value)
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.topMargin: 8
                        implicitHeight: modeText.implicitHeight + 20
                        radius: Theme.radius
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.line
                        Text {
                            id: modeText
                            anchors.fill: parent
                            anchors.margins: 10
                            wrapMode: Text.Wrap
                            textFormat: Text.RichText
                            font.pixelSize: Theme.hint
                            lineHeight: 1.25
                            color: Theme.muted
                            readonly property string mono: "<span style=\"font-family:'" + Theme.mono + "'\">"
                            text: backend.writeMode === "managed"
                                ? "Your own files stay read-only. Every change goes to " + mono + "niri-gui.kdl</span>, which config.kdl includes. Good for NixOS and dotfile repos."
                                : "Changes are written into the file that sets each value. Managed mode keeps your files read-only instead; switching to it adds one line to config.kdl: "
                                  + mono + "include optional=true &quot;niri-gui.kdl&quot;</span>"
                        }
                    }
                    Item { Layout.fillHeight: true }
                }
            }

            // Source with unsaved changes marked
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 200
                spacing: 0
                Text {
                    Layout.fillWidth: true
                    leftPadding: 16; rightPadding: 16; topPadding: 10; bottomPadding: 10
                    elide: Text.ElideRight
                    font.pixelSize: Theme.hint
                    color: Theme.muted
                    text: !page.current ? ""
                        : page.current.name + (page.current.missing ? " · this file does not exist yet"
                        : page.current.dirty ? " · unsaved changes are marked + and −"
                        : " · no unsaved changes in this file")
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                ListView {
                    id: source
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: page.lines
                    topMargin: 14
                    bottomMargin: 14
                    flickableDirection: Flickable.AutoFlickIfNeeded
                    boundsBehavior: Flickable.StopAtBounds
                    contentWidth: {
                        var longest = 0
                        for (var i = 0; i < page.lines.length; i++)
                            longest = Math.max(longest, page.lines[i].text.length)
                        return Math.max(width, longest * 8 + 56)
                    }
                    ScrollBar.vertical: ScrollBar {}
                    ScrollBar.horizontal: ScrollBar {}
                    Accessible.role: Accessible.Document
                    Accessible.name: page.current ? page.current.name : ""
                    delegate: Rectangle {
                        required property var modelData
                        width: source.contentWidth
                        height: 23
                        color: modelData.kind === "added" ? Theme.okFill
                             : modelData.kind === "removed" ? Theme.warnFill : "transparent"
                        Text {
                            x: 16
                            anchors.verticalCenter: parent.verticalCenter
                            text: (modelData.kind === "added" ? "+ " : modelData.kind === "removed" ? "− " : "  ") + modelData.text
                            textFormat: Text.PlainText
                            font.family: Theme.mono
                            font.pixelSize: Theme.config
                            color: modelData.kind === "added" ? Theme.okText
                                 : modelData.kind === "removed" ? Theme.warnText
                                 : modelData.text.trim().startsWith("//") ? Theme.muted : Theme.text
                        }
                    }
                }
            }

            // Validation and snapshots
            Rectangle {
                Layout.preferredWidth: 280
                Layout.fillHeight: true
                color: Theme.chrome
                Rectangle { width: 1; height: parent.height; color: Theme.line }
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 14

                    Banner {
                        Layout.fillWidth: true
                        ok: backend.valid
                        lead: backend.valid ? "✓" : "Invalid:"
                        text: backend.valid
                            ? "niri validate passes for " + (backend.pendingCount ? "your unsaved changes" : "the saved config")
                            : backend.errorSummary
                    }

                    Text {
                        text: "Snapshots"
                        font.pixelSize: Theme.body
                        font.weight: Font.DemiBold
                        color: Theme.text
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.hint
                        color: Theme.muted
                        text: backend.snapshots.length === 0
                            ? "None yet. The touched files are copied aside before every save, so any save can be undone here."
                            : backend.pendingCount > 0
                              ? "Save or revert your unsaved changes before restoring."
                              : "Taken before every save. Restoring is validated and snapshotted too."
                    }
                    ListView {
                        id: snapList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 4
                        model: backend.snapshots
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Rectangle {
                            id: snap
                            required property var modelData
                            readonly property bool on: page.selectedSnapshot === modelData.id
                            width: snapList.width
                            height: snapColumn.implicitHeight + 16
                            radius: Theme.radius
                            color: on ? Theme.selected : snapHover.hovered ? Theme.raised : "transparent"
                            border.width: on ? 1 : 0
                            border.color: Theme.accent
                            HoverHandler { id: snapHover; cursorShape: Qt.PointingHandCursor }
                            TapHandler { onTapped: page.selectedSnapshot = snap.on ? "" : snap.modelData.id }
                            ColumnLayout {
                                id: snapColumn
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 8
                                AbstractButton {
                                    id: head
                                    property real radius: Theme.radiusSmall
                                    Layout.fillWidth: true
                                    implicitHeight: 20
                                    onClicked: page.selectedSnapshot = snap.on ? "" : snap.modelData.id
                                    Accessible.name: snap.modelData.title + ", " + snap.modelData.when
                                    contentItem: RowLayout {
                                        spacing: 8
                                        Text {
                                            Layout.fillWidth: true
                                            text: snap.modelData.title
                                            elide: Text.ElideRight
                                            font.pixelSize: Theme.secondary
                                            font.weight: snap.modelData.name ? Font.DemiBold : Font.Normal
                                            color: Theme.text
                                        }
                                        Text {
                                            text: snap.modelData.when
                                            font.pixelSize: Theme.secondary
                                            color: Theme.muted
                                        }
                                    }
                                    background: Rectangle { color: "transparent"; radius: head.radius; FocusRing { target: head } }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    visible: snap.on
                                    text: snap.modelData.files
                                    elide: Text.ElideRight
                                    font.family: Theme.mono
                                    font.pixelSize: Theme.groupLabel
                                    color: Theme.muted
                                }
                                Field {
                                    Layout.fillWidth: true
                                    visible: snap.on
                                    font.pixelSize: Theme.secondary
                                    placeholderText: "Name it to keep it"
                                    text: snap.modelData.name
                                    onEditingFinished: if (text !== snap.modelData.name) backend.nameSnapshot(snap.modelData.id, text)
                                    Accessible.name: "Snapshot name"
                                }
                                Btn {
                                    Layout.fillWidth: true
                                    visible: snap.on
                                    text: "Restore this snapshot"
                                    enabled: backend.pendingCount === 0
                                    onClicked: { backend.restoreSnapshot(snap.modelData.id); page.selectedSnapshot = "" }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
