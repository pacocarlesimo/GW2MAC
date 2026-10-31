"""Post-session checks, crash reports and ``gw2mac doctor``.

Wine logs prefix every line with a 4-digit *thread* id (not a process id).
"""
import platform
import re
import time
from pathlib import Path

import dxmt
import runtime
import wine as wine_module
from config import Config
from paths import BACKUP_DIR, DATA_DIR, LOGS_DIR, PREFIX_DIR, RUNTIME_DIR
from ui import say, warn
from version import __version__
from wine import Wine

REPORT = LOGS_DIR / "crash-report.txt"
#: A session shorter than this is treated as a failed start.
SHORT_SESSION = 120

#: Libraries Wine opens at runtime: (name, message Wine prints when it is missing).
RUNTIME_LIBRARIES = (
    ("FreeType (fonts)", "cannot find the freetype"),
    ("GnuTLS (secure connections)", "failed to load libgnutls"),
    ("MoltenVK (Vulkan)", "driver supporting vulkan"),
)

LOADED_DLL = re.compile(r'^([0-9a-f]{4}):trace:loaddll:build_module Loaded L"([^"]+)"', re.M | re.I)


def game_renderer(log_text: str) -> str:
    """Which Direct3D the game thread loaded, according to the DLL-load log."""
    loads = {}
    for thread, path in LOADED_DLL.findall(log_text):
        loads.setdefault(thread, []).append(path.replace("\\\\", "\\").lower())
    game = [t for t, paths in loads.items()
            if any(p.endswith(("\\nvapi64.dll", "\\amd_ags_x64.dll", "\\winemetal.dll"))
                   or re.search(r"guild wars 2\\(d3d11|dxgi)\.dll$", p) for p in paths)]
    if not game:
        return "unknown (the game didn't start 3D, or the log has no DLL loads)"
    paths = loads[game[-1]]
    if any(p.endswith("\\winemetal.dll") for p in paths):
        return "DXMT (Metal)"
    if any(p.endswith("\\d3d11.dll") for p in paths):
        return "wined3d (OpenGL): DXMT was not loaded"
    return "no Direct3D loaded"


def arenanet_log() -> "Path | None":
    """ArenaNet.log, the game's own log and crash report."""
    users = PREFIX_DIR / "drive_c/users"
    logs = sorted(users.glob("*/AppData/Roaming/Guild Wars 2/ArenaNet.log"),
                  key=lambda p: p.stat().st_mtime, reverse=True) if users.exists() else []
    return logs[0] if logs else None


def write_report(wine_log: Path, since: float = 0.0) -> Path:
    """Collect everything needed to understand a failed start into one file."""
    cfg = Config.load()
    parts = [f"GW2Mac {__version__}, {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"macOS {platform.mac_ver()[0]} {platform.machine()}",
             f"Runtime: {runtime.installed_version()}",
             f"DXMT: {dxmt.installed_version()}",
             f"Retina: {cfg.retina}  HUD: {cfg.hud}  Debug: {wine_module.debug}",
             f"Game arguments: {' '.join(cfg.game_args) or '-'}", ""]

    def section(path: "Path | None", title: str, lines: int) -> None:
        parts.append(f"===== {title} ({path or 'not found'}) =====")
        if path and path.exists():
            parts.extend(path.read_text(errors="replace").splitlines()[-lines:])
        parts.append("")

    section(wine_log, "Wine log", 200)
    anet = arenanet_log()
    stale = anet is not None and since and anet.stat().st_mtime < since
    section(anet, "ArenaNet.log" + (" (FROM AN EARLIER SESSION)" if stale else ""), 150)
    dxmt_logs = sorted((p for p in LOGS_DIR.glob("*.log")
                        if re.search(r"dxmt|d3d11|dxgi|d3d10", p.name, re.I)
                        and p.stat().st_mtime >= since),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    if not dxmt_logs:
        section(None, "DXMT log of this session", 0)
    for p in dxmt_logs[:4]:
        section(p, "DXMT log", 120)
    REPORT.write_text("\n".join(parts))
    return REPORT


def after_session(log: Path, started: float) -> None:
    """Explain what happened after the game exits."""
    seconds = int(time.time() - started)
    say(f"Session ended after {seconds // 60} min {seconds % 60} s")
    text = log.read_text(errors="replace") if log.exists() else ""
    lowered = text.lower()
    missing = [name for name, sign in RUNTIME_LIBRARIES if sign in lowered]
    if missing:
        warn("Wine could not load: " + ", ".join(missing))
        warn("Without FreeType and GnuTLS the launcher stays empty. Check with: gw2mac doctor")
    say("Renderer used by the game: " + game_renderer(text))
    if seconds < SHORT_SESSION or wine_module.debug:
        report = write_report(log, since=started)
        if seconds < SHORT_SESSION:
            warn("The game closed very quickly: it probably failed to start.")
        if "Library not loaded" in text:
            warn("Cause: a Wine library is missing. Fix with: gw2mac repair")
        warn(f"Diagnostic report: {report}")
        if not wine_module.debug:
            warn("For a detailed report run: gw2mac debug")


def doctor() -> None:
    """Check the runtime: library folders, runtime-loaded libraries and DXMT."""
    w = Wine()
    say("Library folders:")
    for d in w.lib_dirs():
        print(f"   {'ok' if d.is_dir() else '--'}  {d}")
    wanted = (("FreeType (fonts)", "libfreetype*.dylib", True),
              ("GnuTLS (HTTPS)", "libgnutls*.dylib", True),
              ("MoltenVK (Vulkan)", "libMoltenVK*.dylib", False),
              ("SDL2 (controllers)", "libSDL2*.dylib", False))
    healthy = True
    for name, pattern, essential in wanted:
        hit = next((f for d in w.lib_dirs() if d.is_dir() for f in d.rglob(pattern)), None)
        print(f"   {'ok' if hit else 'NO'}  {name}: {hit or 'not found'}")
        healthy &= hit is not None or not essential
    bundled = dxmt.find_bundled()
    print(f"   DXMT in template: {bundled[0] if bundled else 'not found'}")
    print(f"   Prepared d3d11 is DXMT: {'yes' if dxmt.is_prepared() else 'NO'}")
    print(f"   DXMT in use: {dxmt.installed_version()}")
    print("   DXMT files in the runtime and backups:")
    for root in (RUNTIME_DIR, BACKUP_DIR):
        found = sorted(root.rglob("winemetal*")) + [
            d for d in sorted(root.rglob("d3d11.dll")) if dxmt.is_dxmt_dll(d)]
        for f in found:
            print(f"      {f.relative_to(DATA_DIR)}")
    if healthy:
        say("Essential libraries found.")
    else:
        warn("An essential library is missing. Please report this output in a GitHub issue.")
