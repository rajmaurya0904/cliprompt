"""Tests for the shell history readers."""

import os
from pathlib import Path

import pytest

from cliprompt.history import (
    HistoryError,
    detect_format,
    find_history_file,
    parse_bash,
    parse_fish,
    parse_history,
    parse_powershell,
    parse_zsh,
    read_history,
    read_text_tail,
)


def commands(entries):
    return [e.command for e in entries]


def test_bash_plain_lines():
    assert commands(parse_bash("ls\ngit status\n\n  \ncd ..\n")) == ["ls", "git status", "cd .."]


def test_bash_timestamps_attach_to_next_command():
    entries = parse_bash("#1700000000\nls -la\npwd\n#1700000100\nmake\n")
    assert [(e.command, e.timestamp) for e in entries] == [
        ("ls -la", 1700000000),
        ("pwd", None),
        ("make", 1700000100),
    ]


def test_bash_comment_that_is_not_a_timestamp_is_kept():
    assert commands(parse_bash("# a note\nls\n")) == ["# a note", "ls"]


def test_zsh_extended_format():
    text = ": 1700000000:0;git commit -m 'x'\n: 1700000005:2;npm test\n"
    entries = parse_zsh(text)
    assert [(e.command, e.timestamp) for e in entries] == [
        ("git commit -m 'x'", 1700000000),
        ("npm test", 1700000005),
    ]


def test_zsh_plain_lines_and_continuation():
    text = "ls\n: 1700000000:0;echo one \\\ntwo\nwhoami\n"
    entries = parse_zsh(text)
    assert commands(entries) == ["ls", "echo one \ntwo", "whoami"]


def test_fish_format_with_when():
    text = "- cmd: git status\n  when: 1700000000\n- cmd: echo a\\nb\n  when: 1700000050\n  paths:\n    - x\n"
    entries = parse_fish(text)
    assert [(e.command, e.timestamp) for e in entries] == [
        ("git status", 1700000000),
        ("echo a\nb", 1700000050),
    ]


def test_powershell_backtick_continuation():
    entries = parse_powershell("Get-ChildItem `\n  -Recurse\nGet-Date\n")
    assert commands(entries) == ["Get-ChildItem \n  -Recurse", "Get-Date"]


def test_unknown_shell_is_an_error():
    with pytest.raises(HistoryError, match="unknown shell"):
        parse_history("ls", "tcsh")


@pytest.mark.parametrize(
    ("name", "text", "expected"),
    [
        (".zsh_history", "", "zsh"),
        (".bash_history", "", "bash"),
        ("fish_history", "", "fish"),
        ("ConsoleHost_history.txt", "", "powershell"),
        ("history.txt", "- cmd: ls\n  when: 1\n", "fish"),
        ("history.txt", ": 1700000000:0;ls\n", "zsh"),
        ("history.txt", "ls\n", "bash"),
    ],
)
def test_detect_format(name, text, expected):
    assert detect_format(Path(name), text) == expected


def test_read_history_autodetects(tmp_path):
    path = tmp_path / ".zsh_history"
    path.write_text(": 1700000000:0;make test\n", encoding="utf-8")
    assert commands(read_history(path)) == ["make test"]
    assert commands(read_history(path, "auto")) == ["make test"]


def test_missing_file_raises(tmp_path):
    with pytest.raises(HistoryError, match="not found"):
        read_history(tmp_path / "nope")


def test_directory_raises(tmp_path):
    with pytest.raises(HistoryError, match="directory"):
        read_history(tmp_path)


def test_empty_file_gives_no_entries(tmp_path):
    path = tmp_path / ".bash_history"
    path.write_text("")
    assert read_history(path) == []


def test_binary_garbage_does_not_crash(tmp_path):
    path = tmp_path / ".bash_history"
    path.write_bytes(b"ls\n\xff\xfe\x00\x01bad\ngit status\n")
    result = commands(read_history(path))
    assert "ls" in result and "git status" in result


def test_huge_file_reads_only_the_tail(tmp_path):
    path = tmp_path / ".bash_history"
    path.write_text("old-command\n" * 1000 + "newest\n")
    text = read_text_tail(path, max_bytes=100)
    assert text.rstrip().endswith("newest")
    assert len(text) <= 100


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not enforced on Windows")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores modes")
def test_unreadable_file_raises(tmp_path):
    path = tmp_path / ".bash_history"
    path.write_text("ls\n")
    path.chmod(0)
    try:
        with pytest.raises(HistoryError, match="cannot read"):
            read_history(path)
    finally:
        path.chmod(0o600)


def test_find_history_file_prefers_histfile(tmp_path):
    custom = tmp_path / "my_zsh_history"
    custom.write_text("ls\n")
    shell, path = find_history_file(environ={"HISTFILE": str(custom)}, home=tmp_path)
    assert (shell, path) == ("zsh", custom)


def test_find_history_file_picks_most_recent(tmp_path):
    bash = tmp_path / ".bash_history"
    zsh = tmp_path / ".zsh_history"
    bash.write_text("a\n")
    zsh.write_text("b\n")
    os.utime(bash, (2_000_000_000, 2_000_000_000))
    os.utime(zsh, (1_000_000_000, 1_000_000_000))
    shell, path = find_history_file(environ={}, home=tmp_path)
    assert shell == "bash" and path == bash


def test_find_history_file_by_shell(tmp_path):
    (tmp_path / ".bash_history").write_text("a\n")
    (tmp_path / ".zsh_history").write_text("b\n")
    shell, _ = find_history_file("zsh", environ={}, home=tmp_path)
    assert shell == "zsh"


def test_find_history_file_none_found(tmp_path):
    with pytest.raises(HistoryError, match="no shell history file found"):
        find_history_file(environ={}, home=tmp_path)
