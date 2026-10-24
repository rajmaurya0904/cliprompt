"""End-to-end tests for the command line."""

import json
import subprocess
import sys

import pytest

from cliprompt.cli import main

HISTORY = (
    ": 1700000000:0;git status\n"
    ": 1700000010:0;pytest -q\n"
    ": 1700000020:0;git status\n"
    ": 1700000030:0;make build\n"
    ": 1700000040:0;export API_TOKEN=abcdef1234567890\n"
    ": 1700000050:0;git log --oneline\n"
)


@pytest.fixture
def hist(tmp_path):
    path = tmp_path / ".zsh_history"
    path.write_text(HISTORY, encoding="utf-8")
    return str(path)


def run(args, capsys):
    code = main(args)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "suggest" in capsys.readouterr().out


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("cliprompt ")


def test_default_command_is_suggest(hist, capsys, tmp_path):
    code, out, _ = run(["-f", hist, "--no-git", "--cwd", str(tmp_path)], capsys)
    assert code == 0
    assert out.splitlines()[0] == "git status"


def test_prefix_words_are_joined(hist, capsys, tmp_path):
    code, out, _ = run(
        ["-f", hist, "--no-git", "--cwd", str(tmp_path), "--", "git", "log", "--oneline"], capsys
    )
    assert code == 1  # an exact match is not a completion
    code, out, _ = run(["git", "-f", hist, "--no-git", "--cwd", str(tmp_path)], capsys)
    assert code == 0 and set(out.split("\n")) >= {"git status", "git log --oneline"}


def test_no_match_exits_one_with_message(hist, capsys, tmp_path):
    code, out, err = run(["suggest", "kubectl", "-f", hist, "--cwd", str(tmp_path)], capsys)
    assert (code, out) == (1, "")
    assert "no matching commands" in err


def test_secrets_are_hidden_by_default(hist, capsys, tmp_path):
    _, out, _ = run(["suggest", "-f", hist, "-n", "10", "--no-git", "--cwd", str(tmp_path)], capsys)
    assert "API_TOKEN" not in out
    _, out, _ = run(
        ["suggest", "-f", hist, "-n", "10", "--include-secrets", "--no-git",
         "--cwd", str(tmp_path)],
        capsys,
    )
    assert "API_TOKEN" in out


def test_missing_history_file_is_exit_two(tmp_path, capsys):
    code, out, err = run(["suggest", "-f", str(tmp_path / "nope")], capsys)
    assert code == 2 and out == ""
    assert err.startswith("cliprompt: history file not found")


def test_bad_arguments_are_rejected(hist, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["suggest", "--format", "xml", "-f", hist])
    assert exc.value.code == 2
    code, _, err = run(["suggest", "-n", "0", "-f", hist], capsys)
    assert code == 2 and "--limit" in err
    code, _, err = run(["suggest", "--window", "0", "-f", hist], capsys)
    assert code == 2 and "--window" in err


def test_limit_and_explain(hist, capsys, tmp_path):
    code, out, _ = run(
        ["-f", hist, "-n", "1", "--explain", "--no-git", "--cwd", str(tmp_path)], capsys
    )
    lines = out.splitlines()
    assert code == 0 and len(lines) == 2
    assert lines[0] == "git status" and lines[1].startswith("  # ")


def test_json_format(hist, capsys, tmp_path):
    code, out, _ = run(
        ["-f", hist, "--format", "json", "-n", "2", "--no-git", "--cwd", str(tmp_path)], capsys
    )
    payload = json.loads(out)
    assert code == 0
    assert payload["suggestions"][0]["command"] == "git status"
    assert payload["context"]["cwd"].endswith(tmp_path.name)


def test_markdown_format(hist, capsys, tmp_path):
    _, out, _ = run(
        ["-f", hist, "--format", "markdown", "--no-git", "--cwd", str(tmp_path)], capsys
    )
    assert out.startswith("## Suggested commands")
    assert "1. `git status`" in out


