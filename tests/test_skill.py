"""Tests for the agent-facing renderers."""

import json

import pytest

from cliprompt.engine import Suggestion
from cliprompt.skill import format_for_claude, summarize_context

ITEMS = [
    Suggestion("git push", 3.0, 4, 10, ["2 commit(s) not pushed"]),
    Suggestion("pytest -q", 2.0, 1, 3, []),
]
CTX = {
    "cwd": "/work/app",
    "kinds": ["python"],
    "git": {"is_repo": True, "branch": "main", "dirty": True, "staged": 1, "modified": 2,
            "untracked": 0, "ahead": 2, "behind": 0},
    "prefix": "git",
    "scripts": ["not", "shown"],
}


def test_json_structure():
    payload = json.loads(format_for_claude(ITEMS, CTX, "json"))
    assert set(payload) == {"context", "suggestions"}
    assert payload["suggestions"][0] == {
        "command": "git push",
        "score": 3.0,
        "count": 4,
        "reasons": ["2 commit(s) not pushed"],
    }
    assert payload["context"]["git"]["ahead"] == 2
    assert "scripts" not in payload["context"]


def test_markdown_lists_commands_with_reasons():
    text = format_for_claude(ITEMS, CTX, "markdown")
    assert "1. `git push` - 2 commit(s) not pushed" in text
    assert "2. `pytest -q`" in text
    assert "(python project)" in text
    assert "branch `main`, 1 staged, 2 modified, 0 untracked, 2 ahead" in text


def test_markdown_without_results():
    text = format_for_claude([], {"cwd": "/x"}, "markdown")
    assert "No matching commands" in text


def test_clean_repo_line():
    ctx = {"git": {"is_repo": True, "branch": None, "dirty": False}}
    assert "branch `detached`, clean" in format_for_claude([], ctx)


def test_unknown_format_is_rejected():
    with pytest.raises(ValueError, match="unknown format"):
        format_for_claude(ITEMS, CTX, "yaml")


def test_summary_omits_git_outside_repo():
    assert summarize_context({"git": {"is_repo": False}})["git"] is None
