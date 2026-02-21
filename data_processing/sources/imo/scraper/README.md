# IMO Data Scraper

Scrapes International Mathematical Olympiad (IMO) individual results from [imo-official.org](https://www.imo-official.org/).

## Setup

From the repository root:

```bash
uv sync
```

## Usage

Use the `sigma` CLI to download, parse, and ingest IMO data:

```bash
# Download raw data
sigma download imo -d data/ --year 2024

# Download a range of years
sigma download imo -d data/ --from 2020 --to 2024

# Parse raw data
sigma parse imo -d data/ --year 2024

# Ingest into database
sigma ingest imo -d data/ -o data/olympiad_data.json --year 2024
```

## Options

| Option | Description |
|--------|-------------|
| `-d`, `--data-dir` | Base data directory (required) |
| `--year` | Process a single specific year |
| `--from` | Start year |
| `--to` | End year |
| `--force` | Re-download/re-parse existing files |
