from __future__ import annotations

from datetime import date
import json
from types import SimpleNamespace

import pandas as pd
import pytest

import scripts.probe_thetadata_free_eod_shape_v1 as probe


class FakeClient:
    calls = []

    def stock_history_eod(self, *, symbol, start_date, end_date):
        self.calls.append(("stock_history_eod", symbol, start_date, end_date))
        return pd.DataFrame([{
            "created": pd.Timestamp("2026-10-16T17:15:00"),
            "last_trade": pd.Timestamp("2026-10-16T16:00:00"),
            "open": 500.0, "close": 502.0,
            "bid": 501.99, "ask": 502.01, "volume": 1_000_000,
        }])

    def option_history_eod(
        self, *, symbol, start_date, end_date, expiration, strike, right, strike_range
    ):
        self.calls.append((
            "option_history_eod", symbol, start_date, end_date,
            expiration, strike, right, strike_range,
        ))
        return pd.DataFrame([{
            "symbol": "SPY", "expiration": date(2026, 11, 20),
            "strike": 500.0, "right": "call",
            "created": pd.Timestamp("2026-10-16T17:15:00"),
            "last_trade": pd.Timestamp("2026-10-16T15:57:00"),
            "bid": 10.2, "ask": 10.4, "volume": 33,
        }])


def test_no_sdk_or_provider_use_without_explicit_two_read_flag(monkeypatch):
    monkeypatch.setattr(
        probe, "_auth_present",
        lambda: pytest.fail("No dotenv/auth inspection without flag"),
    )
    assert probe.main([]) == 2


def test_exactly_two_free_eod_reads_with_fixed_one_day_and_one_expiration():
    FakeClient.calls = []
    report = probe.collect_free_eod_shape(FakeClient, lambda: FakeClient())
    assert report["request_cap"] == 2
    assert report["request_attempts"] == 2
    assert report["status"] == "TWO_EOD_DATAFRAMES_RECEIVED"
    assert len(FakeClient.calls) == 2
    assert FakeClient.calls[0] == (
        "stock_history_eod", "SPY", date(2026, 10, 16), date(2026, 10, 16)
    )
    assert FakeClient.calls[1] == (
        "option_history_eod", "SPY", date(2026, 10, 16),
        date(2026, 10, 16), date(2026, 11, 20), "*", "call", 2
    )
    assert report["responses"][0]["normalized_rows"][0]["created"] == (
        "2026-10-16T17:15:00"
    )
    assert report["responses"][1]["normalized_rows"][0]["expiration"] == (
        "2026-11-20"
    )
    assert report["responses"][1]["dtypes"]["strike"] == "float64"
    assert report["not_intraday_or_execution_evidence"] is True
    assert "THETADATA_API_KEY" not in str(report)


def test_missing_sdk_method_fails_before_client_or_request():
    class IncompleteClient:
        def stock_history_eod(self, *, symbol, start_date, end_date):
            pytest.fail("No provider calls allowed")

    with pytest.raises(RuntimeError, match="FREE_EOD_SDK_METHOD_MISSING"):
        probe.collect_free_eod_shape(
            IncompleteClient,
            lambda: pytest.fail("No SDK client initialization allowed"),
        )


def test_unaccepted_sdk_option_keywords_fail_before_client():
    class NoStrikeRange(FakeClient):
        def option_history_eod(
            self, *, symbol, start_date, end_date, expiration, strike, right
        ):
            pytest.fail("No provider calls allowed")

    with pytest.raises(RuntimeError, match="FREE_EOD_SDK_KEYWORDS_NOT_ACCEPTED"):
        probe.collect_free_eod_shape(
            NoStrikeRange,
            lambda: pytest.fail("No SDK client initialization allowed"),
        )


def test_provider_errors_do_not_echo_secret_or_retry():
    class FailingClient(FakeClient):
        def stock_history_eod(self, **kwargs):
            raise ValueError("API key must never appear: fixture-secret")

    report = probe.collect_free_eod_shape(FailingClient, lambda: FailingClient())
    assert report["request_attempts"] == 1
    assert report["status"] == "SOURCE_SHAPE_INCOMPLETE"
    assert report["responses"][0]["error_type"] == "ValueError"
    assert "fixture-secret" not in json.dumps(report)


def test_oversize_dataframe_rejected_without_truncation_or_implicit_retry():
    frame = pd.DataFrame({"symbol": ["SPY"] * (probe.MAX_ROWS_PER_RESPONSE + 1)})
    with pytest.raises(ValueError, match="EXCEEDS_BOUNDED_SHAPE"):
        probe.summarize_frame(frame)


def test_report_is_immutable_and_contains_normalized_rows(tmp_path):
    FakeClient.calls = []
    report = probe.collect_free_eod_shape(FakeClient, lambda: FakeClient())
    path = probe.persist_report(report, tmp_path)
    assert path.exists()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["status"] == "TWO_EOD_DATAFRAMES_RECEIVED"
    assert len(saved["fingerprint"]) == 64
    assert saved["responses"][1]["normalized_rows"][0]["right"] == "call"
    assert path == probe.persist_report(report, tmp_path)
    path.write_text("different", encoding="utf-8")
    with pytest.raises(ValueError, match="FREE_EOD_RECEIPT_COLLISION"):
        probe.persist_report(report, tmp_path)


def test_local_auth_presence_only_no_credential_value(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.delenv("THETADATA_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "THETADATA_API_KEY=synthetic-unit-test-only\n", encoding="utf-8"
    )
    assert probe._auth_present() is True
    (tmp_path / ".env").write_text("THETADATA_API_KEY=\n", encoding="utf-8")
    assert probe._auth_present() is False
