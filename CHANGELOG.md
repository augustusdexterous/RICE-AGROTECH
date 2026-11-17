# Changelog

## 0.1.0

- First release as **sawah** (formerly rice-agrotech).
- Growing degree days, growth stages with crop coefficients, FAO-56 radiation and Hargreaves ET0.
- Daily root-zone water balance with optional irrigation and drainage accounting.
- FAO-33 water-limited yield, reported only for seasons that mature in the record.
- Command line report, `--json` summary, `--daily` CSV export, and a Python API.
- Input validation: no silent NaN, negative rain, zero temperature range or disordered days. Rain above 2000 mm in one day, duplicate column names and basic-format dates (`20260601`) are rejected with a message.
- A water-stress day is one where ETa falls below ETc. On irrigated days the crop receives its full demand.
- Reference ET is never negative.
- Tests for the water balance, yield, input validation and command line; continuous integration on Python 3.9 to 3.13.
