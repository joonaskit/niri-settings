"""NiriState folds event-stream events without a running niri."""
import unittest

from niri_settings.ipc import NiriState


def window(wid, col, row, focused=False, ws=1):
    return {"id": wid, "title": f"w{wid}", "app_id": "app", "workspace_id": ws,
            "is_focused": focused, "is_floating": False,
            "layout": {"pos_in_scrolling_layout": [col, row], "tile_size": [800.0, 600.0]}}


class State(unittest.TestCase):
    def setUp(self):
        self.state = NiriState()
        self.state.apply({"WorkspacesChanged": {"workspaces": [
            {"id": 1, "idx": 1, "output": "DP-1", "is_active": True, "is_focused": True},
            {"id": 2, "idx": 2, "output": "DP-1", "is_active": False, "is_focused": False}]}})
        self.state.apply({"WindowsChanged": {"windows": [
            window(1, 2, 1), window(2, 1, 1, focused=True), window(3, 2, 2), window(4, 1, 1, ws=2)]}})

    def test_columns_are_ordered(self):
        cols = self.state.columns(1)
        self.assertEqual([[w["id"] for w in c] for c in cols], [[2], [1, 3]])

    def test_focus_close_and_workspace_switch(self):
        self.state.apply({"WindowFocusChanged": {"id": 3}})
        self.assertEqual([w["id"] for w in self.state.windows.values() if w["is_focused"]], [3])
        self.state.apply({"WindowClosed": {"id": 1}})
        self.assertEqual([[w["id"] for w in c] for c in self.state.columns(1)], [[2], [3]])
        self.state.apply({"WorkspaceActivated": {"id": 2, "focused": True}})
        self.assertEqual(self.state.focused_workspace()["id"], 2)
        self.assertFalse(self.state.apply({"KeyboardLayoutsChanged": {}}))


if __name__ == "__main__":
    unittest.main()
