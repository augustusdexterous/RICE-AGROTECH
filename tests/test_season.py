from datetime import date, timedelta

import pytest

from sawah import Day, run_season

LAT = 14.5
START = date(2026, 6, 1)


def _days(n, tmin=23.0, tmax=31.0, rain=0.0, start=START):
    return [Day(start + timedelta(days=i), tmin, tmax, rain(i) if callable(rain) else rain) for i in range(n)]


def test_water_balance_closes_every_day_and_over_the_season():
    days = _days(200, rain=lambda i: 12.0 if i % 4 == 0 else 0.0)
    res = run_season(days, LAT, START, irrigate=True)
    storage = 100.0
    for row in res.daily:
        inflow = row["rain"] + row["irrigation"]
        assert storage + inflow - row["eta"] - row["drainage"] - row["storage"] == pytest.approx(
            0.0, abs=1e-9
        )
        storage = row["storage"]
    total_in = res.rain_total + res.irrigation_total
    end_storage = res.daily[-1]["storage"]
    assert total_in - res.eta_total - res.drainage_total - (end_storage - 100.0) == pytest.approx(
        0.0, abs=1e-6
    )


def test_wet_season_has_no_stress_and_reaches_potential_yield():
    res = run_season(_days(200, rain=60.0), LAT, START, potential_yield=8.0)
    assert res.stress_days == 0
    assert res.water_factor == pytest.approx(1.0)
    assert res.water_limited_yield == pytest.approx(8.0)
    assert res.drainage_total > 0


def test_dry_season_is_water_limited():
    res = run_season(_days(200, rain=0.0), LAT, START, potential_yield=8.0)
    assert res.stress_days > 0
    assert res.water_factor < 1.0
    assert res.water_limited_yield < 8.0


def test_yield_rises_with_rainfall():
    dry = run_season(_days(200, rain=2.0), LAT, START).water_limited_yield
    moist = run_season(_days(200, rain=5.0), LAT, START).water_limited_yield
    wet = run_season(_days(200, rain=9.0), LAT, START).water_limited_yield
    assert dry < moist <= wet


def test_irrigation_never_lowers_the_water_factor():
    days = _days(200, rain=1.0)
    rainfed = run_season(days, LAT, START, irrigate=False)
    irrigated = run_season(days, LAT, START, irrigate=True)
    assert irrigated.irrigation_total > 0
    assert irrigated.water_factor >= rainfed.water_factor


def test_water_factor_follows_the_ky_response_formula():
    res = run_season(_days(200, rain=0.5), LAT, START, ky=1.1)
    expected = max(0.0, min(1.0, 1.0 - 1.1 * (1.0 - res.eta_total / res.etc_total)))
    assert res.water_factor == pytest.approx(expected, rel=1e-12)


def test_maturity_and_incomplete_seasons():
    # 30/22 gives a mean of 26 C, so 16 GDD a day; 2000 GDD needs 125 days.
    done = run_season(_days(200, tmin=22.0, tmax=30.0, rain=20.0), LAT, START, cultivar="medium")
    assert done.matured
    assert done.maturity_date == START + timedelta(days=124)
    short = run_season(_days(60, tmin=22.0, tmax=30.0, rain=20.0), LAT, START, cultivar="medium")
    assert not short.matured
    assert short.maturity_date is None


def test_stage_spans_are_contiguous_and_ordered():
    res = run_season(_days(200, tmin=22.0, tmax=30.0, rain=20.0), LAT, START)
    names = [s.name for s in res.stages]
    assert names == ["vegetative", "flowering", "grain filling"]
    for a, b in zip(res.stages, res.stages[1:]):
        assert b.start == a.end + timedelta(days=1)
    assert res.stages[0].start == START


def test_hot_flowering_days_are_counted_only_during_flowering():
    days = _days(200, tmin=22.0, tmax=30.0, rain=20.0)
    flowering = next(s for s in run_season(days, LAT, START).stages if s.name == "flowering")
    # Make only the flowering days hot. Hotter days also add thermal time, so the stage
    # dates change; measure the stage in the modified run itself.
    hot = [Day(d.date, 26.0, 36.0, d.rain) if flowering.start <= d.date <= flowering.end else d for d in days]
    res = run_season(hot, LAT, START)
    span = next(s for s in res.stages if s.name == "flowering")
    expected = (span.end - span.start).days + 1
    assert res.hot_flowering_days == expected
    assert res.hot_flowering_days > 0


def test_planting_outside_the_record_is_an_error():
    with pytest.raises(ValueError, match="not in the weather record"):
        run_season(_days(50), LAT, date(2030, 1, 1))


def test_gaps_in_the_weather_record_are_an_error():
    days = _days(10)
    del days[4]
    with pytest.raises(ValueError, match="consecutive"):
        run_season(days, LAT, START)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cultivar": "giant"},
        {"potential_yield": 0.0},
        {"water_capacity": -1.0},
        {"stress_fraction": 1.2},
        {"ky": 0.0},
    ],
)
def test_invalid_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        run_season(_days(50), LAT, START, **kwargs)


def test_latitude_limits_are_enforced():
    with pytest.raises(ValueError, match="latitude"):
        run_season(_days(50), 75.0, START)
