import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// A text field that offers names: outputs or named workspaces, from
// `backend.suggestions(kind)`. Typing filters the list; Up/Down and Enter,
// or a click, pick one. Anything else can still be typed. `committed` fires
// once per change, with the text as it should be written.
Field {
    id: field
    property string kind: ""
    property string stored: ""
    property var options: []
    signal committed(string value)

    // One colour per monitor, so its two rows (by port, and by make, model
    // and serial) read as one monitor.
    readonly property var groupColors: ["#7fc8ff", "#ffc87f", "#c7ff7f", "#e5989b", "#c49bff", "#7fe0d0"]
    readonly property bool twoNames: options.some(function (o) { return o.by === "monitor" })

    readonly property var shown: {
        var q = text.trim().toLowerCase()
        if (!q || q === stored.toLowerCase())
            return options
        return options.filter(function (o) {
            return (o.match || o.value).toLowerCase().indexOf(q) >= 0
        })
    }

    text: stored
    onStoredChanged: if (!activeFocus) text = stored

    function show() {
        options = backend.suggestions(kind)
        list.currentIndex = -1
        if (options.length) menu.open()
    }
    function pick(value) {
        menu.close()
        text = value
        if (value !== stored) committed(value)
    }

    onActiveFocusChanged: if (activeFocus) show(); else menu.close()
    onTextEdited: { list.currentIndex = -1; if (!menu.opened && shown.length) menu.open() }
    Keys.onDownPressed: {
        if (!menu.opened) show()
        else list.currentIndex = Math.min(list.currentIndex + 1, field.shown.length - 1)
    }
    Keys.onUpPressed: list.currentIndex = Math.max(list.currentIndex - 1, -1)
    Keys.onEscapePressed: event => { if (menu.opened) { menu.close(); event.accepted = true } else event.accepted = false }
    // Taken before the field's own Return handling: editingFinished would
    // otherwise commit the typed text first.
    function pickHighlighted(event) {
        if (menu.opened && list.currentIndex >= 0 && list.currentIndex < shown.length) {
            pick(shown[list.currentIndex].value)
            event.accepted = true
        } else {
            menu.close()
            event.accepted = false
        }
    }
    Keys.onReturnPressed: event => pickHighlighted(event)
    Keys.onEnterPressed: event => pickHighlighted(event)
    onEditingFinished: if (text.trim() !== stored) pick(text.trim())   // the backend skips repeats
    onShownChanged: if (!shown.length) menu.close()

    Popup {
        id: menu
        objectName: "suggestMenu"
        y: field.height + 4
        width: Math.max(field.width, 380)
        padding: 4
        focus: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        implicitHeight: Math.min(list.contentHeight + 8, 320)
        background: Rectangle {
            radius: Theme.radius
            color: Theme.raised
            border.width: 1
            border.color: Theme.line
        }
        contentItem: ListView {
            id: list
            objectName: "suggestList"
            clip: true
            model: field.shown
            currentIndex: -1
            ScrollBar.vertical: ScrollBar {}
            footer: Text {
                visible: field.twoNames && field.kind === "outputs"
                width: ListView.view.width
                height: visible ? implicitHeight + 12 : 0
                topPadding: 8
                leftPadding: 10
                rightPadding: 10
                wrapMode: Text.Wrap
                font.pixelSize: Theme.hint
                color: Theme.muted
                text: "Rows with the same colour are the same monitor, named two ways. By port "
                      + "(like HDMI-A-1) is short but follows the socket: move the cable and the rule "
                      + "misses. By make, model and serial follows the monitor to any port."
            }
            delegate: Rectangle {
                required property var modelData
                required property int index
                width: ListView.view.width
                height: 44
                radius: Theme.radiusSmall
                color: index === list.currentIndex || mouse.containsMouse ? Theme.selected : "transparent"
                Rectangle {     // the monitor's colour, the same on both of its rows
                    visible: modelData.group >= 0
                    anchors.left: parent.left
                    anchors.leftMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    width: 4; height: 30; radius: 2
                    color: visible ? field.groupColors[modelData.group % field.groupColors.length] : "transparent"
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: 18
                    anchors.rightMargin: 10
                    Text {
                        width: parent.width
                        text: modelData.value
                        elide: Text.ElideRight
                        font.family: Theme.mono
                        font.pixelSize: Theme.config
                        color: Theme.text
                    }
                    Text {
                        width: parent.width
                        text: modelData.note
                        elide: Text.ElideRight
                        font.pixelSize: Theme.hint
                        color: Theme.muted
                    }
                }
                MouseArea {
                    id: mouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: field.pick(modelData.value)
                }
                Accessible.role: Accessible.ListItem
                Accessible.name: modelData.value + ", " + modelData.note
            }
        }
    }
}
