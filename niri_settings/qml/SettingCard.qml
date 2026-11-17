import QtQuick
import QtQuick.Layouts
import "."

// One schema entry drawn as a card. The control depends on `setting.kind`.
Card {
    id: card
    required property var setting
    readonly property int rev: backend.revision
    readonly property string path: setting.path

    function read(p, fallback) {
        rev
        var v = backend.value(p)
        return v === undefined || v === null ? fallback : v
    }
    function sourceHint(p) {
        rev
        return backend.hint(p)
    }

    readonly property string error: { rev; return backend.errorFor(path, setting.kind) }
    border.color: error ? Theme.warnBorder : Theme.line

    Loader {
        Layout.fillWidth: true
        sourceComponent: ({ slider: slider, segmented: segmented, flag: flag, onoff: onoff,
                            widths: widths, struts: struts, number: number, decimal: decimal,
                            text: textKind, color: textKind, select: select, bool: boolKind,
                            offflag: offflag, xy: xy, animation: animation, workspaces: workspaces,
                            startup: startup, environment: environment, colors: colors })[card.setting.kind]
    }
    Text {  // niri's own message, on the setting that caused it
        Layout.fillWidth: true
        visible: card.error !== ""
        text: "✕ " + card.error
        wrapMode: Text.Wrap
        font.pixelSize: Theme.hint
        color: Theme.warnText
        Accessible.role: Accessible.AlertMessage
    }

    component Title: Text {
        font.pixelSize: Theme.body
        font.weight: Font.DemiBold
        color: Theme.text
        wrapMode: Text.Wrap
    }
    // `section › key · file:line`: the file:line opens the source editor
    // there, and Reset removes the setting so niri's default applies.
    component SourceHint: Flow {
        id: sh
        property string of: card.path
        property bool resettable: ["slider", "segmented", "number", "decimal", "text", "color", "select",
                                   "bool", "xy"].indexOf(card.setting.kind) >= 0
        readonly property var parts: card.sourceHint(of).split(" · ")
        readonly property bool isSet: parts.length > 1 && parts[1].indexOf("not set") !== 0
        Layout.fillWidth: true
        spacing: 6
        Text {
            text: sh.parts[0]
            font.family: Theme.mono
            font.pixelSize: Theme.hint
            color: Theme.muted
            height: 24
            verticalAlignment: Text.AlignVCenter
        }
        LinkButton {
            visible: sh.isSet
            text: sh.parts.length > 1 ? sh.parts[1] : ""
            mono: true
            Accessible.name: "Open " + text + " in Config files"
            onClicked: backend.showSource(sh.of)
        }
        Text {
            visible: !sh.isSet || sh.parts.length > 2
            text: "· " + (sh.isSet ? sh.parts.slice(2).join(" · ") : "not set, niri default")
            font.pixelSize: Theme.hint
            color: Theme.muted
            height: 24
            verticalAlignment: Text.AlignVCenter
        }
        LinkButton {
            visible: sh.isSet && sh.resettable
            text: "Reset"
            Accessible.name: "Reset " + card.setting.label + " to niri's default"
            onClicked: backend.resetValue(sh.of)
        }
    }

    Component {
        id: slider
        ColumnLayout {
            spacing: 10
            RowLayout {
                Title { text: card.setting.label; Layout.fillWidth: true }
                Text {
                    text: range.value + " " + card.setting.unit
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    color: Theme.muted
                }
            }
            RangeSlider {
                id: range
                Layout.fillWidth: true
                from: card.setting.min
                to: Math.max(card.setting.max, stored)
                readonly property real stored: Number(card.read(card.path, card.setting["default"]))
                value: stored
                onMoved: backend.setValue(card.path, value)
                Accessible.name: card.setting.label
            }
            SourceHint {}
        }
    }

    // Active, inactive and urgent colour of a block, each with an optional
    // gradient that wins over it. An empty colour field removes the colour.
    Component {
        id: colors
        ColumnLayout {
            id: cc
            spacing: 10
            readonly property var rows: { card.rev; return backend.blockColors(card.path, card.setting.defaults) }
            Title { text: card.setting.label; Layout.fillWidth: true }
            Hint { plain: card.setting.hint || ""; visible: !!card.setting.hint }
            Repeater {
                model: cc.rows
                ColumnLayout {
                    id: entry
                    required property var modelData
                    readonly property bool hasGradient: modelData.gradient.from !== undefined
                    property string problem: ""
                    Layout.fillWidth: true
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            Layout.preferredWidth: 64
                            text: entry.modelData.label
                            font.pixelSize: Theme.secondary
                            color: Theme.text
                        }
                        Field {
                            Layout.preferredWidth: 130
                            font.family: Theme.mono
                            font.pixelSize: Theme.config
                            text: entry.modelData.color
                            placeholderText: entry.modelData.fallback
                            Accessible.name: card.setting.label + " " + entry.modelData.state
                            onEditingFinished: if (text !== entry.modelData.color)
                                                   backend.setText(entry.modelData.colorPath, text.trim())
                        }
                        ColorSwatch {
                            value: entry.modelData.color
                            fallback: entry.modelData.fallback
                            label: card.setting.label + " " + entry.modelData.state
                            onPicked: v => backend.setText(entry.modelData.colorPath, v)
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: entry.hasGradient || entry.modelData.kdl !== ""
                            text: "gradient wins"
                            elide: Text.ElideRight
                            Layout.minimumWidth: implicitWidth
                            font.pixelSize: Theme.hint
                            color: Theme.muted
                        }
                        Item { Layout.fillWidth: true; visible: !entry.hasGradient && entry.modelData.kdl === "" }
                        LinkButton {
                            text: entry.hasGradient || entry.modelData.kdl !== "" ? "Remove gradient" : "Add gradient"
                            Accessible.name: text + " for " + card.setting.label + " " + entry.modelData.state
                            onClicked: {
                                entry.problem = ""
                                if (entry.hasGradient || entry.modelData.kdl !== "")
                                    backend.resetValue(entry.modelData.gradientPath)
                                else
                                    entry.problem = backend.setGradient(entry.modelData.gradientPath,
                                                                        backend.gradientDefault(entry.modelData.state))
                            }
                        }
                    }
                    GradientField {
                        visible: entry.hasGradient
                        Layout.fillWidth: true
                        Layout.leftMargin: 72
                        label: card.setting.label + " " + entry.modelData.state + " gradient"
                        value: entry.modelData.gradient
                        relOptions: backend.gradientOptions.rel
                        inOptions: backend.gradientOptions["in"]
                        onEdited: function(v) { entry.problem = backend.setGradient(entry.modelData.gradientPath, v) }
                    }
                    RowLayout {
                        visible: entry.modelData.kdl !== ""
                        Layout.leftMargin: 72
                        spacing: 6
                        Text {
                            text: "gradient " + entry.modelData.kdl
                            font.family: Theme.mono
                            font.pixelSize: Theme.hint
                            color: Theme.muted
                        }
                        LinkButton {
                            text: "edit in source"
                            onClicked: backend.showSource(entry.modelData.gradientPath)
                        }
                    }
                    Text {
                        visible: entry.problem !== ""
                        Layout.leftMargin: 72
                        text: "✕ " + entry.problem
                        font.pixelSize: Theme.hint
                        color: Theme.warnText
                    }
                }
            }
            SourceHint {}
        }
    }

    Component {
        id: segmented
        ColumnLayout {
            spacing: 10
            Title { text: card.setting.label; Layout.fillWidth: true }
            Segmented {
                Layout.fillWidth: true
                label: card.setting.label
                options: card.setting.options
                current: String(card.read(card.path, card.setting["default"]))
                onPicked: value => backend.setValue(card.path, value)
            }
            SourceHint {}
        }
    }

    Component {
        id: flag
        RowLayout {
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Title { text: card.setting.label; Layout.fillWidth: true }
                Hint { plain: card.setting.hint || "" }
                SourceHint {}
            }
            Toggle {
                on: card.read(card.path, false) === true
                onClicked: backend.setFlag(card.path, !on)
                Accessible.name: card.setting.label
            }
        }
    }

    Component {
        id: onoff
        RowLayout {
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Title { text: card.setting.label; Layout.fillWidth: true }
                Hint { plain: card.setting.hint || "" }
                SourceHint {}
            }
            Toggle {
                on: { card.rev; return backend.isOn(card.path, card.setting["default"]) }
                onClicked: backend.setOn(card.path, !on, card.setting["default"])
                Accessible.name: card.setting.label
            }
        }
    }

    Component {
        id: widths
        ColumnLayout {
            id: w
            spacing: 10
            readonly property var current: { card.rev; return backend.widthCurrent(card.path) }
            readonly property var presets: { card.rev; return backend.widthPresets(card.setting.presets) }
            Title { text: card.setting.label; Layout.fillWidth: true }
            Flow {
                Layout.fillWidth: true
                spacing: 6
                Accessible.role: Accessible.Grouping
                Accessible.name: card.setting.label
                Repeater {
                    model: w.presets
                    Chip {
                        required property var modelData
                        text: modelData.label
                        on: modelData.kind === w.current.kind
                            && Math.abs(modelData.value - w.current.value) < 0.002
                        onClicked: backend.setWidth(card.path, modelData.kind, modelData.value)
                    }
                }
            }
            Hint { plain: card.setting.hint || "" }
            SourceHint {}
        }
    }

    Component {
        id: struts
        ColumnLayout {
            spacing: 10
            Title { text: card.setting.label; Layout.fillWidth: true }
            Flow {
                Layout.fillWidth: true
                spacing: 12
                Repeater {
                    model: card.setting.sides
                    Row {
                        required property string modelData
                        spacing: 8
                        Text {
                            id: sideLabel
                            text: modelData
                            font.family: Theme.mono
                            font.pixelSize: Theme.config
                            color: Theme.muted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        NumberField {
                            from: card.setting.min
                            to: card.setting.max
                            number: Number(card.read(card.path + "/" + modelData, 0))
                            onCommitted: value => backend.setValue(card.path + "/" + modelData, value)
                            Accessible.name: card.setting.label + " " + modelData
                        }
                    }
                }
            }
            Hint { plain: card.setting.hint || "" }
            SourceHint {}
        }
    }

    Component {
        id: number
        ColumnLayout {
            spacing: 10
            RowLayout {
                spacing: 8
                Title { text: card.setting.label; Layout.fillWidth: true }
                NumberField {
                    from: card.setting.min !== undefined ? card.setting.min : -99999
                    to: card.setting.max !== undefined ? card.setting.max : 999999
                    implicitWidth: 96
                    number: Number(card.read(card.path, card.setting["default"] || 0))
                    onCommitted: value => backend.setValue(card.path, value)
                    Accessible.name: card.setting.label
                }
                Text {
                    visible: (card.setting.unit || "") !== ""
                    text: card.setting.unit || ""
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    color: Theme.muted
                }
            }
            Text {
                readonly property string unknown: card.setting.suggest ? backend.suggestionNote(card.setting.suggest, tk.stored) : ""
                Layout.fillWidth: true
                visible: unknown !== ""
                text: unknown
                wrapMode: Text.Wrap
                font.pixelSize: Theme.hint
                color: Theme.warnText
            }
            Hint { plain: card.setting.hint || ""; visible: plain !== "" }
            SourceHint {}
        }
    }

    Component {
        id: decimal
        ColumnLayout {
            spacing: 10
            RowLayout {
                spacing: 8
                Title { text: card.setting.label; Layout.fillWidth: true }
                Field {
                    id: dec
                    implicitWidth: 96
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    readonly property string stored: { card.rev; return backend.text(card.path) }
                    text: stored !== "" ? stored : String(card.setting["default"])
                    validator: DoubleValidator {
                        bottom: card.setting.min !== undefined ? card.setting.min : -1e9
                        top: card.setting.max !== undefined ? card.setting.max : 1e9
                        notation: DoubleValidator.StandardNotation
                        locale: "C"
                    }
                    Accessible.name: card.setting.label
                    onEditingFinished: if (acceptableInput && text !== (stored || String(card.setting["default"])))
                                           backend.setDecimal(card.path, text)
                }
            }
            Text {
                Layout.fillWidth: true
                visible: !dec.acceptableInput
                wrapMode: Text.Wrap
                font.pixelSize: Theme.hint
                color: Theme.warnText
                text: "Type a number from " + card.setting.min + " to " + card.setting.max
            }
            Hint { plain: card.setting.hint || ""; visible: plain !== "" }
            SourceHint {}
        }
    }

    Component {
        id: textKind
        ColumnLayout {
            id: tk
            spacing: 10
            readonly property string stored: { card.rev; return backend.text(card.path) }
            readonly property bool numbers: card.setting.numbers !== undefined
            property string problem: ""
            Title { text: card.setting.label; Layout.fillWidth: true }
            RowLayout {
                spacing: 8
                SuggestField {
                    visible: !!card.setting.suggest
                    Layout.fillWidth: true
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    kind: card.setting.suggest || ""
                    stored: tk.stored
                    placeholderText: "niri default"
                    Accessible.name: card.setting.label
                    onCommitted: v => backend.setText(card.path, v)
                }
                Field {
                    visible: !card.setting.suggest
                    Layout.fillWidth: true
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    text: tk.stored
                    placeholderText: card.setting["default"] ? card.setting["default"] : "niri default"
                    Accessible.name: card.setting.label
                    onEditingFinished: {
                        if (text === tk.stored) return
                        if (tk.numbers) tk.problem = backend.setNumbers(card.path, text)
                        else backend.setText(card.path, text)
                    }
                }
                ColorSwatch {
                    visible: card.setting.kind === "color"
                    size: 28
                    value: tk.stored
                    fallback: card.setting["default"] || ""
                    label: card.setting.label
                    onPicked: v => backend.setText(card.path, v)
                }
            }
            Text {
                Layout.fillWidth: true
                visible: tk.problem !== ""
                text: tk.problem
                font.pixelSize: Theme.hint
                color: Theme.warnText
            }
            Hint { plain: card.setting.hint || ""; visible: plain !== "" }
            SourceHint {}
        }
    }

    Component {
        id: select
        ColumnLayout {
            spacing: 10
            Title { text: card.setting.label; Layout.fillWidth: true }
            Select {
                Layout.fillWidth: true
                readonly property bool hasDefault: card.setting["default"] === ""
                model: (hasDefault ? [{ label: "device default", value: "" }] : []).concat(
                           card.setting.options.map(function (o) { return { label: o, value: o } }))
                current: String(card.read(card.path, card.setting["default"]))
                Accessible.name: card.setting.label
                onPicked: value => value === "" ? backend.resetValue(card.path) : backend.setText(card.path, value)
            }
            Hint { plain: card.setting.hint || ""; visible: plain !== "" }
            SourceHint {}
        }
    }

    Component {
        id: boolKind
        RowLayout {
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Title { text: card.setting.label; Layout.fillWidth: true }
                Hint { plain: card.setting.hint || ""; visible: plain !== "" }
                SourceHint {}
            }
            Toggle {
                on: card.read(card.path, card.setting["default"]) === true
                onClicked: backend.setBool(card.path, !on, card.setting["default"])
                Accessible.name: card.setting.label
            }
        }
    }

    Component {
        id: offflag
        RowLayout {
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Title { text: card.setting.label; Layout.fillWidth: true }
                Hint { plain: card.setting.hint || ""; visible: plain !== "" }
                SourceHint { of: card.path + "/off" }
            }
            Toggle {
                on: { card.rev; return backend.isEnabled(card.path, card.setting["default"]) }
                onClicked: backend.setEnabled(card.path, !on)
                Accessible.name: card.setting.label
            }
        }
    }

    Component {
        id: xy
        ColumnLayout {
            id: xyc
            spacing: 10
            readonly property var stored: { card.rev; return backend.xy(card.path) }
            readonly property var cur: stored.length ? stored : card.setting["default"]
            Title { text: card.setting.label; Layout.fillWidth: true }
            Row {
                spacing: 8
                Repeater {
                    model: ["x", "y"]
                    Row {
                        required property string modelData
                        required property int index
                        spacing: 8
                        Text {
                            text: modelData
                            font.family: Theme.mono
                            font.pixelSize: Theme.config
                            color: Theme.muted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        NumberField {
                            number: Number(xyc.cur[index])
                            onCommitted: value => {
                                var c = xyc.cur
                                backend.setXY(card.path, index === 0 ? value : c[0], index === 1 ? value : c[1])
                            }
                            Accessible.name: card.setting.label + " " + modelData
                        }
                    }
                }
            }
            SourceHint {}
        }
    }

    Component {
        id: animation
        ColumnLayout {
            id: anim
            spacing: 10
            readonly property var a: { card.rev; return backend.animation(card.path) }
            Title { text: card.setting.label; Layout.fillWidth: true }
            Segmented {
                Layout.fillWidth: true
                label: card.setting.label
                options: ["default", "spring", "easing", "off"]
                current: anim.a.mode
                onPicked: value => backend.setAnimationMode(card.path, value)
            }
            Repeater {
                model: anim.a.mode === "spring" ? [["damping ratio", "damping"], ["stiffness", "stiffness"], ["epsilon", "epsilon"]] : []
                RowLayout {
                    id: springRow
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 10
                    Text {
                        Layout.fillWidth: true
                        text: springRow.modelData[0]
                        font.family: Theme.mono
                        font.pixelSize: Theme.config
                        color: Theme.muted
                    }
                    Field {
                        implicitWidth: 96
                        font.family: Theme.mono
                        font.pixelSize: Theme.config
                        text: String(anim.a[springRow.modelData[1]])
                        Accessible.name: card.setting.label + " " + springRow.modelData[0]
                        onEditingFinished: {
                            var v = { damping: anim.a.damping, stiffness: anim.a.stiffness, epsilon: anim.a.epsilon }
                            v[springRow.modelData[1]] = text
                            backend.setSpring(card.path, v.damping, v.stiffness, v.epsilon)
                        }
                    }
                }
            }
            RowLayout {
                visible: anim.a.mode === "easing"
                spacing: 8
                NumberField {
                    from: 0; to: 100000
                    number: Number(anim.a.duration)
                    onCommitted: value => backend.setValue(card.path + "/duration-ms", value)
                    Accessible.name: card.setting.label + " duration"
                }
                Text { text: "ms"; font.family: Theme.mono; font.pixelSize: Theme.config; color: Theme.muted }
                Select {
                    Layout.fillWidth: true
                    model: ["ease-out-quad", "ease-out-cubic", "ease-out-expo", "linear"].map(function (c) { return { label: c, value: c } })
                    current: anim.a.curve
                    Accessible.name: card.setting.label + " curve"
                    onPicked: value => backend.setText(card.path + "/curve", value)
                }
            }
            SourceHint {}
        }
    }

    Component {
        id: workspaces
        ColumnLayout {
            id: wsCol
            spacing: 10
            property string problem: ""
            Title { text: card.setting.label; Layout.fillWidth: true }
            Text {
                visible: backend.workspaces.length === 0
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                font.pixelSize: Theme.secondary
                color: Theme.muted
                text: "None yet. Workspaces are created as you need them; a named one always exists."
            }
            Repeater {
                model: backend.workspaces
                RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.preferredWidth: 120
                        text: modelData.name
                        elide: Text.ElideRight
                        font.family: Theme.mono
                        font.pixelSize: Theme.config
                        color: Theme.text
                    }
                    Field {
                        Layout.fillWidth: true
                        font.family: Theme.mono
                        font.pixelSize: Theme.config
                        placeholderText: "any output"
                        text: modelData.output
                        Accessible.name: "Output for workspace " + modelData.name
                        onEditingFinished: if (text !== modelData.output) backend.setWorkspaceOutput(modelData.name, text)
                    }
                    LinkButton {
                        text: modelData.where
                        mono: true
                        onClicked: backend.showSource("workspace[" + modelData.name + "]")
                        Accessible.name: "Open " + modelData.where + " in Config files"
                    }
                    Btn {
                        implicitWidth: 36; leftPadding: 0; rightPadding: 0
                        text: "×"
                        Accessible.name: "Remove workspace " + modelData.name
                        onClicked: backend.removeWorkspace(modelData.name)
                    }
                }
            }
            RowLayout {
                spacing: 8
                Field {
                    id: wsName
                    Layout.fillWidth: true
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    placeholderText: "new workspace name"
                    Accessible.name: "New workspace name"
                    onAccepted: addWs.clicked()
                }
                Btn {
                    id: addWs
                    text: "Add"
                    onClicked: { wsCol.problem = backend.addWorkspace(wsName.text); if (!wsCol.problem) wsName.text = "" }
                }
            }
            Text {
                visible: wsCol.problem !== ""
                text: wsCol.problem
                font.pixelSize: Theme.hint
                color: Theme.warnText
            }
            Hint { plain: "Open-on-output takes a connector like DP-1, or make, model and serial." }
        }
    }

    Component {
        id: startup
        ColumnLayout {
            id: st
            spacing: 10
            property string problem: ""
            readonly property var items: { card.rev; return backend.startupList(card.path) }
            Title { text: card.setting.label; Layout.fillWidth: true }
            Hint { plain: card.setting.hint || "" }
            Repeater {
                model: st.items
                RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 8
                    Toggle {
                        on: !modelData.disabled
                        Accessible.name: (on ? "Turn off " : "Turn on ") + modelData.text
                        onClicked: backend.setStartupEnabled(card.path, modelData.index, !on)
                    }
                    Field {
                        Layout.fillWidth: true
                        font.family: Theme.mono
                        font.pixelSize: Theme.config
                        font.strikeout: modelData.disabled
                        opacity: modelData.disabled ? 0.6 : 1
                        text: modelData.text
                        Accessible.name: card.setting.label + " " + (modelData.index + 1)
                                         + (modelData.disabled ? ", turned off" : "")
                        onEditingFinished: if (text !== modelData.text) st.problem = backend.setStartup(card.path, modelData.index, text)
                    }
                    Btn {
                        implicitWidth: 36; leftPadding: 0; rightPadding: 0
                        text: "×"
                        Accessible.name: "Remove " + modelData.text
                        onClicked: backend.removeStartup(card.path, modelData.index)
                    }
                }
            }
            RowLayout {
                spacing: 8
                Item { visible: st.items.length > 0; implicitWidth: 52 }   // under the on/off switches
                Field {
                    id: newCmd
                    Layout.fillWidth: true
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    placeholderText: card.path === "spawn-sh-at-startup" ? "e.g. qs -c ~/shell" : "e.g. waybar"
                    Accessible.name: "New " + card.setting.label.toLowerCase()
                    onAccepted: addCmd.clicked()
                }
                Btn {
                    id: addCmd
                    text: "Add"
                    onClicked: { st.problem = backend.setStartup(card.path, -1, newCmd.text); if (!st.problem) newCmd.text = "" }
                }
            }
            Text {
                visible: st.problem !== ""
                text: st.problem
                font.pixelSize: Theme.hint
                color: Theme.warnText
            }
        }
    }

    Component {
        id: environment
        ColumnLayout {
            id: env
            spacing: 10
            property string problem: ""
            Title { text: card.setting.label; Layout.fillWidth: true }
            Repeater {
                model: backend.environment
                RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.preferredWidth: 170
                        text: modelData.name
                        elide: Text.ElideRight
                        font.family: Theme.mono
                        font.pixelSize: Theme.config
                        color: Theme.text
                    }
                    Field {
                        Layout.fillWidth: true
                        font.family: Theme.mono
                        font.pixelSize: Theme.config
                        enabled: !modelData.unset
                        text: modelData.unset ? "" : modelData.value
                        placeholderText: modelData.unset ? "unset (null)" : ""
                        Accessible.name: "Value of " + modelData.name
                        onEditingFinished: if (!modelData.unset && text !== modelData.value) env.problem = backend.setEnv(modelData.name, text)
                    }
                    Btn {
                        implicitWidth: 36; leftPadding: 0; rightPadding: 0
                        text: "×"
                        Accessible.name: "Remove " + modelData.name
                        onClicked: backend.removeEnv(modelData.name)
                    }
                }
            }
            RowLayout {
                spacing: 8
                Field {
                    id: envName
                    Layout.preferredWidth: 170
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    placeholderText: "NAME"
                    Accessible.name: "New variable name"
                }
                Field {
                    id: envValue
                    Layout.fillWidth: true
                    font.family: Theme.mono
                    font.pixelSize: Theme.config
                    placeholderText: "value"
                    Accessible.name: "New variable value"
                    onAccepted: addEnv.clicked()
                }
                Btn {
                    id: addEnv
                    text: "Add"
                    onClicked: {
                        env.problem = backend.setEnv(envName.text, envValue.text)
                        if (!env.problem) { envName.text = ""; envValue.text = "" }
                    }
                }
            }
            Text {
                visible: env.problem !== ""
                text: env.problem
                font.pixelSize: Theme.hint
                color: Theme.warnText
            }
            Hint { plain: "Variables written as null are unset for programs niri starts; remove them here or edit them in Config files." }
        }
    }
}
