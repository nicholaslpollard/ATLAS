from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from packages.data import marketdata_massive_disjoint_validation_v1 as validation
from packages.providers.marketdata_app import MarketDataResponse

CONTRACT = validation.CONTRACT
_aggregate_checks = validation._aggregate_checks
_anchor_checks = validation._anchor_checks


def test_validation_anchors_are_disjoint_from_calibration_roots_and_dates() -> None:
    validation_roots = {item["root"] for item in CONTRACT["validation_anchors"]}
    validation_dates = {item["date"] for item in CONTRACT["validation_anchors"]}
    calibration_roots = {"SPY", "MSFT", "NVDA", "QQQ"}
    calibration_dates = {
        "2026-03-02",
        "2026-05-01",
        "2026-07-01",
        "2026-09-01",
    }
    assert validation_roots.isdisjoint(calibration_roots)
    assert validation_dates.isdisjoint(calibration_dates)
    assert validation_roots == {"IWM", "AMZN", "META", "DIA"}
    assert validation_dates == {
        "2026-02-02",
        "2026-04-01",
        "2026-06-01",
        "2026-08-03",
    }


def test_thresholds_are_frozen_and_exact_match_is_descriptive_only() -> None:
    thresholds = CONTRACT["preregistered_thresholds"]
    assert thresholds["required_anchor_count"] == 4
    assert thresholds["minimum_overlap_coverage_rate_per_anchor"] == 1.0
    assert thresholds["minimum_last_inside_massive_range_rate_per_anchor"] == 1.0
    assert thresholds["maximum_median_price_relative_diff_per_anchor"] == 0.05
    assert thresholds["maximum_aggregate_median_price_relative_diff"] == 0.02
    assert thresholds["maximum_median_volume_relative_diff_per_anchor"] == 0.15
    assert thresholds["maximum_aggregate_median_volume_relative_diff"] == 0.10
    assert thresholds["exact_last_close_match_rate"] == "DESCRIPTIVE_ONLY"


def test_anchor_checks_pass_calibration_like_semantics() -> None:
    summary = {
        "overlap_sessions": 7,
        "marketdata_last_inside_massive_range_rate": 1.0,
        "median_price_rel_diff": 0.01,
        "median_volume_rel_diff": 0.05,
    }
    checks = _anchor_checks(marketdata_rows=7, summary=summary)
    assert all(checks.values())


def test_anchor_checks_fail_range_or_coverage_violation() -> None:
    range_failure = _anchor_checks(
        marketdata_rows=7,
        summary={
            "overlap_sessions": 7,
            "marketdata_last_inside_massive_range_rate": 0.99,
            "median_price_rel_diff": 0.01,
            "median_volume_rel_diff": 0.05,
        },
    )
    assert range_failure["last_inside_massive_range_rate"] is False

    coverage_failure = _anchor_checks(
        marketdata_rows=7,
        summary={
            "overlap_sessions": 6,
            "marketdata_last_inside_massive_range_rate": 1.0,
            "median_price_rel_diff": 0.01,
            "median_volume_rel_diff": 0.05,
        },
    )
    assert coverage_failure["overlap_coverage_rate"] is False


def test_anchor_checks_fail_preregistered_price_or_volume_median() -> None:
    price_failure = _anchor_checks(
        marketdata_rows=7,
        summary={
            "overlap_sessions": 7,
            "marketdata_last_inside_massive_range_rate": 1.0,
            "median_price_rel_diff": 0.051,
            "median_volume_rel_diff": 0.05,
        },
    )
    assert price_failure["median_price_relative_diff"] is False

    volume_failure = _anchor_checks(
        marketdata_rows=7,
        summary={
            "overlap_sessions": 7,
            "marketdata_last_inside_massive_range_rate": 1.0,
            "median_price_rel_diff": 0.01,
            "median_volume_rel_diff": 0.151,
        },
    )
    assert volume_failure["median_volume_relative_diff"] is False


def test_aggregate_checks_require_all_four_and_tighter_medians() -> None:
    checks = _aggregate_checks(
        anchor_count=4,
        anchor_pass_count=4,
        aggregate={
            "median_price_rel_diff": 0.019,
            "median_volume_rel_diff": 0.099,
        },
    )
    assert all(checks.values())

    failed = _aggregate_checks(
        anchor_count=4,
        anchor_pass_count=4,
        aggregate={
            "median_price_rel_diff": 0.021,
            "median_volume_rel_diff": 0.101,
        },
    )
    assert failed["aggregate_median_price_relative_diff"] is False
    assert failed["aggregate_median_volume_relative_diff"] is False


