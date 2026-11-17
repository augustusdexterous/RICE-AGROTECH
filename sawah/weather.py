"""Reading daily weather CSV files: columns date,tmin,tmax,rain (rain in mm).

Accepts UTF-8 with or without a byte-order mark, and comma-separated values. The header must be
the first line. Rows may be in any order; they are sorted by date. Duplicate dates, duplicate
column names and rows with more values than the header are rejected. Dates must be written
YYYY-MM-DD on every Python version.
"""

from __future__ import annotations

import csv
import math
import re
from datetime import date

from .season import Day

REQUIRED = ("date", "tmin", "tmax", "rain")
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def parse_date(text: str) -> date:
    """Parse a date written YYYY-MM-DD. Basic-format dates such as 20260601 are rejected."""
    if not _ISO_DATE.fullmatch(text):
        raise ValueError(f"date must be written YYYY-MM-DD, got {text!r}")
    return date.fromisoformat(text)


def load_weather(path: str) -> list[Day]:
    try:
        return _load(path)
    except UnicodeDecodeError:
        raise ValueError(f"{path} is not UTF-8 text; save it as a UTF-8 CSV file") from None


def _load(path: str) -> list[Day]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        header_line = fh.readline()
        if not header_line:
            raise ValueError("weather file is empty")
        if not header_line.strip():
            raise ValueError("line 1 is blank; the header row must be the first line")
        if ";" in header_line and "," not in header_line:
            raise ValueError("the file looks semicolon-separated; use comma-separated values")
        fh.seek(0)
        return _read_days(csv.reader(fh))


def _records(reader):
    """Yield (first line, fields) for each record that is not blank.

    csv does not report where a record starts, so a record starts on the line after the previous
    one ended. This keeps error messages pointing at the first line of a record.
    """
    line = reader.line_num
    while True:
        start = line + 1
        try:
            fields = next(reader)
        except StopIteration:
            return
        except csv.Error as exc:
            raise ValueError(f"line {start}: malformed CSV ({exc})") from None
        line = reader.line_num
        if fields:
            yield start, fields


def _read_days(reader) -> list[Day]:
    records = _records(reader)
    try:
        _, header = next(records)
    except StopIteration:
        raise ValueError("weather file is empty") from None
    columns: dict[str, int] = {}
    for index, name in enumerate(header):
        key = name.strip().lower()
        if not key:
            continue
        if key in columns:
            raise ValueError(f"line 1: duplicate column {key!r} (headers are case-insensitive)")
        columns[key] = index
    missing = [c for c in REQUIRED if c not in columns]
    if missing:
        raise ValueError(f"weather file is missing columns: {', '.join(missing)}")
    days: list[Day] = []
    seen: set[date] = set()
    for number, fields in records:
        if len(fields) > len(header):
            raise ValueError(f"line {number}: {len(fields)} values but the header has {len(header)} columns")
        cells = {}
        for column in REQUIRED:
            index = columns[column]
            value = fields[index].strip() if index < len(fields) else ""
            if not value:
                raise ValueError(f"line {number}: missing value in column {column!r}")
            cells[column] = value
        try:
            d = parse_date(cells["date"])
            tmin = float(cells["tmin"])
            tmax = float(cells["tmax"])
            rain = float(cells["rain"])
        except ValueError as exc:
            raise ValueError(f"line {number}: invalid date or number ({exc})") from None
        if not all(math.isfinite(v) for v in (tmin, tmax, rain)):
            raise ValueError(f"line {number}: values must be finite")
        if tmax <= tmin:
            raise ValueError(f"line {number}: tmax must be greater than tmin")
        if rain < 0:
            raise ValueError(f"line {number}: rain cannot be negative")
        if d in seen:
            raise ValueError(f"line {number}: duplicate date {d}")
        seen.add(d)
        days.append(Day(d, tmin, tmax, rain))
    days.sort(key=lambda day: day.date)
    if not days:
        raise ValueError("weather file has no data rows")
    return days
