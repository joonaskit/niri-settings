import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// First run: where the config is, how changes are written, live preview.
// Both choices can be changed later on the Config files page.
Popup {
    id: dialog
    readonly property var info: backend.setupInfo
    property string mode: "in-place"
    property bool preview: true
    property string error: ""
    readonly property string mono: "<span style=\"font-family:'" + Theme.mono + "'\">"

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(640, Overlay.overlay ? Overlay.overlay.width - 32 : 640)
    height: Math.min(implicitHeight, Overlay.overlay ? Overlay.overlay.height - 32 : implicitHeight)
    padding: 24
    closePolicy: Popup.NoAutoClose
    Overlay.modal: Rectangle { color: "#b30f1115" }
    background: Rectangle {
        radius: Theme.radiusCard
        color: Theme.raised
        border.width: 1
        border.color: Theme.line
    }
    onOpened: {
        mode = info.suggested
        preview = true
        error = ""
        start.forceActiveFocus()
    }

    // The include lines this choice adds to config.kdl, in the order they go in.
    function additions() {
        var out = []
        if (mode === "managed" && !info.managedIncluded) out.push('include optional=true "niri-gui.kdl"')
        if (preview && !info.previewIncluded) out.push('include optional=true "niri-gui-preview.kdl"')
        return out
    }

    contentItem: ColumnLayout {
      spacing: 0
      ScrollView {
        id: scroller
        Layout.fillWidth: true
        Layout.fillHeight: true
        implicitHeight: body.implicitHeight
        contentWidth: availableWidth
        clip: true
        ColumnLayout {
            id: body
            width: scroller.availableWidth
            spacing: 0

            Text {
                Layout.fillWidth: true
                text: "Welcome to niri settings"
                font.pixelSize: Theme.pageTitle
                font.weight: Font.Bold
                font.letterSpacing: -0.22
                color: Theme.text
            }
            Text {
                Layout.fillWidth: true
                Layout.topMargin: 6
                text: "Two choices before you start. You can change both later on the Config files page."
                wrapMode: Text.Wrap
                font.pixelSize: Theme.body
                color: Theme.muted
            }

            GroupLabel { text: "Your config"; Layout.topMargin: 20; Layout.bottomMargin: 8 }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: where.implicitHeight + 24
                radius: Theme.radius
                color: Theme.surface
                border.width: 1
                border.color: Theme.line
                ColumnLayout {
                    id: where
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 4
                    Text {
                        Layout.fillWidth: true
                        text: dialog.info.path
                        elide: Text.ElideMiddle
                        font.family: Theme.mono
                        font.pixelSize: Theme.config
                        color: Theme.text
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        textFormat: Text.RichText
                        font.pixelSize: Theme.hint
                        color: dialog.info.exists ? Theme.muted : Theme.warnText
                        text: dialog.info.exists
                            ? (dialog.info.files === 1 ? "Found. One file, no includes."
                                                       : "Found, with " + (dialog.info.files - 1) + " included file"
                                                         + (dialog.info.files === 2 ? "" : "s") + ".")
                            : dialog.info.defaultSource
                              ? "Not found. It will be created from niri's default config, " + dialog.mono
                                + dialog.info.defaultSource + "</span>."
                              : "Not found, and niri's default config is not installed. An empty config will be created; niri's built-in defaults apply."
                    }
                }
            }

            GroupLabel { text: "How changes are written"; Layout.topMargin: 20; Layout.bottomMargin: 8 }
            Repeater {
                model: [
                    { id: "in-place", title: "Edit my files",
                      text: "Each change goes into the file that sets the value, as if you edited it by hand. Comments and formatting are kept." },
                    { id: "managed", title: "Keep my files read-only",
                      text: "Changes go to niri-gui.kdl, which config.kdl includes. Suits dotfile repos and NixOS. Changing or removing your own binds and rules needs the other mode." }
                ]
                AbstractButton {
                    id: option
                    required property var modelData
                    required property int index
                    readonly property bool on: dialog.mode === modelData.id
                    readonly property bool suggested: dialog.info.suggested === modelData.id
                    property real radius: Theme.radius
                    Layout.fillWidth: true
                    Layout.topMargin: index > 0 ? 8 : 0
                    implicitHeight: optionText.implicitHeight + 24
                    checkable: true
                    checked: on
                    text: modelData.title
                    onClicked: dialog.mode = modelData.id
                    Accessible.role: Accessible.RadioButton
                    Accessible.checked: on
                    Accessible.description: modelData.text
                    contentItem: Item {}
                    background: Rectangle {
                        radius: option.radius
                        color: option.on ? Theme.selected : option.hovered ? Theme.surface : "transparent"
                        border.width: 1
                        border.color: option.on ? Theme.accent : Theme.line
                        FocusRing { target: option }
                    }
                    RowLayout {
                        id: optionText
                        x: 12; y: 12
                        width: option.width - 24
                        spacing: 12
                        Rectangle {
                            Layout.alignment: Qt.AlignTop
                            Layout.topMargin: 1
                            implicitWidth: 18; implicitHeight: 18
                            radius: 9
                            color: Theme.raised
                            border.width: option.on ? 5 : 1
                            border.color: option.on ? Theme.accent : Theme.lineStrong
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Text {
                                Layout.fillWidth: true
                                text: option.modelData.title
                                wrapMode: Text.Wrap
                                font.pixelSize: Theme.body
                                font.weight: Font.DemiBold
                                color: Theme.text
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: option.suggested && dialog.info.reason !== ""
                                text: "Suggested: " + dialog.info.reason + "."
                                wrapMode: Text.Wrap
                                font.pixelSize: Theme.hint
                                color: Theme.accent
                            }
                            Text {
                                Layout.fillWidth: true
                                text: option.modelData.text
                                wrapMode: Text.Wrap
                                font.pixelSize: Theme.secondary
                                lineHeight: 1.2
                                color: Theme.muted
                            }
                        }
                    }
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                }
            }

            GroupLabel { text: "Live preview"; Layout.topMargin: 20; Layout.bottomMargin: 2 }
            Check {
                Layout.fillWidth: true
                text: "Show changes on the desktop before saving"
                on: dialog.preview
                onClicked: dialog.preview = !on
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 28
                text: "Unsaved changes go to niri-gui-preview.kdl, which niri reloads as you edit. Revert or closing the app empties it."
                wrapMode: Text.Wrap
                font.pixelSize: Theme.hint
                color: Theme.muted
            }

            GroupLabel { text: "What changes in config.kdl"; Layout.topMargin: 20; Layout.bottomMargin: 8 }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: changes.implicitHeight + 24
                radius: Theme.radiusBlock
                color: Theme.ground
                border.width: 1
                border.color: Theme.line
                ColumnLayout {
                    id: changes
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 4
                    Repeater {
                        model: dialog.additions()
                        Text {
                            required property string modelData
                            Layout.fillWidth: true
                            text: "+ " + modelData
                            elide: Text.ElideRight
                            font.family: Theme.mono
                            font.pixelSize: Theme.config
                            color: Theme.okText
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.hint
                        color: Theme.muted
                        text: dialog.additions().length === 0
                              ? (dialog.info.exists ? "Nothing. Your files stay as they are until you save a change."
                                                    : "Only the new file. Skip creates it too.")
                              : "Added at the end, each checked with niri validate"
                                + (dialog.info.exists ? ". Your file is copied to Snapshots first." : ", after the new file is created.")
                    }
                }
            }

        }
      }

      Text {
          Layout.fillWidth: true
          Layout.topMargin: 12
          visible: dialog.error !== ""
          text: dialog.error
          wrapMode: Text.Wrap
          font.pixelSize: Theme.secondary
          color: Theme.warnInline
      }

      RowLayout {
          Layout.fillWidth: true
          Layout.topMargin: 20
          spacing: 8
          Item { Layout.fillWidth: true }
          Btn {
              text: "Skip"
              onClicked: {
                  dialog.error = backend.skipSetup()
                  if (dialog.error === "")
                      dialog.close()
              }
          }
          Btn {
              id: start
              text: "Start"
              primary: true
              onClicked: {
                  dialog.error = backend.finishSetup(dialog.mode, dialog.preview)
                  if (dialog.error === "")
                      dialog.close()
              }
          }
      }
    }
}
