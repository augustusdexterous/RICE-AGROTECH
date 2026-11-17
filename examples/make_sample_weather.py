"""Write a synthetic daily weather file for a tropical wet season (NOT observed data).

Temperatures follow a seasonal curve with noise. Rain is a seeded random monsoon pattern.
Use it to try the tool; replace it with a real station record for any decision.

    python examples/make_sample_weather.py examples/sample_weather.csv
"""

import csv
import math
import sys
from datetime import date, timedelta

import numpy as np


def main(path: str) -> None:
    rng = np.random.default_rng(2026)
    start = date(2026, 6, 1)
    rows = []
    for i in range(190):
        d = start + timedelta(days=i)
        season = math.sin(2 * math.pi * i / 365.0)
        tmax = 31.0 + 1.5 * season + rng.normal(0, 1.0)
        tmin = 23.0 + 0.8 * season + rng.normal(0, 0.8)
        wet = 0.55 + 0.25 * math.sin(math.pi * i / 190.0)  # wetter mid-season
        rain = float(rng.gamma(0.6, 9.0)) if rng.random() < wet else 0.0
        rows.append([d.isoformat(), f"{min(tmin, tmax - 0.5):.1f}", f"{tmax:.1f}", f"{rain:.1f}"])
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "tmin", "tmax", "rain"])
        writer.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "examples/sample_weather.csv")
