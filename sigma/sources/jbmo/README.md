# JBMO (Junior Balkan Mathematical Olympiad)

The JBMO has been held annually since 1997. Each year is hosted by a different
Balkan country and results are published on a separate website.

## Included Years

| Year | Source | Contestants | Format | Notes |
|------|--------|-------------|--------|-------|
| 2021 | jbmo2021.ance.gov.md | 128 | HTML (per-country pages) | Complete: names, per-problem scores, awards |
| 2023 | jbmo2023.al | 114 | PDF + HTML team pages | 108 named, 6 unnamed (Greece 404, partial Kyrgyzstan/Tajikistan) |
| 2024 | jbmo2024.tubitak.gov.tr | 135 | HTML | Complete: names, per-problem scores, awards |

## Excluded Years

| Year | Reason |
|------|--------|
| 2020 | No contestant names in any published source. PDFs use anonymous codes (e.g. `BGR4`). COVID online edition. |
| 2022 | Results PDF only includes medalists (~81 of ~110). Non-medalists missing entirely (no scores, no names). |
| 2025 | No per-problem scores published. Only total points available. |

## Adding Future Years

See the main project [CLAUDE.md](../../../CLAUDE.md) for the general process.
Each year needs its own downloader in `downloader/downloaders/dl_YYYY.py` and
parser in `parser/parsers/`, since JBMO websites vary by year.
