# MOResults - Math Olympiad Data Processing

## Pre-push Checklist

Run these checks before pushing code:

```bash
# Lint check
uv run ruff check .

# Format check
uv run ruff format --check .

# Run tests
uv run pytest
```

To auto-fix issues:
```bash
uv run ruff check --fix .
uv run ruff format .
```

## Project Structure

- `data_processing/` - Python data processing modules
  - `sources/` - Data ingesters for various olympiads (APMO, BMO, EGMO, IMO, MEMO, PAMO, RMM)
  - `database/` - JSON database utilities
  - `matching/` - Person matching logic
  - `schemas/` - Pydantic models
  - `cli/` - Command-line interface
- `tests/` - Python tests
- `data/` - Raw data files (gitignored, generated at runtime)

## Package Manager

- Python: `uv` (see `pyproject.toml`)
