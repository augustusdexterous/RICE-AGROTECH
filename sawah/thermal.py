"""Thermal time (growing degree days) and rice development stages.

The base and cap temperatures and the stage split are planning assumptions, not measured
cultivar constants. Calibrate them with local phenology records before relying on dates.
"""

from __future__ import annotations

T_BASE = 10.0  # development stops below this mean temperature, degrees C
T_CAP = 35.0  # development stops increasing above this mean temperature, degrees C

# Thermal time from planting to physiological maturity, growing degree days above T_BASE.
CULTIVAR_GDD = {"early": 1500.0, "medium": 2000.0, "late": 2400.0}

# Stage boundaries as fractions of the total thermal time, and crop coefficients (Kc)
# for each stage. Kc values are approximate, following the FAO-56 range for rice.
STAGE_END_FRACTION = (("vegetative", 0.60), ("flowering", 0.68), ("grain filling", 1.00))
STAGE_KC = {"vegetative": 1.10, "flowering": 1.20, "grain filling": 0.90}


def daily_gdd(tmin: float, tmax: float) -> float:
    """Growing degree days for one day, using the mean temperature with base and cap."""
    tmean = 0.5 * (tmin + tmax)
    capped = min(max(tmean, T_BASE), T_CAP)
    return capped - T_BASE


def stage_for(cumulative_gdd: float, total_gdd: float) -> str:
    """Development stage at a given cumulative thermal time."""
    if cumulative_gdd >= total_gdd:
        return "mature"
    fraction = cumulative_gdd / total_gdd
    for name, end in STAGE_END_FRACTION:
        if fraction < end:
            return name
    return "grain filling"
