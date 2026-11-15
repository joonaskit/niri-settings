import QtQuick
import QtQuick.Controls.Basic
import "."

// Drop-down for a config value. `model` is a list of { label, value }.
ComboBox {
    id: control
    property string current: ""
    signal picked(string value)

    implicitHeight: Theme.control
    textRole: "label"
    valueRole: "value"
    font.family: Theme.mono
    font.pixelSize: Theme.config
    currentIndex: indexOfValue(current)
    onModelChanged: currentIndex = indexOfValue(current)
    onCurrentChanged: currentIndex = indexOfValue(current)
    Component.onCompleted: currentIndex = indexOfValue(current)
    onActivated: picked(currentValue)

    contentItem: Text {
        leftPadding: 12
        rightPadding: 4
        text: control.displayText
        font: control.font
        color: Theme.text
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Text {
        x: control.width - width - 10
        anchors.verticalCenter: parent.verticalCenter
        text: "▾"
        font.pixelSize: Theme.hint
        color: Theme.muted
    }
    background: Rectangle {
        radius: Theme.radius
        color: Theme.raised
        border.width: control.visualFocus || control.popup.visible ? 2 : 1
        border.color: control.visualFocus || control.popup.visible ? Theme.accent : Theme.line
    }
    delegate: ItemDelegate {
        id: option
        required property var modelData
        required property int index
        width: control.width
        height: Theme.control
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: option.modelData.label
            font: control.font
            color: option.index === control.currentIndex ? Theme.accentInk : Theme.text
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: Theme.radiusSmall
            color: option.index === control.currentIndex ? Theme.accent
                 : option.highlighted ? Theme.selected : "transparent"
        }
    }
    popup: Popup {
        y: control.height + 4
        width: control.width
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 320)
        padding: 4
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollBar.vertical: ScrollBar {}
        }
        background: Rectangle {
            radius: Theme.radius
            color: Theme.raised
            border.width: 1
            border.color: Theme.line
        }
    }
}
