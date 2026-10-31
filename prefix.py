"""The Windows prefix ("bottle") that holds drive C: and the game."""
from config import Config
from paths import DATA_DIR, PREFIX_DIR
from ui import say
from wine import Wine

MAC_DRIVER = r"HKCU\Software\Wine\Mac Driver"

TUNE_FILE = DATA_DIR / "prefix.tune"
#: Bump when the settings below change, so existing prefixes get them once.
TUNE_VERSION = "2"


def exists() -> bool:
    return (PREFIX_DIR / "drive_c").is_dir()


def create() -> None:
    if exists():
        return
    say("Creating the Windows prefix")
    wine = Wine()
    wine.run("wineboot", "--init")
    wine.wait()
    tune()


def tune() -> None:
    """Apply GW2Mac's prefix settings."""
    wine, cfg = Wine(), Config.load()
    say("Applying prefix settings")
    wine.reg_add(r"HKCU\Software\Wine", "Version", "win10")
    wine.reg_add(MAC_DRIVER, "RetinaMode", "y" if cfg.retina else "n")
    # Don't capture every display in full screen: a second monitor would go black
    # and windowed modes would misbehave.
    wine.reg_add(MAC_DRIVER, "CaptureDisplaysForFullscreen", "n")
    # Option works as Alt, like on a Windows keyboard.
    wine.reg_add(MAC_DRIVER, "LeftOptionIsAlt", "y")
    wine.reg_add(MAC_DRIVER, "RightOptionIsAlt", "y")
    # No crash dialogs on top of a full-screen game.
    wine.reg_add(r"HKCU\Software\Wine\WineDbg", "ShowCrashDialog", "0", "REG_DWORD")
    wine.wait()
    TUNE_FILE.write_text(TUNE_VERSION)


def ensure_tuned() -> None:
    if not TUNE_FILE.exists() or TUNE_FILE.read_text().strip() != TUNE_VERSION:
        tune()
