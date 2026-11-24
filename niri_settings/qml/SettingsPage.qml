import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// A page drawn from niri_settings/schema/pages.py: each group of setting
// cards in its own panel. A panel's header sticks to the top while its
// cards scroll by, and folds the group to a one-line summary. Wide pages
// get an index of the groups on the right.
Item {
    id: page
    property string pageId: ""
    // "<page>/<group index>" -> true for folded groups; kept by Main so a
    // fold lasts while the app runs.
    property var collapsed: ({})
    signal toggled(string key)

    readonly property var spec: backend.pages[pageId] || ({ title: "", intro: "", groups: [] })
    readonly property var wide: ["animation", "workspaces", "startup", "environment"]
    readonly property Flickable flick: scroll.contentItem
    readonly property bool showIndex: width >= 1000 && spec.groups.length > 1
    // The group whose panel is at the top of the view
    readonly property int currentGroup: {
        var y = flick.contentY + 24, cur = 0
        if (flick.contentHeight > flick.height && flick.contentY >= flick.contentHeight - flick.height - 1)
            return groups.count - 1
        for (var i = 0; i < groups.count; i++) {
            var g = groups.itemAt(i)
            if (g && g.contentTop <= y)
                cur = i
        }
        return cur
    }

    function keyOf(i) { return pageId + "/" + i }
    function scrollTo(i) {
        var g = groups.itemAt(i)
        if (!g) return
        if (page.collapsed[keyOf(i)])
            page.toggled(keyOf(i))
        var max = Math.max(0, flick.contentHeight - flick.height)
        flick.contentY = Math.max(0, Math.min(g.contentTop - 16, max))
    }

    ScrollView {
        id: scroll
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: groupIndex.visible ? groupIndex.left : parent.right
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
            width: scroll.availableWidth
            spacing: 0

            ColumnLayout {
                id: body
                Layout.fillWidth: true
                Layout.margins: 28
                Layout.leftMargin: 32
                Layout.rightMargin: page.showIndex ? 8 : 32
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
                    Layout.bottomMargin: 4
                    visible: page.spec.intro !== ""
                    text: page.spec.intro
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.secondary
                    color: Theme.muted
                }

                Repeater {
                    id: groups
                    model: page.spec.groups
                    GroupPanel {}
                }
            }
        }
    }

    // On this page: one link per group, the current one highlighted
    ColumnLayout {
        id: groupIndex
        visible: page.showIndex
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: 20
        anchors.topMargin: 32
        width: 180
        spacing: 2
        GroupLabel { text: "On this page"; Layout.leftMargin: 10; Layout.bottomMargin: 6 }
        Repeater {
            model: page.spec.groups
            AbstractButton {
                id: link
                required property var modelData
                required property int index
                readonly property var info: { backend.revision; return backend.groupState(page.pageId, index) }
                readonly property bool current: page.currentGroup === index
                Layout.fillWidth: true
                implicitHeight: 30
                Accessible.name: "Go to " + modelData.title
                onClicked: page.scrollTo(index)
                background: Rectangle {
                    radius: Theme.radiusSmall
                    color: link.current ? Theme.selected : link.hovered ? Theme.raised : "transparent"
                    FocusRing { target: link }
                }
                contentItem: RowLayout {
                    spacing: 8
                    Rectangle {
                        Layout.leftMargin: 10
                        implicitWidth: 7
                        implicitHeight: 7
                        radius: 3.5
                        color: link.info.unsaved > 0 ? Theme.accent : "transparent"
                    }
                    Text {
                        Layout.fillWidth: true
                        text: link.modelData.title
                        elide: Text.ElideRight
                        font.pixelSize: Theme.secondary
                        color: link.current ? Theme.text : Theme.muted
                    }
                    Text {
                        Layout.rightMargin: 10
                        visible: link.info.set > 0
                        text: link.info.set
                        font.pixelSize: Theme.hint
                        color: Theme.muted
                    }
                }
                HoverHandler { cursorShape: Qt.PointingHandCursor }
            }
        }
    }

    // One group: a bordered panel with a header that folds it and sticks
    // to the top of the view while the group's cards scroll under it.
    component GroupPanel: Rectangle {
        id: group
        required property var modelData
        required property int index
        readonly property string key: page.keyOf(index)
        readonly property bool open: !page.collapsed[key]
        readonly property var info: { backend.revision; return backend.groupState(page.pageId, index) }
        readonly property real contentTop: body.y + y   // in the scrolled content
        readonly property real stick: open ? Math.max(0, Math.min(page.flick.contentY - contentTop,
                                                                  height - header.height - 2)) : 0
        Layout.fillWidth: true
        implicitHeight: header.height + 2 + (open ? grid.implicitHeight + 22 : 0)
        radius: Theme.radiusCard
        color: Theme.chrome
        border.width: 1
        border.color: Theme.line

        GridLayout {
            id: grid
            visible: group.open
            x: 12
            y: header.height + 12
            width: group.width - 24
            columns: width >= 600 ? 2 : 1
            columnSpacing: 10
            rowSpacing: 10
            Repeater {
                model: group.open ? group.modelData.settings : []
                SettingCard {
                    required property var modelData
                    setting: modelData
                    flat: true
                    Layout.preferredWidth: 1
                    Layout.columnSpan: page.wide.indexOf(modelData.kind) >= 0 && grid.columns > 1
                                       && modelData.kind !== "animation" ? 2 : 1
                }
            }
        }

        Rectangle {
            id: header
            x: 1
            y: Math.max(1, group.stick)
            z: 1
            width: group.width - 2
            height: 52
            color: Theme.chrome
            // Round only the top corners, and only at the top of the panel
            radius: group.stick > 0 ? 0 : Theme.radiusCard - 1
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: parent.radius
                color: parent.color
                visible: group.open
            }
            Rectangle {  // the line between header and cards
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Theme.line
                visible: group.open
            }

            TapHandler { onTapped: page.toggled(group.key) }
            HoverHandler { cursorShape: Qt.PointingHandCursor }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 16
                spacing: 10

                AbstractButton {
                    id: chevron
                    implicitWidth: 28
                    implicitHeight: 28
                    Accessible.name: (group.open ? "Fold " : "Unfold ") + group.modelData.title
                    onClicked: page.toggled(group.key)
                    background: Rectangle {
                        radius: Theme.radiusSmall
                        color: chevron.hovered ? Theme.raised : "transparent"
                        FocusRing { target: chevron }
                    }
                    contentItem: Text {
                        text: "›"
                        rotation: group.open ? 90 : 0
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 18
                        color: Theme.muted
                        Behavior on rotation { NumberAnimation { duration: Theme.motion } }
                    }
                }
                Text {
                    text: group.modelData.title
                    font.pixelSize: Theme.panelTitle - 1
                    font.weight: Font.DemiBold
                    color: Theme.text
                    Accessible.role: Accessible.Heading
                }
                Text {  // what the group sets, when folded
                    Layout.fillWidth: true
                    text: group.open ? "" : group.info.summary
                    elide: Text.ElideRight
                    font.pixelSize: Theme.hint
                    color: Theme.muted
                }
                Rectangle {
                    visible: group.info.unsaved > 0
                    implicitWidth: pill.implicitWidth + 16
                    implicitHeight: 20
                    radius: 10
                    color: Theme.accent
                    Text {
                        id: pill
                        anchors.centerIn: parent
                        text: group.info.unsaved + " unsaved"
                        font.pixelSize: Theme.hint
                        font.weight: Font.DemiBold
                        color: Theme.accentInk
                    }
                }
                Text {
                    text: group.info.set > 0 ? group.info.set + " set" : "niri defaults"
                    font.pixelSize: Theme.hint
                    color: Theme.muted
                }
                LinkButton {
                    visible: group.open && group.info.resettable > 0
                    text: "Reset group"
                    Accessible.name: "Reset every " + group.modelData.title + " setting to niri's default"
                    onClicked: backend.resetGroup(page.pageId, group.index)
                }
            }
        }
    }
}
