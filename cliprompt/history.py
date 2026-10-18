"""Read and parse shell history files (bash, zsh, fish, PowerShell)."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

SHELLS = ("bash", "zsh", "fish", "powershell")

# Only the tail of a huge history file matters; read at most this many bytes from the end.
MAX_BYTES = 4 * 1024 * 1024

_BASH_STAMP = re.compile(r"^#(\d{9,11})$")
_ZSH_EXTENDED = re.compile(r"^: (\d+):\d+;(.*)$")
_FISH_CMD = re.compile(r"^- cmd: (.*)$")
_FISH_WHEN = re.compile(r"^\s+when: (\d+)$")


class HistoryError(Exception):
    """The history file could not be located or read."""


@dataclass(frozen=True)
class HistoryEntry:
    """One command from history, oldest first. ``timestamp`` is epoch seconds if recorded."""

    command: str
    timestamp: int | None = None


def read_text_tail(path: Path, max_bytes: int = MAX_BYTES) -> str:
    """Decode the last ``max_bytes`` of ``path``; bad bytes become U+FFFD.

    Raises :class:`HistoryError` if the file is missing, a directory or unreadable.
    """
    try:
        if not path.exists():
            raise HistoryError(f"history file not found: {path}")
        if path.is_dir():
            raise HistoryError(f"history path is a directory: {path}")
        with path.open("rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            truncated = size > max_bytes
            handle.seek(max(0, size - max_bytes))
            raw = handle.read()
    except OSError as exc:
        raise HistoryError(f"cannot read history file {path}: {exc.strerror or exc}") from None
    if truncated:
        # The first line is probably cut in half; drop it.
        newline = raw.find(b"\n")
        raw = raw[newline + 1 :] if newline != -1 else b""
    return raw.decode("utf-8", errors="replace").replace("\x00", "")


def detect_format(path: Path, text: str) -> str:
    """Guess the history format from the file name, falling back to its content."""
    name = path.name.lower()
    if "fish_history" in name:
        return "fish"
    if "zsh" in name:
        return "zsh"
    if "consolehost_history" in name:
        return "powershell"
    if "bash" in name:
        return "bash"
    head = text[:4000]
    if re.search(r"^- cmd: ", head, re.MULTILINE):
        return "fish"
    if re.search(r"^: \d+:\d+;", head, re.MULTILINE):
        return "zsh"
    return "bash"


def _clean(command: str) -> str:
    return command.strip().replace("\x00", "")


def parse_bash(text: str) -> list[HistoryEntry]:
    """Plain lines, optionally preceded by ``#<epoch>`` comment lines (HISTTIMEFORMAT)."""
    entries: list[HistoryEntry] = []
    stamp: int | None = None
    for line in text.splitlines():
        match = _BASH_STAMP.match(line)
        if match:
            stamp = int(match.group(1))
            continue
        command = _clean(line)
        if command:
            entries.append(HistoryEntry(command, stamp))
        stamp = None
    return entries


def parse_zsh(text: str) -> list[HistoryEntry]:
    """Plain or extended (``: epoch:duration;cmd``) lines; ``\\`` continues a command."""
    entries: list[HistoryEntry] = []
    pending: list[str] = []
    stamp: int | None = None
    for line in text.splitlines():
        if pending:
            pending.append(line)
        else:
            match = _ZSH_EXTENDED.match(line)
            stamp = int(match.group(1)) if match else None
            pending = [match.group(2) if match else line]
        if pending[-1].endswith("\\"):
            pending[-1] = pending[-1][:-1]
            continue
        command = _clean("\n".join(pending))
        if command:
            entries.append(HistoryEntry(command, stamp))
        pending = []
        stamp = None
    if pending:
        command = _clean("\n".join(pending))
        if command:
            entries.append(HistoryEntry(command, stamp))
    return entries


