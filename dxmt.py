"""DXMT: DirectX 11 on Metal for Guild Wars 2.

How DXMT is wired, and why (each point was learned the hard way):

1. **Use the DXMT build that ships with the Sikarugir template.** It is compiled
   for the engine's Wine version; other builds fail with GR_DEVICE_ERROR_INIT_FAILED.

2. **The launcher and the game are the same process.** Gw2-64.exe shows the
   launcher, then initialises 3D in the same process after "Play". dxgi and d3d11
   must both be DXMT from the start, otherwise DXMT reports "Not a DXMT adapter".

3. **The launcher UI is drawn by CefHost.exe (Chromium) in another process.**
   With DXMT's d3d11 it stays black: DXMT can't present into windows owned by
   another process on this Wine version. CefHost.exe must keep Wine's own d3d11
   (wined3d) and must still find a d3d11.dll, or Chromium exits.

4. **Gw2-64.exe loads dxgi early, as a dependency of Wine's own DLLs,** which
   ignores per-application overrides. So DXMT's dxgi replaces Wine's in the
   runtime. CefHost.exe then fails to create a d3d11 device cleanly and Chromium
   falls back to software rendering, which is plenty for the launcher.

5. **DXMT's d3d11 goes next to Gw2-64.exe as a native DLL,** enabled by an
   override that applies to Gw2-64.exe only. DXMT DLLs carry Wine's
   "Wine builtin DLL" signature right after the DOS header; when Wine finds that
   signature it loads its own DLL of the same name instead. GW2Mac clears those
   16 bytes in the copies, so Wine loads them as regular Windows DLLs.

6. **winemetal stays in the runtime as a builtin,** because it is the bridge to
   the macOS side (winemetal.dll talks to winemetal.so).

Files GW2Mac changes in the runtime are backed up first and restored on demand.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

from paths import BACKUP_DIR, DATA_DIR, GAME_EXE, OVERLAYS_DIR, RUNTIME_DIR
from ui import die, say
from wine import TEMPLATE_APP, Wine

#: Prepared DXMT files, laid out like the runtime's lib/ folder.
DXMT_DIR = OVERLAYS_DIR / "dxmt"
DXMT_PE_DIR = DXMT_DIR / "wine/x86_64-windows"
DXMT_FILES = ("d3d11.dll", "dxgi.dll", "d3d10core.dll", "winemetal.dll")
#: DLLs loaded from the game folder by Gw2-64.exe.
GAME_DLLS = ("d3d11.dll", "dxgi.dll", "d3d10core.dll")
#: What goes into the runtime itself (point 4 and 6 above).
RUNTIME_FILES = ("winemetal*", "dxgi.dll")

GAME_OVERRIDES_KEY = rf"HKCU\Software\Wine\AppDefaults\{GAME_EXE}\DllOverrides"
#: Used by a pre-release that disabled Direct3D in CefHost.exe; removed when found.
LEGACY_CEF_KEY = r"HKCU\Software\Wine\AppDefaults\CefHost.exe\DllOverrides"

VERSION_FILE = DATA_DIR / "dxmt.version"
MODE_FILE = DATA_DIR / "dxmt.mode"
MODE = "native-game-2"                       # bump to re-apply the setup on upgrade
OVERLAY_STATE = DATA_DIR / "overlay_state.json"
GAME_DLLS_STATE = DATA_DIR / "game_dlls.json"

BUILTIN_SIGNATURE = b"Wine builtin DLL"
SIGNATURE_OFFSET = 0x40                      # sizeof(IMAGE_DOS_HEADER)


# --------------------------------------------------------------------------- #
# Finding and preparing DXMT
# --------------------------------------------------------------------------- #
def is_dxmt_dll(path: Path) -> bool:
    """DXMT's d3d11/dxgi import winemetal.dll; Wine's own versions don't."""
    try:
        return b"winemetal" in path.read_bytes().lower()
    except OSError:
        return False


def find_bundled() -> "tuple | None":
    """DXMT shipped with the template: ``(folder of the x86_64 DLLs, winemetal.so)``."""
    template = RUNTIME_DIR / TEMPLATE_APP
    if not template.is_dir():
        return None
    # The runtime's own lib folders are modified by GW2Mac, so they are not a source.
    modified = set()
    if Wine.installed():
        own = (Wine().lib / "wine").resolve()
        modified = {own / d for d in ("x86_64-windows", "x86_64-unix", "i386-windows")}

    def candidates(name: str) -> list:
        found = [p for p in template.rglob(name) if p.resolve().parent not in modified]
        return sorted(found, key=lambda p: ("x86_64" not in p.as_posix(), len(p.parts)))

    dll = next((p for p in candidates("winemetal.dll")
                if "i386" not in p.as_posix() and is_dxmt_dll(p.parent / "d3d11.dll")), None)
    if not dll:
        return None
    sibling = dll.parent.parent / "x86_64-unix" / "winemetal.so"
    so = sibling if sibling.exists() else next(iter(candidates("winemetal.so")), None)
    return (dll.parent, so) if so else None


