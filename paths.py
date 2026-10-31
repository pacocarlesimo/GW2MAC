"""Filesystem locations used by GW2Mac.

Everything GW2Mac installs lives in ``~/Library/Application Support/GW2Mac``:
the Wine runtime, the Windows prefix (with the game inside), downloads, logs
and the configuration. Deleting that folder removes GW2Mac completely.
"""
from pathlib import Path

HOME = Path.home()

#: Root folder for everything GW2Mac installs.
DATA_DIR = HOME / "Library/Application Support/GW2Mac"
#: Wine runtime: the Sikarugir template with the CrossOver engine inside.
RUNTIME_DIR = DATA_DIR / "runtime"
#: Windows prefix ("bottle") that contains drive C: and the game.
PREFIX_DIR = DATA_DIR / "prefix"
#: Cached downloads (engine, template, game installer).
DOWNLOADS_DIR = DATA_DIR / "downloads"
#: Original Wine files replaced by GW2Mac, restored on update or repair.
BACKUP_DIR = DATA_DIR / "backup"
#: Files GW2Mac copies into the runtime (DXMT).
OVERLAYS_DIR = DATA_DIR / "overlays"
#: Wine logs and diagnostic reports.
LOGS_DIR = DATA_DIR / "logs"
#: User configuration.
CONFIG_PATH = DATA_DIR / "config.json"

#: The game inside the prefix.
GAME_DIR = PREFIX_DIR / "drive_c/Program Files/Guild Wars 2"
GAME_EXE = "Gw2-64.exe"

#: The "Guild Wars 2" shortcut app shown in Launchpad.
APPS_DIR = HOME / "Applications"
SHORTCUT_APP = APPS_DIR / "Guild Wars 2.app"
#: Shortcut created by pre-release versions; removed when found.
LEGACY_TOOLS_APP = APPS_DIR / "GW2Mac Strumenti.app"


def ensure_dirs() -> None:
    """Create the data folders if they don't exist yet."""
    for d in (DATA_DIR, DOWNLOADS_DIR, BACKUP_DIR, OVERLAYS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
