"""Tests for the suggestion engine."""

from cliprompt.engine import suggest


def test_frequency_weighting():
    """Higher frequency commands should be ranked higher."""
    history = ["git status", "git commit", "git status", "git push"]
    context = {}
    # Expected: git status (2), then git commit and git push (1 each) alphabetically
    assert suggest(history, context) == ["git status", "git commit", "git push"]


def test_tie_breaking_alphabetical():
    """When frequencies are equal, sort alphabetically."""
    history = ["zebra", "apple", "banana", "apple"]
    context = {}
    # apple (2), then banana and zebra (1 each) -> banana before zebra
    assert suggest(history, context) == ["apple", "banana", "zebra"]


def test_context_prefix_filter():
    """Only commands matching the prefix should be considered."""
    history = ["git status", "git commit", "npm start", "npm test"]
    context = {"prefix": "git"}
    # Only git commands, git status and git commit each once -> alphabetical
    assert suggest(history, context) == ["git commit", "git status"]


def test_context_prefix_no_matches():
    """If no commands match prefix, return empty list."""
    history = ["ls", "cd"]
    context = {"prefix": "git"}
    assert suggest(history, context) == []


def test_context_none_prefix():
    """If prefix is None or missing, consider all commands."""
    history = ["ls", "ls", "cd"]
    context = {}  # no prefix key
    assert suggest(history, context) == ["ls", "cd"]
    # Also test with explicit None
    context_none = {"prefix": None}
    assert suggest(history, context_none) == ["ls", "cd"]


def test_empty_history():
    """Empty history should return empty list."""
    assert suggest([], {}) == []
    assert suggest([], {"prefix": "x"}) == []


def test_duplicate_commands_and_prefix():
    """Duplicates increase frequency, prefix filters."""
    history = ["python run.py", "python run.py", "python debug.py", "ruby script"]
    context = {"prefix": "python"}
    # python run.py (2), python debug.py (1)
    assert suggest(history, context) == ["python run.py", "python debug.py"]