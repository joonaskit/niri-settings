import QtQuick
import QtQuick.Layouts
import "."

// Status banner: bold lead word, one sentence, actions on the right.
Rectangle {
    id: banner
    property bool ok: false
    property string lead: ""
    property string text: ""
    property string details: ""      // optional monospace block under the sentence
    property bool rich: false        // `text` carries monospace spans
    property bool stacked: false     // actions under the sentence, for narrow panels
    default property alias actions: actionRow.data

    implicitHeight: column.implicitHeight + 24
    radius: Theme.radiusBlock
    color: ok ? Theme.okFill : Theme.warnFill
    border.width: 1
    border.color: ok ? Theme.okBorder : Theme.warnBorder
    Accessible.role: Accessible.AlertMessage
    Accessible.name: lead + " " + text

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        GridLayout {
            Layout.fillWidth: true
            columns: banner.stacked ? 1 : 2
            columnSpacing: 12
            rowSpacing: 10
            Text {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                textFormat: banner.rich ? Text.RichText : Text.StyledText
                font.pixelSize: Theme.secondary
                color: banner.ok ? Theme.okText : Theme.warnText
                text: (banner.lead ? "<b>" + banner.lead + "</b> " : "") + banner.text
            }
            RowLayout { id: actionRow; spacing: 8 }
        }
        Text {
            Layout.fillWidth: true
            visible: banner.details !== ""
            text: banner.details
            wrapMode: Text.Wrap
            maximumLineCount: 14
            elide: Text.ElideRight
            font.family: Theme.mono
            font.pixelSize: Theme.hint
            color: banner.ok ? Theme.okText : Theme.warnText
        }
    }
}
