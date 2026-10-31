"""GW2Mac version string.

In the packaged app the version comes from the bundle's ``Info.plist``, which
``build.sh`` fills in. When running from source it is ``dev`` unless the
``GW2MAC_VERSION`` environment variable says otherwise.
"""
import os
import plistlib
from pathlib import Path


def _read_version() -> str:
    resources = os.environ.get("RESOURCEPATH")  # set by py2app inside the .app
    if resources:
        try:
            with open(Path(resources).parent / "Info.plist", "rb") as f:
                return plistlib.load(f).get("CFBundleShortVersionString", "dev")
        except (OSError, plistlib.InvalidFileException):
            pass
    return os.environ.get("GW2MAC_VERSION", "dev")


__version__ = _read_version()
