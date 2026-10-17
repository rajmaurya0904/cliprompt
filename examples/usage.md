# Usage Examples

This file demonstrates advanced configuration and workflow patterns for **Cliprompt**.

## 1. Custom Prompt Template

Cliprompt allows you to override the default prompt that is sent to Claude.  The
`--prompt-template` flag accepts a Jinja‑style template.  The template can refer to
variables that are automatically populated by the engine:

* `history` – a list of the last *N* commands.
* `cwd` – the current working directory.
* `env` – a dictionary of environment variables.

```bash
cliprompt --prompt-template "{{ cwd }}$ {{ history[-1] }}"
```

The above will ask Claude to continue the last command in the current directory.

## 2. Persisting History Across Sessions

By default Cliprompt stores history in a temporary file.  To keep a persistent
history you can set the `CLIPROMPT_HISTORY_FILE` environment variable:

```bash
export CLIPROMPT_HISTORY_FILE=~/.cliprompt_history
cliprompt
```

Now every invocation will read from and write to `~/.cliprompt_history`.

## 3. Using a Custom Model

If you have access to a different Claude model you can specify it with the
`--model` flag:

```bash
cliprompt --model claude-3-haiku-20240307
```

The engine will automatically use the chosen model for all completions.

## 4. Batch Mode

Cliprompt can process a list of commands from a file and output the suggested
completions.  Create a file `commands.txt`:

```
git status
python -m venv venv
pip install -r requirements.txt
```

Run in batch mode:

```bash
cliprompt --batch commands.txt
```

The output will be a numbered list of completions, one per line.

## 5. Integrating with a Shell Prompt

You can embed Cliprompt directly in your shell prompt by adding the following to
`.bashrc` or `.zshrc`:

```bash
function _cliprompt_prompt() {
  local suggestion=$(cliprompt --last-command)
  if [[ -n $suggestion ]]; then
    echo -e "\e[32m$ suggestion\e[0m"
  fi
}

PROMPT_COMMAND=_cliprompt_prompt
```

Now after each command the shell will display the suggested next command in
green.

---

These examples cover the most common advanced use‑cases.  For a full list of
options run `cliprompt --help`.
