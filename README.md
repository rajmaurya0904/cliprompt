# cliprompt

**Suggests the shell command you are about to type, ranked from your own history, the current directory and the state of your git repo.**

Shell history search is dumb: it matches text and shows the latest hit. It will happily offer `git commit` on a clean tree, `cargo build` in a Python project, or `npm run deploy` when `package.json` has no such script. cliprompt reads your history, looks at where you are, and puts the command that makes sense first.

Run in a Python repo with staged changes, using the sample history in `examples/`:

```console
$ cliprompt -f examples/zsh_history_sample --explain -n 4
git commit -m wip
  # used 6x, staged changes ready to commit, often follows `git add -A`
git add -A
  # used 7x, used moments ago, uncommitted changes
git status
  # used 7x, used moments ago, uncommitted changes
ruff check .
  # used 6x, fits this python project

$ cliprompt -f examples/zsh_history_sample git c --explain -n 3
git commit -m wip
  # used 6x, staged changes ready to commit, often follows `git add -A`
```

Same history, same repo after the commit (clean tree), so `git commit` drops out of the picture:

```console
$ cliprompt -f examples/zsh_history_sample --explain -n 4
ruff check .
  # used 6x, fits this python project
pytest -q
  # used 6x, fits this python project
git status
  # used 7x, used moments ago
pip install -e .[dev]
  # used 2x, used moments ago, fits this python project
```

## Install

Not on PyPI yet; install from a clone:

```bash
pip install -e .
```

This gives you the `cliprompt` command (also `python -m cliprompt`). Needs Python 3.11+. `git` is optional; without it the git signals are skipped.

## Usage

```bash
cliprompt                              # best commands for right now
cliprompt git c                        # complete what you have typed so far
cliprompt -- git log --oneline         # put -- before a prefix that contains flags
cliprompt --format json                # for scripts and agents (also: markdown, plain, color)
cliprompt stats                        # most used commands and programs
cliprompt context                      # what cliprompt sees about the directory
```

Useful flags: `-n` how many to show, `--explain` why each one ranked, `-f PATH` and `-s bash|zsh|fish|powershell` to pick a history file and format, `--cwd DIR` to score against another directory, `--no-git` to skip running git. `cliprompt` is shorthand for `cliprompt suggest`; the subcommand must come first when you use `stats` or `context`.

Exit codes: 0 suggestions printed, 1 nothing matched, 2 bad arguments or unreadable history.

With no `-f`, it uses `$HISTFILE`, otherwise the most recently modified of `~/.zsh_history`, `~/.bash_history`, fish's `fish_history` and PowerShell's PSReadLine `ConsoleHost_history.txt`.

### As a Claude Code skill

`SKILL.md` describes the skill: copy this folder to `~/.claude/skills/cliprompt`, and the agent can run `cliprompt --format json` to see what you usually run in a directory. The same output is available in Python through `cliprompt.skill.format_for_claude`.

## How it works

- **History** is read from the last 4 MB of the file and parsed per shell: bash with `#epoch` stamps, zsh plain and extended entries with `\` continuations, fish's `- cmd:` records, PSReadLine with backtick continuations. Bad bytes are replaced, never fatal.
- **Score** per distinct command is `log2(1 + uses)`, plus a recency bonus that halves every 300 history entries.
- **Prefix** matching: commands starting with what you typed score highest; commands merely containing your words are kept but ranked lower.
- **Context** adds or removes points: git commands are demoted outside a repo, `git push` rises when you are ahead of upstream, `git commit` when something is staged and disappears on a clean tree, `git pull` when you are behind. Tools of the detected project type (pytest in a Python project, cargo in Rust) rise, tools of other ecosystems fall, `npm run X` and `make X` are checked against `package.json` and the `Makefile`.
- **Sequences**: if the command you just ran was usually followed by another, that one gets a bonus proportional to how often it followed.
- **Filtering**: commands that look like they contain a password, token, API key, bearer header or URL credential are never suggested.

## Limitations

- It ranks commands you already ran. It does not complete file names, flags or arguments you have never used.
- It is a command you run, not a shell widget: there is no key binding or inline ghost text. Wire `cliprompt` into your shell yourself if you want that.
- Bash only writes history when a session exits, so the newest commands may be missing until then (`history -a` flushes them).
- History carries no working directory, so "what I ran in this folder" is approximated from project type, git state and `package.json`/`Makefile`, not recorded per folder.
- The secret filter is a set of regexes. It catches common patterns, not everything; do not treat it as a guarantee.
- Multi-line commands are skipped. Weights are hand-tuned, not learned.
- Everything stays local. Nothing is sent anywhere.

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```

## Licence

MIT, see [LICENSE](LICENSE).
