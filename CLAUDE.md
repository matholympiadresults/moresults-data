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

- `sigma/` - Python data processing modules
  - `sources/` - Data ingesters for various olympiads (APMO, BMO, EGMO, IMO, MEMO, PAMO, RMM)
  - `database/` - JSON database utilities
  - `matching/` - Person matching logic
  - `schemas/` - Pydantic models
  - `cli/` - Command-line interface
- `tests/` - Python tests
- `data/` - Raw data files (gitignored, generated at runtime)

## Comparing Database Changes

After modifying data or ingesters, compare the database before and after:

```bash
# Compare current DB against main branch
sigma compare <(git show origin/main:data/olympiad_data.json) data/olympiad_data.json

# Verbose mode to see individual added/removed keys
sigma compare <(git show origin/main:data/olympiad_data.json) data/olympiad_data.json -v
```

## Adding a New Year of Data

When a new competition year becomes available:

1. **Update the year range** in the source's downloader (e.g. `sigma/sources/rmm/downloader/rmm_downloader.py`) — bump the `AVAILABLE_YEARS` range upper bound.
2. **Download, parse, and rebuild**:
   ```bash
   sigma download <source> -d data/ --year <year>
   sigma parse <source> -d data/ --year <year>
   sigma ingest-all -d data/ -o data/olympiad_data.json
   ```
3. **Verify** with `sigma info <source> <year> -d data/` and compare the database.

## Package Manager

- Python: `uv` (see `pyproject.toml`)
