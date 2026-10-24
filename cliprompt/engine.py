"""Rank past commands as completions for what the user is about to type."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .context import KIND_TOOLS

# How many history entries it takes for the recency bonus to halve.
RECENCY_HALF_LIFE = 300

# Commands that are never worth suggesting on their own.
TRIVIAL = {"ls", "ll", "la", "cd", "pwd", "clear", "cls", "exit", "history", "dir", "logout"}

GENERIC_TOOLS = {"git", "cd", "ls", "cat", "echo", "grep", "rg", "ssh", "curl", "code", "gh"}
ALL_TOOLS = set().union(*KIND_TOOLS.values())

_SENSITIVE = [
    re.compile(r"(?i)(pass(word|wd)?|secret|token|api[_-]?key|access[_-]?key)\w*\s*[=:]\s*\S+"),
    re.compile(r"(?i)--(pass(word)?|token|secret|api-key)(=|\s+)\S+"),
    re.compile(r"(?i)authorization:\s*\S+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\b(sk-|ghp_|gho_|ghs_|github_pat_|xox[abp]-)[A-Za-z0-9_-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"://[^/\s:@]+:[^/\s@]+@"),
]


@dataclass
class Suggestion:
    """A candidate command with its score and the reasons that produced it."""

    command: str
    score: float
    count: int
    last_index: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "score": round(self.score, 3),
            "count": self.count,
            "reasons": list(self.reasons),
        }


def looks_sensitive(command: str) -> bool:
    """True if the command appears to contain a password, token, key or URL credential."""
    return any(pattern.search(command) for pattern in _SENSITIVE)


def normalize(command: str) -> str:
    """Collapse runs of whitespace; multi-line commands are returned as an empty string."""
    command = command.strip()
    if "\n" in command:
        return ""
    return " ".join(command.split())


def program_of(command: str) -> str:
    """First word of a command, lower-cased, without a directory or ``.exe`` suffix."""
    first = command.split(" ", 1)[0]
    if first.startswith("./"):
        return first
    first = first.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return first[:-4] if first.endswith(".exe") else first


def _text(item: Any) -> str:
    return item if isinstance(item, str) else getattr(item, "command", "")


def prepare(history: Iterable[Any]) -> list[str]:
    """Normalise raw history items (strings or entries) to a clean list, oldest first."""
    cleaned = []
    for item in history:
        text = normalize(_text(item))
        if text:
            cleaned.append(text)
    return cleaned


def _matches_prefix(command: str, prefix: str) -> tuple[bool, float, str | None]:
    """Return (matches, bonus, reason) for a typed prefix."""
    if not prefix.strip():
        return True, 0.0, None
    typed = " ".join(prefix.split()) + (" " if prefix.endswith(" ") else "")
    if command == typed.strip():
        return False, 0.0, None
    if command.startswith(typed):
        return True, 1.0, None
    if prefix.endswith(" "):
        return False, 0.0, None
    words = typed.lower().split()
    lowered = command.lower()
    if words and all(word in lowered for word in words):
        return True, -0.4, "contains your text"
    return False, 0.0, None


def _git_adjust(command: str, git: Mapping[str, Any]) -> tuple[float, list[str]]:
    parts = command.split()
    sub = parts[1] if len(parts) > 1 else ""
    if not git.get("is_repo"):
        return -2.0, ["not inside a git repository"]
    bonus = 0.0
    why: list[str] = []

    def add(amount: float, reason: str) -> None:
        nonlocal bonus
        bonus += amount
        why.append(reason)

    if git.get("conflicted") and sub in {"status", "add", "merge", "rebase", "diff"}:
        add(0.9, "merge conflicts present")
    if git.get("dirty") and sub in {"status", "diff", "add", "stash", "commit"}:
        add(0.5, "uncommitted changes")
    if git.get("staged") and sub == "commit":
        add(0.6, "staged changes ready to commit")
    if git.get("ahead") and sub == "push":
        add(0.9, f"{git['ahead']} commit(s) not pushed")
    if git.get("behind") and sub in {"pull", "merge", "rebase"}:
        add(0.9, f"{git['behind']} commit(s) behind upstream")
    if git.get("dirty") is False and sub in {"commit", "add"}:
        add(-0.6, "working tree is clean")
    branch = git.get("branch")
    if branch and branch in parts[2:]:
        add(0.5, f"mentions branch {branch}")
    return bonus, why


def _tool_adjust(command: str, context: Mapping[str, Any]) -> tuple[float, list[str]]:
    program = program_of(command)
    tools = set(context.get("tools") or [])
    kinds = context.get("kinds") or []
    if program in tools:
        return 0.7, [f"fits this {kinds[0]} project" if kinds else "fits this project"]
    if kinds and program in ALL_TOOLS and program not in GENERIC_TOOLS:
        return -0.5, ["belongs to a different toolchain"]
    return 0.0, []


def _runner_adjust(command: str, context: Mapping[str, Any]) -> tuple[float, list[str]]:
    parts = command.split()
    program = program_of(command)
    scripts = context.get("scripts") or []
    targets = context.get("make_targets") or []
    if program in {"npm", "yarn", "pnpm", "bun"} and scripts and "run" in parts[:3]:
        at = parts.index("run") + 1
        name = parts[at] if at < len(parts) else ""
        if name in scripts:
            return 0.6, [f"package.json defines {name!r}"]
        if name:
            return -0.7, [f"package.json has no script {name!r}"]
    if program == "make" and targets and len(parts) > 1 and not parts[1].startswith("-"):
        if parts[1] in targets:
            return 0.6, [f"Makefile defines {parts[1]!r}"]
        return -0.7, [f"Makefile has no target {parts[1]!r}"]
    return 0.0, []


def rank(
    history: Iterable[Any],
    context: Mapping[str, Any] | None = None,
    limit: int | None = None,
    allow_sensitive: bool = False,
) -> list[Suggestion]:
    """Score every distinct command in ``history`` (oldest first) against ``context``.

    ``context`` may carry ``prefix`` (what the user has typed), ``last_command`` and the
    keys produced by :func:`cliprompt.context.get_context`. Returns best-first suggestions.
    """
    context = context or {}
    commands = prepare(history)
    prefix = context.get("prefix") or ""
    last_command = normalize(context.get("last_command") or "")
    git = context.get("git")
    total = len(commands)

    counts: Counter[str] = Counter(commands)
    last_seen = {cmd: index for index, cmd in enumerate(commands)}
    followers: Counter[str] = Counter()
    if last_command:
        for before, after in zip(commands, commands[1:], strict=False):
            if before == last_command:
                followers[after] += 1

    results: list[Suggestion] = []
    for command, count in counts.items():
        if program_of(command) == "cliprompt":
            continue
        if not allow_sensitive and looks_sensitive(command):
            continue
        if not prefix.strip() and command in TRIVIAL:
            continue
        matched, bonus, match_reason = _matches_prefix(command, prefix)
        if not matched:
            continue

        reasons = [f"used {count}x"] if count > 1 else []
        age = total - 1 - last_seen[command]
        score = math.log2(1 + count) + 1.5 * 0.5 ** (age / RECENCY_HALF_LIFE) + bonus
        if age < 5:
            reasons.append("used moments ago")
        if match_reason:
            reasons.append(match_reason)

        if program_of(command) == "git":
            delta, why = _git_adjust(command, git) if git is not None else (0.0, [])
        else:
            delta, why = _tool_adjust(command, context)
            extra, extra_why = _runner_adjust(command, context)
            delta, why = delta + extra, why + extra_why
        score += delta
        reasons.extend(why)

        if followers[command]:
            score += 1.2 * math.log2(1 + followers[command])
            reasons.append(f"often follows `{last_command}`")
        dir_name = context.get("dir_name")
        if dir_name and len(dir_name) > 2 and dir_name in command:
            score += 0.3
            reasons.append(f"mentions {dir_name}")

        results.append(Suggestion(command, score, count, last_seen[command], reasons))

    results.sort(key=lambda s: (-s.score, -s.last_index, s.command))
    return results[:limit] if limit is not None else results


def suggest(
    history: Iterable[Any], context: Mapping[str, Any] | None = None, limit: int | None = None
) -> list[str]:
    """Best-first list of command strings; see :func:`rank` for the scoring inputs."""
    return [item.command for item in rank(history, context, limit)]
