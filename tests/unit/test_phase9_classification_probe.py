from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.providers.massive.reference_data import MassiveReferenceProvider
from packages.providers.massive.rest import MassiveRESTClient
from packages.regimes.classification_probe import (
    REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION,
    ClassificationCandidate,
    ClassificationObservation,
    RegimeClassificationProbe,
)

ROOT = Path(__file__).resolve().parents[2]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_classification_probe_contract_and_path_are_separate_from_input_inventory() -> None:
    assert REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION == (
        "regime-classification-probe-v1-massive-sic-point-in-time"
    )
    settings = load_settings(ROOT, "development")
    paths = MarketDataPaths(settings)
    session = date(2026, 8, 14)
    probe = paths.regime_classification_probe_report(session)
    inventory = paths.regime_input_inventory_report(session)
    assert probe != inventory
    assert "classification_probe" in probe.parts


def test_deterministic_sample_is_stable_bounded_and_not_input_order_dependent() -> None:
    candidates = [
        ClassificationCandidate("id-3", "CCC", "CS"),
        ClassificationCandidate("id-1", "AAA", "CS"),
        ClassificationCandidate("id-4", "DDD", "ETF"),
        ClassificationCandidate("id-2", "BBB", "CS"),
    ]
    first = RegimeClassificationProbe.deterministic_sample(candidates, 3)
    second = RegimeClassificationProbe.deterministic_sample(reversed(candidates), 3)
    assert first == second
    assert len(first) == 3
    assert RegimeClassificationProbe.deterministic_sample(candidates, 99) != []
    assert len(RegimeClassificationProbe.deterministic_sample(candidates, 99)) == 4


def test_probe_helpers_measure_sic_coverage_without_creating_sector_labels() -> None:
    observations = [
        ClassificationObservation("1", "AAA", "CS", "ok", "AAA", True, "3571", "ELECTRONIC COMPUTERS", None),
        ClassificationObservation("2", "BBB", "CS", "ok", "BBB", True, None, None, None),
        ClassificationObservation("3", "ETF", "ETF", "provider_error", None, False, None, None, "error"),
    ]
    assert RegimeClassificationProbe.coverage_fraction(1, 2) == 0.5
    summary = RegimeClassificationProbe._security_type_summary(observations)
    assert summary["CS"] == {
        "sampled": 2,
        "successful": 2,
        "sic_code": 1,
        "missing_sic": 1,
        "provider_error": 0,
    }
    assert summary["ETF"]["provider_error"] == 1


class FakeOverviewClient:
    def ticker_overview(self, ticker: str, *, as_of_date: str):
        assert ticker == "TpC"
        assert as_of_date == "2026-08-14"
        return {
            "ticker": "TpC",
            "name": "  Test Preferred  ",
            "sic_code": " 6021 ",
            "sic_description": " NATIONAL COMMERCIAL BANKS ",
            "composite_figi": "bbg000test01",
        }


def test_reference_provider_preserves_ticker_case_and_normalizes_sic_text() -> None:
    settings = load_settings(ROOT, "development")
    provider = MassiveReferenceProvider(settings, client=FakeOverviewClient())
    row = provider.ticker_overview("TpC", date(2026, 8, 14))
    assert row["ticker"] == "TpC"
    assert row["sic_code"] == "6021"
    assert row["sic_description"] == "NATIONAL COMMERCIAL BANKS"
    assert row["composite_figi"] == "BBG000TEST01"


def test_massive_ticker_overview_sends_point_in_time_date(monkeypatch) -> None:
    monkeypatch.setenv("MASSIVE_API_KEY", "super-secret")
    settings = load_settings(ROOT, "development")
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        return FakeResponse(
            {
                "status": "OK",
                "results": {
                    "ticker": "TpC",
                    "sic_code": "6021",
                    "sic_description": "NATIONAL COMMERCIAL BANKS",
                },
            }
        )

    client = MassiveRESTClient(settings, opener=opener, sleeper=lambda _: None)
    result = client.ticker_overview("TpC", as_of_date="2026-08-14")
    parts = urlsplit(calls[0][0].full_url)
    assert parts.path.endswith("/v3/reference/tickers/TpC")
    assert parse_qs(parts.query)["date"] == ["2026-08-14"]
    assert calls[0][0].get_header("Authorization") == "Bearer super-secret"
    assert result["sic_code"] == "6021"
