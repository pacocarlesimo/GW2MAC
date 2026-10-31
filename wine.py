"""Running Wine.

Finds the Wine binaries inside the runtime, builds the environment they need and
repairs missing library links.

Two macOS details shape this module:

* Wine opens FreeType (fonts), GnuTLS (HTTPS) and MoltenVK with ``dlopen()``.
  In the Sikarugir runtime those libraries live in the template, so their folders
  go into ``DYLD_FALLBACK_LIBRARY_PATH``. Without them the game launcher shows no
  text and cannot log in.
* macOS strips every ``DYLD_*`` variable when it runs a protected system binary.
  Wine must therefore never be started through ``/usr/bin/caffeinate`` or similar.
"""
import os
import re
import subprocess
from pathlib import Path

from config import Config
from paths import LOGS_DIR, PREFIX_DIR, RUNTIME_DIR
from ui import die, say

#: Set by ``gw2mac debug``: verbose Wine and DXMT logs.
debug = False

#: Name of the Sikarugir template app inside the runtime folder.
TEMPLATE_APP = "Template.app"

DYLD_MISSING = re.compile(r"Library not loaded: @rpath/(\S+)")
DYLD_TRIED = re.compile(r"tried: '([^']+)'")


class Wine:
    """The Wine installation inside the runtime folder."""

    def __init__(self) -> None:
        self.bin = self.find()
        if not self.bin:
            die("Wine is not installed. Run: gw2mac setup")
        self.root = self.bin.parent.parent          # contains bin/ and lib/
        self.lib = self.root / "lib"
        self.server = self.bin.parent / "wineserver"

    @staticmethod
    def find() -> "Path | None":
        """Path of the 64-bit Wine loader, or None if the runtime is missing."""
        if not RUNTIME_DIR.exists():
            return None
        candidates = [p for p in RUNTIME_DIR.rglob("bin/wine*")
                      if p.name in ("wine", "wine64") and p.is_file() and os.access(p, os.X_OK)]
        # CrossOver engines ship wine64 as the 64-bit loader; WoW64 builds only "wine".
        candidates.sort(key=lambda p: ("wswine.bundle" not in p.parts, p.name != "wine64",
                                       len(p.parts)))
        return candidates[0] if candidates else None

    @staticmethod
    def installed() -> bool:
        return Wine.find() is not None

    def lib_dirs(self) -> list:
        """Folders where Wine's runtime-loaded libraries can be found."""
        dirs = []
        contents = RUNTIME_DIR / TEMPLATE_APP / "Contents"
        if contents.is_dir():
            dirs += [contents / "Frameworks", contents / "SharedSupport/wine",
                     contents / "Resources"]
        dirs += [self.lib, self.lib / "external", self.root.parent]
        unique = []
        for d in dirs:
            if d not in unique:
                unique.append(d)
        return unique

    def env(self, trace_dlls: bool = False) -> dict:
        """Environment for running Wine with the GW2Mac prefix."""
        cfg = Config.load()
        e = dict(os.environ)
        e.update({
            "WINEPREFIX": str(PREFIX_DIR),
            "WINEDEBUG": "-all",
            "WINEESYNC": "1",
            "WINEMSYNC": "1",
            "WINEDLLOVERRIDES": "winemenubuilder.exe=d;mscoree=;mshtml=",
            "DXMT_LOG_LEVEL": "none",
            "MVK_CONFIG_LOG_LEVEL": "0",
            "PATH": f"{self.bin.parent}:{e.get('PATH', '')}",
        })
        libs = [str(p) for p in self.lib_dirs() if p.is_dir()]
        if libs:
            e["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(libs + ["/usr/lib", "/usr/local/lib"])
            e["DYLD_FALLBACK_FRAMEWORK_PATH"] = ":".join(
                libs + ["/Library/Frameworks", "/System/Library/Frameworks"])
        if trace_dlls:
            # Only DLL loads: cheap, and enough to tell which renderer the game used.
            e["WINEDEBUG"] = "-all,+loaddll"
        if debug:
            e["WINEDEBUG"] = "err+all,+seh,+loaddll,+process,fixme-all"
            e["DXMT_LOG_LEVEL"] = "info"
            e["DXMT_LOG_PATH"] = str(LOGS_DIR)
        if cfg.hud:
            e["MTL_HUD_ENABLED"] = "1"
        else:
            e.pop("MTL_HUD_ENABLED", None)
        return e

    def run(self, *args: str, cwd: "Path | None" = None, log: "Path | None" = None) -> int:
        """Run a Windows program and wait for it to exit."""
        out = open(log, "w") if log else subprocess.DEVNULL
        try:
            return subprocess.run([str(self.bin), *args], env=self.env(), cwd=cwd,
                                  stdout=out, stderr=subprocess.STDOUT).returncode
        finally:
            if log:
                out.close()

    def wait(self) -> None:
        """Wait until every Wine process of the prefix has exited."""
        subprocess.run([str(self.server), "-w"], env=self.env(), capture_output=True)

    def kill(self) -> None:
        """Stop every Wine process of the prefix."""
        subprocess.run([str(self.server), "-k"], env=self.env(), capture_output=True)

    def reg_add(self, key: str, name: str, value: str, kind: str = "REG_SZ") -> None:
        self.run("reg", "add", key, "/v", name, "/t", kind, "/d", value, "/f")

    def reg_delete(self, key: str) -> None:
        self.run("reg", "delete", key, "/f")

    def version(self) -> str:
        r = subprocess.run([str(self.bin), "--version"], env=self.env(),
                           capture_output=True, text=True)
        return r.stdout.strip() or "?"


def fix_library_links(wine: Wine, rounds: int = 25) -> None:
    """Start wine and wineserver; whenever macOS can't find a linked library, look
    for it in the runtime and link it where the binary expects it."""
    linked = []
    errors = ""
    for _ in range(rounds):
        errors = ""
        for cmd in ([str(wine.bin), "--version"], [str(wine.server), "-k"]):
            r = subprocess.run(cmd, env=wine.env(), capture_output=True, text=True, timeout=60)
            errors += r.stderr
        missing = DYLD_MISSING.search(errors)
        if not missing:
            if linked:
                say(f"Linked libraries: {', '.join(linked)}")
            return
        rel = missing.group(1)
        tried = DYLD_TRIED.search(errors[missing.end():])
        if not tried:
            break
        dest = Path(tried.group(1))                 # where dyld looked first
        found = next((p for p in RUNTIME_DIR.rglob(Path(rel).name)
                      if p.as_posix().endswith(rel) and p.resolve() != dest.resolve()), None)
        if not found or dest.exists():
            break
        dest.parent.mkdir(parents=True, exist_ok=True)
        if ".framework/" in rel:                    # link the whole framework
            src_fw = Path(str(found).split(".framework/")[0] + ".framework")
            dst_fw = Path(str(dest).split(".framework/")[0] + ".framework")
            if dst_fw.exists():
                break
            os.symlink(os.path.relpath(src_fw, dst_fw.parent), dst_fw)
            linked.append(dst_fw.name)
        else:
            os.symlink(os.path.relpath(found, dest.parent), dest)
            linked.append(dest.name)
    details = [line for line in errors.splitlines()
               if "dyld" in line or "Library" in line or "tried" in line]
    die("Wine can't load one of its libraries:\n" + "\n".join(details))
