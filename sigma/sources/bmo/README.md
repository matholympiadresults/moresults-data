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

## Excluded Years

| Year | Reason |
|------|--------|
| 2006 | Only totals and medals are in the Wayback snapshot — per-problem scores were never archived, and re-deriving them from elsewhere isn't possible. |
| 2007 | Source only publishes contestant codes (`ALB1`, `ROM2`, …), not names. |
| 2012–2017 | No accessible source with full results found. |
| 2019 | No accessible source with full results found. |

Raw 2006 and 2007 files are kept under `data/bmo/raw/{2006,2007}/` in case a better source appears; they are not parsed.

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
| `MDAB`, `MDA2_N` | `MDA` | Moldova B (host second team, 2010) |

## Notes

- 2010 prints names in a mix of Surname-Given (SRB, BGR, HEL, CYP, ITA, KAZ, MDA, MNE, SAU, TJK, TKM) and Given-Surname (ALB, AZE, FRA, MKD, ROU, TUR, UNK) conventions. The parser flips the former so matching works across editions, and handles particles like "von Burg" and "Al Saeed" specifically.
- 2011 has one contestant (MNE2 Oleg Cmiljanić) with all-blank per-problem cells; stored as total 0.
