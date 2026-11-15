import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes
import "."

// Arrange outputs on a canvas, edit one in the side panel. Risky changes
// (mode, scale, position…) are tried on niri for 15 s before they can be saved.
Item {
    id: page
    readonly property var outputs: displays.outputs
    readonly property var current: {
        for (var i = 0; i < outputs.length; i++)
            if (outputs[i].name === displays.selected) return outputs[i]
        return null
    }
    Component.onCompleted: displays.refresh()

    Popup {
        id: profilePopup
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: 360
        padding: 20
        Overlay.modal: Rectangle { color: "#b30f1115" }
        onOpened: { profileName.text = ""; profileName.forceActiveFocus() }
        background: Rectangle { radius: Theme.radiusCard; color: Theme.raised; border.width: 1; border.color: Theme.line }
        contentItem: ColumnLayout {
            spacing: 14
            Text { text: "Save display profile"; font.pixelSize: Theme.panelTitle; font.weight: Font.Bold; color: Theme.text }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                font.pixelSize: Theme.secondary
                color: Theme.muted
                text: "Stores the mode, scale, rotation and position of every connected display under a name, so you can switch back to this arrangement later."
            }
            Field {
                id: profileName
                Layout.fillWidth: true
                placeholderText: "Docked, Laptop only…"
                Accessible.name: "Profile name"
                onAccepted: saveProfile.clicked()
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                Btn { text: "Cancel"; onClicked: profilePopup.close() }
                Btn {
                    id: saveProfile
                    text: "Save profile"
                    primary: true
                    enabled: profileName.text.trim() !== ""
                    onClicked: { displays.saveProfile(profileName.text); profilePopup.close() }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Page header: title, profiles, the trial button
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
                    text: "Displays"
                    font.pixelSize: Theme.pageTitle
                    font.weight: Font.Bold
                    font.letterSpacing: -0.44
                    color: Theme.text
                    Accessible.role: Accessible.Heading
                }
                Rectangle {
                    Layout.leftMargin: 12
                    implicitHeight: 40
                    implicitWidth: profileRow.implicitWidth + 8
                    radius: Theme.radius
                    color: Theme.ground
                    Accessible.role: Accessible.Grouping
                    Accessible.name: "Display profile"
                    RowLayout {
                        id: profileRow
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 4
                        Repeater {
                            model: displays.profiles
                            AbstractButton {
                                id: prof
                                required property var modelData
                                property real radius: Theme.radiusSmall
                                implicitHeight: 32
                                leftPadding: 12; rightPadding: 12
                                text: modelData.name
                                checkable: true
                                checked: modelData.active
                                onClicked: displays.applyProfile(modelData.name)
                                contentItem: Text {
                                    text: prof.text
                                    font.pixelSize: Theme.secondary
                                    font.weight: prof.modelData.active ? Font.DemiBold : Font.Normal
                                    color: prof.modelData.active ? Theme.accentInk : Theme.text
                                    verticalAlignment: Text.AlignVCenter
                                }
                                background: Rectangle {
                                    radius: prof.radius
                                    color: prof.modelData.active ? Theme.accent : prof.hovered ? Theme.raised : "transparent"
                                    FocusRing { target: prof }
                                }
                                HoverHandler { cursorShape: Qt.PointingHandCursor }
                            }
                        }
                        AbstractButton {
                            id: addProfile
                            property real radius: Theme.radiusSmall
                            implicitHeight: 32
                            leftPadding: 12; rightPadding: 12
                            text: "+ Profile"
                            onClicked: profilePopup.open()
                            contentItem: Text {
                                text: addProfile.text
                                font.pixelSize: Theme.secondary
                                color: Theme.muted
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: addProfile.radius
                                color: addProfile.hovered ? Theme.raised : "transparent"
                                FocusRing { target: addProfile }
                            }
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                        }
                    }
                }
                Btn {
                    readonly property var active: displays.profiles.filter(function (p) { return p.active })
                    visible: active.length > 0
                    text: "Delete profile"
                    onClicked: displays.deleteProfile(active[0].name)
                }
                Item { Layout.fillWidth: true }
                Btn {
                    text: "Try for " + displays.trialSeconds + " s"
                    primary: true
                    enabled: displays.needsTry && !displays.trialRunning
                    onClicked: displays.tryNow()
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        }

        Banner {
            Layout.fillWidth: true
            Layout.margins: 12
            Layout.bottomMargin: 0
            visible: displays.trialRunning
            lead: "Keep these display settings?"
            text: "Reverting in " + displays.trialSecondsLeft + " s. Nothing is written to your config until you press Save."
            Btn { text: "Revert now"; onClicked: displays.revertNow() }
            Btn { text: "Keep"; onClicked: displays.keep() }
        }
        Banner {
            Layout.fillWidth: true
            Layout.margins: 12
            Layout.bottomMargin: 0
            visible: !displays.trialRunning && displays.trialError !== ""
            lead: "Refused:"
            text: "niri did not accept the change, so nothing was applied. " + displays.trialError
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Arrangement
            ScrollView {
                id: left
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 0   // take what the side panel leaves, whatever the content wants
                Layout.minimumWidth: 300
                contentWidth: availableWidth
                clip: true
                ColumnLayout {
                    width: left.availableWidth
                    spacing: 0
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.margins: 28
                        spacing: 16

                        Rectangle {
                            id: canvas
                            Layout.fillWidth: true
                            implicitHeight: 420
                            radius: 14
                            color: Theme.chrome
                            clip: true
                            Accessible.role: Accessible.Graphic
                            Accessible.name: "Display arrangement"

                            // What is being dragged, and where it would land (logical px).
                            property string dragging: ""
                            property real dragX: 0
                            property real dragY: 0
                            property string snappedEdge: ""
                            // The view is frozen while dragging so the canvas does not rescale under the pointer.
                            property var frozen: null
                            readonly property var view: frozen || fit()

                            function fit() {
                                var minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9, n = 0
                                for (var i = 0; i < page.outputs.length; i++) {
                                    var o = page.outputs[i]
                                    if (!o.connected) continue
                                    minX = Math.min(minX, o.x); minY = Math.min(minY, o.y)
                                    maxX = Math.max(maxX, o.x + o.w); maxY = Math.max(maxY, o.y + o.h)
                                    n++
                                }
                                if (n === 0) return { k: 0.1, ox: 0, oy: 0 }
                                var pad = 70
                                var k = Math.min((width - 2 * pad) / (maxX - minX), (height - 2 * pad - 20) / (maxY - minY), 0.25)
                                return { k: k, ox: (width - (maxX - minX) * k) / 2 - minX * k,
                                         oy: (height - 20 - (maxY - minY) * k) / 2 - minY * k }
                            }

                            Shape {  // 1 px dashed border: an area you can arrange things in
                                anchors.fill: parent
                                ShapePath {
                                    strokeColor: Theme.line
                                    strokeWidth: 1
                                    strokeStyle: ShapePath.DashLine
                                    dashPattern: [4, 4]
                                    fillColor: "transparent"
                                    PathRectangle { x: 0.5; y: 0.5; width: canvas.width - 1; height: canvas.height - 1; radius: 14 }
                                }
                            }

                            Repeater {
                                model: page.outputs
                                Item {
                                    id: mon
                                    required property var modelData
                                    readonly property bool sel: displays.selected === modelData.name
                                    readonly property bool moving: canvas.dragging === modelData.name
                                    readonly property real lx: moving ? canvas.dragX : modelData.x
                                    readonly property real ly: moving ? canvas.dragY : modelData.y
                                    visible: modelData.connected
                                    x: canvas.view.ox + lx * canvas.view.k
                                    y: canvas.view.oy + ly * canvas.view.k
                                    width: Math.max(96, modelData.w * canvas.view.k)
                                    height: Math.max(60, modelData.h * canvas.view.k)
                                    z: moving ? 3 : sel ? 2 : 1

                                    Rectangle {  // 6 px halo around the selected monitor
                                        anchors.fill: parent
                                        anchors.margins: -6
                                        radius: 14
                                        color: Theme.accent
                                        opacity: 0.15
                                        visible: mon.sel
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: Theme.radius
                                        color: mon.sel ? Theme.selected : Theme.previewGround
                                        border.width: mon.sel ? 2 : 1
                                        border.color: mon.sel ? Theme.accent : Theme.lineStrong
                                        opacity: mon.modelData.enabled ? 1 : 0.55
                                    }
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 4
                                        clip: true
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Text {
                                                Layout.fillWidth: true
                                                text: mon.modelData.title
                                                elide: Text.ElideRight
                                                font.pixelSize: mon.width > 280 ? Theme.body : Theme.secondary
                                                font.weight: Font.DemiBold
                                                color: Theme.text
                                            }
                                            Text {
                                                visible: !mon.modelData.enabled || mon.modelData.needsTry
                                                text: !mon.modelData.enabled ? "off" : "not tried yet"
                                                font.pixelSize: Theme.hint
                                                color: mon.modelData.enabled ? Theme.warnInline : Theme.muted
                                            }
                                        }
                                        Item { Layout.fillHeight: true }
                                        Text {
                                            Layout.fillWidth: true
                                            wrapMode: Text.Wrap
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                            font.family: Theme.mono
                                            font.pixelSize: mon.width > 280 ? Theme.hint : Theme.groupLabel
                                            color: Theme.muted
                                            text: mon.width > 280
                                                ? mon.modelData.mode.replace("x", "×").replace("@", " @ ") + " Hz · scale " + mon.modelData.scale
                                                  + "\nlogical " + mon.modelData.w + "×" + mon.modelData.h + " at (" + Math.round(mon.lx) + ", " + Math.round(mon.ly) + ")"
                                                : mon.modelData.mode.split("@")[0].replace("x", "×") + " · " + mon.modelData.scale
                                                  + "\nat (" + Math.round(mon.lx) + ", " + Math.round(mon.ly) + ")"
                                        }
                                    }
                                    Rectangle {  // the edge that snapped to a neighbour
                                        visible: mon.moving && canvas.snappedEdge !== ""
                                        color: Theme.warnInline
                                        readonly property bool vertical: canvas.snappedEdge === "left" || canvas.snappedEdge === "right"
                                        width: vertical ? 2 : parent.width
                                        height: vertical ? parent.height : 2
                                        x: canvas.snappedEdge === "right" ? parent.width - 2 : 0
                                        y: canvas.snappedEdge === "bottom" ? parent.height - 2 : 0
                                    }
                                    Text {
                                        visible: mon.moving && canvas.snappedEdge !== ""
                                        anchors.top: parent.bottom
                                        anchors.topMargin: 6
                                        text: "snapped edge"
                                        font.pixelSize: Theme.hint
                                        color: Theme.warnInline
                                    }
                                    AbstractButton {  // keyboard: select with Space/Enter, move with arrows
                                        id: grip
                                        anchors.fill: parent
                                        property real radius: Theme.radius
                                        onClicked: displays.select(mon.modelData.name)
                                        Accessible.name: mon.modelData.title + ", at " + mon.modelData.x + ", " + mon.modelData.y
                                        background: Rectangle { color: "transparent"; radius: grip.radius; FocusRing { target: grip } }
                                        Keys.onPressed: event => {
                                            var step = (event.modifiers & Qt.ShiftModifier) ? 100 : 10
                                            var dx = event.key === Qt.Key_Left ? -step : event.key === Qt.Key_Right ? step : 0
                                            var dy = event.key === Qt.Key_Up ? -step : event.key === Qt.Key_Down ? step : 0
                                            if (dx || dy) {
                                                displays.setPosition(mon.modelData.name, mon.modelData.x + dx, mon.modelData.y + dy)
                                                event.accepted = true
                                            }
                                        }
                                    }
                                    DragHandler {
                                        id: drag
                                        target: null
                                        cursorShape: active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                                        property real startX: 0
                                        property real startY: 0
                                        onActiveChanged: {
                                            if (active) {
                                                displays.select(mon.modelData.name)
                                                startX = mon.modelData.x; startY = mon.modelData.y
                                                canvas.frozen = canvas.fit()
                                                canvas.dragX = startX; canvas.dragY = startY
                                                canvas.dragging = mon.modelData.name
                                            } else if (canvas.dragging === mon.modelData.name) {
                                                var name = canvas.dragging, x = canvas.dragX, y = canvas.dragY
                                                canvas.dragging = ""; canvas.snappedEdge = ""; canvas.frozen = null
                                                displays.setPosition(name, Math.round(x), Math.round(y))
                                            }
                                        }
                                        onTranslationChanged: {
                                            if (!active) return
                                            var s = displays.snap(mon.modelData.name,
                                                                  startX + translation.x / canvas.view.k,
                                                                  startY + translation.y / canvas.view.k)
                                            canvas.dragX = s.x; canvas.dragY = s.y; canvas.snappedEdge = s.edge
                                        }
                                    }
                                }
                            }

                            Text {
                                visible: page.outputs.filter(function (o) { return o.connected }).length === 0
                                anchors.centerIn: parent
                                font.pixelSize: Theme.secondary
                                color: Theme.muted
                                text: "niri is not running, so there are no displays to arrange."
                            }
                            Hint {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.margins: 12
                                anchors.leftMargin: 16
                                plain: "Drag to arrange in logical pixels · snaps to edges · positions are written as <span style=\"font-family:'" + Theme.mono + "'\">position x= y=</span>"
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: width >= 520 ? 2 : 1
                            columnSpacing: 12
                            rowSpacing: 12
                            Card {
                                Layout.preferredWidth: 1
                                Text { text: "Safe apply"; font.weight: Font.DemiBold; font.pixelSize: Theme.body; color: Theme.text }
                                Text {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.secondary
                                    color: Theme.muted
                                    text: "Mode, scale, rotation, position and on/off are tried on niri first and revert after "
                                          + displays.trialSeconds + " s unless you press Keep. A separate process does the revert, so it happens even if this app closes."
                                }
                            }
                            Card {
                                Layout.preferredWidth: 1
                                Text { text: "How this display is matched"; font.weight: Font.DemiBold; font.pixelSize: Theme.body; color: Theme.text }
                                Hint {
                                    font.pixelSize: Theme.secondary
                                    plain: page.current
                                        ? "Settings are stored under <span style=\"font-family:'" + Theme.mono + "'\">output &quot;" + page.current.key + "&quot;</span>. niri also accepts the make, model and serial there, so a screen keeps its settings on any port."
                                        : ""
                                }
                            }
                        }
                    }
                }
            }

            // Settings of the selected output
            Rectangle {
                Layout.preferredWidth: 300
                Layout.fillHeight: true
                color: Theme.chrome
                Rectangle { width: 1; height: parent.height; color: Theme.line }
                ScrollView {
                    id: side
                    anchors.fill: parent
                    anchors.leftMargin: 1
                    contentWidth: availableWidth
                    clip: true
                    visible: page.current !== null
                    ColumnLayout {
                        id: form
                        width: side.availableWidth
                        spacing: 0
                        readonly property var o: page.current || ({ name: "", model: "", modes: [], mode: "", scale: 1, transform: "normal",
                            vrr: "off", vrrSupported: false, enabled: true, connected: false, backdrop: "", kdl: "", overrides: [], workspaces: [] })
                        component Label: Text { font.pixelSize: Theme.secondary; color: Theme.muted }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.margins: 24
                            spacing: 16

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text { Layout.fillWidth: true; elide: Text.ElideRight; text: form.o.name; font.pixelSize: Theme.panelTitle; font.weight: Font.Bold; color: Theme.text }
                                    Text {
                                        Layout.fillWidth: true
                                        text: form.o.connected ? (form.o.model || "connected") : "in the config, not connected"
                                        elide: Text.ElideRight
                                        font.pixelSize: Theme.hint
                                        color: Theme.muted
                                    }
                                }
                                Toggle {
                                    on: form.o.enabled
                                    onClicked: displays.setEnabled(form.o.name, !on)
                                    Accessible.name: "Display enabled"
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                Label { text: "Mode" }
                                Select {
                                    Layout.fillWidth: true
                                    model: form.o.modes
                                    current: form.o.mode
                                    enabled: form.o.modes.length > 0
                                    onPicked: value => displays.setMode(form.o.name, value)
                                    Accessible.name: "Mode"
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                RowLayout {
                                    Layout.fillWidth: true
                                    Label { text: "Scale"; Layout.fillWidth: true }
                                    Text {
                                        text: scale.value + (scale.value % 1 ? " (fractional)" : "")
                                        font.family: Theme.mono
                                        font.pixelSize: Theme.config
                                        color: Theme.muted
                                    }
                                }
                                RangeSlider {
                                    id: scale
                                    Layout.fillWidth: true
                                    from: 0.5; to: 3; stepSize: 0.25
                                    value: form.o.scale
                                    // Commit on release: every step would otherwise be its own edit.
                                    onPressedChanged: if (!pressed && value !== form.o.scale) displays.setScale(form.o.name, value)
                                    Keys.onReleased: if (value !== form.o.scale) displays.setScale(form.o.name, value)
                                    Accessible.name: "Scale"
                                }
                            }

                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                columnSpacing: 10
                                rowSpacing: 6
                                Label { text: "Transform"; Layout.fillWidth: true; Layout.preferredWidth: 1 }
                                Label { text: "Variable refresh"; Layout.fillWidth: true; Layout.preferredWidth: 1 }
                                Select {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    model: displays.transforms
                                    current: form.o.transform
                                    onPicked: value => displays.setTransform(form.o.name, value)
                                    Accessible.name: "Transform"
                                }
                                Select {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    model: [{ label: "off", value: "off" }, { label: "on-demand", value: "on-demand" }, { label: "always", value: "on" }]
                                    current: form.o.vrr
                                    enabled: form.o.vrrSupported || form.o.vrr !== "off"
                                    onPicked: value => displays.setVrr(form.o.name, value)
                                    Accessible.name: "Variable refresh rate"
                                }
                            }
                            Hint {
                                visible: form.o.connected && !form.o.vrrSupported
                                plain: "This display does not report variable refresh support."
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                Label { text: "Backdrop colour" }
                                Field {
                                    Layout.fillWidth: true
                                    font.family: Theme.mono
                                    font.pixelSize: Theme.config
                                    placeholderText: "niri default"
                                    text: form.o.backdrop
                                    onEditingFinished: if (text !== form.o.backdrop) displays.setBackdrop(form.o.name, text)
                                    Accessible.name: "Backdrop colour"
                                }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "Layout overrides on this output"; font.weight: Font.DemiBold; font.pixelSize: Theme.body; color: Theme.text }
                                Text {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.secondary
                                    color: Theme.muted
                                    text: form.o.overrides.length ? form.o.overrides.join(" · ") : "None. This output uses the Layout page settings."
                                }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "Workspaces that open here"; font.weight: Font.DemiBold; font.pixelSize: Theme.body; color: Theme.text }
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 6
                                    visible: form.o.workspaces.length > 0
                                    Repeater {
                                        model: form.o.workspaces
                                        Rectangle {
                                            required property string modelData
                                            width: chip.implicitWidth + 20
                                            height: chip.implicitHeight + 8
                                            radius: height / 2
                                            color: Theme.raised
                                            border.width: 1
                                            border.color: Theme.line
                                            Text { id: chip; anchors.centerIn: parent; text: modelData; font.pixelSize: Theme.secondary; color: Theme.text }
                                        }
                                    }
                                }
                                Text {
                                    visible: form.o.workspaces.length === 0
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.secondary
                                    color: Theme.muted
                                    text: "No named workspace is pinned to this output."
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: kdl.implicitHeight + 24
                                radius: Theme.radius
                                color: Theme.ground
                                border.width: 1
                                border.color: Theme.line
                                Text {
                                    id: kdl
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    text: form.o.kdl
                                    textFormat: Text.PlainText
                                    wrapMode: Text.Wrap
                                    font.family: Theme.mono
                                    font.pixelSize: Theme.hint
                                    lineHeight: 1.3
                                    color: Theme.muted
                                    Accessible.name: "Config section for this output"
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
