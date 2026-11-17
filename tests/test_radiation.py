import math

import pytest

from sawah import et0_hargreaves, extraterrestrial_radiation


def test_radiation_at_equator_on_equinox_is_about_38_mj():
    assert 37.0 <= extraterrestrial_radiation(0.0, 80) <= 38.5


def test_radiation_at_40n_midsummer_is_within_the_reference_band():
    assert 40.5 <= extraterrestrial_radiation(40.0, 172) <= 43.0


def test_radiation_is_higher_in_summer_than_winter_at_high_latitude():
    assert extraterrestrial_radiation(50.0, 172) > extraterrestrial_radiation(50.0, 355) > 0


def test_southern_summer_radiation_exceeds_northern_summer_because_of_perihelion():
    # Earth is closest to the Sun in early January, so December is brighter than June
    # at the same latitude magnitude.
    assert extraterrestrial_radiation(-30.0, 355) > extraterrestrial_radiation(30.0, 172)


def test_radiation_rejects_out_of_range_inputs():
    with pytest.raises(ValueError):
        extraterrestrial_radiation(70.0, 100)
    with pytest.raises(ValueError):
        extraterrestrial_radiation(10.0, 0)
    with pytest.raises(ValueError):
        extraterrestrial_radiation(10.0, 367)


def test_hargreaves_matches_its_formula_term_by_term():
    tmin, tmax, lat, doy = 24.0, 32.0, 14.0, 170
    ra_mm = extraterrestrial_radiation(lat, doy) / 2.45
    expected = 0.0023 * ((tmin + tmax) / 2 + 17.8) * math.sqrt(tmax - tmin) * ra_mm
    assert et0_hargreaves(tmin, tmax, lat, doy) == pytest.approx(expected, rel=1e-12)


def test_hargreaves_is_in_the_tropical_range_for_typical_days():
    assert 3.0 <= et0_hargreaves(24.0, 32.0, 14.0, 170) <= 7.0


def test_hargreaves_is_zero_when_the_temperature_range_is_zero():
    assert et0_hargreaves(27.0, 27.0, 10.0, 100) == 0.0


def test_hargreaves_rejects_bad_temperatures():
    with pytest.raises(ValueError):
        et0_hargreaves(30.0, 25.0, 10.0, 100)
    with pytest.raises(ValueError):
        et0_hargreaves(float("nan"), 30.0, 10.0, 100)
