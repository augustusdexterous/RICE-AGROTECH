"""Rice season planning from daily weather: growth stages, crop water use, water stress and
a water-limited yield estimate.

These are planning estimates from simplified models with literature-based defaults. They
are not a substitute for local agronomic advice, and the defaults should be calibrated
against field records before decisions depend on them.
"""

from .radiation import et0_hargreaves, extraterrestrial_radiation
from .season import Day, SeasonResult, StageSpan, run_season
from .thermal import CULTIVAR_GDD, daily_gdd, stage_for
from .weather import load_weather

__version__ = "0.1.0"

__all__ = [
    "CULTIVAR_GDD",
    "Day",
    "SeasonResult",
    "StageSpan",
    "__version__",
    "daily_gdd",
    "et0_hargreaves",
    "extraterrestrial_radiation",
    "load_weather",
    "run_season",
    "stage_for",
]
