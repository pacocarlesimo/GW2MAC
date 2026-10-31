"""The "Guild Wars 2" shortcut app and the GW2Mac menu.

GW2Mac.app shows a menu when opened from Finder. Setup also creates a small
"Guild Wars 2" app in ~/Applications that starts the game directly, so it can be
launched from Launchpad, Spotlight or the Dock.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from config import Config
from paths import LEGACY_TOOLS_APP, LOGS_DIR, SHORTCUT_APP
from ui import alert, choose, open_in_terminal, say
from version import __version__

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Guild Wars 2</string>
  <key>CFBundleDisplayName</key><string>Guild Wars 2</string>
  <key>CFBundleIdentifier</key><string>io.github.gw2mac.launcher</string>
  <key>CFBundleVersion</key><string>{version}</string>
  <key>CFBundleShortVersionString</key><string>{version}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.role-playing-games</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
"""


def own_command() -> list:
    """Command that runs this copy of GW2Mac (packaged app or source checkout)."""
    resources = os.environ.get("RESOURCEPATH")      # set by py2app
    if getattr(sys, "frozen", False) and resources:
        return [str(Path(resources).parent / "MacOS" / "GW2Mac")]
    return [sys.executable, str(Path(__file__).resolve().parent / "main.py")]


def _quote(arg: str) -> str:
    return "'" + arg.replace("'", "'\\''") + "'"


def create() -> None:
    """Create (or refresh) the "Guild Wars 2" app in ~/Applications."""
    if LEGACY_TOOLS_APP.exists():
        shutil.rmtree(LEGACY_TOOLS_APP, ignore_errors=True)
    shutil.rmtree(SHORTCUT_APP, ignore_errors=True)
    macos = SHORTCUT_APP / "Contents/MacOS"
    macos.mkdir(parents=True)
    (SHORTCUT_APP / "Contents/Info.plist").write_text(INFO_PLIST.format(version=__version__))
    launcher = macos / "launcher"
    command = " ".join(_quote(a) for a in own_command())
    launcher.write_text(f"#!/bin/bash\nexec {command} play\n")
    launcher.chmod(0o755)
    try:   # ad-hoc signature, so macOS runs the app without complaints
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(SHORTCUT_APP)],
                       capture_output=True)
    except OSError:
        pass
    say(f"Created {SHORTCUT_APP}: start the game from Launchpad or Spotlight")


def menu(installed: bool, play, toggle, set_screen) -> None:
    """GW2Mac's menu, shown when the app is opened from Finder.

    Quick actions run here; long ones open a Terminal window to show progress.
    """
    cfg = Config.load()
    in_terminal = lambda cmd: lambda: open_in_terminal(own_command() + [cmd])  # noqa: E731
    on_off = lambda flag: "on" if flag else "off"                             # noqa: E731
    actions = {
        "Play": play,
        "Install or finish setup": in_terminal("setup"),
        "Import an existing installation": in_terminal("import"),
        "Repair": in_terminal("repair"),
        "Screen: windowed": lambda: set_screen("windowed"),
        "Screen: borderless window": lambda: set_screen("borderless"),
        "Screen: full screen": lambda: set_screen("fullscreen"),
        f"Retina resolution (now {on_off(cfg.retina)})": lambda: toggle("retina"),
        f"Performance HUD (now {on_off(cfg.hud)})": lambda: toggle("hud"),
        "Update Wine": in_terminal("update"),
        "Check installation": in_terminal("doctor"),
        "Open logs folder": lambda: subprocess.run(["/usr/bin/open", str(LOGS_DIR)]),
    }
    default = "Play" if installed else "Install or finish setup"
    prompt = "Choose an action:" if installed else "Guild Wars 2 is not set up yet."
    picked = choose(f"GW2Mac {__version__}", prompt, list(actions), default)
    if picked in actions:
        actions[picked]()
        if picked.startswith(("Screen:", "Retina", "Performance")):
            alert("Done. It takes effect the next time you start the game.")