def test_color_format_has_ansi(hist, capsys, tmp_path):
    _, out, _ = run(["-f", hist, "--format", "color", "--no-git", "--cwd", str(tmp_path)], capsys)
    assert "\033[1mgit status\033[0m" in out


def test_plain_output_has_no_ansi_when_piped(hist, capsys, tmp_path):
    _, out, _ = run(["-f", hist, "--no-git", "--cwd", str(tmp_path)], capsys)
    assert "\033" not in out


def test_window_limits_history(hist, capsys, tmp_path):
    _, out, _ = run(
        ["-f", hist, "--window", "1", "-n", "5", "--no-git", "--cwd", str(tmp_path)], capsys
    )
    assert out.split() == ["git", "log", "--oneline"]


def test_last_command_is_used_for_sequences(tmp_path, capsys):
    path = tmp_path / "h"
    path.write_text("make build\nmake test\nls -la\nmake build\nmake test\nmake build\n")
    _, out, _ = run(["-f", str(path), "--no-git", "--cwd", str(tmp_path), "--explain"], capsys)
    assert out.splitlines()[0] == "make test"
    assert "often follows `make build`" in out
    _, out, _ = run(
        ["-f", str(path), "--last", "", "--no-git", "--cwd", str(tmp_path), "--explain"], capsys
    )
    assert "often follows" not in out


def test_stats(hist, capsys):
    code, out, _ = run(["stats", "-f", hist, "-n", "2"], capsys)
    assert code == 0
    assert "6 entries, 5 unique" in out or "6 entries" in out
    assert "git status" in out


def test_stats_json(hist, capsys):
    code, out, _ = run(["stats", "-f", hist, "--json"], capsys)
    report = json.loads(out)
    assert code == 0 and report["entries"] == 6
    assert report["top_commands"][0] == ["git status", 2]
    assert report["top_programs"][0] == ["git", 3]


def test_stats_on_empty_history(tmp_path, capsys):
    path = tmp_path / "h"
    path.write_text("")
    code, out, _ = run(["stats", "-f", str(path)], capsys)
    assert code == 1 and out.startswith("0 entries")


def test_context_command(tmp_path, capsys):
    (tmp_path / "go.mod").write_text("module x\n")
    code, out, _ = run(["context", "--cwd", str(tmp_path), "--no-git"], capsys)
    data = json.loads(out)
    assert code == 0 and data["kinds"] == ["go"]


def test_python_dash_m_entry_point(hist, tmp_path):
    done = subprocess.run(
        [sys.executable, "-m", "cliprompt", "-f", hist, "--no-git", "--cwd", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0
    assert done.stdout.splitlines()[0] == "git status"


def test_explicit_shell_overrides_detection(tmp_path, capsys):
    path = tmp_path / "history.txt"  # name gives no hint
    path.write_text(
        "- cmd: cargo test\n  when: 1700000000\n- cmd: cargo build\n  when: 1700000001\n"
    )
    args = ["-f", str(path), "-s", "fish", "--no-git", "--cwd", str(tmp_path)]
    code, out, _ = run(args, capsys)
    assert code == 0 and out.splitlines() == ["cargo build", "cargo test"]


def test_powershell_history_through_the_cli(tmp_path, capsys):
    path = tmp_path / "ConsoleHost_history.txt"
    path.write_text("dotnet build\nGet-Process\ndotnet build\n")
    _, out, _ = run(["-f", str(path), "--last", "", "--no-git", "--cwd", str(tmp_path)], capsys)
    assert out.splitlines()[0] == "dotnet build"


def test_auto_format_is_plain_when_not_a_tty(hist, capsys, tmp_path):
    _, out, _ = run(["-f", hist, "--format", "auto", "--no-git", "--cwd", str(tmp_path)], capsys)
    assert "\033" not in out


def test_no_color_env_disables_auto_colour(hist, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)
    from cliprompt.cli import _wants_color

    assert _wants_color("auto") is False
    assert _wants_color("color") is True
