# AGENTS.md — Guidance for Codex

## Testing
- Always run `pytest -q` before committing.
- All tests must pass.

## Linting
- Use `black` + `mypy`. Run `black . && mypy` locally before committing.

## Geo stack quirks
- Never upgrade GDAL or PROJ versions inside the sandbox; stick with those from the setup script.
- For Earth Engine calls, mock them in unit tests (`tests/conftest.py` holds stubs).

## Commit style
- Conventional Commits: feat:, fix:, chore:, docs:

## Response and code quality
- Ensure responses are clear and accurate.
- Generated code must follow modern best practices, include type hints and docstrings,
  and adhere to OOP principles.
  - Aim for production-ready quality in all code snippets.

## Integration principles
- Follow `docs/development_principles.md` for OOP and cloud-oriented
  design guidelines.
- Reuse existing helpers such as `convert_to_cog` and the `StorageAdapter`
  abstractions instead of duplicating functionality.
- New CLI commands should operate on all AOIs by default and use service
  classes rather than embedding logic directly in the CLI.
