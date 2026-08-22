from datetime import date

from packages.data.alpaca_backfill_quality import inspect_daily_bar


def _valid_bar(**overrides):
    row = {
        "t": "2020-06-15T04:00:00Z",
        "o": 10.0,
        "h": 11.0,
        "l": 9.5,
        "c": 10.5,
        "v": 1000,
        "n": 25,
        "vw": 10.4,
    }
    row.update(overrides)
    return row


def test_gate5a_valid_daily_bar_has_no_definite_quality_defect() -> None:
    result = inspect_daily_bar(
        _valid_bar(),
        unit_start=date(2020, 1, 1),
        unit_end=date(2020, 12, 31),
    )

    assert result.definite_invalid is False
    assert result.zero_activity_placeholder is False
    assert result.zero_volume_nonplaceholder is False
    assert result.session_date == date(2020, 6, 15)
    assert result.time_utc == "04:00:00"
    assert result.weekend_session is False


def test_gate5a_detects_invalid_ohlc_geometry() -> None:
    result = inspect_daily_bar(
        _valid_bar(h=10.25, c=10.5),
        unit_start=date(2020, 1, 1),
        unit_end=date(2020, 12, 31),
    )

    assert result.invalid_ohlc_geometry is True
    assert result.definite_invalid is True


def test_gate5a_detects_nonfinite_and_negative_numeric_fields() -> None:
    result = inspect_daily_bar(
        _valid_bar(o=float("nan"), v=-1, n=-2, vw=0),
        unit_start=date(2020, 1, 1),
        unit_end=date(2020, 12, 31),
    )

    assert result.invalid_ohlc_numeric is True
    assert result.invalid_volume is True
    assert result.invalid_trade_count is True
    assert result.invalid_vwap is True
    assert result.definite_invalid is True


def test_gate5a_missing_optional_trade_count_and_vwap_are_diagnostic_only() -> None:
    bar = _valid_bar()
    bar.pop("n")
    bar.pop("vw")
    result = inspect_daily_bar(
        bar,
        unit_start=date(2020, 1, 1),
        unit_end=date(2020, 12, 31),
    )

    assert result.missing_trade_count is True
    assert result.missing_vwap is True
    assert result.invalid_trade_count is False
    assert result.invalid_vwap is False
    assert result.definite_invalid is False


def test_gate5a_flags_range_and_weekend_independently() -> None:
    result = inspect_daily_bar(
        _valid_bar(t="2021-01-02T05:00:00Z"),
        unit_start=date(2020, 1, 1),
        unit_end=date(2020, 12, 31),
    )

    assert result.out_of_unit_range is True
    assert result.weekend_session is True
    assert result.definite_invalid is True


def test_gate5a_zero_activity_flat_bar_is_preserved_placeholder_not_invalid() -> None:
    result = inspect_daily_bar(
        _valid_bar(o=4.1, h=4.1, l=4.1, c=4.1, v=0, n=0, vw=0),
        unit_start=date(2020, 1, 1),
        unit_end=date(2020, 12, 31),
    )

    assert result.zero_activity_placeholder is True
    assert result.zero_volume_nonplaceholder is False
    assert result.invalid_volume is False
    assert result.invalid_trade_count is False
    assert result.invalid_vwap is False
    assert result.definite_invalid is False


def test_gate5a_other_zero_volume_pattern_fails_closed() -> None:
    result = inspect_daily_bar(
        _valid_bar(v=0, n=1, vw=10.4),
        unit_start=date(2020, 1, 1),
        unit_end=date(2020, 12, 31),
    )

    assert result.zero_activity_placeholder is False
    assert result.zero_volume_nonplaceholder is True
    assert result.definite_invalid is True
