import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Keyboard map of `binds {}` for one modifier layer, with the selected key's
// action and properties in the side panel.
Item {
    id: page
    readonly property var detail: binds.detail
    property string shownKey: ""

    function syncFields() {
        var key = binds.layer + "/" + (detail.has ? detail.name : "")
        var moved = key !== shownKey
        shownKey = key
        if (!detail.has) return
        if (moved || (!actionField.activeFocus && detail.error === "" && binds.confirmText === ""))
            { actionField.text = detail.actionText; actionField.cursorPosition = 0 }
        if (moved || !titleField.activeFocus)
            titleField.text = detail.title
    }
    Connections { target: binds; function onChanged() { page.syncFields() } }
    Component.onCompleted: syncFields()

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Page header
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 64
            color: Theme.chrome
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 28
                anchors.rightMargin: 28
                spacing: 12
                Text {
                    text: "Key bindings"
                    font.pixelSize: Theme.pageTitle
                    font.weight: Font.Bold
                    font.letterSpacing: -0.44
                    color: Theme.text
                    Accessible.role: Accessible.Heading
                }
                Text {
                    Layout.fillWidth: true
                    text: binds.count + (binds.count === 1 ? " bind" : " binds")
                    font.pixelSize: Theme.secondary
                    color: Theme.muted
                    elide: Text.ElideRight
                }
                Select {
                    implicitWidth: 190
                    model: [{ label: "Wheel or mouse…", value: "" }].concat(binds.pointerTriggers)
                    current: ""
                    Accessible.name: "Select a wheel, touchpad or mouse trigger"
                    onPicked: function(value) { if (value) binds.selectKey(value); current = ""; currentIndex = 0 }
                }
                Btn {
                    text: binds.recording === "select" ? "Cancel recording" : "● Record shortcut"
                    primary: binds.recording !== "select"
                    onClicked: binds.recording === "select" ? binds.cancelRecording() : binds.startRecording("select")
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Map
            ScrollView {
                id: mapScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 0
                contentWidth: availableWidth
                clip: true
                ColumnLayout {
                    width: mapScroll.availableWidth
                    spacing: 0
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.margins: 24
                        spacing: 16

                        // Modifier layer
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: layerFlow.implicitHeight + 8
                            radius: Theme.radius
                            color: Theme.ground
                            Accessible.role: Accessible.Grouping
                            Accessible.name: "Modifier layer"
                            Flow {
                                id: layerFlow
                                x: 4; y: 4
                                width: parent.width - 8
                                spacing: 4
                                Repeater {
                                    model: binds.layers
                                    AbstractButton {
                                        id: seg
                                        required property var modelData
                                        readonly property bool on: modelData.value === binds.layer
                                        property real radius: Theme.radiusSmall
                                        implicitHeight: 32
                                        leftPadding: 12; rightPadding: 12
                                        checkable: true
                                        checked: on
                                        Accessible.name: modelData.label + ", " + modelData.count + " binds"
                                        Accessible.checked: on
                                        onClicked: binds.setLayer(modelData.value)
                                        contentItem: Row {
                                            spacing: 6
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: seg.modelData.label
                                                font.pixelSize: Theme.secondary
                                                font.weight: seg.on ? Font.DemiBold : Font.Normal
                                                color: seg.on ? Theme.accentInk : Theme.text
                                            }
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: seg.modelData.count
                                                font.family: Theme.mono
                                                font.pixelSize: Theme.groupLabel
                                                color: seg.on ? Theme.accentInk : Theme.muted
                                            }
                                        }
                                        background: Rectangle {
                                            radius: seg.radius
                                            color: seg.on ? Theme.accent : (seg.hovered ? Theme.raised : "transparent")
                                            FocusRing { target: seg }
                                        }
                                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                                    }
                                }
                            }
                        }

                        // Recording
                        Rectangle {
                            id: recorder
                            Layout.fillWidth: true
                            visible: binds.recording !== ""
                            implicitHeight: recordRow.implicitHeight + 24
                            radius: Theme.radiusBlock
                            color: Theme.selected
                            border.width: 1
                            border.color: Theme.accent
                            onVisibleChanged: if (visible) catcher.forceActiveFocus()
                            RowLayout {
                                id: recordRow
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 12
                                Item {
                                    id: catcher
                                    Layout.fillWidth: true
                                    implicitHeight: recordText.implicitHeight
                                    focus: recorder.visible
                                    Accessible.role: Accessible.AlertMessage
                                    Accessible.name: recordText.text
                                    Keys.onShortcutOverride: function(event) { event.accepted = true }
                                    Keys.onPressed: function(event) {
                                        binds.recorded(event.nativeScanCode, event.modifiers, event.text)
                                        event.accepted = true
                                    }
                                    Text {
                                        id: recordText
                                        width: parent.width
                                        wrapMode: Text.Wrap
                                        font.pixelSize: Theme.secondary
                                        color: Theme.text
                                        text: (binds.recording === "move" ? "Press the new shortcut for this bind." : "Press a shortcut to select it.")
                                              + " Esc cancels. A shortcut niri already uses is run by niri and does not reach this window: pick those on the map instead."
                                    }
                                }
                                Btn { text: "Cancel"; onClicked: binds.cancelRecording() }
                            }
                        }

                        // Keyboard plate; scrolls sideways inside its own box
                        Flickable {
                            id: plateScroll
                            Layout.fillWidth: true
                            implicitHeight: plate.height + (contentWidth > width ? 14 : 0)
                            contentWidth: plate.width
                            contentHeight: plate.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.horizontal: ScrollBar { policy: plateScroll.contentWidth > plateScroll.width ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
                            Rectangle {
                                id: plate
                                // The navigation block wraps under the main block before anything scrolls
                                width: Math.max(694, Math.min(plateScroll.width, 844))
                                height: plateRow.height + 24
                                radius: 14
                                color: Theme.chrome
                                border.width: 1
                                border.color: Theme.line
                                Accessible.role: Accessible.Grouping
                                Accessible.name: "Keyboard map"
                                Flow {
                                    id: plateRow
                                    x: 12; y: 12
                                    width: plate.width - 24
                                    spacing: 20
                                    Repeater {
                                        model: [binds.rows, binds.navRows]
                                        Column {
                                            id: block
                                            required property var modelData
                                            spacing: 5
                                            Repeater {
                                                model: block.modelData
                                                Row {
                                                    id: keyRow
                                                    required property var modelData
                                                    spacing: 5
                                                    Repeater {
                                                        model: keyRow.modelData
                                                        Loader {
                                                            id: slot
                                                            required property var modelData
                                                            width: modelData.w * 45 - 5
                                                            height: 48
                                                            sourceComponent: modelData.gap ? null : capComponent
                                                            Component {
                                                                id: capComponent
                                                                KeyCap {
                                                                    cap: slot.modelData
                                                                    onClicked: cap.modifier ? binds.toggleMod(cap.modifier)
                                                                                            : binds.selectKey(cap.key)
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Binds of this layer with no key on the map
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: binds.extras.length > 0
                            spacing: 8
                            GroupLabel { text: "Other keys in this layer" }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 5
                                Repeater {
                                    model: binds.extras
                                    KeyCap {
                                        required property var modelData
                                        cap: ({ w: 0, label: modelData.label, short: modelData.short, color: modelData.color,
                                                bound: modelData.color !== "", selected: modelData.selected, aria: modelData.aria })
                                        implicitWidth: Math.max(88, labelWidth.implicitWidth + 12)
                                        onClicked: binds.selectKey(modelData.key)
                                        Text { id: labelWidth; visible: false; text: parent.modelData.label; font.pixelSize: 11; font.weight: Font.DemiBold }
                                    }
                                }
                            }
                        }

                        // Legend
                        Flow {
                            Layout.fillWidth: true
                            spacing: 14
                            Repeater {
                                model: binds.categories.concat([{ label: "Free", color: "" }])
                                Row {
                                    required property var modelData
                                    spacing: 6
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 14; height: 14; radius: 3
                                        color: modelData.color || Theme.raised
                                        border.width: modelData.color ? 0 : 1
                                        border.color: Theme.lineStrong
                                    }
                                    Text { text: modelData.label; font.pixelSize: Theme.secondary; color: Theme.muted }
                                }
                            }
                        }

                        Repeater {
                            model: binds.conflicts
                            Banner {
                                id: conflict
                                required property var modelData
                                Layout.fillWidth: true
                                lead: modelData.lead
                                text: modelData.text
                                rich: true
                                Btn {
                                    text: "Show"
                                    onClicked: { binds.setLayer(conflict.modelData.layer); binds.selectKey(conflict.modelData.key) }
                                }
                            }
                        }
                    }
                }
            }

            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: Theme.line }

            // Binding details
            Rectangle {
                Layout.fillHeight: true
                implicitWidth: 280
                color: Theme.chrome
                ScrollView {
                    id: panelScroll
                    anchors.fill: parent
                    contentWidth: availableWidth
                    clip: true
                    ColumnLayout {
                        width: panelScroll.availableWidth
                        spacing: 0
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.margins: 22
                            spacing: 14

                            Text {
                                Layout.fillWidth: true
                                visible: !page.detail.has
                                wrapMode: Text.Wrap
                                font.pixelSize: Theme.secondary
                                color: Theme.muted
                                text: "Select a key on the map to see or change what it does. Click Mod, Shift, Ctrl or Alt on the map to switch the modifier layer."
                            }

                            // The combination and where it is set
                            Flow {
                                Layout.fillWidth: true
                                visible: page.detail.has === true
                                spacing: 6
                                Repeater {
                                    model: page.detail.combo || []
                                    Rectangle {
                                        required property string modelData
                                        width: chipText.implicitWidth + 16
                                        height: 28
                                        radius: Theme.radiusSmall
                                        color: Theme.raised
                                        border.width: 1
                                        border.color: Theme.line
                                        Text {
                                            id: chipText
                                            anchors.centerIn: parent
                                            text: parent.modelData
                                            font.family: Theme.mono
                                            font.pixelSize: Theme.config
                                            color: Theme.text
                                        }
                                    }
                                }
                                Text {
                                    height: 28
                                    verticalAlignment: Text.AlignVCenter
                                    text: page.detail.status || ""
                                    font.family: page.detail.bound ? Theme.mono : Theme.sans
                                    font.pixelSize: Theme.hint
                                    color: page.detail.bound ? Theme.muted : Theme.okInline
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: page.detail.missing === true
                                wrapMode: Text.Wrap
                                font.pixelSize: Theme.hint
                                color: Theme.warnText
                                text: "No key on your keyboard layout produces this without a modifier, so this shortcut cannot be pressed."
                            }

                            // Action
                            ColumnLayout {
                                Layout.fillWidth: true
                                visible: page.detail.has === true
                                spacing: 6
                                Text { text: "Action"; font.pixelSize: Theme.secondary; color: Theme.muted }
                                Field {
                                    id: actionField
                                    Layout.fillWidth: true
                                    font.family: Theme.mono
                                    font.pixelSize: Theme.config
                                    placeholderText: "Search actions…"
                                    Accessible.name: "Action"
                                    // Applied on Enter only: losing focus must not bind half-typed
                                    // text, or a click on the list below would be lost.
                                    onAccepted: if (text.trim() !== "") binds.setActionText(text)
                                    Keys.onEscapePressed: { text = page.detail.actionText || ""; focus = false }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    visible: text !== ""
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.hint
                                    color: Theme.warnText
                                    text: page.detail.error || (backend.revision, backend.errorFor(page.detail.path || "", "bind"))
                                }
                                Text {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.hint
                                    color: Theme.muted
                                    text: picker.searching ? "Press Enter to use what you typed, or pick an action from the list."
                                                           : (page.detail.description || "")
                                }
                                Hint {
                                    visible: (page.detail.usage || "") !== ""
                                    text: "Takes <span style=\"font-family:'" + Theme.mono + "'\">"
                                          + (page.detail.usage || "").replace(/</g, "&lt;") + "</span>"
                                }
                            }

                            // Picker
                            ColumnLayout {
                                id: picker
                                Layout.fillWidth: true
                                visible: page.detail.has === true && matches.length > 0
                                spacing: 6
                                readonly property bool searching: actionField.text.trim() !== (page.detail.actionText || "")
                                readonly property var matches: {
                                    page.detail
                                    return binds.actionMatches(searching ? actionField.text : "")
                                }
                                Text {
                                    text: picker.searching ? "Matching actions" : page.detail.bound ? "Related actions" : "Common actions"
                                    font.pixelSize: Theme.secondary
                                    color: Theme.muted
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: pickerColumn.implicitHeight + 2
                                    radius: Theme.radius
                                    color: Theme.surface
                                    border.width: 1
                                    border.color: Theme.line
                                    ColumnLayout {
                                        id: pickerColumn
                                        x: 1; y: 1
                                        width: parent.width - 2
                                        spacing: 0
                                        Repeater {
                                            model: picker.matches
                                            AbstractButton {
                                                id: option
                                                required property var modelData
                                                required property int index
                                                property real radius: Theme.radiusSmall
                                                Layout.fillWidth: true
                                                implicitHeight: Theme.control
                                                leftPadding: 10; rightPadding: 10
                                                Accessible.name: modelData.name + ": " + modelData.description
                                                onClicked: { actionField.focus = false; binds.pickAction(modelData.name) }
                                                contentItem: RowLayout {
                                                    spacing: 8
                                                    Rectangle { implicitWidth: 8; implicitHeight: 8; radius: 2; color: option.modelData.color }
                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: option.modelData.name
                                                        elide: Text.ElideRight
                                                        font.family: Theme.mono
                                                        font.pixelSize: Theme.config
                                                        color: Theme.text
                                                    }
                                                }
                                                background: Rectangle {
                                                    radius: option.radius
                                                    color: option.hovered ? Theme.raised : "transparent"
                                                    FocusRing { target: option; anchors.margins: 0 }
                                                    Rectangle {
                                                        visible: option.index > 0
                                                        width: parent.width; height: 1
                                                        color: Theme.raised
                                                    }
                                                }
                                                HoverHandler { cursorShape: Qt.PointingHandCursor }
                                            }
                                        }
                                    }
                                }
                            }

                            // Properties of an existing bind
                            ColumnLayout {
                                Layout.fillWidth: true
                                visible: page.detail.bound === true
                                spacing: 6
                                Text { text: "Hotkey overlay title"; font.pixelSize: Theme.secondary; color: Theme.muted }
                                Field {
                                    id: titleField
                                    Layout.fillWidth: true
                                    enabled: !page.detail.titleHidden
                                    opacity: enabled ? 1 : 0.45
                                    placeholderText: "Shown by niri as is"
                                    Accessible.name: "Hotkey overlay title"
                                    onEditingFinished: if (text !== page.detail.title) binds.setProp("hotkey-overlay-title", text)
                                }
                                Check {
                                    Layout.fillWidth: true
                                    text: "Hide from the hotkey overlay"
                                    on: page.detail.titleHidden === true
                                    onClicked: binds.setTitleHidden(!on)
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                visible: page.detail.bound === true
                                spacing: 0
                                Check {
                                    Layout.fillWidth: true
                                    text: "Repeat while held"
                                    on: page.detail.repeat === true
                                    onClicked: binds.setProp("repeat", !on)
                                }
                                Check {
                                    Layout.fillWidth: true
                                    text: "Allow when screen is locked"
                                    enabled: page.detail.isSpawn === true
                                    on: page.detail.allowWhenLocked === true
                                    onClicked: binds.setProp("allow-when-locked", !on)
                                }
                                Check {
                                    Layout.fillWidth: true
                                    text: "Allow inhibiting (games, VMs)"
                                    on: page.detail.allowInhibiting === true
                                    onClicked: binds.setProp("allow-inhibiting", !on)
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.topMargin: 6
                                    spacing: 10
                                    Text {
                                        Layout.fillWidth: true
                                        text: "Cooldown"
                                        font.pixelSize: Theme.body
                                        color: Theme.text
                                    }
                                    NumberField {
                                        number: page.detail.cooldown || 0
                                        from: 0; to: 60000
                                        Accessible.name: "Cooldown in milliseconds"
                                        onCommitted: function(value) { binds.setProp("cooldown-ms", value) }
                                    }
                                    Text { text: "ms"; font.family: Theme.mono; font.pixelSize: Theme.config; color: Theme.muted }
                                }
                            }

                            Repeater {
                                model: page.detail.overridden || []
                                Hint {
                                    required property string modelData
                                    text: "Replaces <span style=\"font-family:'" + Theme.mono + "'\">" + modelData.replace(/</g, "&lt;") + "</span>"
                                }
                            }

                            // Lockout confirm
                            Banner {
                                Layout.fillWidth: true
                                visible: binds.confirmText !== ""
                                lead: "Careful:"
                                text: binds.confirmText
                                stacked: true
                                Btn { text: binds.confirmLabel; onClicked: binds.confirm(true) }
                                Btn { text: "Cancel"; onClicked: binds.confirm(false) }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                visible: page.detail.bound === true && binds.confirmText === ""
                                spacing: 8
                                Btn {
                                    Layout.fillWidth: true
                                    text: binds.recording === "move" ? "Press keys…" : "Change keys"
                                    enabled: page.detail.pointer !== true
                                    onClicked: binds.recording === "move" ? binds.cancelRecording() : binds.startRecording("move")
                                }
                                Btn {
                                    Layout.fillWidth: true
                                    text: "Remove"
                                    onClicked: binds.removeBind()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
