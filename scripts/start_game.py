"""Double-click launcher: keep a local Streamlit service running and open the game."""

from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8502/"


def ready() -> bool:
    try:
        with urllib.request.urlopen(URL + "_stcore/health", timeout=1) as response:
            return response.status == 200 and response.read(64).decode().strip() == "ok"
    except (OSError, urllib.error.URLError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Check/start without opening UI")
    args = parser.parse_args()
    try:
        if not ready():
            logs = ROOT / "outputs" / "preview"
            logs.mkdir(parents=True, exist_ok=True)
            options = {}
            if sys.platform == "win32":
                startup = subprocess.STARTUPINFO()
                startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup.wShowWindow = 0
                options = {
                    "startupinfo": startup,
                    "creationflags": (
                        subprocess.CREATE_NEW_PROCESS_GROUP
                        | subprocess.DETACHED_PROCESS
                        | subprocess.CREATE_BREAKAWAY_FROM_JOB
                    ),
                }
            with (logs / "game-launch.log").open("a", encoding="utf-8") as log:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "streamlit",
                        "run",
                        "app/streamlit_app.py",
                        "--server.headless",
                        "true",
                        "--server.address",
                        "127.0.0.1",
                        "--server.port",
                        "8502",
                        "--browser.gatherUsageStats",
                        "false",
                    ],
                    cwd=ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    **options,
                )
                deadline = time.monotonic() + 45
                while not ready():
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError(
                            "起動に失敗しました。outputs/preview/game-launch.logを確認してください。"
                        )
                    time.sleep(0.25)
        if not args.no_browser:
            webbrowser.open(URL)
        print(URL)
        return 0
    except (OSError, RuntimeError) as error:
        if sys.platform == "win32" and not args.no_browser:
            ctypes.windll.user32.MessageBoxW(0, str(error), "MedLink-LEO の起動", 0x10)
        else:
            print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
