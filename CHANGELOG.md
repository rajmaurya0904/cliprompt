# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-10-17
### Added
- Initial release of **cliprompt** providing command-line completion suggestions based on shell history and context.
- Implemented package metadata and versioning.
- Added history reader, context analyzer, suggestion engine, and CLI entry point.
- Registered console script `cliprompt`.
- Comprehensive test suite covering history parsing, context extraction, engine suggestions, and CLI behavior.

### Tasks Completed
- Configure project metadata and dependencies.
- Create package `__init__` with version.
- Implement `cliprompt/history.py` for reading shell history.
- Implement `cliprompt/context.py` for gathering environment context.
- Implement `cliprompt/engine.py` for generating suggestions.
- Implement `cliprompt/cli.py` with argument parsing and entry point.
- Register script in `pyproject.toml`.
- Add robust error handling for empty or corrupt history.
- Provide full test coverage for all modules.
