"""Tests for the directory/git context collector."""

import json
import shutil
import subprocess

import pytest

from cliprompt.context import (
    detect_kinds,
    get_context,
    git_state,
    make_targets,
    package_scripts,
)

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def git(path, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=path,
        check=True,
        capture_output=True,
    )


def test_plain_directory_has_no_kinds(tmp_path):
    ctx = get_context(tmp_path, use_git=False)
    assert ctx["kinds"] == []
    assert ctx["tools"] == []
    assert ctx["git"] == {"is_repo": False}
    assert ctx["dir_name"] == tmp_path.name


def test_python_and_docker_markers(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    assert detect_kinds(tmp_path) == ["python", "docker"]
    ctx = get_context(tmp_path, use_git=False)
    assert "pytest" in ctx["tools"] and "docker" in ctx["tools"]


def test_markers_found_in_parent(tmp_path):
    (tmp_path / "Cargo.toml").write_text("")
    sub = tmp_path / "src" / "bin"
    sub.mkdir(parents=True)
    assert detect_kinds(sub) == ["rust"]


def test_package_scripts(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "x", "build": "y"}}))
    assert package_scripts(tmp_path) == ["build", "test"]


def test_package_scripts_malformed(tmp_path):
    (tmp_path / "package.json").write_text("{not json")
    assert package_scripts(tmp_path) == []
    (tmp_path / "package.json").write_text("[1, 2]")
    assert package_scripts(tmp_path) == []


def test_make_targets(tmp_path):
    (tmp_path / "Makefile").write_text(
        ".PHONY: all\nall: build\n\nbuild:\n\tcc x.c\nVAR := 1\ntest: build\n"
    )
    assert make_targets(tmp_path) == ["all", "build", "test"]


def test_missing_directory_does_not_crash(tmp_path):
    ctx = get_context(tmp_path / "nope")
    assert ctx["kinds"] == [] and ctx["git"]["is_repo"] is False


def test_prefix_and_last_command_are_recorded(tmp_path):
    ctx = get_context(tmp_path, prefix="git ", last_command="git add .", use_git=False)
    assert ctx["prefix"] == "git " and ctx["last_command"] == "git add ."


@needs_git
def test_git_state_clean_and_dirty(tmp_path):
    git(tmp_path, "init", "-q", "-b", "trunk")
    assert git_state(tmp_path)["dirty"] is False
    (tmp_path / "a.txt").write_text("hi")
    state = git_state(tmp_path)
    assert state["is_repo"] and state["branch"] == "trunk"
    assert state["untracked"] == 1 and state["dirty"] is True
    git(tmp_path, "add", "a.txt")
    state = git_state(tmp_path)
    assert state["staged"] == 1 and state["untracked"] == 0


@needs_git
def test_git_state_modified_after_commit(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("hi")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "first")
    (tmp_path / "a.txt").write_text("changed")
    state = git_state(tmp_path)
    assert state["modified"] == 1 and state["staged"] == 0
    assert state["has_upstream"] is False
