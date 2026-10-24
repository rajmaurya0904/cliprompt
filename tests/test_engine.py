"""Tests for the suggestion engine."""

from cliprompt.engine import looks_sensitive, normalize, program_of, rank, suggest
from cliprompt.history import HistoryEntry


def test_frequency_beats_a_single_use():
    history = ["git push", "git status", "git status", "git commit"]
    # push and commit are used once; the repeated one wins even though it is not last
    assert suggest(history, {})[0] == "git status"


def test_recency_breaks_frequency_ties():
    history = ["zebra", "apple", "banana"]
    assert suggest(history, {}) == ["banana", "apple", "zebra"]


def test_prefix_filters_candidates():
    history = ["git status", "git commit", "npm start", "npm test"]
    result = suggest(history, {"prefix": "git"})
    assert sorted(result) == ["git commit", "git status"]


def test_prefix_with_trailing_space_respects_word_boundary():
    history = ["gitk --all", "git log"]
    assert suggest(history, {"prefix": "git "}) == ["git log"]


def test_prefix_no_matches():
    assert suggest(["ls -l", "cd src"], {"prefix": "kubectl"}) == []


def test_exact_match_is_not_a_completion():
    assert suggest(["make", "make test"], {"prefix": "make"}) == ["make test"]


def test_substring_match_ranks_below_prefix_match():
    history = ["docker compose up", "echo docker"]
    assert suggest(history, {"prefix": "docker"}) == ["docker compose up", "echo docker"]


def test_empty_history():
    assert suggest([], {}) == []
    assert suggest([], {"prefix": "x"}) == []


def test_none_context_is_allowed():
    assert suggest(["make test"], None) == ["make test"]


def test_whitespace_is_normalised_and_deduplicated():
    result = rank(["git   status", "git status ", " git status"], {})
    assert len(result) == 1 and result[0].count == 3


def test_multiline_commands_are_dropped():
    assert suggest(["echo a\necho b", "pytest"], {}) == ["pytest"]


def test_history_entries_are_accepted():
    entries = [HistoryEntry("make build", 1), HistoryEntry("make test", 2)]
    assert suggest(entries, {"prefix": "make"}) == ["make test", "make build"]


def test_trivial_commands_hidden_unless_typed():
    assert suggest(["ls", "cd", "pytest -q"], {}) == ["pytest -q"]
    assert suggest(["ls", "ls -la"], {"prefix": "ls"}) == ["ls -la"]


def test_cliprompt_invocations_are_not_suggested():
    assert suggest(["cliprompt suggest git", "git status"], {}) == ["git status"]


def test_secrets_are_never_suggested():
    history = [
        "curl -H 'Authorization: Bearer abcdef123456' https://x.test",
        "export GITHUB_TOKEN=ghp_abcdefghijklmnop123",
        "mysql -u root --password=hunter2",
        "git clone https://user:pw@example.com/r.git",
        "git status",
    ]
    assert suggest(history, {}) == ["git status"]
    assert len(rank(history, {}, allow_sensitive=True)) == 5


def test_looks_sensitive_negatives():
    assert not looks_sensitive("git commit -m 'rotate tokens docs'")
    assert not looks_sensitive("passwd")
    assert looks_sensitive("aws configure set aws_secret_access_key=abc")


def test_helpers():
    assert normalize("  a   b \t c ") == "a b c"
    assert program_of("/usr/bin/Python3") == "python3"
    assert program_of("C:\\tools\\Git.exe status") == "git"
    assert program_of("./gradlew build") == "./gradlew"


def test_git_commands_are_demoted_outside_a_repo():
    history = ["git status", "git status", "pytest -q"]
    ctx = {"git": {"is_repo": False}}
    assert suggest(history, ctx)[0] == "pytest -q"


def test_unpushed_commits_promote_push():
    history = ["git push", "git status", "git status", "git log"]
    ctx = {"git": {"is_repo": True, "dirty": False, "ahead": 2, "behind": 0, "branch": "main"}}
    ranked = rank(history, ctx)
    assert ranked[0].command == "git push"
    assert "2 commit(s) not pushed" in ranked[0].reasons


def test_staged_changes_promote_commit():
    history = ["git commit -m wip", "git status", "git log"]
    ctx = {"git": {"is_repo": True, "dirty": True, "staged": 1, "branch": "main"}}
    assert suggest(history, ctx)[0] == "git commit -m wip"


def test_clean_tree_demotes_commit():
    history = ["git commit -m wip", "git log"]
    ctx = {"git": {"is_repo": True, "dirty": False, "staged": 0, "branch": "main"}}
    assert suggest(history, ctx) == ["git log", "git commit -m wip"]


def test_branch_name_in_command_is_rewarded():
    history = ["git push origin feature-x", "git push origin main"]
    ctx = {"git": {"is_repo": True, "dirty": False, "branch": "feature-x"}}
    assert suggest(history, ctx)[0] == "git push origin feature-x"


def test_project_toolchain_is_rewarded():
    history = ["cargo build", "pytest -q", "cargo build", "pytest -q"]
    ctx = {"kinds": ["python"], "tools": ["pytest", "pip", "python"]}
    ranked = rank(history, ctx)
    assert ranked[0].command == "pytest -q"
    assert "belongs to a different toolchain" in ranked[1].reasons


def test_missing_npm_script_is_demoted():
    history = ["npm run deploy", "npm run build"]
    ctx = {"kinds": ["node"], "tools": ["npm"], "scripts": ["build", "test"]}
    ranked = rank(history, ctx)
    assert ranked[0].command == "npm run build"
    assert any("no script" in reason for reason in ranked[1].reasons)


def test_makefile_targets_are_checked():
    history = ["make dist", "make test"]
    ctx = {"kinds": ["make"], "tools": ["make"], "make_targets": ["test", "build"]}
    assert suggest(history, ctx) == ["make test", "make dist"]


def test_last_command_promotes_its_followers():
    history = ["git add .", "git commit -m x", "ls -la", "git add .", "git commit -m x", "pwd"]
    history += ["make", "make", "make", "git add ."]
    ctx = {"last_command": "git add ."}
    ranked = rank(history, ctx)
    assert ranked[0].command == "git commit -m x"
    assert "often follows `git add .`" in ranked[0].reasons


def test_limit():
    history = [f"cmd{i} --flag" for i in range(10)]
    assert len(suggest(history, {}, limit=3)) == 3
    assert suggest(history, {}, limit=3) == ["cmd9 --flag", "cmd8 --flag", "cmd7 --flag"]


def test_to_dict_shape():
    item = rank(["make test", "make test"], {})[0].to_dict()
    assert set(item) == {"command", "score", "count", "reasons"}
    assert item["count"] == 2 and "used 2x" in item["reasons"]


def test_clean_tree_outweighs_a_strong_sequence():
    history = ["git add -A", "git commit -m x"] * 5 + ["git status", "git add -A"]
    ctx = {
        "last_command": "git add -A",
        "git": {"is_repo": True, "dirty": False, "staged": 0, "branch": "main"},
    }
    assert suggest(history, ctx)[0] != "git commit -m x"


def test_rare_sequences_are_damped():
    history = ["make", "make test", "make", "make", "make", "make"]
    ranked = rank(history, {"last_command": "make"})
    assert ranked[0].command == "make"
