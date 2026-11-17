"""Daily season simulation: thermal time, crop water use, water stress and a water-limited yield.

Water is a single root-zone store in mm, starting at capacity after land preparation. Each
day, rain is added. If irrigation is enabled and the water left after rain is below the stress
threshold or the day's crop demand, the store is refilled to capacity, or to the demand if that
is larger, so irrigated days meet the full crop demand. The crop takes Ks * Kc * ET0, limited to
the water available, and anything above capacity drains.

Stress: Ks = available / threshold below the threshold, 1 at or above it, with threshold =
stress_fraction * capacity and available = store + rain + irrigation for the day. In FAO-56
terms stress_fraction = 1 - p, where p is the depletion fraction (FAO-56 uses p = 0.5 for most
crops, which equals the default here). FAO-56 itself bases Ks on the start-of-day depletion; this
model judges it on the water available after the day's inputs. A water-stress day is one where
ETa falls below ETc, so a refilled day is stressed only if the water left after rain and irrigation
falls short of the threshold or of the day's ETc.

Yield: Y = potential_yield * (1 - Ky * (1 - ETa / ETc)), clipped to [0, potential_yield]
(FAO-33 water-yield response). Ky = 1.1 is an approximate value for rice. The yield is only
reported for seasons that reach maturity inside the weather record.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from .radiation import TEMPERATURE_RANGE_C, et0_hargreaves
from .thermal import CULTIVAR_GDD, STAGE_KC, daily_gdd, stage_for

HOT_DAY_TMAX = 35.0  # daily maximum at or above which spikelet sterility risk is flagged, degrees C
MAX_DAILY_RAIN = 2000.0  # mm; far beyond any recorded daily rainfall, so larger values are input errors
STRESS_TOLERANCE_MM = 1e-9  # absorbs float rounding when refilled water exactly meets the day's demand


@dataclass(frozen=True)
class Day:
    date: date
    tmin: float
    tmax: float
    rain: float


@dataclass(frozen=True)
class StageSpan:
    name: str
    start: date
    end: date


@dataclass
class SeasonResult:
    planting: date
    cultivar: str
    total_gdd: float
    matured: bool
    maturity_date: date | None
    stages: list
    et0_total: float = 0.0
    etc_total: float = 0.0
    eta_total: float = 0.0
    rain_total: float = 0.0
    irrigation_total: float = 0.0
    drainage_total: float = 0.0
    stress_days: int = 0
    hot_flowering_days: int = 0
    water_factor: float = 1.0
    potential_yield: float = 0.0
    water_limited_yield: float | None = None  # None unless the crop matured in the record
    daily: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Season summary as plain types (no daily rows), for JSON output and other tools."""
        return {
            "planting": self.planting.isoformat(),
            "cultivar": self.cultivar,
            "total_gdd": self.total_gdd,
            "matured": self.matured,
            "maturity_date": self.maturity_date.isoformat() if self.maturity_date else None,
            "stages": [
                {"name": s.name, "start": s.start.isoformat(), "end": s.end.isoformat()} for s in self.stages
            ],
            "rain_mm": round(self.rain_total, 2),
            "et0_mm": round(self.et0_total, 2),
            "etc_mm": round(self.etc_total, 2),
            "eta_mm": round(self.eta_total, 2),
            "irrigation_mm": round(self.irrigation_total, 2),
            "drainage_mm": round(self.drainage_total, 2),
            "stress_days": self.stress_days,
            "hot_flowering_days": self.hot_flowering_days,
            "water_factor": round(self.water_factor, 4),
            "potential_yield_t_ha": self.potential_yield,
            "water_limited_yield_t_ha": None
            if self.water_limited_yield is None
            else round(self.water_limited_yield, 3),
        }


