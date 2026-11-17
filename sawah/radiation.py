"""Extraterrestrial radiation and reference evapotranspiration (FAO-56 forms).

Allen, Pereira, Raes and Smith (1998), FAO Irrigation and Drainage Paper 56.
"""

from __future__ import annotations

import math

_GSC = 0.0820  # solar constant, MJ m^-2 min^-1
_MJ_PER_MM = 2.45  # latent heat of vaporization expressed as MJ per kg, used to convert to mm of water
TEMPERATURE_RANGE_C = (-90.0, 60.0)  # bounds for daily air temperature, degrees C; keeps tmax - tmin finite


def extraterrestrial_radiation(lat_deg: float, doy: int) -> float:
    """Daily extraterrestrial radiation Ra in MJ m^-2 day^-1.

    lat_deg : latitude in degrees, north positive, limited to [-60, 60] for tropical rice.
    doy : day of year, 1..366.
    """
    if not -60.0 <= lat_deg <= 60.0:
        raise ValueError("latitude must be between -60 and 60 degrees for this model")
    if not 1 <= doy <= 366:
        raise ValueError("day of year must be between 1 and 366")
    phi = math.radians(lat_deg)
    angle = 2.0 * math.pi * doy / 365.0
    dr = 1.0 + 0.033 * math.cos(angle)  # inverse relative distance Earth-Sun
    delta = 0.409 * math.sin(angle - 1.39)  # solar declination, radians
    x = -math.tan(phi) * math.tan(delta)
    x = max(-1.0, min(1.0, x))  # polar day or night is clipped to the limits
    ws = math.acos(x)  # sunset hour angle, radians
    return (
        (24.0 * 60.0 / math.pi)
        * _GSC
        * dr
        * (ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))
    )


def et0_hargreaves(tmin: float, tmax: float, lat_deg: float, doy: int) -> float:
    """Reference evapotranspiration ET0 in mm per day (Hargreaves-Samani, 1985).

    Needs only temperature, so it suits fields without wind or humidity records.
    Expect roughly 3 to 7 mm per day in tropical conditions.
    """
    if not (math.isfinite(tmin) and math.isfinite(tmax)):
        raise ValueError("temperatures must be finite")
    if tmax < tmin:
        raise ValueError("tmax must not be below tmin")
    lo, hi = TEMPERATURE_RANGE_C
    if not (lo <= tmin <= hi and lo <= tmax <= hi):
        raise ValueError(f"temperatures must be between {lo:.0f} and {hi:.0f} C")
    tmean = 0.5 * (tmin + tmax)
    ra_mm = extraterrestrial_radiation(lat_deg, doy) / _MJ_PER_MM
    et0 = 0.0023 * (tmean + 17.8) * math.sqrt(tmax - tmin) * ra_mm
    return max(0.0, et0)  # negative only for mean temperatures below -17.8 C; ET cannot be negative
