# BMO - Balkan Mathematical Olympiad

Data processing pipeline for the Balkan Mathematical Olympiad.

## Data Sources

Years available online (`sigma download bmo ...` fetches these):

- 2008: `https://matematickitalent.mk/uploads/books/i77ZsGyCqEeVJ_JkreZPuw.pdf` (PDF bulletin with a complete ranking on pages 42–44)
- 2018: `https://bmo2018.dms.rs/results/` (HTML)
- 2020: `https://bmo2020.ssmr.ro/.../results_bmov.pdf` (PDF)
- 2021: `https://cdn.b3web.xyz/.../BMO2021-Medalsforwebsite.pdf` (PDF)
- 2022: `https://cdn.b3web.xyz/.../BMO2022results_Medals.pdf` (PDF)
- 2023: `https://bmo2023.tubitak.gov.tr/results` (HTML)
- 2024: `https://bmo2024.org/results/` (HTML)
- 2025: `https://bmo2025.pmf.unsa.ba/.../BMO2025-Official-Results.pdf` (PDF)

Years available offline only (raw files bundled under `data/bmo/raw/<year>/`):

- 2005: `BalkanResults.xls` — one-sheet workbook with per-problem scores, totals, and medals.
- 2009: `RESULTS_BMO_2009.pdf` — BMO 2009 official ranking PDF.
- 2010: `Official_Results_BMO_2010.pdf` — official ranking PDF from math.md/bmo2010/.
- 2011: `results.html` — BMO 2011 official results from bmo-2011.info (Iași).
- 2013: `Medals_BMO_2013__Members_.pdf` + `Medals_BMO_2013__Guests_.pdf` — **medalists only** (no non-medalists, no per-problem scores, no totals).
- 2014: `individual-results.pdf` — 3-page ranking PDF from the Bulgarian organiser (no Medal column).
- 2015: HTML dump — per-country score tables (`sgXXX.htm`) merged with per-country team rosters (`teamXXX.htm`) plus the aggregate medal-tier pages (`gold.htm`, `silver.htm`, `bronze.htm`, `mentions.htm`).
- 2016: `bmo2016_results.pdf` — PDF with first-name/last-name separate columns.
- 2017: `results-total.html` — HTML ranking table (the accompanying scanned PDF is image-only and not parseable).
- 2019: `results.html` — single ranking table from bmo2019.md.

## Excluded Years

| Year | Reason |
|------|--------|
| 2006 | Only totals and medals are in the Wayback snapshot — per-problem scores were never archived. |
| 2007 | Source only publishes contestant codes (`ALB1`, `ROM2`, …), not names. |
| 2012 | No accessible source with full results found. |

Raw 2006 and 2007 files are kept under `data/bmo/raw/{year}/` in case a better source appears; they are not parsed.

### Partial data years

2013 is ingested but is **medalists-only** — the source PDFs list only the 67 medal winners (40 official + 27 guests), with no per-problem scores and no totals. Every 2013 contestant has `problem_scores=[None, None, None, None]` and a placeholder `total=0`; only `rank`, `award`, `name`, and `country` are real. Useful for cross-edition person matching; misleading for any query that reads the total.

## Usage

Three-stage pipeline:

```bash
# 1. Fetch (for online years) or sanity-check bundled files (pass-through years)
sigma download bmo -d data/ --year 2025

# 2. Parse raw files into JSON
sigma parse bmo -d data/ --year 2025

# 3. Ingest parsed JSON into the database
sigma ingest bmo -d data/ -o data/olympiad_data.json --year 2025
```

## Competition Format

- 4 problems, 10 points each (max 40)
- Awards: Gold, Silver, Bronze, Honourable Mention
- Some years additionally publish a "Special Prize" for elegant solutions; this is not ingested as a medal.

## Country Codes

BMO data uses a mix of IOC codes, ISO-3166 alpha-3 codes, and historical codes.
The parser normalises these into a canonical form (`canonical_team_code`) and
the ingester resolves them to ISO alpha-3 via `BMO_CODE_MAPPING`.

### IOC / historical → ISO

| Raw code | Mapped to | Note |
|----------|-----------|------|
| `BUL` | `BGR` | Bulgaria (IOC) |
| `GRE`, `HEL` | `GRC` | Greece |
| `ROM` | `ROU` | Romania (IOC) |
| `MLD` | `MDA` | Moldova (2005/2006 spelling) |
| `MCD`, `FYR`, `FRM`, `FYROM` | `MKD` | Macedonia (various spellings across years) |
| `MON`, `MNG` | `MNE` | Montenegro (2008/2007 abbreviations) |
| `UNK`, `UNKIRL` | `GBR` | United Kingdom (UNKIRL = UK+Ireland combined team, 2008) |
| `YAC` | `RUS` | Yakutia / Sakha, Russia (2005 invited regional team) |
| `BRN` | `CZE` | Brno (Czech regional team, 2006/2009 invited) |
| `AZB` | `AZE` | Azerbaijan (2007 spelling) |
| `KTA` | `QAT` | Qatar observers (2017; Qatari contestants with Al-* family names) |

### Secondary (B) teams

Hosts and a handful of invited delegations fielded two squads. The parser
collapses the various raw spellings into a canonical `XYZB` form, and the
ingester flags these as `is_secondary_team=True` while resolving the base
country.

| Raw code | Mapped to | Note |
|----------|-----------|------|
| `TURB` | `TUR` | Turkey B |
| `ROMB`, `ROM A/B`, `ROMnA` | `ROU` | Romania B (ROM A = main host squad; ROM B / ROMnA = secondary) |
| `SRBB` | `SRB` | Serbia B |
| `MKDA`, `MKDB`, `MKDnA`, `MKDnB` | `MKD` | Macedonia A = main, B = secondary |
| `MDAB`, `MDA2_N` | `MDA` | Moldova B (host second team, 2010 / 2019) |
| `BGRB`, `BGR B` | `BGR` | Bulgaria B (2014 host bonus team) |
| `HELB` | `GRC` | Greece B (2015 host bonus team) |
| `ALBB`, `ALB-B` | `ALB` | Albania B (2016 host bonus team) |

## Notes

- Name-ordering conventions vary per edition and per country. Each year-specific parser declares its own `_SURNAME_FIRST_COUNTRIES` set and flips those through the shared `split_name()` helper, which also absorbs particles (`Von Burg`, `Al Saeed`) into the family name.
- 2010 prints names in a mix of Surname-Given (SRB, BGR, HEL, CYP, ITA, KAZ, MDA, MNE, SAU, TJK, TKM) and Given-Surname (ALB, AZE, FRA, MKD, ROU, TUR, UNK).
- 2011 has one contestant (MNE2 Oleg Cmiljanić) with all-blank per-problem cells; stored as total 0.
- 2013 is medalists-only (see the "Partial data years" note above) — `total=0` is a placeholder, not a real score.
- 2014 has no Medal column in the source PDF — awards are stored as `None` for every contestant.
- 2015 is reconstructed from a fragmented HTML site: scores come from `sg<country>.htm`, names from the matching `team<country>.htm` (by `<li>` position), and medals from the aggregate tier pages. The naming between `sg` and `team` files is not consistent (e.g. `sgmng`/`teammont`, `sgbih`/`teamboz`, `sgunk`/`teamuk`).
- 2017's HTML tags a stray "MKD3" code for one contestant where the rest of the delegation uses "MKDA<n>" / "MKDB<n>"; both map to Macedonia either way.
