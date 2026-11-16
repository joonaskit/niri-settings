import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

ApplicationWindow {
    id: window
    width: 1280
    height: 820
    minimumWidth: 640
    minimumHeight: 480
    visible: true
    title: "niri settings"
    color: Theme.ground

    property string currentPage: "layout"
    property string currentTitle: "Layout"
    // Where Config files should open: set by a setting's file:line link.
    property string sourceFile: ""
    property int sourceLine: 0
    property int sourceSeq: 0

    function go(id) {
        var sections = backend.sections
        for (var i = 0; i < sections.length; i++)
            for (var j = 0; j < sections[i].pages.length; j++)
                if (sections[i].pages[j].id === id) {
                    currentPage = id
                    currentTitle = sections[i].pages[j].title
                }
        search.text = ""
    }
    Connections {
        target: backend
        function onSourceRequested(file, line) {
            window.sourceFile = file
            window.sourceLine = line
            window.sourceSeq += 1
            window.go("files")
        }
    }

    Shortcut { sequence: "Ctrl+K"; onActivated: search.forceActiveFocus() }
    Shortcut { sequence: "Ctrl+S"; enabled: saveButton.enabled; onActivated: backend.save() }

    DiffDialog { id: diffDialog; diff: backend.diffText }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Top bar
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 64
            color: Theme.chrome
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.rightMargin: 20
                spacing: 16
                Text {
                    text: "niri settings"
                    font.pixelSize: Theme.panelTitle
                    font.weight: Font.Bold
                    font.letterSpacing: -0.16
                    color: Theme.text
                }
                TextField {
                    id: search
                    objectName: "search"
                    Layout.fillWidth: true
                    Layout.maximumWidth: 520
                    implicitHeight: Theme.control
                    leftPadding: 12
                    rightPadding: 12
                    font.pixelSize: Theme.body
                    color: Theme.text
                    placeholderText: "Search every setting…  (Ctrl+K)"
                    placeholderTextColor: Theme.muted
                    selectionColor: Theme.accent
                    selectedTextColor: Theme.accentInk
                    Accessible.name: "Search settings"
                    Keys.onEscapePressed: { text = ""; focus = false }
                    background: Rectangle {
                        radius: Theme.radius
                        color: Theme.raised
                        border.width: search.activeFocus ? 2 : 1
                        border.color: search.activeFocus ? Theme.accent : Theme.line
                    }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    width: 8; height: 8; radius: 4
                    color: backend.connected ? Theme.okInline : Theme.lineStrong
                }
                Text {
                    text: backend.statusText
                    font.pixelSize: Theme.secondary
                    color: Theme.muted
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Sidebar
            Rectangle {
                Layout.preferredWidth: Theme.sidebar
                Layout.fillHeight: true
                color: Theme.chrome
                Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }
                ScrollView {
                    anchors.fill: parent
                    anchors.rightMargin: 1
                    contentWidth: availableWidth
                    clip: true
                    ColumnLayout {
                        width: Theme.sidebar - 1
                        spacing: 0
                        Item { implicitHeight: 16 }
                        Repeater {
                            model: backend.sections
                            ColumnLayout {
                                id: group
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                Layout.leftMargin: 12
                                Layout.rightMargin: 12
                                spacing: 2
                                Text {
                                    Layout.topMargin: group.index === 0 ? 8 : 14
                                    Layout.leftMargin: 10
                                    Layout.bottomMargin: 2
                                    text: group.modelData.group.toUpperCase()
                                    font.pixelSize: Theme.groupLabel
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.88
                                    color: Theme.muted
                                }
                                Repeater {
                                    model: group.modelData.pages
                                    AbstractButton {
                                        id: item
                                        required property var modelData
                                        readonly property bool current: window.currentPage === modelData.id
                                        property real radius: Theme.radiusSmall
                                        Layout.fillWidth: true
                                        implicitHeight: Theme.control
                                        text: modelData.title
                                        onClicked: window.go(modelData.id)
                                        Accessible.role: Accessible.PageTab
                                        Accessible.selected: current
                                        contentItem: Text {
                                            leftPadding: 10
                                            rightPadding: 10
                                            text: item.text
                                            font.pixelSize: Theme.body
                                            font.weight: item.current ? Font.DemiBold : Font.Normal
                                            color: item.current ? Theme.accentInk : Theme.text
                                            verticalAlignment: Text.AlignVCenter
                                            elide: Text.ElideRight
                                        }
                                        background: Rectangle {
                                            radius: item.radius
                                            color: item.current ? Theme.accent
                                                 : item.hovered ? Theme.raised : "transparent"
                                            FocusRing { target: item }
                                        }
                                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                                    }
                                }
                            }
                        }
                        Item { implicitHeight: 16 }
                    }
                }
            }

            // Content
            Loader {
                Layout.fillWidth: true
                Layout.fillHeight: true
                sourceComponent: search.text.trim() !== "" ? searchPage
                               : window.currentPage === "layout" ? layoutPage
                               : window.currentPage === "files" ? filesPage
                               : window.currentPage === "displays" ? displaysPage
                               : window.currentPage === "binds" ? bindsPage
                               : window.currentPage === "window-rules" ? rulesPage
                               : backend.pages[window.currentPage] !== undefined ? settingsPage : placeholder
            }
            Component { id: layoutPage; LayoutPage {} }
            Component { id: searchPage; SearchPage { query: search.text; onOpenPage: id => window.go(id) } }
            Component { id: settingsPage; SettingsPage { pageId: window.currentPage } }
            Component {
                id: filesPage
                ConfigFilesPage {
                    jumpFile: window.sourceFile
                    jumpLine: window.sourceLine
                    jumpSeq: window.sourceSeq
                    onOpenPage: id => window.go(id)
                }
            }
            Component { id: displaysPage; DisplaysPage {} }
            Component { id: bindsPage; KeyBindingsPage {} }
            Component { id: rulesPage; WindowRulesPage {} }
            Component { id: placeholder; PlaceholderPage { title: window.currentTitle } }
        }

        // An outside edit touched a setting that also has an unsaved change
        Banner {
            Layout.fillWidth: true
            Layout.margins: 12
            Layout.bottomMargin: 0
            visible: backend.conflicts.length > 0
            lead: "Conflict:"
            text: {
                var c = backend.conflicts
                if (c.length === 0) return ""
                if (c.length === 1)
                    return c[0].path + " changed on disk to " + c[0].disk + " while you set it to " + c[0].mine + "."
                return c.length + " settings changed both here and on disk: "
                     + c.map(function (x) { return x.path }).join(", ") + "."
            }
            Btn { text: "Use the file's"; onClicked: backend.resolveConflicts(false) }
            Btn { text: "Keep mine"; onClicked: backend.resolveConflicts(true) }
        }

        // Validation error, shown above the footer
        Banner {
            id: errorBanner
            property bool expanded: false
            Layout.fillWidth: true
            Layout.margins: 12
            visible: !backend.valid
            lead: "Invalid:"
            text: backend.errorSummary
            details: expanded ? backend.validationText : ""
            Btn {
                text: errorBanner.expanded ? "Hide details" : "Details"
                onClicked: errorBanner.expanded = !errorBanner.expanded
            }
        }

        // Footer
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 60
            color: Theme.chrome
            Rectangle { width: parent.width; height: 1; color: Theme.line }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.rightMargin: 20
                spacing: 12
                Text {
                    text: backend.valid ? "✓ niri validate: OK" : "✕ niri validate: failed"
                    font.pixelSize: Theme.secondary
                    color: backend.valid ? Theme.okInline : Theme.warnInline
                }
                Text {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    font.pixelSize: Theme.secondary
                    color: Theme.muted
                    text: {
                        var n = backend.pendingCount
                        if (backend.notice) return backend.notice
                        if (backend.blockReason) return backend.blockReason
                        return n + " unsaved change" + (n === 1 ? "" : "s") + " · " + backend.targetText
                    }
                }
                RowLayout {
                    spacing: 8
                    Btn { text: "Review diff"; enabled: backend.pendingCount > 0; onClicked: diffDialog.open() }
                    Btn { text: "Revert"; enabled: backend.pendingCount > 0; onClicked: backend.revert() }
                    Btn {
                        id: saveButton
                        text: "Save"
                        primary: true
                        enabled: backend.pendingCount > 0 && backend.valid && backend.conflicts.length === 0
                                 && backend.blockReason === ""
                        onClicked: backend.save()
                    }
                }
            }
        }
    }
}
