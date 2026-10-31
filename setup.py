"""py2app build configuration.

Builds a standalone GW2Mac.app that bundles Python. GW2Mac uses only the
standard library, so nothing else needs to be installed.
Usage: ``python setup.py py2app`` (normally called by build.sh).
"""
import os

from setuptools import setup

#: Version string, injected by build.sh / the release workflow.
VERSION = os.environ.get("GW2MAC_VERSION", "0.0.0")

OPTIONS = {
    "argv_emulation": False,
    "includes": [
        "config", "diagnostics", "dxmt", "game", "net", "paths",
        "prefix", "runtime", "shortcut", "ui", "version", "wine",
    ],
    "plist": {
        "CFBundleName": "GW2Mac",
        "CFBundleDisplayName": "GW2Mac",
        "CFBundleIdentifier": "io.github.gw2mac",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSUIElement": True,                 # no Dock icon: GW2Mac only shows dialogs
        "LSMinimumSystemVersion": "13.0",
        "LSApplicationCategoryType": "public.app-category.utilities",
        "NSHumanReadableCopyright": "MIT License",
    },
}

setup(
    name="GW2Mac",
    version=VERSION,
    app=["main.py"],
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
