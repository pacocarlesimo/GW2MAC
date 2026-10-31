# GW2Mac

Play **Guild Wars 2 on macOS** again, now that the native Mac client is gone and Whisky
is no longer maintained.

GW2Mac sets up a CrossOver-based Wine engine with **DXMT** (DirectX 11 on Metal),
installs or imports the game, and gives you a **Guild Wars 2** app in Launchpad.
Free and open source.

## Features

- One-step setup: Wine runtime, Windows prefix, game and Launchpad shortcut
- DirectX 11 translated straight to Metal with DXMT
- Working launcher: login, news and patching
- Imports an existing installation from Whisky or CrossOver without downloading 70 GB again
  (an instant copy on APFS that takes no extra space)
- Multi-monitor friendly: your other displays stay usable, windowed and borderless modes work
- Screen mode, Retina resolution and Apple's performance HUD from the menu
- Built-in diagnostics: `doctor` checks the installation, `debug` writes a crash report

## Install

1. Download the latest **GW2Mac-x.y.z.dmg** from
   [Releases](https://github.com/pacocarlesimo/gw2mac/releases/latest).
2. Open it and drag **GW2Mac** into **Applications**.
3. Open GW2Mac from Applications. macOS will say it can't verify the developer:
   click **Done**, then open **System Settings → Privacy & Security**, scroll down
   and click **Open Anyway** next to GW2Mac. You only need to do this once.
4. Choose **Install or finish setup**. A Terminal window shows the progress:
    - Rosetta 2 is installed if needed, then the Wine runtime is downloaded (a few hundred MB).
    - If Guild Wars 2 is already installed in **Whisky** or **CrossOver**, it is imported.
    - Otherwise ArenaNet's installer opens. Keep the default folder
      (`C:\Program Files\Guild Wars 2`), wait for the download to finish, then close it.
5. Start **Guild Wars 2** from Launchpad or Spotlight.

## Usage

| Action | How |
|---|---|
| Play | **Guild Wars 2** in Launchpad, or GW2Mac → **Play** |
| Change screen mode | GW2Mac → **Screen: …** (with the game closed) |
| Sharper image | GW2Mac → **Retina resolution** (much heavier on the GPU) |
| Show fps and frame time | GW2Mac → **Performance HUD** |
| Fix a broken install | GW2Mac → **Repair** |
| Check the installation | GW2Mac → **Check installation** |

**With more than one display**, use **borderless window** (*Windowed Fullscreen* in
GW2's options): the game fills the main display and you can move the mouse or Cmd+Tab
to the others without the game minimising.

### Terminal

Every action is also a command. Add an alias to `~/.zshrc`:

    alias gw2mac="/Applications/GW2Mac.app/Contents/MacOS/GW2Mac"

| Command | What it does |
|---|---|
| `gw2mac` | Set up whatever is missing, then play |
| `gw2mac play` | Start the game |
| `gw2mac screen borderless` | Screen mode: `windowed`, `borderless`, `fullscreen` |
| `gw2mac import "/path/to/Guild Wars 2"` | Import an installation from any folder |
| `gw2mac args -- -maploadinfo` | Extra arguments for the game |
| `gw2mac repair` | Verify game files and re-apply GW2Mac's settings |
| `gw2mac doctor` | Check the Wine runtime and DXMT |
| `gw2mac debug` | Start with detailed logs and write a crash report |
| `gw2mac update` | Reinstall the Wine runtime (game and settings are kept) |

Run `gw2mac --help` for the full list.

## Troubleshooting

If the game doesn't start, run `gw2mac debug`, reproduce the problem, then open an
[issue](https://github.com/pacocarlesimo/gw2mac/issues) and attach
`~/Library/Application Support/GW2Mac/logs/crash-report.txt`.
After every session GW2Mac also prints which renderer the game used: it should say
**DXMT (Metal)**.

## Updating

Download the new .dmg and replace the app in Applications, then choose GW2Mac → **Update
Wine** if the release notes say so. If you moved GW2Mac.app, run `gw2mac shortcut` to
repair the Launchpad shortcut.

## Uninstall

Run `gw2mac uninstall`, or delete these by hand:

- GW2Mac from Applications
- **Guild Wars 2** from `~/Applications`
- the folder `~/Library/Application Support/GW2Mac` (this contains the game, about 80 GB)

## Requirements

- macOS 13 Ventura or later (DXMT needs Metal 3)
- Apple Silicon. Intel Macs are untested.
- About 80 GB of free space

## How it works

GW2Mac uses a CrossOver-based Wine engine and its support libraries from
[Sikarugir](https://github.com/Sikarugir-App), and the DXMT build that ships with them.
Guild Wars 2 gets DXMT's Direct3D 11, while the launcher's embedded browser keeps Wine's
own Direct3D, because DXMT can't draw into windows owned by another process yet. The
details are documented at the top of [`dxmt.py`](dxmt.py).

## Building from source

GW2Mac uses only the Python standard library (Python 3.9 or later).

    python3 main.py --help            # run from source
    bash build.sh 1.0.0               # build dist/GW2Mac-1.0.0.dmg

Pushing a tag such as `v1.0.0` builds the .dmg and publishes a release.

## Credits

- [Wine](https://www.winehq.org) and [CodeWeavers](https://www.codeweavers.com), whose
  CrossOver sources the engine is built from. If you want a supported product,
  buy CrossOver: it funds Wine development.
- [Sikarugir](https://github.com/Sikarugir-App) and [Gcenx](https://github.com/Gcenx)
  for the macOS engines and template
- [DXMT](https://github.com/3Shain/dxmt) by 3Shain

## Disclaimer

GW2Mac is a fan project, not affiliated with or endorsed by ArenaNet or NCSoft, and running
Guild Wars 2 through Wine is not supported by ArenaNet. Guild Wars 2 is a trademark of
NCSoft Corporation. GW2Mac downloads the game only from ArenaNet's official installer.
