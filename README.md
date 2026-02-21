# MOResults Data

Math Olympiad data processing and preservation.

## Why This Exists

Math olympiad results are scattered across various websites that often disappear after a few years. Competition organizers change, domains expire, and valuable historical data is lost forever. This repository aims to preserve this information by:

1. **Archiving raw data** - Original HTML, PDF, and CSV files from official sources
2. **Structuring the data** - Parsed into consistent JSON formats
3. **Building a unified database** - All competitions in one queryable format

## Philosophy

The data pipeline has three stages with different purposes:

| Stage | Purpose | Frequency |
|-------|---------|-----------|
| **download** | Fetch raw files from source websites | Once per competition (archived) |
| **parse** | Convert raw files to structured JSON | Re-run when parser improves |
| **ingest** | Combine into unified database | Re-run when schema changes |

Raw data (`data/<source>/raw/`) is the source of truth and should never be modified. If a parser has bugs, fix the parser and re-run `parse` + `ingest`. This separation ensures we never lose original data even as our processing improves.

**On ingestion:** Always rebuild the database from scratch using `sigma ingest-all`. Person and country IDs are assigned in encounter order, so partial or out-of-order ingestion produces different IDs. This ensures deterministic, reproducible output.

**On storing data in git:** Yes, git isn't ideal for data storage - it increases bundle size and wasn't designed for this. But we're optimizing for simplicity and pragmatism over perfection. The data changes slowly (a few competitions per year), the total size is manageable (~50MB), and keeping everything in one repo means no external dependencies, no broken links, no expired cloud storage. Clone the repo and you have everything.

## Installation

```bash
uv sync
```

## CLI Usage

The `sigma` CLI provides commands to download, parse, and ingest math olympiad data.

### Data Pipeline

The data flows through three stages:

1. **download** - Fetch raw data (HTML, PDF, CSV) to `<data-dir>/<source>/raw/<year>/`
2. **parse** - Parse raw data to `<data-dir>/<source>/parsed/<year>/`
3. **ingest** - Ingest parsed data into the JSON database

### Available Sources

- `apmo` - Asian Pacific Mathematics Olympiad
- `bmo` - Balkan Mathematical Olympiad
- `egmo` - European Girls' Mathematical Olympiad
- `imo` - International Mathematical Olympiad
- `memo` - Middle European Mathematical Olympiad
- `pamo` - Pan African Mathematics Olympiad
- `rmm` - Romanian Master of Mathematics

### Commands

#### Download raw data

```bash
# Download a single year
sigma download egmo -d data/ --year 2024

# Download a range of years
sigma download imo -d data/ --from 2010 --to 2024

# Force re-download
sigma download memo -d data/ --year 2023 --force
```

#### Parse raw data

```bash
# Parse a single year
sigma parse egmo -d data/ --year 2024

# Parse all available years
sigma parse imo -d data/

# Parse multiple specific years
sigma parse memo -d data/ --year 2022 --year 2023 --year 2024
```

#### Ingest into database

```bash
# Rebuild the full database (always use this for committing)
sigma ingest-all -d data/ -o data/olympiad_data.json

# Ingest a single source/year (for quick testing only)
sigma ingest egmo -d data/ -o /tmp/test.json --year 2024
```

#### View information

```bash
# Show info for a specific year
sigma info egmo 2024 -d data/

# Show database summary
sigma summary data/olympiad_data.json
```

### Full Example

```bash
# Add new year of EGMO data
sigma download egmo -d data/ --year 2024
sigma parse egmo -d data/ --year 2024

# Rebuild the full database
sigma ingest-all -d data/ -o data/olympiad_data.json
sigma summary data/olympiad_data.json
```

## Development

```bash
# Run linting
uv run ruff check .

# Run formatter
uv run ruff format .

# Run tests
uv run pytest
```