def test_passed_authority_remains_narrow() -> None:
    authority = CONTRACT["authority_if_passed"]
    assert authority["marketdata_eod_last_volume_semantics_validated"] is True
    assert authority["historical_bid_ask_validated"] is False
    assert authority["historical_intraday_validated"] is False
    assert authority["execution_price_authority"] is False
    assert authority["simulator_authority"] is False
    assert authority["paper"] is False
    assert authority["live"] is False



def _epoch_seconds_eastern(date_text: str) -> int:
    return int(datetime.fromisoformat(date_text + "T16:00:00-04:00").timestamp())


def _epoch_millis_eastern(date_text: str) -> int:
    return int(datetime.fromisoformat(date_text + "T00:00:00-04:00").timestamp() * 1000)


class _FakeMassive:
    def __init__(self, rows_by_symbol):
        self.rows_by_symbol = rows_by_symbol
        self.calls = []

    def get_json(self, path, params):
        self.calls.append((path, params))
        ticker = path.split("/ticker/")[1].split("/range/")[0]
        return {"status": "OK", "results": self.rows_by_symbol[ticker]}


def test_end_to_end_disjoint_validation_passes_only_frozen_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    quote_dates_by_symbol = {}
    marketdata_calls = {"chains": 0, "quotes": 0}

    def fake_chain(underlying, *, date, dte, strike_limit, side=None):
        marketdata_calls["chains"] += 1
        option_symbol = f"{underlying}261231C00100000"
        return MarketDataResponse(
            http_status=200,
            payload={
                "s": "ok",
                "optionSymbol": [option_symbol],
                "side": ["call"],
                "strike": [100.0],
                "underlyingPrice": [100.0],
            },
            headers={
                "X-Api-Ratelimit-Limit": "10000",
                "X-Api-Ratelimit-Remaining": str(9999 - marketdata_calls["chains"]),
                "X-Api-Ratelimit-Consumed": "1",
            },
            response_bytes=100,
            elapsed_seconds=0.01,
        )

    def fake_quotes(option_symbol, *, from_date, to_date):
        marketdata_calls["quotes"] += 1
        start = datetime.fromisoformat(from_date).date()
        dates = []
        cursor = start
        while len(dates) < 6:
            if cursor.weekday() < 5:
                dates.append(cursor.isoformat())
            cursor += timedelta(days=1)
        quote_dates_by_symbol[option_symbol] = dates
        return MarketDataResponse(
            http_status=200,
            payload={
                "s": "ok",
                "optionSymbol": [option_symbol] * len(dates),
                "last": [1.10] * len(dates),
                "volume": [100] * len(dates),
                "updated": [_epoch_seconds_eastern(d) for d in dates],
            },
            headers={
                "X-Api-Ratelimit-Limit": "10000",
                "X-Api-Ratelimit-Remaining": str(9990 - marketdata_calls["quotes"]),
                "X-Api-Ratelimit-Consumed": "1",
            },
            response_bytes=100,
            elapsed_seconds=0.01,
        )

    monkeypatch.setattr(validation, "historical_chain", fake_chain)
    monkeypatch.setattr(validation, "historical_quote_series", fake_quotes)

    rows_by_symbol = {}
    fake_massive = _FakeMassive(rows_by_symbol)

    original_get_json = fake_massive.get_json

    def dynamic_get_json(path, params):
        ticker = path.split("/ticker/")[1].split("/range/")[0]
        option_symbol = ticker.removeprefix("O:")
        dates = quote_dates_by_symbol[option_symbol]
        rows_by_symbol[ticker] = [
            {
                "t": _epoch_millis_eastern(d),
                "o": 1.05,
                "h": 1.20,
                "l": 1.00,
                "c": 1.10,
                "v": 100,
            }
            for d in dates
        ]
        return original_get_json(path, params)

    fake_massive.get_json = dynamic_get_json

    report = validation.run_marketdata_massive_disjoint_validation_v1(
        SimpleNamespace(project_root=tmp_path),
        massive_client=fake_massive,
    )

    assert report["status"] == "VALIDATED_FOR_EOD_LAST_VOLUME_SEMANTICS"
    assert report["validation_passed"] is True
    assert report["anchor_pass_count"] == 4
    assert len(fake_massive.calls) == 4
    assert marketdata_calls == {"chains": 4, "quotes": 4}
    assert report["observed_marketdata_api_credits_consumed"] == 8
    assert report["authority"]["marketdata_eod_last_volume_semantics_validated"] is True
    assert report["authority"]["historical_bid_ask_validated"] is False
    assert report["authority"]["execution_price_authority"] is False
