# MOResults Data

Math Olympiad data processing tools.

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
# Ingest a single source
sigma ingest egmo -d data/ -o data/olympiad_data.json --year 2024

# Ingest all data from a source
sigma ingest imo -d data/ -o data/olympiad_data.json

# Ingest all sources at once
sigma ingest-all -d data/ -o data/olympiad_data.json
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
# Process EGMO 2024 data end-to-end
sigma download egmo -d data/ --year 2024
sigma parse egmo -d data/ --year 2024
sigma ingest egmo -d data/ -o data/olympiad_data.json --year 2024
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
