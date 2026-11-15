import QtQuick
import "."

// A scrolling workspace drawn from real columns. Gaps, ring and border are
// drawn at 1:1 pixels so small values stay readable at this size.
Rectangle {
    id: root
    property var columns: []
    property real gaps: 16
    property real ring: 4
    property bool ringOn: true
    property real borderWidth: 4
    property bool borderOn: false
    property string center: "never"

    implicitWidth: 560
    implicitHeight: 300
    radius: Theme.radiusCard
    color: Theme.previewGround
    border.width: 1
    border.color: Theme.line
    clip: true
    Accessible.role: Accessible.Graphic
    Accessible.name: "Live preview of the focused workspace"

    readonly property var geo: {
        var W = width, H = height, g = gaps, x = g, items = [], fx = 0, fw = 0
        for (var i = 0; i < columns.length; i++) {
            var c = columns[i]
            var w = Math.max(24, Math.round((W - g) * c.share - g))
            var y = g
            for (var j = 0; j < c.rows.length; j++) {
                var r = c.rows[j]
                var h = Math.max(16, Math.round((H - g) * r.share - g))
                items.push({ x: x, y: y, w: w, h: h, label: r.label, focused: r.focused })
                y += h + g
            }
            if (c.focused) { fx = x; fw = w }
            x += w + g
        }
        var off = 0
        var overflows = fx + fw + g > W
        if (center === "always") off = fx + fw / 2 - W / 2
        else if (center === "on-overflow") off = overflows ? fx + fw / 2 - W / 2 : 0
        else off = overflows ? fx + fw + g - W : 0
        return { items: items, offset: -Math.round(off) }
    }

    Item {
        id: strip
        width: parent.width
        height: parent.height
        x: root.geo.offset
        Behavior on x { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }

        Repeater {
            model: root.geo.items.length
            Item {
                id: tile
                required property int index
                readonly property var it: root.geo.items[index] || ({ x: 0, y: 0, w: 0, h: 0, label: "", focused: false })
                x: it.x; y: it.y; width: it.w; height: it.h
                Behavior on x { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }
                Behavior on y { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }
                Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }
                Behavior on height { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }

                Rectangle {  // focus ring, outside the window
                    anchors.fill: parent
                    anchors.margins: -root.ring
                    radius: Theme.radiusBlock + root.ring
                    color: Theme.accent
                    visible: tile.it.focused && root.ringOn && root.ring > 0
                }
                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusBlock
                    color: tile.it.focused ? Theme.tileFocused : Theme.tile
                    border.width: root.borderOn ? Math.min(root.borderWidth, width / 2) : 0
                    border.color: Theme.lineStrong
                }
                Text {
                    anchors.fill: parent
                    anchors.margins: 10 + (root.borderOn ? root.borderWidth : 0)
                    text: tile.it.label
                    font.pixelSize: Theme.hint
                    color: Theme.muted
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }
        }
    }
}
