# Changelog

## 0.1.0

- Reads bash, zsh, fish and PowerShell (PSReadLine) history, including timestamps and multi-line entries.
- Ranks commands by frequency, recency, typed prefix, git state, project type, `package.json` scripts, Makefile targets and what usually follows the previous command.
- Never suggests commands that look like they contain credentials.
- `suggest`, `stats` and `context` subcommands; plain, colour, JSON and Markdown output.
- `SKILL.md` for use from Claude Code.
