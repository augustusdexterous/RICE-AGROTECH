"""Invariants on fixed and seeded random seasons, and regressions found in independent review."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta

import pytest

from sawah.cli import main
from sawah.radiation import et0_hargreaves
from sawah.season import MAX_DAILY_RAIN, STRESS_TOLERANCE_MM, Day, run_season
from sawah.thermal import CULTIVAR_GDD
from sawah.weather import load_weather, parse_date

START = date(2026, 5, 1)


def _days(n, tmin=22.0, tmax=30.0, rain=0.0):
    return [Day(START + timedelta(days=i), tmin, tmax, rain) for i in range(n)]


def _write_csv(path, rows, header="date,tmin,tmax,rain"):
    path.write_text(header + "\n" + "".join(rows), encoding="utf-8")


def _random_season(rng):
    n = rng.randint(60, 240)
    days = []
    for i in range(n):
        tmin = rng.uniform(10.0, 26.0)
        tmax = tmin + rng.uniform(2.0, 16.0)
        rain = 0.0 if rng.random() < 0.6 else rng.uniform(0.0, 60.0)
        days.append(Day(START + timedelta(days=i), tmin, tmax, rain))
    kwargs = {
        "lat_deg": rng.uniform(-20.0, 20.0),
        "planting": START,
        "cultivar": rng.choice(sorted(CULTIVAR_GDD)),
        "potential_yield": rng.uniform(2.0, 10.0),
        "irrigate": rng.random() < 0.5,
        "water_capacity": rng.uniform(3.0, 150.0),
        "stress_fraction": rng.uniform(0.05, 0.95),
        "ky": rng.uniform(0.5, 1.5),
    }
    return days, kwargs


def test_random_seasons_hold_the_water_balance_invariants():
    rng = random.Random(20260617)
    for _ in range(300):
        days, kwargs = _random_season(rng)
        res = run_season(days, **kwargs)
        capacity = kwargs["water_capacity"]
        storage_prev = capacity
        stress = 0
        for row in res.daily:
            inflow = storage_prev + row["rain"] + row["irrigation"]
            assert row["eta"] + row["drainage"] + row["storage"] == pytest.approx(inflow, abs=1e-9)
            assert -1e-12 <= row["storage"] <= capacity + 1e-9
            assert row["eta"] <= row["etc"] + 1e-9
            assert row["eta"] <= inflow + 1e-9
            if row["irrigation"] > 0:
                assert row["eta"] == pytest.approx(row["etc"], abs=1e-9)
            if row["eta"] < row["etc"] - STRESS_TOLERANCE_MM:
                stress += 1
            storage_prev = row["storage"]
        assert res.stress_days == stress
        assert 0.0 <= res.water_factor <= 1.0
        if res.matured:
            assert res.water_limited_yield == pytest.approx(kwargs["potential_yield"] * res.water_factor)
        else:
            assert res.water_limited_yield is None


def test_storage_never_goes_negative_with_a_small_stress_threshold():
    res = run_season(_days(60), lat_deg=14.5, planting=START, water_capacity=10.0, stress_fraction=0.1)
    assert min(row["storage"] for row in res.daily) >= 0.0


def test_irrigated_days_meet_full_demand_even_when_the_root_zone_is_small():
    res = run_season(_days(200), lat_deg=14.5, planting=START, irrigate=True, water_capacity=3.0)
    assert res.stress_days == 0
    assert res.eta_total == pytest.approx(res.etc_total)
    assert res.water_factor == pytest.approx(1.0)


def test_small_root_zone_without_irrigation_is_counted_as_stress():
    res = run_season(_days(200, rain=3.0), lat_deg=14.5, planting=START, water_capacity=3.0)
    assert res.stress_days > 0
    assert res.stress_days == sum(1 for row in res.daily if row["eta"] < row["etc"] - STRESS_TOLERANCE_MM)
    assert res.water_factor < 1.0


def test_refilled_store_that_falls_short_of_demand_is_a_stress_day():
    days = _days(11)  # ten dry days drain the store to zero
    days[10] = Day(days[10].date, 22.0, 30.0, 2.5)
    res = run_season(days, lat_deg=14.5, planting=START, water_capacity=10.0, stress_fraction=0.2)
    row = res.daily[10]
    assert row["eta"] == pytest.approx(2.5)
    assert row["eta"] < row["etc"] - STRESS_TOLERANCE_MM


def test_rain_that_covers_demand_is_not_a_stress_day():
    days = _days(11)
    days[10] = Day(days[10].date, 22.0, 30.0, 6.0)
    res = run_season(days, lat_deg=14.5, planting=START, water_capacity=10.0, stress_fraction=0.2)
    row = res.daily[10]
    assert row["eta"] == pytest.approx(row["etc"])


@pytest.mark.parametrize("potential", [1.0, 4.0, 6.5, 8.0, 10.0, 12.0])
@pytest.mark.parametrize("ky", [0.8, 1.1, 1.3])
def test_yield_follows_fao33_for_several_potentials_and_ky(potential, ky):
    res = run_season(
        _days(200, rain=1.0),
        lat_deg=14.5,
        planting=START,
        cultivar="early",
        potential_yield=potential,
        ky=ky,
    )
    assert res.matured
    expected = potential * (1.0 - ky * (1.0 - res.eta_total / res.etc_total))
    assert res.water_limited_yield == pytest.approx(expected, rel=1e-9)


def test_rain_above_a_plausible_daily_total_is_rejected():
    days = _days(10)
    days[3] = Day(days[3].date, 22.0, 30.0, MAX_DAILY_RAIN + 1.0)
    with pytest.raises(ValueError, match="plausible"):
        run_season(days, lat_deg=14.5, planting=START)


def test_temperatures_outside_the_plausible_range_are_rejected():
    days = _days(10)
    days[4] = Day(days[4].date, -1e308, 1e308, 0.0)
    with pytest.raises(ValueError, match="between"):
        run_season(days, lat_deg=14.5, planting=START)


def test_summary_is_strict_json_for_large_but_valid_totals():
    res = run_season(_days(200, rain=1900.0), lat_deg=14.5, planting=START)
    json.dumps(res.to_dict(), allow_nan=False)


def test_reference_et_is_not_negative_in_extreme_cold():
    assert et0_hargreaves(-30.0, -10.0, 14.0, 150) == 0.0


def test_reference_et_rejects_overflowing_temperatures():
    with pytest.raises(ValueError, match="between"):
        et0_hargreaves(-1e308, 1e308, 14.0, 150)


def test_duplicate_column_names_differing_only_by_case_are_rejected(tmp_path):
    path = tmp_path / "w.csv"
    _write_csv(path, ["2026-06-01,23,31,0,5\n"], header="date,tmin,tmax,rain,Rain")
    with pytest.raises(ValueError, match="duplicate column"):
        load_weather(str(path))


def test_malformed_csv_is_reported_as_a_value_error_with_a_line_number(tmp_path):
    path = tmp_path / "nul.csv"
    path.write_bytes(b"date,tmin,tmax,rain\n2026-06-01,23,31,1.0\x00\n")
    with pytest.raises(ValueError, match="line 2"):
        load_weather(str(path))

    path = tmp_path / "long.csv"
    path.write_bytes(b"date,tmin,tmax,rain\n2026-06-01," + b"9" * 200_000 + b",31,1\n")
    with pytest.raises(ValueError, match="line 2"):
        load_weather(str(path))


def test_rows_with_more_values_than_the_header_are_rejected(tmp_path, capsys):
    path = tmp_path / "w.csv"
    _write_csv(path, ["2026-06-01,23,31,1,5\n"])  # a decimal comma in the rain value
    with pytest.raises(ValueError, match="line 2"):
        load_weather(str(path))
    assert main([str(path), "--lat", "14.5", "--planting", "2026-06-01"]) == 2


def test_blank_first_line_is_reported_as_such(tmp_path):
    path = tmp_path / "w.csv"
    path.write_text("\ndate,tmin,tmax,rain\n2026-06-01,23,31,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1 is blank"):
        load_weather(str(path))


def test_non_utf8_file_gets_a_clear_message(tmp_path):
    path = tmp_path / "w.csv"
    path.write_bytes(b"date,tmin,tmax,rain\n2026-06-01,23,31,\xff\n")
    with pytest.raises(ValueError, match="UTF-8"):
        load_weather(str(path))


def test_utf8_bom_and_crlf_line_endings_are_accepted(tmp_path):
    path = tmp_path / "w.csv"
    path.write_bytes(b"\xef\xbb\xbfdate,tmin,tmax,rain\r\n2026-06-01,23,31,1\r\n2026-06-02,23,31,0\r\n")
    days = load_weather(str(path))
    assert [d.rain for d in days] == [1.0, 0.0]


def test_dates_must_be_written_yyyy_mm_dd_on_every_python_version():
    assert parse_date("2026-06-01") == date(2026, 6, 1)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_date("20260601")


def test_cli_rejects_a_basic_format_planting_date_with_exit_code_2(tmp_path, capsys):
    path = tmp_path / "w.csv"
    _write_csv(path, [f"{d.date.isoformat()},{d.tmin},{d.tmax},{d.rain}\n" for d in _days(10)])
    assert main([str(path), "--lat", "14.5", "--planting", "20260501"]) == 2
    assert "YYYY-MM-DD" in capsys.readouterr().err
