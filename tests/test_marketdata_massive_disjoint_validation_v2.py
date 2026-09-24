from datetime import datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from packages.data import marketdata_massive_disjoint_validation_v2 as validation
from packages.providers.marketdata_app import MarketDataResponse


EASTERN = ZoneInfo("America/New_York")
CONTRACT = validation.CONTRACT


def _epoch_seconds(date_text: str) -> int:
    d = datetime.fromisoformat(date_text).date()
    return int(datetime.combine(d, time(16, 0), tzinfo=EASTERN).timestamp())


def _epoch_millis(date_text: str) -> int:
    d = datetime.fromisoformat(date_text).date()
    return int(datetime.combine(d, time(0, 0), tzinfo=EASTERN).timestamp() * 1000)


def test_v2_sample_is_disjoint_from_prior_cross_provider_evidence() -> None:
    roots = {item["root"] for item in CONTRACT["validation_anchors"]}
    dates = {item["date"] for item in CONTRACT["validation_anchors"]}
    assert len(roots) == 6
    assert len(dates) == 6
    assert roots.isdisjoint(set(CONTRACT["prior_cross_provider_roots"]))
    assert dates.isdisjoint(set(CONTRACT["prior_cross_provider_dates"]))


def test_activity_concordance_accepts_positive_present_and_zero_absent() -> None:
    md = [
        {"updated": _epoch_seconds("2026-01-05"), "volume": 10},
        {"updated": _epoch_seconds("2026-01-06"), "volume": 0},
    ]
    massive = [
        {"t": _epoch_millis("2026-01-05"), "v": 10},
    ]
    result = validation._activity_concordance(md, massive)
    assert result["passed"] is True
    assert result["activity_concordance_rate"] == 1.0
    assert result["positive_volume_session_count"] == 1
    assert result["zero_volume_session_count"] == 1


def test_activity_concordance_rejects_positive_missing_or_zero_present() -> None:
    md = [
        {"updated": _epoch_seconds("2026-01-05"), "volume": 10},
        {"updated": _epoch_seconds("2026-01-06"), "volume": 0},
    ]
    massive = [
        {"t": _epoch_millis("2026-01-06"), "v": 0},
    ]
    result = validation._activity_concordance(md, massive)
    assert result["passed"] is False
    dispositions = {item["disposition"] for item in result["records"]}
    assert "POSITIVE_VOLUME_MISSING_MASSIVE_BAR" in dispositions
    assert "ZERO_VOLUME_WITH_MASSIVE_BAR" in dispositions


def test_thresholds_preserve_price_volume_rules_and_require_sparse_case() -> None:
    thresholds = CONTRACT["preregistered_thresholds"]
    assert thresholds["minimum_activity_concordance_rate_per_anchor"] == 1.0
    assert thresholds["minimum_positive_volume_sessions_per_anchor"] == 5
    assert thresholds["minimum_last_inside_massive_range_rate_per_anchor"] == 1.0
    assert thresholds["maximum_median_price_relative_diff_per_anchor"] == 0.05
    assert thresholds["maximum_aggregate_median_price_relative_diff"] == 0.02
    assert thresholds["maximum_median_volume_relative_diff_per_anchor"] == 0.15
    assert thresholds["maximum_aggregate_median_volume_relative_diff"] == 0.10
    assert thresholds["minimum_zero_volume_sessions_complete_sample"] == 1


class _FakeMassive:
    def __init__(self):
        self.calls = []
        self.quote_dates_by_symbol = {}

    def get_json(self, path, params):
        self.calls.append((path, params))
        ticker = path.split("/ticker/")[1].split("/range/")[0]
        option_symbol = ticker.removeprefix("O:")
        dates = self.quote_dates_by_symbol[option_symbol]
        results = [
            {
                "t": _epoch_millis(d),
                "o": 1.05,
                "h": 1.20,
                "l": 1.00,
                "c": 1.10,
                "v": 100,
            }
            for d, volume in dates
            if volume > 0
        ]
        return {"status": "OK", "results": results}


def test_end_to_end_v2_passes_activity_aware_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    fake_massive = _FakeMassive()
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
                "X-Api-Ratelimit-Remaining": "9999",
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
        rows = [(d, 100 if index < 5 else 0) for index, d in enumerate(dates)]
        fake_massive.quote_dates_by_symbol[option_symbol] = rows
        return MarketDataResponse(
            http_status=200,
            payload={
                "s": "ok",
                "optionSymbol": [option_symbol] * len(rows),
                "last": [1.10] * len(rows),
                "volume": [volume for _, volume in rows],
                "updated": [_epoch_seconds(d) for d, _ in rows],
            },
            headers={
                "X-Api-Ratelimit-Limit": "10000",
                "X-Api-Ratelimit-Remaining": "9998",
                "X-Api-Ratelimit-Consumed": "1",
            },
            response_bytes=100,
            elapsed_seconds=0.01,
        )

    monkeypatch.setattr(validation, "historical_chain", fake_chain)
    monkeypatch.setattr(validation, "historical_quote_series", fake_quotes)

    report = validation.run_marketdata_massive_disjoint_validation_v2(
        SimpleNamespace(project_root=tmp_path),
        massive_client=fake_massive,
    )

    assert report["status"] == "VALIDATED_FOR_POSITIVE_VOLUME_EOD_LAST_VOLUME_SEMANTICS"
    assert report["validation_passed"] is True
    assert report["anchor_pass_count"] == 6
    assert report["total_zero_volume_sessions"] == 6
    assert len(fake_massive.calls) == 6
    assert marketdata_calls == {"chains": 6, "quotes": 6}
    assert report["aggregate_summary"]["overlap_sessions"] == 30
    assert report["authority"][
        "marketdata_positive_volume_eod_last_volume_semantics_validated"
    ] is True
    assert report["authority"]["marketdata_zero_volume_last_validated"] is False
    assert report["authority"]["historical_bid_ask_validated"] is False
