# JBMO (Junior Balkan Mathematical Olympiad)

The JBMO has been held annually since 1997. Each year is hosted by a different
Balkan country and results are published on a separate website.

## Included Years

| Year | Source | Contestants | Format | Notes |
|------|--------|-------------|--------|-------|
| 2010 | fmi.unibuc.ro/jbmo2010 (Wayback Machine) | 93 | PDF | 60 official + 31 invited + 2 reserve. Old-style country codes (BUL, ROM, FYR). |
| 2012 | hms.gr/16jbmo2012 (Wayback Machine) | 89 | HTML | Non-standard medal labels (FIRST/SECOND/THIRD). Mixed name formats. |
| 2013 | jbmo2013.tubitak.gov.tr | 114 | HTML | Complete: names, per-problem scores, awards. Separate Name/Surname columns. |
| 2014 | jbmo2014.smm.com.mk (Wayback Machine) | 104 | HTML | Mixed-case names. Includes guest countries (Iran, France). |
| 2015 | dms.rs/jbmo/results | 106 | HTML (Excel-generated) | Separate First/Last name columns. Country names instead of codes. |
| 2016 | jbmo.ssmr.ro/results | 122 | HTML | Space-separated country codes (e.g. "TUR 1", "ROU B 2"). |
| 2021 | jbmo2021.ance.gov.md | 128 | HTML (per-country pages) | Complete: names, per-problem scores, awards |
| 2023 | jbmo2023.al | 114 | PDF + HTML team pages | 108 named, 6 unnamed (Greece 404, partial Kyrgyzstan/Tajikistan) |
| 2024 | jbmo2024.tubitak.gov.tr | 135 | HTML | Complete: names, per-problem scores, awards |

## Excluded Years

| Year | Reason |
|------|--------|
| 2011 | No discoverable online results. |
| 2017 | No discoverable online results. |
| 2018 | No discoverable online results. |
| 2019 | No discoverable online results. |
| 2020 | No contestant names in any published source. PDFs use anonymous codes (e.g. `BGR4`). COVID online edition. |
| 2022 | Results PDF only includes medalists (~81 of ~110). Non-medalists missing entirely (no scores, no names). |
| 2025 | No per-problem scores published. Only total points available. |

## Adding Future Years

See the main project [CLAUDE.md](../../../CLAUDE.md) for the general process.
Each year needs its own downloader in `downloader/downloaders/dl_YYYY.py` and
parser in `parser/parsers/`, since JBMO websites vary by year.
