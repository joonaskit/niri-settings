import QtQuick
import QtQuick.Controls.Basic
import "."

// Text input on `raised`; the border turns accent on focus.
TextField {
    id: control
    implicitHeight: Theme.control
    leftPadding: 12
    rightPadding: 12
    font.pixelSize: Theme.body
    color: Theme.text
    placeholderTextColor: Theme.muted
    selectionColor: Theme.accent
    selectedTextColor: Theme.accentInk
    selectByMouse: true
    // Show the start of a long value, not its end, until the user edits it.
    onTextChanged: if (!activeFocus) cursorPosition = 0
    background: Rectangle {
        radius: Theme.radius
        color: Theme.raised
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.accent : Theme.line
    }
}
