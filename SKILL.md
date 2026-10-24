---
name: cliprompt
description: Suggest the shell command the user is likely to run next, using their shell history, the current directory and git state. Use when the user asks what to run, wants a command they ran before, or asks for a completion of a partial command.
---

# cliprompt

`cliprompt` ranks commands from the user's own shell history against the current
directory (project type, `package.json` scripts, Makefile targets) and git state
(staged, ahead, behind, clean). It needs `pip install -e .` from this repository first.

## When to use it

- The user asks "what do I usually run here?" or "what was that command?".
- The user typed the start of a command and wants it completed from history.
- Before proposing a build, test or deploy command, to match what they already use.

## How to use it

```bash
cliprompt --format json -n 5            # best commands for this directory
cliprompt --format json -- git c        # complete a partial command
cliprompt stats --json                  # what the user runs most
```

The JSON has `context` (cwd, project kinds, git summary) and `suggestions`, each with
`command`, `score`, `count` and `reasons`. Use `--format markdown` for a ready-made
list to show the user.

## Rules

- Suggest commands; do not run them without the user agreeing.
- Exit code 1 means nothing matched; exit code 2 means the history file could not be
  read (use `-f PATH` to point at one). Say so instead of guessing a command.
- Commands containing credentials are filtered out. Do not pass `--include-secrets`
  unless the user asks for it.
