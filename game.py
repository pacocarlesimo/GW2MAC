"""Guild Wars 2 itself: install, import, launch, repair and screen mode."""
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import diagnostics
import dxmt
import prefix
from config import Config
from net import download
from paths import DOWNLOADS_DIR, GAME_DIR, GAME_EXE, HOME, LOGS_DIR, PREFIX_DIR
from ui import die, say, warn
from wine import Wine, fix_library_links

INSTALLER_URL = "https://s3.amazonaws.com/gw2cdn/client/branches/Gw2Setup-64.exe"

#: Where other Wine front-ends keep their bottles, for ``import`` without a path.
OTHER_BOTTLES = (
    HOME / "Library/Containers/com.isaacmarovitz.Whisky/Bottles",
    HOME / "Library/Application Support/CrossOver/Bottles",
)

#: ``gw2mac screen <mode>`` -> value of GW2's screenMode option.
SCREEN_MODES = {
    "windowed": "windowed",
    "borderless": "windowed_fullscreen",
    "fullscreen": "fullscreen",
}

#: Logs of the last sessions to keep.
KEEP_LOGS = 5


def find_exe() -> "Path | None":
    """Gw2-64.exe inside the prefix, or None."""
    exe = GAME_DIR / GAME_EXE
    if exe.is_file():
        return exe
    drive = PREFIX_DIR / "drive_c"
    if not drive.exists():
        return None
    for root, dirs, files in os.walk(drive):
        if len(Path(root).relative_to(drive).parts) >= 4:
            dirs.clear()
        for f in files:
            if f.lower() == GAME_EXE.lower():
                return Path(root) / f
    return None


def find_other_install() -> "Path | None":
    """A Guild Wars 2 folder in a Whisky or CrossOver bottle, if any."""
    for root in OTHER_BOTTLES:
        if root.exists():
            for exe in root.glob(f"**/{GAME_EXE}"):
                return exe.parent
    return None


def install() -> None:
    """Run ArenaNet's official installer inside the prefix."""
    prefix.create()
    exe = find_exe()
    if exe:
        say(f"Guild Wars 2 is already installed: {exe}")
        return
    installer = download(INSTALLER_URL, DOWNLOADS_DIR / "Gw2Setup-64.exe")
    say(r"Starting ArenaNet's installer. Keep the default folder (C:\Program Files\Guild Wars 2).")
    say("The game (about 70 GB) downloads inside the installer: let it finish, then close it.")
    wine = Wine()
    wine.run(str(installer), cwd=DOWNLOADS_DIR, log=LOGS_DIR / "install.log")
    wine.wait()
    exe = find_exe()
    if exe:
        say(f"Installed: {exe}")
    else:
        warn("Gw2-64.exe not found. Run the installer again with: gw2mac install")


def import_from(source: "str | None" = None) -> None:
    """Copy an existing installation into the prefix.

    On APFS the copy is a copy-on-write clone: instant, and it takes no extra space.
    """
    if source:
        path = Path(source).expanduser()
    else:
        path = find_other_install()
        if not path:
            die('No existing installation found. Use: gw2mac import "/path/to/Guild Wars 2"')
        say(f"Found an existing installation: {path}")
    if not (path / GAME_EXE).is_file():
        die(f"{GAME_EXE} not found in {path}")
    prefix.create()
    if find_exe():
        die(f"Guild Wars 2 is already installed in {GAME_DIR}. Remove it before importing.")
    GAME_DIR.parent.mkdir(parents=True, exist_ok=True)
    say("Copying (APFS clone when possible)")
    if subprocess.run(["/bin/cp", "-cR", str(path), str(GAME_DIR)],
                      capture_output=True).returncode != 0:
        shutil.rmtree(GAME_DIR, ignore_errors=True)
        shutil.copytree(path, GAME_DIR, symlinks=True)
    say(f"Imported into {GAME_DIR}")


def _keep_awake(pid: int) -> None:
    """Prevent idle sleep while ``pid`` runs.

    caffeinate runs as a separate process watching the game: wrapping Wine in it
    would strip the DYLD_* variables Wine needs (see wine.py).
    """
    try:
        subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(pid)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def _rotate_logs() -> None:
    logs = sorted(LOGS_DIR.glob("gw2-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in logs[KEEP_LOGS - 1:]:
        old.unlink(missing_ok=True)


def play() -> None:
    """Launch Guild Wars 2 and wait until it exits."""
    exe = find_exe()
    if not exe:
        die("Guild Wars 2 is not installed. Run: gw2mac setup")
    wine, cfg = Wine(), Config.load()
    prefix.ensure_tuned()
    dxmt.ensure_ready(exe)
    _rotate_logs()
    log = LOGS_DIR / f"gw2-{time.strftime('%Y%m%d-%H%M%S')}.log"
    say("Starting Guild Wars 2")
    started = time.time()
    with open(log, "w") as out:
        proc = subprocess.Popen([str(wine.bin), str(exe), "-autologin", *cfg.game_args],
                                env=wine.env(trace_dlls=True), cwd=exe.parent,
                                stdout=out, stderr=subprocess.STDOUT)
        _keep_awake(proc.pid)
        proc.wait()
    wine.wait()                       # CefHost.exe and other helpers may still be running
    diagnostics.after_session(log, started)


def repair() -> None:
    """Re-link libraries, re-apply DXMT and prefix settings, verify the game files."""
    exe = find_exe()
    if not exe:
        die("Guild Wars 2 is not installed. Run: gw2mac setup")
    wine = Wine()
    say("Repairing: stopping Wine, re-applying settings, verifying game files")
    wine.kill()
    fix_library_links(wine)
    dxmt.enable(exe, prefix_ready=prefix.exists())
    prefix.tune()
    wine.run(str(exe), "-repair", cwd=exe.parent, log=LOGS_DIR / "repair.log")
    wine.wait()
    dxmt.sync_game_dlls(exe)          # the repair may have removed them
    say("Repair complete")


def graphics_settings() -> "Path | None":
    """GW2's graphics options file, most recently used first."""
    files = sorted((PREFIX_DIR / "drive_c/users").glob(
        "*/AppData/Roaming/Guild Wars 2/GFXSettings.Gw2-64.exe.xml"),
        key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def set_screen_mode(mode: str) -> None:
    """Change GW2's screen mode while the game is closed (a backup is kept)."""
    path = graphics_settings()
    if not path:
        die("GW2's graphics settings were not found: start the game once first.")
    text = path.read_text(errors="replace")
    option = re.search(r'(<OPTION\b[^>]*Name="screenMode"[^>]*>)(.*?)</OPTION>',
                       text, re.S | re.I)
    if not option:
        die("The screenMode option was not found in GW2's graphics settings.")
    allowed = re.findall(r'EnumValue="([^"]+)"', option.group(2))
    value = SCREEN_MODES[mode]
    if allowed and value not in allowed:
        die(f"GW2 doesn't accept '{value}' (allowed: {', '.join(allowed)})")
    if 'Value="' not in option.group(1):
        die("Unrecognised format for the screenMode option.")
    tag = re.sub(r'Value="[^"]*"', f'Value="{value}"', option.group(1), count=1)
    shutil.copy2(path, path.with_name(path.name + ".bak"))
    path.write_text(text[:option.start(1)] + tag + text[option.end(1):])
    say(f"Screen mode: {mode}. Takes effect the next time you start the game.")
