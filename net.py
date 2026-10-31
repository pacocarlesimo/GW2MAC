"""Downloads: GitHub release lookup, file download with retries, extraction.

Only the Python standard library is used, so GW2Mac has no dependencies.
"""
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

from ui import die, progress, say, warn
from version import __version__

HEADERS = {"User-Agent": f"GW2Mac/{__version__}"}


def github_assets(repo: str, pattern: str) -> list:
    """All release assets of ``repo`` whose name matches ``pattern``.

    Returns ``(name, download_url)`` pairs, newest release first.
    """
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases?per_page=30",
        headers={**HEADERS, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            releases = json.load(r)
    except Exception as e:  # noqa: BLE001 - any network error is reported the same way
        die(f"Could not reach GitHub ({repo}): {e}")
    rx = re.compile(pattern)
    return [(a["name"], a["browser_download_url"])
            for rel in releases if not rel.get("draft")
            for a in rel.get("assets", []) if rx.search(a["name"])]


def download(url: str, dest: Path, attempts: int = 3) -> Path:
    """Download ``url`` to ``dest`` unless it is already there."""
    if dest.exists():
        return dest
    say(f"Downloading {dest.name}")
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done, last = 0, 0.0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if time.time() - last > 0.2:
                        last = time.time()
                        progress(done, total)
                progress(total, total)
            part.rename(dest)
            return dest
        except Exception as e:  # noqa: BLE001
            warn(f"Download failed ({e}), attempt {attempt}/{attempts}")
            time.sleep(2)
    die(f"Download failed: {url}")


def extract(archive: Path, into: Path) -> None:
    """Extract with the system tar, which keeps permissions, symlinks and .app bundles."""
    into.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/usr/bin/tar", "-xf", str(archive), "-C", str(into)], check=True)


def unquarantine(path: Path) -> None:
    """Remove the download quarantine flag so macOS lets the files run."""
    subprocess.run(["/usr/bin/xattr", "-dr", "com.apple.quarantine", str(path)],
                   capture_output=True)
