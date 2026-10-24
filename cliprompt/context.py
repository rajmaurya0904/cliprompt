"""Describe the directory the user is working in: project type, git state, task runners."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

# marker file -> project kind
PROJECT_MARKERS = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "Gemfile": "ruby",
    "composer.json": "php",
    "Makefile": "make",
    "Dockerfile": "docker",
    "docker-compose.yml": "docker",
    "compose.yaml": "docker",
    "main.tf": "terraform",
}

# project kind -> programs whose commands are relevant there
KIND_TOOLS = {
    "python": {"python", "python3", "py", "pip", "pip3", "pytest", "ruff", "uv", "poetry", "tox"},
    "node": {"npm", "npx", "node", "yarn", "pnpm", "bun", "tsc", "jest", "vitest"},
    "rust": {"cargo", "rustc", "rustup"},
    "go": {"go"},
    "java": {"mvn", "gradle", "java", "./gradlew", "./mvnw"},
    "ruby": {"bundle", "ruby", "rake", "rails", "gem"},
    "php": {"composer", "php", "artisan"},
    "make": {"make"},
    "docker": {"docker", "docker-compose", "podman"},
    "terraform": {"terraform", "tofu"},
}

GIT_TIMEOUT = 5
_MAKE_TARGET = re.compile(r"^([A-Za-z0-9][\w.-]*)\s*:(?!=)")


def _run_git(cwd: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def git_state(cwd: Path) -> dict[str, Any]:
    """Branch and working tree summary; ``{"is_repo": False}`` outside a repository."""
    out = _run_git(cwd, "status", "--porcelain=v2", "--branch")
    if out is None:
        return {"is_repo": False}
    state: dict[str, Any] = {
        "is_repo": True,
        "branch": None,
        "ahead": 0,
        "behind": 0,
        "staged": 0,
        "modified": 0,
        "untracked": 0,
        "conflicted": 0,
        "has_upstream": False,
    }
    for line in out.splitlines():
        if line.startswith("# branch.head "):
            head = line.split(" ", 2)[2]
            state["branch"] = None if head == "(detached)" else head
        elif line.startswith("# branch.upstream "):
            state["has_upstream"] = True
        elif line.startswith("# branch.ab "):
            _, _, ahead, behind = line.split()
            state["ahead"], state["behind"] = int(ahead[1:]), int(behind[1:])
        elif line.startswith(("1 ", "2 ")):
            xy = line.split(" ", 2)[1]
            if xy[0] != ".":
                state["staged"] += 1
            if xy[1] != ".":
                state["modified"] += 1
        elif line.startswith("u "):
            state["conflicted"] += 1
        elif line.startswith("? "):
            state["untracked"] += 1
    state["dirty"] = bool(
        state["staged"] or state["modified"] or state["untracked"] or state["conflicted"]
    )
    return state


def detect_kinds(cwd: Path) -> list[str]:
    """Project kinds for ``cwd``, looking at the directory and up to three parents."""
    kinds: list[str] = []
    for folder in [cwd, *list(cwd.parents)[:3]]:
        for marker, kind in PROJECT_MARKERS.items():
            if kind not in kinds and (folder / marker).is_file():
                kinds.append(kind)
        if kinds:
            break
    return kinds


def package_scripts(cwd: Path) -> list[str]:
    """Script names from ``package.json``; empty if absent or malformed."""
    try:
        data = json.loads((cwd / "package.json").read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
        return sorted(scripts) if isinstance(scripts, dict) else []
    except (OSError, ValueError, AttributeError):
        return []


def make_targets(cwd: Path) -> list[str]:
    """Target names defined in a ``Makefile`` (skips pattern rules and ``.PHONY``)."""
    try:
        text = (cwd / "Makefile").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    targets: list[str] = []
    for line in text.splitlines():
        match = _MAKE_TARGET.match(line)
        if match and match.group(1) not in targets and not match.group(1).startswith("."):
            targets.append(match.group(1))
    return targets


def get_context(
    cwd: Path | str | None = None,
    prefix: str | None = None,
    last_command: str | None = None,
    use_git: bool = True,
) -> dict[str, Any]:
    """Collect the facts the suggestion engine scores against. Never raises."""
    folder = Path(cwd).expanduser() if cwd else Path.cwd()
    try:
        folder = folder.resolve()
    except OSError:
        pass
    is_dir = folder.is_dir()
    kinds = detect_kinds(folder) if is_dir else []
    tools: set[str] = set()
    for kind in kinds:
        tools |= KIND_TOOLS.get(kind, set())
    context: dict[str, Any] = {
        "cwd": str(folder),
        "dir_name": folder.name,
        "kinds": kinds,
        "tools": sorted(tools),
        "git": git_state(folder) if use_git and is_dir else None,  # None = not inspected
        "scripts": package_scripts(folder) if is_dir else [],
        "make_targets": make_targets(folder) if is_dir else [],
    }
    if prefix is not None:
        context["prefix"] = prefix
    if last_command:
        context["last_command"] = last_command
    return context
