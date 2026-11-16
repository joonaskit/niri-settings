import QtQuick
import QtQuick.Layouts
import "."

// 12 px muted line under a control. `config` is the part shown in monospace.
Text {
    property string config: ""
    property string plain: ""
    Layout.fillWidth: true
    wrapMode: Text.Wrap
    textFormat: Text.RichText
    font.pixelSize: Theme.hint
    color: Theme.muted
    text: (config ? "<span style=\"font-family:'" + Theme.mono + "'\">" + config + "</span>" : "")
          + (config && plain ? " · " : "") + plain
}
