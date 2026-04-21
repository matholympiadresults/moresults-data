# RMM - Romanian Masters of Mathematics

Data processing pipeline for the Romanian Masters of Mathematics competition.

## Data Source

- URL: `https://rmms.lbi.ro/rmm{YYYY}/index.php?id=results_math`
- Years available online: 2011, 2012-2013, 2015-2021, 2023-present
- Years available offline only (place files under `data/rmm/raw/{year}/`):
  - 2008: `rmm_2008.html` — original results page (4 problems, split-name HTML)
  - 2009: `rmm_2009.xls` — 2nd edition Excel (4 problems)
  - 2010: `rmm_2010.xls` — 3rd edition Excel (6 problems, "Individual" sheet)
- Missing years: 2014, 2022 (not available)

## Usage

Use the `sigma` CLI for the three-stage pipeline:

```bash
# 1. Download raw HTML from rmms.lbi.ro
sigma download rmm -d data/ --year 2024

# 2. Parse HTML into structured JSON
sigma parse rmm -d data/ --year 2024

# 3. Ingest parsed data into database
sigma ingest rmm -d data/ -o data/olympiad_data.json --year 2024
```

### Download Options

```bash
sigma download rmm --help

# Download single year
sigma download rmm -d data/ --year 2025

# Download range of years
sigma download rmm -d data/ --from 2020 --to 2025

# Force re-download existing files
sigma download rmm -d data/ --force
```

### Parse Options

```bash
sigma parse rmm --help

# Parse single year
sigma parse rmm -d data/ --year 2025

# Force re-parse existing files
sigma parse rmm -d data/ --force
```

### Ingest Options

```bash
sigma ingest rmm --help

# Ingest specific years
sigma ingest rmm -d data/ -o data/olympiad_data.json --year 2024 --year 2025
```

## Competition Format

- 4 problems in 2008-2009 (P1-P4), 6 problems from 2010 onwards (P1-P6)
- Maximum 7 points per problem
- Awards: GOLD, SILVER, BRONZE, HON. MEN. (Honorable Mention)

## Country Codes

RMM uses various country codes, some of which are non-standard:

### Standard ISO Codes
| Code | Country |
|------|---------|
| BGR | Bulgaria |
| BLR | Belarus |
| BRA | Brazil |
| CHN | China |
| FRA | France |
| GEO | Georgia |
| HRV | Croatia |
| HUN | Hungary |
| IDN | Indonesia |
| IND | India |
| IRN | Iran |
| ISR | Israel |
| ITA | Italy |
| KOR | South Korea |
| MDA | Moldova |
| MEX | Mexico |
| PER | Peru |
| POL | Poland |
| ROU | Romania |
| RUS | Russia |
| SRB | Serbia |
| SVN | Slovenia |
| UKR | Ukraine |
| USA | United States |

### Legacy/Alternative Codes
| Code | Meaning |
|------|---------|
| BRZ | Brazil (older format) |
| BUL | Bulgaria (older format) |
| ROM | Romania (older format) |

### Special Team Codes
| Code | Meaning |
|------|---------|
| TBT | The Baltic Team (combined Baltic states) |
| TND | The Nordic Team (combined Nordic countries) |
| UNK | United Kingdom |
| VIANU | Colegiul National "Tudor Vianu" (Romanian school team) |
| VIANU2 | Tudor Vianu secondary school team (2010) |
| ROMA | Romania A Team (2009, ingested as main ROU) |
| ROMB / ROUB | Romania B Team |
| ROMF | Romania F Team (girls team) |
| YAKUTSK | Yakutsk regional delegation (2008, mapped to RUS) |

## Notes

- Online contestants (remote participants) are scraped but not ingested
- The `is_official_team` flag indicates contestants marked with `*` in the results
- Country codes in older years (2012-2013) used format like "CHN1" while newer years use "CHN 1"
