import pytest

from sawah import daily_gdd, stage_for
from sawah.thermal import CULTIVAR_GDD


def test_daily_gdd_uses_the_mean_and_the_base_temperature():
    assert daily_gdd(20.0, 30.0) == pytest.approx(15.0)  # mean 25, base 10


def test_no_development_below_base_temperature():
    assert daily_gdd(4.0, 12.0) == 0.0  # mean 8


def test_development_stops_increasing_above_the_cap():
    assert daily_gdd(40.0, 40.0) == pytest.approx(25.0)  # mean 40, capped at 35


def test_stage_boundaries_follow_the_fractions_of_thermal_time():
    total = 2000.0
    assert stage_for(0.0, total) == "vegetative"
    assert stage_for(0.59 * total, total) == "vegetative"
    assert stage_for(0.60 * total, total) == "flowering"
    assert stage_for(0.67 * total, total) == "flowering"
    assert stage_for(0.68 * total, total) == "grain filling"
    assert stage_for(total, total) == "mature"


def test_cultivar_table_is_ordered_early_to_late():
    assert CULTIVAR_GDD["early"] < CULTIVAR_GDD["medium"] < CULTIVAR_GDD["late"]
