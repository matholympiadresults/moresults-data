# BalcanMO Data Scraper

Scrapes Balkan Mathematical Olympiad (BMO) individual results from various official sources.

## Data Sources

| Year | URL | Format | Notes |
|------|-----|--------|-------|
| 2025 | https://bmo2025.pmf.unsa.ba/wp-content/uploads/2025/04/BMO2025-Official-Results.pdf | PDF | |
| 2024 | https://bmo2024.org/results/ | HTML | |
| 2023 | https://bmo2023.tubitak.gov.tr/results | HTML | |
| 2022 | https://cdn.b3web.xyz/web/cms/optimizedBMO2022results_Medals.pdf1652185269.pdf | PDF | |
| 2021 | https://cdn.b3web.xyz/web/cms/optimizedBMO2021-Medalsforwebsite.pdf1631272290.pdf | PDF | |
| 2020 | https://bmo2020.ssmr.ro/sites/bmo2020.ssmr.ro/files/results_bmov.pdf | PDF | Virtual BMO due to COVID-19 |
| 2018 | https://bmo2018.dms.rs/results/ | HTML | |

### Excluded Years

| Year | URL | Reason |
|------|-----|--------|
| 2015 | https://www.hms.gr/32bmo2015/ | Only contestant codes available (no names) |

## Setup

```bash
uv sync
```

For PDF parsing, ensure `pdfplumber` is installed (included in dependencies).

## Usage

Use the `sigma` CLI for the data pipeline:

```bash
# Download raw data
sigma download bmo -d data/ --year 2024

# Download a range of years
sigma download bmo -d data/ --from 2020 --to 2025

# Parse raw data
sigma parse bmo -d data/ --year 2024

# Ingest into database
sigma ingest bmo -d data/ -o data/olympiad_data.json --year 2024
```

### Full pipeline example

```bash
sigma download bmo -d data/ --from 2018 --to 2025
sigma parse bmo -d data/
sigma ingest bmo -d data/ -o data/olympiad_data.json
```

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `-d` | `--data-dir` | Base data directory (required) |
| `--year` | | Process a single specific year |
| `--from` | | Start year |
| `--to` | | End year |
| `--force` | | Re-download/re-parse existing files |

## Data Format

### Output JSON Structure

```json
{
  "year": 2024,
  "source_url": "https://bmo2024.org/results/",
  "source_type": "html",
  "total_contestants": 137,
  "results": [
    {
      "name": "John Doe",
      "country": "ROU",
      "problem_scores": [10, 10, 10, 10],
      "total": 40,
      "rank": 1,
      "award": "Gold"
    }
  ],
  "validation": {
    "all_totals_match": true,
    "mismatches": []
  }
}
```

### Competition Details

- **Problems**: 4 problems (P1-P4)
- **Max score per problem**: 10 points
- **Max total score**: 40 points
- **Awards**: Gold, Silver, Bronze, Honourable Mention

## Raw Data Storage

The scraper stores raw HTML and PDF files in the `--raw-data` directory:
- HTML files: `bmo_{year}_raw.html`
- PDF files: `bmo_{year}_raw.pdf`

This allows for:
- Avoiding repeated downloads
- Manual verification of source data
- Re-parsing if parser logic is updated

## Known Limitations

1. **Country codes**: Some years use full country names (e.g., "ROMANIA"), while others use codes (e.g., "ROU"). The data is preserved as-is from the source.

2. **2015 excluded**: The 2015 source (hms.gr) only contains contestant codes (e.g., TUR3, ROU1), not actual names, so it is excluded from the scraper.
