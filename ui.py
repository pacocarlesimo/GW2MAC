"""Terminal output and native macOS dialogs.

Long operations print progress to the terminal. When GW2Mac is opened from
Finder there is no terminal, so choices and errors are shown with AppleScript
dialogs instead.
"""
import json
import subprocess
import sys

#: True when stdout is a terminal (colours and progress bars are enabled).
TTY = sys.stdout.isatty()


class GW2MacError(Exception):
    """An expected failure with a message meant for the user."""


def _colour(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if TTY else text


def say(msg: str) -> None:
    print(f"{_colour('32', '==>')} {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"{_colour('33', '[!]')} {msg}", file=sys.stderr, flush=True)


def error(msg: str) -> None:
    print(f"{_colour('31', '[x]')} {msg}", file=sys.stderr, flush=True)


def die(msg: str) -> "None":
    """Stop the current operation with a message for the user."""
    raise GW2MacError(msg)


def progress(done: int, total: int) -> None:
    """Draw a one-line download progress bar (terminal only)."""
    if not TTY or not total:
        return
    pct = done * 100 // total
    bar = "#" * (pct // 3)
    end = "\n" if done >= total else ""
    print(f"\r   [{bar:<33}] {pct:3d}%  {done >> 20}/{total >> 20} MB", end=end, flush=True)


def osascript(script: str) -> str:
    """Run an AppleScript and return its output."""
    r = subprocess.run(["/usr/bin/osascript", "-"], input=script, text=True,
                       capture_output=True)
    return r.stdout.strip()


def alert(msg: str) -> None:
    """Show a dialog with an OK button."""
    osascript(f'display alert "GW2Mac" message {json.dumps(msg)}')


def choose(title: str, prompt: str, items: list, default: str) -> str:
    """Let the user pick one item from a list. Returns "" if cancelled."""
    options = ", ".join(json.dumps(i) for i in items)
    return osascript(
        f"set r to choose from list {{{options}}} with title {json.dumps(title)} "
        f"with prompt {json.dumps(prompt)} default items {{{json.dumps(default)}}}\n"
        'if r is false then return ""\n'
        "return item 1 of r")


def open_in_terminal(command: list) -> None:
    """Run a command in a new Terminal window, so its progress is visible."""
    line = " ".join("'" + part.replace("'", "'\\''") + "'" for part in command)
    osascript(f'tell application "Terminal" to do script {json.dumps(line)}\n'
              'tell application "Terminal" to activate')
