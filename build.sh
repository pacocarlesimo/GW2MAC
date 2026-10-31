#!/bin/bash
# Build GW2Mac.app and a drag-to-install .dmg.
# Usage: bash build.sh [version]     e.g. bash build.sh 1.0.0
set -euo pipefail
cd "$(dirname "$0")"

VERSION="${1:-0.0.0}"
export GW2MAC_VERSION="$VERSION"

echo "==> Building GW2Mac $VERSION"
rm -rf build dist .build-venv

# Isolated build environment (GW2Mac itself has no dependencies)
python3 -m venv .build-venv
source .build-venv/bin/activate
pip install --upgrade pip
pip install py2app

python setup.py py2app

# Ad-hoc signature: required to run on Apple Silicon, no Apple account needed
codesign --force --deep --sign - dist/GW2Mac.app

# Disk image with a shortcut to /Applications
mkdir -p dist/dmg
cp -R dist/GW2Mac.app dist/dmg/
ln -s /Applications dist/dmg/Applications
hdiutil create -volname "GW2Mac" -srcfolder dist/dmg -ov -format UDZO "dist/GW2Mac-${VERSION}.dmg"
rm -rf dist/dmg

echo "==> Done: dist/GW2Mac-${VERSION}.dmg"
