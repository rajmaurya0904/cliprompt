"""Command-line interface for cliprompt."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from .context import get_context
from .engine import Suggestion, prepare, program_of, rank
from .history import SHELLS, HistoryError, find_history_file, read_history
from .skill import format_for_claude

COMMANDS = ("suggest", "stats", "context")
FORMAT_CHOICES = ("auto", "plain", "color", "json", "markdown")
DEFAULT_WINDOW = 5000

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"


class CliError(Exception):
    """A user-facing error; the message is printed and the exit code is 2."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cliprompt",
        description="Suggest shell commands from your history, ranked by the current "
        "directory, git state and what you ran just before.",
    )
    parser.add_argument("--version", action="version", version=f"cliprompt {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="{suggest,stats,context}")

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "-s",
            "--shell",
            choices=("auto", *SHELLS),
            default="auto",
            help="history format; default detects it from the file",
        )
        p.add_argument(
            "-f",
            "--history-file",
            metavar="PATH",
            help="read this file instead of searching for one",
        )
        p.add_argument(
            "--window",
            type=int,
            default=DEFAULT_WINDOW,
            metavar="N",
            help=f"only look at the last N history entries (default {DEFAULT_WINDOW})",
        )
        p.add_argument("--cwd", metavar="DIR", help="directory to use as context (default: .)")
        p.add_argument("--no-git", action="store_true", help="do not run git for context")

    suggest = sub.add_parser("suggest", help="rank history commands (the default)")
    common(suggest)
    suggest.add_argument("prefix", nargs="*", help="what you have typed so far")
    suggest.add_argument(
        "-n", "--limit", type=int, default=5, metavar="N", help="suggestions to show (default 5)"
    )
    suggest.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default="auto",
        help="output style; auto uses colour on a terminal",
    )
    suggest.add_argument("--explain", action="store_true", help="show why each command ranked")
    suggest.add_argument(
        "--last",
        metavar="CMD",
        help="the command you just ran; default is the newest history entry, "
        "pass '' to ignore it",
    )
    suggest.add_argument(
        "--include-secrets",
        action="store_true",
        help="do not filter commands that look like they hold credentials",
    )

    stats = sub.add_parser("stats", help="most used commands and programs in your history")
    common(stats)
    stats.add_argument("-n", "--limit", type=int, default=10, metavar="N")
    stats.add_argument("--json", action="store_true", help="machine-readable output")

    ctx = sub.add_parser("context", help="show what cliprompt sees about the directory")
    common(ctx)
    return parser


def _load_history(args: argparse.Namespace) -> tuple[str, Path, list[str]]:
    if args.window < 1:
        raise CliError("--window must be at least 1")
    if args.history_file:
        path = Path(args.history_file).expanduser()
        shell = None if args.shell == "auto" else args.shell
        entries = read_history(path, shell)
        label = shell or "auto"
    else:
        label, path = find_history_file(args.shell)
        entries = read_history(path, label)
    return label, path, prepare(entries)[-args.window :]


def _paint(text: str, code: str, on: bool) -> str:
    return f"{code}{text}{RESET}" if on else text


def render_plain(items: list[Suggestion], explain: bool, color: bool) -> str:
    """One command per line (pipe friendly); numbered and bold when ``color`` is on."""
    lines = []
    for number, item in enumerate(items, 1):
        if color:
            lines.append(f"{_paint(str(number), DIM, True)}  {_paint(item.command, BOLD, True)}")
        else:
            lines.append(item.command)
        if explain:
            reasons = ", ".join(item.reasons) or "most recent match"
            lines.append(_paint(f"   {reasons}" if color else f"  # {reasons}", DIM, color))
    return "\n".join(lines)


def _wants_color(choice: str) -> bool:
    if choice == "color":
        return True
    if choice != "auto":
        return False
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def run_suggest(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise CliError("--limit must be at least 1")
    _, _, history = _load_history(args)
    typed = args.prefix[0] if len(args.prefix) == 1 else " ".join(args.prefix)
    last = args.last
    if last is None:
        tail = [c for c in history if program_of(c) != "cliprompt"]
        last = tail[-1] if tail else ""
    context = get_context(
        args.cwd, prefix=typed or None, last_command=last or None, use_git=not args.no_git
    )
    items = rank(history, context, limit=args.limit, allow_sensitive=args.include_secrets)
    if args.format in ("json", "markdown"):
        print(format_for_claude(items, context, args.format))
    elif items:
        print(render_plain(items, args.explain, _wants_color(args.format)))
    else:
        print("no matching commands in history", file=sys.stderr)
    return 0 if items else 1


def run_stats(args: argparse.Namespace) -> int:
    label, path, history = _load_history(args)
    commands = Counter(history)
    programs = Counter(program_of(c) for c in history)
    report = {
        "file": str(path),
        "format": label,
        "entries": len(history),
        "unique": len(commands),
        "top_commands": commands.most_common(args.limit),
        "top_programs": programs.most_common(args.limit),
    }
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if history else 1
    print(f"{report['entries']} entries, {report['unique']} unique ({path})")
    print("\nmost used commands")
    for command, count in report["top_commands"]:
        print(f"  {count:>5}  {command}")
    print("\nmost used programs")
    for program, count in report["top_programs"]:
        print(f"  {count:>5}  {program}")
    return 0 if history else 1


def run_context(args: argparse.Namespace) -> int:
    print(json.dumps(get_context(args.cwd, use_git=not args.no_git), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    top_level = {"-h", "--help", "--version"}
    if not argv or (argv[0] not in COMMANDS and argv[0] not in top_level):
        argv.insert(0, "suggest")  # `cliprompt git` means `cliprompt suggest git`
    args = build_parser().parse_args(argv)
    handlers = {"suggest": run_suggest, "stats": run_stats, "context": run_context}
    try:
        return handlers[args.command](args)
    except (HistoryError, CliError) as exc:
        print(f"cliprompt: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
