"""Render suggestions for a coding agent (JSON or Markdown) instead of a human terminal."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from .engine import Suggestion

FORMATS = ("json", "markdown")


def summarize_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """The parts of the context worth showing to an agent (no file listings)."""
    git = context.get("git") or {}
    summary: dict[str, Any] = {
        "cwd": context.get("cwd"),
        "project": list(context.get("kinds") or []),
        "git": None,
    }
    if git.get("is_repo"):
        summary["git"] = {
            key: git.get(key)
            for key in ("branch", "dirty", "staged", "modified", "untracked", "ahead", "behind")
        }
    if context.get("prefix"):
        summary["prefix"] = context["prefix"]
    if context.get("last_command"):
        summary["last_command"] = context["last_command"]
    return summary


def _git_line(git: Mapping[str, Any]) -> str:
    bits = [f"branch `{git.get('branch') or 'detached'}`"]
    if git.get("dirty"):
        bits.append(
            f"{git.get('staged', 0)} staged, {git.get('modified', 0)} modified, "
            f"{git.get('untracked', 0)} untracked"
        )
    else:
        bits.append("clean")
    if git.get("ahead"):
        bits.append(f"{git['ahead']} ahead")
    if git.get("behind"):
        bits.append(f"{git['behind']} behind")
    return ", ".join(bits)


def format_for_claude(
    suggestions: Sequence[Suggestion],
    context: Mapping[str, Any] | None = None,
    fmt: str = "markdown",
) -> str:
    """Return the suggestions as a JSON document or a Markdown snippet.

    JSON has the keys ``context`` and ``suggestions`` (each with ``command``, ``score``,
    ``count``, ``reasons``). Markdown is a short context line plus a numbered list of
    commands, each followed by why it ranked.
    """
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}; expected one of {', '.join(FORMATS)}")
    summary = summarize_context(context or {})
    if fmt == "json":
        payload = {
            "context": summary,
            "suggestions": [item.to_dict() for item in suggestions],
        }
        return json.dumps(payload, indent=2)

    lines = ["## Suggested commands", ""]
    where = f"`{summary['cwd']}`" if summary.get("cwd") else "the current directory"
    kinds = summary["project"]
    lines.append(f"Working in {where}" + (f" ({', '.join(kinds)} project)" if kinds else "") + ".")
    if summary["git"]:
        lines.append(f"Git: {_git_line(summary['git'])}.")
    lines.append("")
    if not suggestions:
        lines.append("No matching commands in shell history.")
        return "\n".join(lines)
    for number, item in enumerate(suggestions, 1):
        why = f" - {'; '.join(item.reasons)}" if item.reasons else ""
        lines.append(f"{number}. `{item.command}`{why}")
    return "\n".join(lines)
