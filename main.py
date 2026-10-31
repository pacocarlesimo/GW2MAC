"""GW2Mac entry point.

Run Guild Wars 2 on macOS with a CrossOver-based Wine engine and DXMT
(DirectX 11 on Metal).

* Opened from Finder (GW2Mac.app): shows a menu.
* From a terminal without arguments: sets up whatever is missing, then plays.
* From a terminal with a command: see ``gw2mac --help``.
"""
import argparse
import shutil
import sys

import diagnostics
import dxmt
import game
import prefix
import runtime
import shortcut
import wine
from config import Config
from paths import DATA_DIR, LEGACY_TOOLS_APP, SHORTCUT_APP, ensure_dirs
from ui import TTY, GW2MacError, alert, error, say
from version import __version__


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def is_ready() -> bool:
    return runtime.is_installed() and game.find_exe() is not None


def setup() -> None:
    """Install everything that is missing: runtime, prefix, DXMT, game, shortcut."""
    runtime.preflight()
    if not runtime.is_installed():
        runtime.install()
    prefix.create()
    if not game.find_exe():
        if game.find_other_install():
            game.import_from()
        else:
            game.install()
    dxmt.enable(game.find_exe(), prefix_ready=True)
    shortcut.create()
    status()
    if game.find_exe():
        say("Setup complete. Start Guild Wars 2 from Launchpad or with: gw2mac play")


def auto() -> None:
    """No command given: finish setup if needed, then play."""
    if not is_ready():
        say("First run: setting everything up")
        setup()
        if not game.find_exe():
            return          # installer closed early: running again resumes
    game.play()


def update(latest: bool) -> None:
    """Reinstall the Wine runtime and DXMT; the game and its settings are kept."""
    runtime.preflight()
    runtime.clear_download_cache()
    runtime.install(latest=latest)
    if prefix.exists():
        dxmt.enable(game.find_exe(), prefix_ready=True)
    shortcut.create()
    say("Update complete")


def set_option(name: str, value: bool) -> None:
    cfg = Config.load()
    setattr(cfg, name, value)
    cfg.save()
    if name == "retina" and prefix.exists():
        prefix.tune()
    say(f"{name}: {'on' if value else 'off'}")


def toggle(name: str) -> None:
    set_option(name, not getattr(Config.load(), name))


def status() -> None:
    cfg = Config.load()
    print(f"GW2Mac {__version__}")
    print(f"  Runtime:   {runtime.installed_version()}")
    print(f"  DXMT:      {dxmt.installed_version()}")
    print(f"  Retina:    {'on' if cfg.retina else 'off'}    HUD: {'on' if cfg.hud else 'off'}")
    print(f"  Arguments: {' '.join(cfg.game_args) or '-'}")
    print(f"  Data:      {DATA_DIR}")
    print(f"  Game:      {game.find_exe() or 'not installed'}")


def uninstall() -> None:
    if not TTY:
        error("Run this from a terminal: gw2mac uninstall")
        return
    answer = input(f"Remove GW2Mac, its Wine runtime and THE GAME ({DATA_DIR})? Type YES: ")
    if answer.strip() != "YES":
        print("Cancelled.")
        return
    if wine.Wine.installed():
        wine.Wine().kill()
    for path in (SHORTCUT_APP, LEGACY_TOOLS_APP, DATA_DIR):
        shutil.rmtree(path, ignore_errors=True)
    say("GW2Mac removed. You can now delete GW2Mac.app from Applications.")


def play_from_menu() -> None:
    try:
        game.play()
    except GW2MacError as e:
        alert(str(e))


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #
def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gw2mac", description=f"GW2Mac {__version__}: Guild Wars 2 on macOS.",
        epilog="Without a command: set up whatever is missing, then play.")
    p.add_argument("--version", action="version", version=f"GW2Mac {__version__}")
    sub = p.add_subparsers(dest="command", metavar="command")
    sub.add_parser("setup", help="install the runtime, the game and the Launchpad shortcut")
    sub.add_parser("play", help="start Guild Wars 2")
    sub.add_parser("debug", help="start the game with detailed logs and write a report")
    sub.add_parser("install", help="run ArenaNet's installer")
    c = sub.add_parser("import", help="import an existing installation (Whisky, CrossOver, folder)")
    c.add_argument("path", nargs="?", help="Guild Wars 2 folder (found automatically if omitted)")
    sub.add_parser("repair", help="verify game files and re-apply GW2Mac's settings")
    c = sub.add_parser("screen", help="screen mode: windowed | borderless | fullscreen")
    c.add_argument("mode", choices=tuple(game.SCREEN_MODES))
    for name, text in (("retina", "render at native Retina resolution (slower)"),
                       ("hud", "show Apple's Metal performance HUD")):
        c = sub.add_parser(name, help=text)
        c.add_argument("state", choices=("on", "off"))
    c = sub.add_parser("args", help="extra arguments for Gw2-64.exe, e.g. args -- -maploadinfo")
    c.add_argument("extra", nargs=argparse.REMAINDER)
    c = sub.add_parser("update", help="reinstall the Wine runtime (game and settings are kept)")
    c.add_argument("--latest", action="store_true",
                   help="use the newest engine instead of the tested one")
    sub.add_parser("doctor", help="check the Wine runtime and DXMT")
    sub.add_parser("status", help="show versions and settings")
    sub.add_parser("shortcut", help="recreate the Guild Wars 2 app in ~/Applications")
    sub.add_parser("menu", help="show the GW2Mac menu")
    sub.add_parser("uninstall", help="remove GW2Mac, the runtime and the game")
    return p


def run(args: argparse.Namespace) -> None:
    command = args.command
    if command is None:
        if TTY:
            auto()
        else:   # opened from Finder
            shortcut.menu(is_ready(), play_from_menu, toggle, game.set_screen_mode)
    elif command == "setup":
        setup()
    elif command == "play":
        game.play()
    elif command == "debug":
        wine.debug = True
        game.play()
    elif command == "install":
        game.install()
        dxmt.enable(game.find_exe(), prefix_ready=True)
        shortcut.create()
    elif command == "import":
        game.import_from(args.path)
        dxmt.enable(game.find_exe(), prefix_ready=True)
        shortcut.create()
    elif command == "repair":
        game.repair()
    elif command == "screen":
        game.set_screen_mode(args.mode)
    elif command in ("retina", "hud"):
        set_option(command, args.state == "on")
    elif command == "args":
        cfg = Config.load()
        cfg.game_args = [a for a in args.extra if a != "--"]
        cfg.save()
        say(f"Game arguments: {' '.join(cfg.game_args) or 'none'}")
    elif command == "update":
        update(args.latest)
    elif command == "doctor":
        diagnostics.doctor()
    elif command == "status":
        status()
    elif command == "shortcut":
        shortcut.create()
    elif command == "menu":
        shortcut.menu(is_ready(), play_from_menu, toggle, game.set_screen_mode)
    elif command == "uninstall":
        uninstall()


def main(argv: "list | None" = None) -> int:
    ensure_dirs()
    args = parser().parse_args(argv)
    try:
        run(args)
    except GW2MacError as e:
        error(str(e))
        if not TTY:
            alert(str(e))
        return 1
    except KeyboardInterrupt:
        print()
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
