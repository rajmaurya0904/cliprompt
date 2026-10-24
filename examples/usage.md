# Usage examples

All of these use the sample history in this folder, so you can run them as they are.

## Try it on the sample history

```bash
cliprompt -f examples/zsh_history_sample                 # best commands for this directory
cliprompt -f examples/zsh_history_sample --explain       # with the reasons
cliprompt -f examples/zsh_history_sample -- git c        # complete "git c"
```

## Use another shell's history

```bash
cliprompt -s bash -f ~/.bash_history
cliprompt -s fish -f ~/.local/share/fish/fish_history
cliprompt -s powershell -f "$env:APPDATA/Microsoft/Windows/PowerShell/PSReadLine/ConsoleHost_history.txt"
```

Without `-f`, `$HISTFILE` is used, then the newest of the usual locations.

## Score against a different directory

```bash
cliprompt --cwd ~/code/web-app --explain    # npm scripts and git state of that project
cliprompt --cwd /tmp --no-git               # ignore git entirely
```

## Pipe it

```bash
cliprompt -n 1 git | head -1                # the single best git command
cliprompt --format json | python -m json.tool
cliprompt stats --json | python -c "import json,sys; print(json.load(sys.stdin)['entries'])"
```

## Shell glue

Print the top suggestion on demand from bash or zsh:

```bash
alias next='cliprompt -n 1 --format plain'
```

In PowerShell:

```powershell
function next { cliprompt -n 1 --format plain }
```

Bash only writes history on exit, so run `history -a` first if you want commands from the
current session to count.