def _validate(
    days: Sequence[Day],
    lat_deg: float,
    cultivar: str,
    potential_yield: float,
    water_capacity: float,
    stress_fraction: float,
    ky: float,
) -> None:
    if cultivar not in CULTIVAR_GDD:
        raise ValueError(f"cultivar must be one of {sorted(CULTIVAR_GDD)}")
    if not -60.0 <= lat_deg <= 60.0:
        raise ValueError("latitude must be between -60 and 60 degrees for this model")
    if not (math.isfinite(potential_yield) and potential_yield > 0):
        raise ValueError("potential_yield must be a positive number in t/ha")
    if not (math.isfinite(water_capacity) and water_capacity > 0):
        raise ValueError("water_capacity must be a positive number in mm")
    if not 0.0 < stress_fraction < 1.0:
        raise ValueError("stress_fraction must be between 0 and 1")
    if not (math.isfinite(ky) and ky > 0):
        raise ValueError("ky must be a positive number")
    if not days:
        raise ValueError("the weather record is empty")
    for day in days:
        if not all(math.isfinite(v) for v in (day.tmin, day.tmax, day.rain)):
            raise ValueError(f"{day.date}: temperatures and rain must be finite numbers")
        lo, hi = TEMPERATURE_RANGE_C
        if not (lo <= day.tmin <= hi and lo <= day.tmax <= hi):
            raise ValueError(f"{day.date}: temperatures must be between {lo:.0f} and {hi:.0f} C")
        if day.tmax <= day.tmin:
            raise ValueError(f"{day.date}: tmax must be greater than tmin")
        if day.rain < 0:
            raise ValueError(f"{day.date}: rain cannot be negative")
        if day.rain > MAX_DAILY_RAIN:
            raise ValueError(f"{day.date}: rain above {MAX_DAILY_RAIN:.0f} mm in one day is not plausible")
    for a, b in zip(days, days[1:]):
        if b.date <= a.date:
            raise ValueError("weather days must be in chronological order")
        if b.date - a.date != timedelta(days=1):
            raise ValueError(f"weather days must be consecutive; gap after {a.date}")


def run_season(
    days: Sequence[Day],
    lat_deg: float,
    planting: date,
    cultivar: str = "medium",
    potential_yield: float = 8.0,
    irrigate: bool = False,
    water_capacity: float = 100.0,
    stress_fraction: float = 0.5,
    ky: float = 1.1,
) -> SeasonResult:
    """Simulate one season from ``planting`` until maturity or the end of the weather record."""
    _validate(days, lat_deg, cultivar, potential_yield, water_capacity, stress_fraction, ky)
    starts = [i for i, d in enumerate(days) if d.date == planting]
    if not starts:
        raise ValueError(f"planting date {planting} is not in the weather record")
    start = starts[0]
    total = CULTIVAR_GDD[cultivar]
    threshold = stress_fraction * water_capacity

    result = SeasonResult(
        planting=planting,
        cultivar=cultivar,
        total_gdd=total,
        matured=False,
        maturity_date=None,
        stages=[],
        potential_yield=potential_yield,
    )
    storage = water_capacity
    cumulative = 0.0
    current_stage = None
    stage_start = None
    last_date = planting

    for day in days[start:]:
        stage = stage_for(cumulative, total)
        if stage == "mature":
            result.matured = True
            result.maturity_date = day.date
            break
        if stage != current_stage:
            if current_stage is not None:
                result.stages.append(StageSpan(current_stage, stage_start, last_date))
            current_stage, stage_start = stage, day.date

        doy = day.date.timetuple().tm_yday
        et0 = et0_hargreaves(day.tmin, day.tmax, lat_deg, doy)
        etc = STAGE_KC[stage] * et0

        # The day's rain comes first. If irrigation is enabled and the water left after rain is below
        # the stress threshold or the day's crop demand, the store is refilled to capacity, or to the
        # demand if that is larger, so irrigated days meet the full ETc. Stress is judged on the water
        # available after these inputs.
        pre = storage + day.rain
        irrigation = 0.0
        if irrigate and pre < max(threshold, etc):
            irrigation = max(water_capacity, etc) - pre
        available = pre + irrigation
        ks = 1.0 if available >= threshold else available / threshold
        eta = min(ks * etc, available)
        pre_drain = available - eta
        drainage = max(0.0, pre_drain - water_capacity)
        storage = min(pre_drain, water_capacity)

        result.et0_total += et0
        result.etc_total += etc
        result.eta_total += eta
        result.rain_total += day.rain
        result.irrigation_total += irrigation
        result.drainage_total += drainage
        if eta < etc - STRESS_TOLERANCE_MM:  # the crop received less water than its demand
            result.stress_days += 1
        if stage == "flowering" and day.tmax >= HOT_DAY_TMAX:
            result.hot_flowering_days += 1
        result.daily.append(
            {
                "date": day.date.isoformat(),
                "stage": stage,
                "tmin": day.tmin,
                "tmax": day.tmax,
                "rain": day.rain,
                "et0": et0,
                "etc": etc,
                "irrigation": irrigation,
                "eta": eta,
                "drainage": drainage,
                "storage": storage,
            }
        )

        cumulative += daily_gdd(day.tmin, day.tmax)
        last_date = day.date
        if cumulative >= total:
            result.matured = True
            result.maturity_date = day.date
            result.stages.append(StageSpan(current_stage, stage_start, day.date))
            current_stage = None
            break

    if current_stage is not None:
        result.stages.append(StageSpan(current_stage, stage_start, last_date))

    if result.etc_total > 0:
        result.water_factor = max(0.0, min(1.0, 1.0 - ky * (1.0 - result.eta_total / result.etc_total)))
    if result.matured:
        result.water_limited_yield = potential_yield * result.water_factor
    return result
