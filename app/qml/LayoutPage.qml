import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

ScrollView {
    id: page
    property string filter: ""
    readonly property int rev: backend.revision
    contentWidth: availableWidth
    clip: true

    function num(path, fallback) {
        rev
        var v = backend.value(path)
        return v === undefined || v === null ? fallback : Number(v)
    }
    readonly property var overrides: { rev; return backend.layoutOverrides() }
    readonly property var shown: backend.layoutSettings.filter(function (s) {
        var q = page.filter.trim().toLowerCase()
        return !q || s.label.toLowerCase().indexOf(q) >= 0 || s.path.indexOf(q) >= 0
    })

    ColumnLayout {
        width: page.availableWidth
        spacing: 0

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 28
            Layout.leftMargin: 32
            Layout.rightMargin: 32
            spacing: 24

            Flow {
                Layout.fillWidth: true
                spacing: 12
                Text {
                    text: "Layout"
                    font.pixelSize: Theme.pageTitle
                    font.weight: Font.Bold
                    font.letterSpacing: -0.44
                    color: Theme.text
                    Accessible.role: Accessible.Heading
                }
                Text {
                    height: 28
                    verticalAlignment: Text.AlignBottom
                    font.pixelSize: Theme.secondary
                    color: Theme.muted
                    text: "Applies to all outputs" + (page.overrides.length
                        ? " · " + page.overrides.length + " override"
                          + (page.overrides.length > 1 ? "s" : "") + " ("
                          + page.overrides.map(function (p) { return p.replace(/^.*\[(.*)\]$/, "$1") }).join(", ") + ")"
                        : "")
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 10
                visible: !page.filter
                LayoutPreview {
                    Layout.preferredWidth: 560
                    Layout.maximumWidth: parent.width
                    Layout.preferredHeight: 300
                    columns: backend.previewColumns
                    gaps: page.num("layout/gaps", 16)
                    ring: page.num("layout/focus-ring/width", 4)
                    ringOn: { page.rev; return backend.isOn("layout/focus-ring", true) }
                    borderWidth: page.num("layout/border/width", 4)
                    borderOn: { page.rev; return backend.isOn("layout/border", false) }
                    center: { page.rev; return String(backend.value("layout/center-focused-column") || "never") }
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.hint
                    color: Theme.muted
                    text: (backend.previewIsLive
                           ? "Preview of your focused workspace, drawn from your real windows over IPC. "
                           : "Preview with sample windows. ")
                          + (backend.previewEnabled
                             ? "Changes are applied to niri as you drag, and undone if you revert."
                             : "Changes reach niri when you save.")
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.maximumWidth: 560
                    spacing: 12
                    visible: backend.connected && !backend.previewEnabled
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.secondary
                        color: Theme.text
                        textFormat: Text.RichText
                        text: "Live preview on your desktop is off. Turning it on adds one line to the end of config.kdl: "
                              + "<span style=\"font-family:'" + Theme.mono + "'\">include optional=true &quot;niri-gui-preview.kdl&quot;</span>"
                    }
                    Btn {
                        text: "Turn on live preview"
                        onClicked: backend.enablePreview()
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: width >= 640 ? 2 : 1
                columnSpacing: 16
                rowSpacing: 16
                Repeater {
                    model: page.shown
                    SettingCard {
                        required property var modelData
                        setting: modelData
                        Layout.preferredWidth: 1
                    }
                }
            }
            Text {
                visible: page.shown.length === 0
                font.pixelSize: Theme.secondary
                color: Theme.muted
                text: "No layout setting matches “" + page.filter + "”."
            }
        }
    }
}
