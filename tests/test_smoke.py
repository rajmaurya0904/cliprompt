"""Smoke test: package imports cleanly. Replace/extend as modules land."""

import cliprompt


def test_version_is_set() -> None:
    assert cliprompt.__version__