def prepare() -> None:
    """Copy the template's DXMT into the overlays folder."""
    found = find_bundled()
    if not found:
        die("The Sikarugir template does not contain DXMT. Run: gw2mac update")
    pe_dir, so = found
    shutil.rmtree(DXMT_DIR, ignore_errors=True)
    DXMT_PE_DIR.mkdir(parents=True)
    (DXMT_DIR / "wine/x86_64-unix").mkdir(parents=True)
    for name in DXMT_FILES:
        if (pe_dir / name).exists():
            shutil.copy2(pe_dir / name, DXMT_PE_DIR / name)
    shutil.copy2(so, DXMT_DIR / "wine/x86_64-unix/winemetal.so")
    rel = pe_dir.relative_to(RUNTIME_DIR)
    VERSION_FILE.write_text(f"Sikarugir template ({rel})")
    say("DXMT: using the build included in the Sikarugir template")


def is_prepared() -> bool:
    return is_dxmt_dll(DXMT_PE_DIR / "d3d11.dll")


def installed_version() -> str:
    return VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "not installed"


def forget_runtime() -> None:
    """Called when the runtime is replaced: the overlay records and the prepared
    DXMT belong to the old runtime and must not be applied to the new one."""
    OVERLAY_STATE.unlink(missing_ok=True)
    MODE_FILE.unlink(missing_ok=True)
    VERSION_FILE.unlink(missing_ok=True)
    shutil.rmtree(DXMT_DIR, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Runtime overlay with backup
# --------------------------------------------------------------------------- #
def restore_runtime(wine: Wine) -> None:
    """Put back every runtime file GW2Mac replaced."""
    touched = json.loads(OVERLAY_STATE.read_text()) if OVERLAY_STATE.exists() else []
    for rel in touched:
        target, backup = wine.lib / rel, BACKUP_DIR / rel
        if backup.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target, follow_symlinks=False)
        elif target.exists() or target.is_symlink():
            target.unlink()
    OVERLAY_STATE.unlink(missing_ok=True)


def _apply_overlay(wine: Wine, src: Path) -> None:
    """Copy ``src`` over the runtime's lib/ folder, backing up the originals."""
    touched = []
    for f in src.rglob("*"):
        if f.is_dir() and not f.is_symlink():
            continue
        rel = f.relative_to(src).as_posix()
        target, backup = wine.lib / rel, BACKUP_DIR / rel
        if target.exists() and not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup, follow_symlinks=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            target.unlink()
        shutil.copy2(f, target, follow_symlinks=False)
        touched.append(rel)
    OVERLAY_STATE.write_text(json.dumps(touched))


# --------------------------------------------------------------------------- #
# Native DLLs for the game
# --------------------------------------------------------------------------- #
def as_native_dll(data: bytes) -> bytes:
    """Clear Wine's builtin signature so the DLL loads as a regular Windows DLL."""
    end = SIGNATURE_OFFSET + len(BUILTIN_SIGNATURE)
    if data[SIGNATURE_OFFSET:end] == BUILTIN_SIGNATURE:
        data = data[:SIGNATURE_OFFSET] + b"\0" * len(BUILTIN_SIGNATURE) + data[end:]
    return data


def sync_game_dlls(game_exe: "Path | None") -> None:
    """Place DXMT's d3d11/dxgi/d3d10core (as native DLLs) next to Gw2-64.exe.

    Called before every launch, because a game repair or update can delete them.
    """
    if not game_exe or not is_prepared():
        return
    placed = []
    for name in GAME_DLLS:
        if not (DXMT_PE_DIR / name).exists():
            continue
        data = as_native_dll((DXMT_PE_DIR / name).read_bytes())
        dst = game_exe.parent / name
        if not dst.exists() or dst.read_bytes() != data:
            tmp = dst.with_name(f".{name}.gw2mac")
            tmp.write_bytes(data)
            os.replace(tmp, dst)
        placed.append(str(dst))
    GAME_DLLS_STATE.write_text(json.dumps(placed))


def remove_game_dlls() -> None:
    if GAME_DLLS_STATE.exists():
        for f in json.loads(GAME_DLLS_STATE.read_text()):
            Path(f).unlink(missing_ok=True)
        GAME_DLLS_STATE.unlink()


# --------------------------------------------------------------------------- #
# Turning DXMT on
# --------------------------------------------------------------------------- #
def enable(game_exe: "Path | None", prefix_ready: bool) -> None:
    """Set up DXMT as described in the module docstring."""
    if not is_prepared():
        prepare()
    wine = Wine()
    remove_game_dlls()
    restore_runtime(wine)
    with tempfile.TemporaryDirectory() as tmp:
        for pattern in RUNTIME_FILES:
            for f in DXMT_DIR.rglob(pattern):
                dst = Path(tmp) / f.relative_to(DXMT_DIR)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
        _apply_overlay(wine, Path(tmp))
    if prefix_ready:
        wine.run("wineboot", "-u")               # refresh system DLLs in the prefix
        for name in GAME_DLLS:
            wine.reg_add(GAME_OVERRIDES_KEY, name[:-4], "native,builtin")
        wine.reg_delete(LEGACY_CEF_KEY)
        wine.wait()
    sync_game_dlls(game_exe)
    MODE_FILE.write_text(MODE)
    say("DXMT enabled")


def ensure_ready(game_exe: "Path | None") -> None:
    """Before launching: (re)apply the setup if needed and restore the game DLLs."""
    if not is_prepared():
        prepare()
        enable(game_exe, prefix_ready=True)
    elif not MODE_FILE.exists() or MODE_FILE.read_text().strip() != MODE:
        enable(game_exe, prefix_ready=True)
    else:
        sync_game_dlls(game_exe)
