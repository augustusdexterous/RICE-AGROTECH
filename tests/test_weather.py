import pytest

from sawah import load_weather


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_and_sorts_rows(tmp_path):
    p = _write(tmp_path / "w.csv", "date,tmin,tmax,rain\n2026-06-02,23,31,0\n2026-06-01,22,30,5.5\n")
    days = load_weather(str(p))
    assert [d.date.isoformat() for d in days] == ["2026-06-01", "2026-06-02"]
    assert days[0].rain == 5.5


def test_column_names_are_case_insensitive(tmp_path):
    p = _write(tmp_path / "w.csv", "Date,TMIN,TMAX,Rain\n2026-06-01,22,30,0\n")
    assert len(load_weather(str(p))) == 1


@pytest.mark.parametrize(
    "text, message",
    [
        ("date,tmin,tmax\n2026-06-01,22,30\n", "missing columns: rain"),
        ("date,tmin,tmax,rain\n2026-06-01,31,30,0\n", "tmax must be greater than tmin"),
        ("date,tmin,tmax,rain\n2026-06-01,22,30,-1\n", "rain cannot be negative"),
        ("date,tmin,tmax,rain\n2026-06-01,22,30,0\n2026-06-01,22,30,0\n", "duplicate date"),
        ("date,tmin,tmax,rain\n2026-06-01,22,abc,0\n", "invalid date or number"),
        ("date,tmin,tmax,rain\n2026-06-01,22,nan,0\n", "finite"),
        ("date,tmin,tmax,rain\n", "no data rows"),
    ],
)
def test_invalid_files_are_rejected_with_the_line(tmp_path, text, message):
    p = _write(tmp_path / "bad.csv", text)
    with pytest.raises(ValueError, match=message):
        load_weather(str(p))
