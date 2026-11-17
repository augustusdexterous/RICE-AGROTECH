import csv
from pathlib import Path

import pytest

from sawah.cli import main

SAMPLE = str(Path(__file__).resolve().parent.parent / "examples" / "sample_weather.csv")


def test_report_runs_on_the_sample_season(capsys):
    assert main([SAMPLE, "--lat", "14.5", "--planting", "2026-06-15"]) == 0
    out = capsys.readouterr().out
    assert "water-limited yield" in out
    assert "vegetative" in out and "flowering" in out and "grain filling" in out


def test_daily_file_is_written_with_a_header(tmp_path, capsys):
    target = tmp_path / "daily.csv"
    assert main([SAMPLE, "--lat", "14.5", "--planting", "2026-06-15", "--daily", str(target)]) == 0
    with open(target, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and {"date", "stage", "etc", "eta", "storage"} <= set(rows[0].keys())


def test_bad_latitude_and_planting_date_return_exit_code_two(capsys):
    assert main([SAMPLE, "--lat", "80", "--planting", "2026-06-15"]) == 2
    assert main([SAMPLE, "--lat", "14.5", "--planting", "2030-01-01"]) == 2
    assert "not in the weather record" in capsys.readouterr().err


def test_json_output_is_valid_and_matches_the_report(capsys):
    import json

    assert main([SAMPLE, "--lat", "14.5", "--planting", "2026-06-15", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["matured"] is True
    assert data["maturity_date"] == "2026-10-04"
    assert [s["name"] for s in data["stages"]] == ["vegetative", "flowering", "grain filling"]
    assert data["water_limited_yield_t_ha"] == pytest.approx(7.129, abs=1e-3)