def parse_fish(text: str) -> list[HistoryEntry]:
    """Fish's YAML-ish format: ``- cmd: ...`` followed by ``when: ...``."""
    entries: list[HistoryEntry] = []
    command: str | None = None
    stamp: int | None = None

    def flush() -> None:
        if command and _clean(command):
            entries.append(HistoryEntry(_clean(command), stamp))

    for line in text.splitlines():
        cmd_match = _FISH_CMD.match(line)
        if cmd_match:
            flush()
            command, stamp = cmd_match.group(1).replace("\\n", "\n").replace("\\\\", "\\"), None
            continue
        when_match = _FISH_WHEN.match(line)
        if when_match and command is not None:
            stamp = int(when_match.group(1))
    flush()
    return entries


def parse_powershell(text: str) -> list[HistoryEntry]:
    """PSReadLine's ConsoleHost_history.txt: one command per line, backtick continues."""
    entries: list[HistoryEntry] = []
    buffer = ""
    for line in text.splitlines():
        if line.endswith("`"):
            buffer += line[:-1] + "\n"
            continue
        command = _clean(buffer + line)
        buffer = ""
        if command:
            entries.append(HistoryEntry(command))
    if buffer.strip():
        entries.append(HistoryEntry(_clean(buffer)))
    return entries


_PARSERS = {
    "bash": parse_bash,
    "zsh": parse_zsh,
    "fish": parse_fish,
    "powershell": parse_powershell,
}


def parse_history(text: str, shell: str = "bash") -> list[HistoryEntry]:
    """Parse history text in the given format into entries, oldest first."""
    try:
        parser = _PARSERS[shell]
    except KeyError:
        known = ", ".join(SHELLS)
        raise HistoryError(f"unknown shell {shell!r}; expected one of {known}") from None
    return parser(text)


def read_history(path: Path | str, shell: str | None = None) -> list[HistoryEntry]:
    """Read and parse a history file. ``shell`` of ``None`` or ``"auto"`` detects the format."""
    target = Path(path).expanduser()
    text = read_text_tail(target)
    fmt = shell if shell and shell != "auto" else detect_format(target, text)
    return parse_history(text, fmt)


def candidate_files(
    environ: Mapping[str, str] | None = None, home: Path | None = None
) -> list[tuple[str, Path]]:
    """Likely history locations as ``(shell, path)``, most specific first."""
    env = os.environ if environ is None else environ
    base = home if home is not None else Path(env.get("USERPROFILE") or Path.home())
    found: list[tuple[str, Path]] = []
    if env.get("HISTFILE"):
        histfile = Path(env["HISTFILE"]).expanduser()
        found.append((detect_format(histfile, ""), histfile))
    xdg = Path(env.get("XDG_DATA_HOME") or base / ".local" / "share")
    appdata = Path(env["APPDATA"]) if env.get("APPDATA") else base / "AppData" / "Roaming"
    found += [
        ("zsh", base / ".zsh_history"),
        ("bash", base / ".bash_history"),
        ("fish", xdg / "fish" / "fish_history"),
        (
            "powershell",
            appdata
            / "Microsoft"
            / "Windows"
            / "PowerShell"
            / "PSReadLine"
            / "ConsoleHost_history.txt",
        ),
    ]
    return found


def find_history_file(
    shell: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> tuple[str, Path]:
    """Pick the history file to use.

    With ``shell`` set, the first existing candidate for that shell. Otherwise the most
    recently modified existing candidate. Raises :class:`HistoryError` if none exists.
    """
    wanted = None if shell in (None, "auto") else shell
    existing = [
        (name, path)
        for name, path in candidate_files(environ, home)
        if (wanted is None or name == wanted) and path.is_file()
    ]
    if not existing:
        scope = f"{wanted} " if wanted else ""
        raise HistoryError(
            f"no {scope}shell history file found; pass --history-file PATH "
            "(searched $HISTFILE, ~/.zsh_history, ~/.bash_history, fish and PSReadLine locations)"
        )
    if wanted:
        return existing[0]
    return max(existing, key=lambda item: item[1].stat().st_mtime)
