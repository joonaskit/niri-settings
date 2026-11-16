import os
import tempfile

# Tests must never reach the niri session they run in: the display trial's
# guard process runs `niri msg output ...`, which would move real screens.
# Tests that need niri start a nested one with its own socket (test_nested.py).
os.environ["NIRI_SOCKET"] = os.path.join(tempfile.gettempdir(), "niri-settings-tests-no-niri.sock")
