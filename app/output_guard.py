"""Reverts a display trial unless told to keep it.

Runs as its own process so the revert still happens if the settings app
crashes or its window cannot be seen. Usage:

    python3 -m app.output_guard SECONDS  (revert commands as JSON on argv[2])

It waits on stdin. "keep" ends it without doing anything. "revert", a closed
stdin (the app died) or the timeout all run the revert commands.
"""

import json
import select
import subprocess
import sys


def main() -> int:
    seconds = float(sys.argv[1])
    commands = json.loads(sys.argv[2])
    ready, _, _ = select.select([sys.stdin], [], [], seconds)
    if ready and sys.stdin.readline().strip() == "keep":
        return 0
    for argv in commands:
        subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
