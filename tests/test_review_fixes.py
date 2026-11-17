"""Regression tests for defects found in review. Each one failed before its fix."""

from datetime import date, timedelta

import pytest

from sawah import Day, load_weather, run_season
from sawah.cli import main

LAT = 14.5
START = date(2026, 6, 1)


def _days(n, rain=0.0, tmin=22.0, tmax=30.0):
    return [Day(START + timedelta(days=i), tmin, tmax, rain) for i in range(n)]


def test_nan_rain_is_rejected_by_the_api_instead_of_giving_full_yield():
    days = _days(200, rain=20.0)
    days[10] = Day(days[10].date, 22.0, 30.0, float("nan"))
    with pytest.raises(ValueError, match="finite"):
        run_season(days, LAT, START)


def test_negative_rain_is_rejected_by_the_api():
    days = _days(200, rain=20.0)
    days[3] = Day(days[3].date, 22.0, 30.0, -5.0)
    with pytest.raises(ValueError, match="negative"):
        run_season(days, LAT, START)


def test_zero_temperature_range_is_rejected():
    days = _days(200)
    days[0] = Day(days[0].date, 27.0, 27.0, 0.0)
    with pytest.raises(ValueError, match="greater than tmin"):
        run_season(days, LAT, START)


def test_irrigation_is_not_counted_for_water_that_drains_the_same_day():
    # One very wet day: the refill must not claim water that then drains away.
    days = [Day(START + timedelta(days=i), 22.0, 30.0, 150.0 if i == 5 else 0.0) for i in range(30)]
    res = run_season(days, LAT, START, irrigate=True)
    for row in res.daily:
        if row["drainage"] > 0:
            assert row["irrigation"] == pytest.approx(0.0)
    storage = 100.0
    for row in res.daily:
        assert storage + row["rain"] + row["irrigation"] - row["eta"] - row["drainage"] - row[
            "storage"
        ] == pytest.approx(0.0, abs=1e-9)
        storage = row["storage"]


def test_irrigated_days_are_not_counted_as_stress_days():
    res = run_season(_days(120, rain=0.0), LAT, START, irrigate=True)
    refilled = [row for row in res.daily if row["irrigation"] > 0]
    assert refilled
    assert all(row["eta"] == pytest.approx(row["etc"]) for row in refilled)


def test_water_limited_yield_is_withheld_when_the_crop_does_not_mature():
    res = run_season(_days(5, rain=20.0), LAT, START, potential_yield=8.0)
    assert not res.matured
    assert res.water_limited_yield is None


def test_cli_says_yield_is_not_estimated_for_a_truncated_season(tmp_path, capsys):
    p = tmp_path / "short.csv"
    rows = [f"{(START + timedelta(days=i)).isoformat()},22,30,0" for i in range(5)]
    p.write_text("date,tmin,tmax,rain\n" + "\n".join(rows) + "\n")
    assert main([str(p), "--lat", "14.5", "--planting", START.isoformat()]) == 0
    assert "not estimated" in capsys.readouterr().out


def test_unsorted_input_is_reported_as_ordering_not_as_a_gap():
    days = list(reversed(_days(20)))
    with pytest.raises(ValueError, match="chronological order"):
        run_season(days, LAT, START)


def test_weather_file_with_a_byte_order_mark_loads(tmp_path):
    p = tmp_path / "bom.csv"
    p.write_bytes("﻿date,tmin,tmax,rain\n2026-06-01,23,31,0\n".encode())
    assert len(load_weather(str(p))) == 1


def test_short_row_gives_a_line_number_error(tmp_path):
    p = tmp_path / "short.csv"
    p.write_text("date,tmin,tmax,rain\n2026-06-01,23,31\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2: missing value in column 'rain'"):
        load_weather(str(p))


def test_semicolon_file_gets_a_helpful_message(tmp_path):
    p = tmp_path / "semi.csv"
    p.write_text("date;tmin;tmax;rain\n2026-06-01;23;31;0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="semicolon-separated"):
        load_weather(str(p))


def _storm_season(rain, irrigate=True):
    """A dry spell that drops storage below the threshold, then one storm day."""
    base = [Day(START + timedelta(days=i), 22.0, 30.0, 0.0) for i in range(60)]
    dry = run_season(base, LAT, START, irrigate=False)
    storm = next(i for i in range(1, len(dry.daily)) if dry.daily[i - 1]["storage"] < 50.0)
    days = [Day(d.date, d.tmin, d.tmax, rain if i == storm else 0.0) for i, d in enumerate(base)]
    return run_season(days, LAT, START, irrigate=irrigate), storm


def test_rain_that_refills_the_store_is_not_a_stress_day():
    res, storm = _storm_season(80.0)
    row = res.daily[storm]
    assert res.daily[storm - 1]["storage"] < 50.0  # the store really was below the threshold
    assert row["eta"] == pytest.approx(row["etc"])
    assert row["irrigation"] == pytest.approx(0.0)


def test_stress_does_not_flip_with_small_changes_in_rain():
    # More rain must never make the crop more stressed on the same day.
    etas = []
    for rain in (53.80, 53.87, 53.89, 53.95):
        res, storm = _storm_season(rain)
        row = res.daily[storm]
        etas.append(row["eta"] / row["etc"])
    assert all(ratio == pytest.approx(1.0) for ratio in etas)


def test_yield_follows_the_formula_for_another_potential_and_a_partial_factor():
    res = run_season(_days(200, rain=1.0), LAT, START, potential_yield=6.5, ky=1.1)
    assert res.matured
    assert 0.0 < res.water_factor < 1.0
    assert res.water_limited_yield == pytest.approx(6.5 * res.water_factor, rel=1e-12)
