import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Window rules or layer rules: the list in niri's order, a match / apply
// builder for the selected rule, and the open windows (or layer surfaces) with
// the rules that touch each one. `view` is a RulesView or LayerRulesView.
Item {
    id: page
    required property var view
    readonly property var detail: page.view.detail
    readonly property var why: page.view.why
    readonly property var words: page.view.words

    // niri does not stream layer surfaces; the view polls while the page is shown.
    Timer {
        interval: 2000
        repeat: true
        running: page.view.connected
        onTriggered: page.view.poll()
    }

    function statusMark(status) {
        return status === "yes" ? "✓" : status === "maybe" ? "?" : status === "no" ? "–" : ""
    }

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
                    text: page.words.title
                    font.pixelSize: Theme.pageTitle
                    font.weight: Font.Bold
                    font.letterSpacing: -0.44
                    color: Theme.text
                    Accessible.role: Accessible.Heading
                }
                Text {
                    Layout.fillWidth: true
                    text: "Rules apply top to bottom; later rules win"
                    font.pixelSize: Theme.secondary
                    color: Theme.muted
                    elide: Text.ElideRight
                }
                Btn {
                    visible: page.view.canPick
                    text: page.view.picking ? "Click a window…" : "Pick a window…"
                    enabled: page.view.connected && !page.view.picking
                    onClicked: page.view.pickWindow()
                }
                Btn {
                    text: "+ New rule"
                    primary: true
                    onClicked: page.view.newRule("blank")
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Rule list and templates
            Rectangle {
                Layout.fillHeight: true
                implicitWidth: 210
                color: Theme.chrome
                ScrollView {
                    id: listScroll
                    anchors.fill: parent
                    contentWidth: availableWidth
                    clip: true
                    ColumnLayout {
                        width: listScroll.availableWidth
                        spacing: 4
                        Item { implicitHeight: 12 }
                        Text {
                            Layout.fillWidth: true
                            Layout.leftMargin: 12
                            Layout.rightMargin: 12
                            visible: page.view.rules.length === 0
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.secondary
                            color: Theme.muted
                            text: "No " + page.words.title.toLowerCase() + " yet. Start from a template below or press New rule."
                        }
                        Repeater {
                            model: page.view.rules
                            AbstractButton {
                                id: ruleRow
                                required property var modelData
                                readonly property bool current: modelData.index === page.view.selected
                                property real radius: Theme.radius
                                Layout.fillWidth: true
                                Layout.leftMargin: 12
                                Layout.rightMargin: 12
                                implicitHeight: Math.max(44, ruleText.implicitHeight + 20)
                                Accessible.role: Accessible.ListItem
                                Accessible.name: modelData.title + ", " + modelData.subtitle
                                                 + (modelData.disabled ? ", turned off" : "")
                                                 + (modelData.status === "yes" ? ", applies to the selected " + page.words.one
                                                    : modelData.status === "maybe" ? ", may apply to the selected " + page.words.one : "")
                                Accessible.selected: current
                                onClicked: page.view.select(modelData.index)
                                contentItem: RowLayout {
                                    spacing: 8
                                    ColumnLayout {
                                        id: ruleText
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text {
                                            Layout.fillWidth: true
                                            text: ruleRow.modelData.title
                                            elide: Text.ElideRight
                                            font.pixelSize: Theme.body
                                            font.weight: Font.DemiBold
                                            color: ruleRow.modelData.error ? Theme.warnText
                                                   : ruleRow.modelData.disabled ? Theme.muted : Theme.text
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: ruleRow.modelData.subtitle
                                            elide: Text.ElideRight
                                            font.pixelSize: Theme.hint
                                            color: Theme.muted
                                        }
                                    }
                                    Text {
                                        visible: ruleRow.modelData.disabled
                                        text: "off"
                                        font.pixelSize: Theme.hint
                                        color: Theme.muted
                                    }
                                    Text {
                                        visible: ruleRow.modelData.status === "yes" || ruleRow.modelData.status === "maybe"
                                        text: page.statusMark(ruleRow.modelData.status)
                                        font.pixelSize: Theme.body
                                        font.weight: Font.Bold
                                        color: ruleRow.modelData.status === "yes" ? Theme.okInline : Theme.muted
                                    }
                                }
                                leftPadding: 12; rightPadding: 10
                                background: Rectangle {
                                    radius: ruleRow.radius
                                    color: ruleRow.current ? Theme.selected : ruleRow.hovered ? Theme.raised : "transparent"
                                    border.width: ruleRow.current ? 1 : 0
                                    border.color: Theme.accent
                                    FocusRing { target: ruleRow }
                                }
                                HoverHandler { cursorShape: Qt.PointingHandCursor }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.topMargin: 12
                            implicitHeight: 1
                            color: Theme.line
                        }
                        GroupLabel {
                            Layout.leftMargin: 24
                            Layout.topMargin: 10
                            text: "Start from a template"
                        }
                        Repeater {
                            model: page.view.templates
                            AbstractButton {
                                id: tpl
                                required property var modelData
                                property real radius: Theme.radius
                                Layout.fillWidth: true
                                Layout.leftMargin: 12
                                Layout.rightMargin: 12
                                implicitHeight: Math.max(Theme.control, tplText.implicitHeight + 12)
                                leftPadding: 12; rightPadding: 12
                                Accessible.name: "New rule from template: " + modelData.title + ". " + modelData.description
                                ToolTip.visible: hovered
                                ToolTip.delay: 500
                                ToolTip.text: modelData.description
                                                + (modelData.needsApp ? " Select a " + page.words.one + " first to use its "
                                                                      + page.words.fill[0].key + "." : "")
                                onClicked: page.view.newRule(modelData.id)
                                contentItem: Text {
                                    id: tplText
                                    text: tpl.modelData.title
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.secondary
                                    color: tpl.hovered ? Theme.accentHover : Theme.accent
                                    verticalAlignment: Text.AlignVCenter
                                }
                                background: Rectangle {
                                    radius: tpl.radius
                                    color: tpl.hovered ? Theme.raised : "transparent"
                                    FocusRing { target: tpl }
                                }
                                HoverHandler { cursorShape: Qt.PointingHandCursor }
                            }
                        }
                        Item { implicitHeight: 16 }
                    }
                }
            }

            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: Theme.line }

            // Builder
            ScrollView {
                id: mainScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 0
                contentWidth: availableWidth
                clip: true
                ColumnLayout {
                    width: mainScroll.availableWidth
                    spacing: 0
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.margins: 24
                        spacing: 18

                        Text {
                            Layout.fillWidth: true
                            visible: !page.detail.has
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.secondary
                            color: Theme.muted
                            text: page.words.intro
                        }

                        // Name, place in the list and where it is written
                        RowLayout {
                            Layout.fillWidth: true
                            visible: page.detail.has === true
                            spacing: 8
                            Field {
                                id: nameField
                                Layout.fillWidth: true
                                font.pixelSize: Theme.sectionTitle
                                font.weight: Font.Bold
                                placeholderText: page.detail.title || "Name this rule"
                                text: page.detail.comment || ""
                                Accessible.name: "Rule name, written as a comment above the rule"
                                onEditingFinished: if (text !== (page.detail.comment || "")) page.view.rename(text)
                                background: Rectangle {
                                    radius: Theme.radius
                                    color: nameField.activeFocus ? Theme.raised : "transparent"
                                    border.width: nameField.activeFocus ? 2 : nameField.hovered ? 1 : 0
                                    border.color: nameField.activeFocus ? Theme.accent : Theme.line
                                }
                            }
                            Toggle {
                                on: page.detail.disabled === false
                                Accessible.name: on ? "Turn rule off" : "Turn rule on"
                                ToolTip.visible: hovered; ToolTip.delay: 500
                                ToolTip.text: on ? "Turn off: comments the rule out with /-, so niri skips it"
                                                 : "Turn on: removes the /- in front of the rule"
                                onClicked: page.view.setEnabled(page.detail.index, !on)
                            }
                            Btn {
                                implicitWidth: 36; leftPadding: 0; rightPadding: 0
                                text: "↑"
                                enabled: page.detail.first === false
                                Accessible.name: "Move rule up"
                                ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "Move up: earlier rules lose to later ones"
                                onClicked: page.view.moveRule(-1)
                            }
                            Btn {
                                implicitWidth: 36; leftPadding: 0; rightPadding: 0
                                text: "↓"
                                enabled: page.detail.last === false
                                Accessible.name: "Move rule down"
                                ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "Move down: later rules win"
                                onClicked: page.view.moveRule(1)
                            }
                            Btn { text: "Remove"; onClicked: page.view.removeRule() }
                        }
                        Banner {
                            Layout.fillWidth: true
                            visible: page.detail.disabled === true
                            lead: "Turned off."
                            text: "This rule is commented out with /-, so niri skips it. You can still edit it."
                        }
                        Hint {
                            visible: page.detail.has === true
                            Layout.topMargin: -12
                            config: page.detail.where || ""
                            plain: page.detail.saved || page.words.saved
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: (page.detail.error || "") !== ""
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.secondary
                            color: Theme.warnText
                            text: page.detail.error || ""
                        }

                        // When a window or surface matches
                        Card {
                            visible: page.detail.has === true
                            GroupLabel { text: "When a " + page.words.one + " matches" }
                            Text {
                                Layout.fillWidth: true
                                visible: page.detail.matchesAll === true
                                wrapMode: Text.Wrap
                                font.pixelSize: Theme.secondary
                                color: Theme.muted
                                text: "No match line: this rule applies to every " + page.words.one
                                      + ((page.detail.directives || []).length ? ", except the ones below." : ".")
                            }
                            Repeater {
                                model: page.detail.directives || []
                                ColumnLayout {
                                    id: line
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Flow {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        Text {
                                            height: Theme.control
                                            verticalAlignment: Text.AlignVCenter
                                            text: line.modelData.kind === "match" ? (line.modelData.index === 0 ? "Match" : "or match")
                                                                                   : "except"
                                            font.pixelSize: Theme.body
                                            font.weight: Font.DemiBold
                                            color: line.modelData.kind === "match" ? Theme.text : Theme.warnText
                                        }
                                        Repeater {
                                            model: line.modelData.fields
                                            Row {
                                                id: field
                                                required property var modelData
                                                required property int index
                                                spacing: 6
                                                Text {
                                                    height: Theme.control
                                                    verticalAlignment: Text.AlignVCenter
                                                    text: (field.index > 0 ? "and " : "") + field.modelData.label
                                                    font.family: field.modelData.kind === "regex" ? Theme.mono : Theme.sans
                                                    font.pixelSize: Theme.secondary
                                                    color: Theme.muted
                                                }
                                                Field {
                                                    visible: field.modelData.kind === "regex"
                                                    width: 210
                                                    font.family: Theme.mono
                                                    font.pixelSize: Theme.config
                                                    text: field.modelData.kind === "regex" ? field.modelData.value : ""
                                                    placeholderText: "regex, e.g. " + field.modelData.example
                                                    Accessible.name: line.modelData.kind + " " + field.modelData.label + " regex"
                                                    onEditingFinished: if (text !== field.modelData.value)
                                                        page.view.setMatcher(line.modelData.kind, line.modelData.index, field.modelData.key, text)
                                                }
                                                Select {
                                                    visible: field.modelData.kind === "enum"
                                                    width: 130
                                                    model: field.modelData.options
                                                    current: field.modelData.kind === "enum" ? field.modelData.value : ""
                                                    Accessible.name: line.modelData.kind + " " + field.modelData.label
                                                    onPicked: function(value) {
                                                        page.view.setMatcher(line.modelData.kind, line.modelData.index, field.modelData.key, value)
                                                    }
                                                }
                                                Select {
                                                    visible: field.modelData.kind === "bool"
                                                    width: 96
                                                    model: [{ label: "true", value: "true" }, { label: "false", value: "false" }]
                                                    current: field.modelData.kind === "bool" ? String(field.modelData.value) : ""
                                                    Accessible.name: line.modelData.kind + " " + field.modelData.label
                                                    onPicked: function(value) {
                                                        page.view.setMatcher(line.modelData.kind, line.modelData.index, field.modelData.key, value === "true")
                                                    }
                                                }
                                                Btn {
                                                    width: 36; leftPadding: 0; rightPadding: 0
                                                    text: "×"
                                                    Accessible.name: "Remove " + field.modelData.label + " from this line"
                                                    onClicked: page.view.removeMatcher(line.modelData.kind, line.modelData.index, field.modelData.key)
                                                }
                                            }
                                        }
                                        Select {
                                            width: 150
                                            visible: line.modelData.free.length > 0
                                            model: [{ label: "+ and…", value: "" }].concat(line.modelData.free)
                                            current: ""
                                            Accessible.name: "Add a condition to this line"
                                            onPicked: function(value) {
                                                if (value) page.view.addMatcher(line.modelData.kind, line.modelData.index, value)
                                                current = ""; currentIndex = 0
                                            }
                                        }
                                    }
                                    Repeater {
                                        model: line.modelData.fields
                                        Text {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            visible: modelData.error !== ""
                                            wrapMode: Text.Wrap
                                            font.pixelSize: Theme.hint
                                            color: Theme.warnText
                                            text: modelData.error
                                        }
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        visible: line.modelData.warn !== ""
                                        wrapMode: Text.Wrap
                                        font.pixelSize: Theme.hint
                                        color: Theme.warnText
                                        text: line.modelData.warn
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        visible: line.modelData.status !== ""
                                        font.pixelSize: Theme.hint
                                        readonly property bool exclude: line.modelData.kind === "exclude"
                                        color: line.modelData.status !== "yes" ? Theme.muted : exclude ? Theme.warnText : Theme.okInline
                                        text: line.modelData.status === "yes" ? (exclude ? "✕ This line excludes the selected " + page.words.one
                                                                                         : "✓ The selected " + page.words.one + " fits this line")
                                            : line.modelData.status === "maybe" ? "? Cannot tell whether the selected " + page.words.one + " fits this line"
                                            : "– The selected " + page.words.one + " does not fit this line"
                                    }
                                }
                            }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 8
                                Btn { text: "+ Match"; onClicked: page.view.addDirective("match") }
                                Btn { text: "+ Exclude…"; onClicked: page.view.addDirective("exclude") }
                                Repeater {
                                    model: page.words.fill
                                    Btn {
                                        required property var modelData
                                        visible: page.why.has === true
                                        text: modelData.label
                                        onClicked: page.view.fillFromTarget(modelData.key)
                                    }
                                }
                            }
                            Hint {
                                plain: page.why.has ? page.words.fillHint : page.words.matchHint
                            }
                        }

                        // Then
                        Card {
                            visible: page.detail.has === true
                            GroupLabel { visible: page.words.hasOpen; text: "Then, when it opens" }
                            Text {
                                Layout.fillWidth: true
                                visible: page.words.hasOpen && (page.detail.open || []).length === 0
                                font.pixelSize: Theme.secondary
                                color: Theme.muted
                                text: "Nothing set for opening."
                            }
                            GridLayout {
                                Layout.fillWidth: true
                                visible: page.words.hasOpen
                                columns: width > 620 ? 2 : 1
                                columnSpacing: 12
                                rowSpacing: 12
                                Repeater {
                                    model: page.detail.open || []
                                    RuleProp {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.columnSpan: modelData.wide && parent.columns > 1 ? 2 : 1
                                        item: modelData
                                        onEdited: function(value) { page.view.setProp(modelData.path, value) }
                                        onRemoved: page.view.removeProp(modelData.path)
                                    }
                                }
                            }
                            GroupLabel {
                                Layout.topMargin: page.words.hasOpen ? 6 : 0
                                text: page.words.hasOpen ? "And while it is open" : "Then"
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: (page.detail.always || []).length === 0
                                font.pixelSize: Theme.secondary
                                color: Theme.muted
                                text: page.words.hasOpen ? "Nothing set while open." : "Nothing set yet."
                            }
                            GridLayout {
                                Layout.fillWidth: true
                                columns: width > 620 ? 2 : 1
                                columnSpacing: 12
                                rowSpacing: 12
                                Repeater {
                                    model: page.detail.always || []
                                    RuleProp {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.columnSpan: modelData.wide && parent.columns > 1 ? 2 : 1
                                        item: modelData
                                        onEdited: function(value) { page.view.setProp(modelData.path, value) }
                                        onRemoved: page.view.removeProp(modelData.path)
                                    }
                                }
                            }
                            Select {
                                Layout.preferredWidth: 300
                                model: [{ label: "+ Add property…", value: "" }].concat(page.detail.addable || [])
                                current: ""
                                font.family: Theme.sans
                                font.pixelSize: Theme.secondary
                                Accessible.name: "Add a property to this rule"
                                onPicked: function(value) {
                                    if (value) page.view.addProp(value)
                                    current = ""; currentIndex = 0
                                }
                            }
                        }

                        // The rule as written
                        Rectangle {
                            Layout.fillWidth: true
                            visible: page.detail.has === true
                            implicitHeight: kdlText.implicitHeight + 24
                            radius: Theme.radiusBlock
                            color: Theme.chrome
                            border.width: 1
                            border.color: Theme.line
                            TextEdit {
                                id: kdlText
                                x: 14; y: 12
                                width: parent.width - 28
                                readOnly: true
                                selectByMouse: true
                                wrapMode: Text.Wrap
                                text: page.detail.kdl || ""
                                font.family: Theme.mono
                                font.pixelSize: Theme.hint
                                color: Theme.muted
                                selectionColor: Theme.accent
                                selectedTextColor: Theme.accentInk
                                Accessible.name: "The rule as written in the config"
                            }
                        }
                    }
                }
            }

            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: Theme.line }

            // Open windows or surfaces, and the "why" view
            Rectangle {
                Layout.fillHeight: true
                implicitWidth: 270
                color: Theme.chrome
                ScrollView {
                    id: asideScroll
                    anchors.fill: parent
                    contentWidth: availableWidth
                    clip: true
                    ColumnLayout {
                        width: asideScroll.availableWidth
                        spacing: 0
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.margins: 20
                            spacing: 10

                            Text {
                                text: page.words.listTitle
                                font.pixelSize: Theme.panelTitle
                                font.weight: Font.Bold
                                color: Theme.text
                                Accessible.role: Accessible.Heading
                            }
                            Text {
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                font.pixelSize: Theme.hint
                                color: Theme.muted
                                text: !page.view.connected ? page.words.offline
                                    : page.view.targets.length === 0 ? page.words.none
                                    : "Live from niri IPC · ✓ marks " + page.words.many + " the selected rule applies to"
                            }
                            Repeater {
                                model: page.view.targets
                                AbstractButton {
                                    id: win
                                    required property var modelData
                                    readonly property bool hit: modelData.status === "yes"
                                    property real radius: Theme.radius
                                    Layout.fillWidth: true
                                    implicitHeight: winText.implicitHeight + 20
                                    leftPadding: 10; rightPadding: 10
                                    Accessible.role: Accessible.ListItem
                                    Accessible.name: modelData.title + ", " + modelData.subtitle
                                                     + (hit ? ", matches the selected rule" : modelData.status === "maybe" ? ", may match the selected rule" : "")
                                    Accessible.selected: modelData.selected
                                    ToolTip.visible: hovered && modelData.reason !== ""
                                    ToolTip.delay: 500
                                    ToolTip.text: modelData.reason
                                    onClicked: page.view.selectTarget(modelData.id)
                                    contentItem: ColumnLayout {
                                        id: winText
                                        spacing: 2
                                        Text {
                                            Layout.fillWidth: true
                                            text: (win.hit ? "✓ " : win.modelData.status === "maybe" ? "? " : "") + win.modelData.title
                                            elide: Text.ElideRight
                                            font.pixelSize: Theme.body
                                            font.weight: Font.DemiBold
                                            color: win.hit ? Theme.okText : Theme.text
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: win.modelData.subtitle
                                            elide: Text.ElideRight
                                            font.family: Theme.mono
                                            font.pixelSize: Theme.groupLabel
                                            color: Theme.muted
                                        }
                                    }
                                    background: Rectangle {
                                        radius: win.radius
                                        color: win.hit ? Theme.okFill : win.modelData.selected ? Theme.selected : Theme.raised
                                        border.width: win.hit || win.modelData.selected ? 1 : 0
                                        border.color: win.modelData.selected ? Theme.accent : Theme.okBorder
                                        FocusRing { target: win }
                                    }
                                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                                }
                            }

                            // Why: which rules touch the selected window, and the result
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.topMargin: 10
                                visible: page.why.has === true
                                spacing: 8
                                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.line }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.topMargin: 6
                                    text: page.why.title || ""
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.panelTitle
                                    font.weight: Font.Bold
                                    color: Theme.text
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: page.why.subtitle || ""
                                    elide: Text.ElideRight
                                    font.family: Theme.mono
                                    font.pixelSize: Theme.groupLabel
                                    color: Theme.muted
                                }
                                GroupLabel { Layout.topMargin: 6; text: "Rules, top to bottom" }
                                Repeater {
                                    model: page.why.rules || []
                                    AbstractButton {
                                        id: whyRule
                                        required property var modelData
                                        property real radius: Theme.radiusSmall
                                        Layout.fillWidth: true
                                        implicitHeight: whyText.implicitHeight + 12
                                        leftPadding: 8; rightPadding: 8
                                        Accessible.name: modelData.title + ": " + (modelData.status === "yes" ? "applies" : modelData.status === "maybe" ? "may apply" : "does not apply")
                                                         + ", " + modelData.reason
                                        onClicked: page.view.select(modelData.index)
                                        contentItem: RowLayout {
                                            id: whyText
                                            spacing: 8
                                            Text {
                                                Layout.alignment: Qt.AlignTop
                                                text: page.statusMark(whyRule.modelData.status)
                                                font.pixelSize: Theme.secondary
                                                font.weight: Font.Bold
                                                color: whyRule.modelData.status === "yes" ? Theme.okInline : Theme.muted
                                            }
                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 1
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: whyRule.modelData.title
                                                    elide: Text.ElideRight
                                                    font.pixelSize: Theme.secondary
                                                    color: whyRule.modelData.status === "no" ? Theme.muted : Theme.text
                                                }
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: whyRule.modelData.reason
                                                    wrapMode: Text.Wrap
                                                    maximumLineCount: 3
                                                    elide: Text.ElideRight
                                                    font.pixelSize: Theme.hint
                                                    color: Theme.muted
                                                }
                                            }
                                        }
                                        background: Rectangle {
                                            radius: whyRule.radius
                                            color: whyRule.hovered ? Theme.raised : "transparent"
                                            FocusRing { target: whyRule }
                                        }
                                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                                    }
                                }
                                GroupLabel { Layout.topMargin: 6; text: "Final values" }
                                Text {
                                    Layout.fillWidth: true
                                    visible: (page.why.values || []).length === 0
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.secondary
                                    color: Theme.muted
                                    text: page.words.noValues
                                }
                                Repeater {
                                    model: page.why.values || []
                                    ColumnLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: 1
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8
                                            Text {
                                                Layout.fillWidth: true
                                                text: (modelData.maybe ? "? " : "") + modelData.label
                                                elide: Text.ElideRight
                                                font.pixelSize: Theme.secondary
                                                color: Theme.text
                                            }
                                            Text {
                                                Layout.maximumWidth: 120
                                                text: modelData.value
                                                elide: Text.ElideRight
                                                font.family: Theme.mono
                                                font.pixelSize: Theme.config
                                                color: Theme.text
                                            }
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            wrapMode: Text.Wrap
                                            font.pixelSize: Theme.hint
                                            color: Theme.muted
                                            text: "from " + modelData.rule
                                                  + (modelData.replaces ? " (replaces " + modelData.replaces + " earlier)" : "")
                                                  + (modelData.when === "open" ? " · when it opened" : "")
                                        }
                                    }
                                }
                                Btn {
                                    Layout.topMargin: 6
                                    text: "Deselect " + page.words.one
                                    onClicked: page.view.selectTarget(-1)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
