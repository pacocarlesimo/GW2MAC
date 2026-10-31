"""The Wine runtime: a CrossOver-based engine inside the Sikarugir template.

Why this combination:

* DXMT (DirectX 11 on Metal) needs Mac-driver functions that stock Wine builds keep
  private. CrossOver-based engines export them.
* Sikarugir engines are not self-contained: their support libraries (FreeType,
  GnuTLS, MoltenVK...) and a DXMT build matching the engine ship in the Sikarugir
  template. The engine goes in ``Template.app/Contents/SharedSupport/wine``.

Engines: https://github.com/Sikarugir-App/Engines
Template: https://github.com/Sikarugir-App/Template
"""
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import dxmt
from net import download, extract, github_assets, unquarantine
from paths import BACKUP_DIR, DATA_DIR, DOWNLOADS_DIR, HOME, RUNTIME_DIR
from ui import die, say, warn
from wine import TEMPLATE_APP, Wine, fix_library_links

ENGINES_REPO = "Sikarugir-App/Engines"
TEMPLATE_REPOS = ("Sikarugir-App/Template", "Sikarugir-App/Wrapper")

#: Engine tested with Guild Wars 2. Used unless ``update --latest`` is requested.
PREFERRED_ENGINE = "WS12WineCX24.0.7_7"

ENGINE_PATTERN = r"^WS12WineCX[\d._]+\.tar\.(xz|gz)$"
TEMPLATE_PATTERN = r"^Template-[\d.]+\.tar\.(xz|gz)$"

VERSION_FILE = DATA_DIR / "runtime.version"
#: Written by every version so far; kept for compatibility.
KIND_FILE = DATA_DIR / "runtime.kind"


def _numbers(name: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", name))


def is_installed() -> bool:
    """True when a complete runtime (template + engine) is present."""
    template_ok = (RUNTIME_DIR / TEMPLATE_APP / "Contents/SharedSupport/wine").is_dir()
    return template_ok and Wine.installed()


def installed_version() -> str:
    return VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "not installed"


def preflight() -> None:
    """Check that this Mac can run GW2Mac; install Rosetta 2 if needed."""
    if platform.system() != "Darwin":
        die("GW2Mac only runs on macOS.")
    version = platform.mac_ver()[0]
    cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                         capture_output=True, text=True).stdout.strip()
    say(f"macOS {version} on {platform.machine()} ({cpu or 'unknown CPU'})")
    if int(version.split(".")[0] or 0) < 13:
        die("macOS 13 Ventura or later is required (DXMT needs Metal 3).")
    if platform.machine() == "arm64":
        has_rosetta = subprocess.run(["/usr/bin/arch", "-x86_64", "/usr/bin/true"],
                                     capture_output=True).returncode == 0
        if not has_rosetta:
            say("Installing Rosetta 2 (required by Wine)...")
            if subprocess.run(["/usr/sbin/softwareupdate", "--install-rosetta",
                               "--agree-to-license"]).returncode != 0:
                die("Rosetta 2 could not be installed.")
    free_gb = shutil.disk_usage(HOME).free // (1 << 30)
    if free_gb < 80:
        warn(f"Only {free_gb} GB free: Guild Wars 2 needs about 80 GB.")


def _engine(latest: bool) -> tuple:
    assets = [a for a in github_assets(ENGINES_REPO, ENGINE_PATTERN) if "32Bit" not in a[0]]
    if not assets:
        die(f"No CrossOver engine found at github.com/{ENGINES_REPO}")
    if not latest:
        for name, url in assets:
            if name.startswith(PREFERRED_ENGINE + "."):
                return name, url
        warn(f"{PREFERRED_ENGINE} is no longer available, using the newest engine.")
    return max(assets, key=lambda a: _numbers(a[0]))


def _template() -> tuple:
    for repo in TEMPLATE_REPOS:
        assets = github_assets(repo, TEMPLATE_PATTERN)
        if assets:
            return max(assets, key=lambda a: _numbers(a[0]))
    die("Sikarugir template not found on GitHub.")


def install(latest: bool = False) -> None:
    """Download and install the template and the engine, replacing any old runtime.

    The prefix and the game are not touched.
    """
    say("Installing the Wine runtime (CrossOver engine by Sikarugir)")
    engine_name, engine_url = _engine(latest)
    template_name, template_url = _template()
    engine = download(engine_url, DOWNLOADS_DIR / engine_name)
    template = download(template_url, DOWNLOADS_DIR / template_name)

    if Wine.installed():
        Wine().kill()
    shutil.rmtree(RUNTIME_DIR, ignore_errors=True)
    shutil.rmtree(BACKUP_DIR, ignore_errors=True)   # backups belong to the old runtime
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dxmt.forget_runtime()

    with tempfile.TemporaryDirectory(dir=DATA_DIR) as tmp:
        extract(template, Path(tmp))
        apps = sorted((p for p in Path(tmp).rglob("*.app") if (p / "Contents").is_dir()),
                      key=lambda p: len(p.parts))
        if not apps:
            die(f"Unrecognised template archive: {template.name}")
        RUNTIME_DIR.mkdir(parents=True)
        shutil.move(str(apps[0]), str(RUNTIME_DIR / TEMPLATE_APP))
    wine_dir = RUNTIME_DIR / TEMPLATE_APP / "Contents/SharedSupport/wine"
    wine_dir.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(wine_dir / "wswine.bundle", ignore_errors=True)
    extract(engine, wine_dir)
    unquarantine(RUNTIME_DIR)

    if not Wine.installed():
        die(f"Unrecognised engine archive: {engine.name}")
    fix_library_links(Wine())
    VERSION_FILE.write_text(f"{Path(engine_name).name.split('.tar')[0]} "
                            f"+ {template_name.split('.tar')[0]}")
    KIND_FILE.write_text("cx")
    say(f"Wine ready: {Wine().version()}")


def clear_download_cache() -> None:
    """Forget downloaded engines and templates so the next install fetches them again."""
    for f in [*DOWNLOADS_DIR.glob("WS*Wine*.tar.*"), *DOWNLOADS_DIR.glob("Template-*.tar.*")]:
        f.unlink()
