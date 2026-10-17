# Cliprompt

**A Claude Code skill that suggests command-line completions based on recent history and context, reducing typing.**

Repeatedly typing the same command-line flags, arguments, or sequences wastes time and breaks focus. Cliprompt learns from your recent history to suggest completions that fit the current context, so you spend less time recalling syntax and more time getting work done.

## Example

<!-- A real command and its REAL pasted output. Run it first. -->

## Install

```bash
pip install -e ".[dev]"
```

## Usage

<!-- The 2-4 commands people actually need, one line each. -->

## How it works

<!-- 3-6 bullets: what it checks, computes or produces. -->

## Limitations

Currently, cliprompt supports Bash and Zsh shells. It does not yet support Fish or PowerShell. The tool reads your local shell history to generate suggestions, which remains private and is not transmitted externally. However, it does not analyze the content of commands for sensitive information beyond what is necessary for completion suggestions.

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```

## License

MIT -- see [LICENSE](LICENSE).
