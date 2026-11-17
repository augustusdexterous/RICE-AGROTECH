"""Command line: ``sawah weather.csv --lat 14.5 --planting 2026-06-15``."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys

from .season import SeasonResult, run_season
from .thermal import CULTIVAR_GDD
from .weather import load_weather, parse_date


def _print_report(result: SeasonResult) -> None:
    print(
        f"planting           : {result.planting}  cultivar: {result.cultivar} "
        f"({result.total_gdd:.0f} GDD to maturity)"
    )
    print("stages:")
    for span in result.stages:
        print(f"  {span.name:<15} {span.start} to {span.end}")
    if result.matured:
        print(f"maturity           : {result.maturity_date}")
    else:
        print("maturity           : not reached within the weather record (no yield estimate)")
    print(f"rain               : {result.rain_total:8.1f} mm")
    print(f"ET0 (reference)    : {result.et0_total:8.1f} mm")
    print(f"ETc (potential)    : {result.etc_total:8.1f} mm")
    print(f"ETa (actual)       : {result.eta_total:8.1f} mm")
    print(f"irrigation applied : {result.irrigation_total:8.1f} mm")
    print(f"drainage           : {result.drainage_total:8.1f} mm")
    print(f"water stress days  : {result.stress_days}")
    print(f"hot flowering days : {result.hot_flowering_days} (tmax >= 35 C during flowering)")
    print(f"water factor       : {result.water_factor:.3f}")
    if result.water_limited_yield is None:
        print("water-limited yield: not estimated (maturity is outside the weather record)")
    else:
        print(
            f"water-limited yield: {result.water_limited_yield:.2f} t/ha "
            f"(potential {result.potential_yield:.2f} t/ha)"
        )


def _write_daily(result: SeasonResult, path: str) -> None:
    if not result.daily:
        raise ValueError("no daily rows to write")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(result.daily[0].keys()))
        writer.writeheader()
        writer.writerows(result.daily)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sawah",
        description="Rice season planning estimates from daily weather.",
    )
    parser.add_argument("weather", help="CSV with columns date,tmin,tmax,rain (rain in mm)")
    parser.add_argument("--lat", type=float, required=True, help="latitude in degrees, north positive")
    parser.add_argument("--planting", required=True, help="planting date, YYYY-MM-DD")
    parser.add_argument("--cultivar", choices=sorted(CULTIVAR_GDD), default="medium")
    parser.add_argument("--potential-yield", type=float, default=8.0, help="potential yield in t/ha")
    parser.add_argument(
        "--irrigate",
        action="store_true",
        help="refill the root zone when it drops below the stress threshold or the day's crop demand",
    )
    parser.add_argument(
        "--water-capacity", type=float, default=100.0, help="root-zone storage at capacity, mm"
    )
    parser.add_argument(
        "--stress-fraction",
        type=float,
        default=0.5,
        help="storage fraction of capacity below which crop stress starts (FAO-56: 1 - p)",
    )
    parser.add_argument("--daily", metavar="PATH", help="also write the daily simulation to this CSV")
    parser.add_argument("--json", action="store_true", help="print the season summary as JSON")
    args = parser.parse_args(argv)
    if not (math.isfinite(args.lat) and -60.0 <= args.lat <= 60.0):
        print("error: --lat must be between -60 and 60 degrees", file=sys.stderr)
        return 2
    try:
        planting = parse_date(args.planting)
        days = load_weather(args.weather)
        result = run_season(
            days,
            args.lat,
            planting,
            cultivar=args.cultivar,
            potential_yield=args.potential_yield,
            irrigate=args.irrigate,
            water_capacity=args.water_capacity,
            stress_fraction=args.stress_fraction,
        )
        if args.daily:
            _write_daily(result, args.daily)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        _print_report(result)
    return 0
