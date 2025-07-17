# AGENTS.md — Guidance for Codex

## Testing
- Always run `pytest -q` before committing.
- All tests must pass.

## Linting
- Use `black` + `flake8`. Run `black . && flake8` locally.

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
