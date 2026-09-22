from __future__ import annotations

from pathlib import Path

from packages.core.settings import load_settings
from packages.data.tradier_source_qualification import (
    TRADIER_SOURCE_QUALIFICATION_CONTRACT,
    TRADIER_SOURCE_QUALIFICATION_CONTRACT_FINGERPRINT,
    deterministic_symbol_sample,
    run_tradier_rest_source_qualification,
)
from packages.providers.tradier.client import TradierApiResponse, TradierQuoteBatch


ROOT = Path(__file__).resolve().parents[2]


class _FakeTradierClient:
    def __init__(self, *, missing: set[str] | None = None) -> None:
        self.missing = missing or set()
        self.calls: list[tuple[str, ...]] = []

    def post_quotes(self, symbols):
        requested = tuple(symbols)
        self.calls.append(requested)
        rows = tuple(
            {
                "symbol": symbol,
                "last": 100.0,
                "bid": 99.99,
                "ask": 100.01,
            }
            for symbol in requested
            if symbol not in self.missing
        )
        response = TradierApiResponse(
            request_name="post_quotes",
            url="https://api.tradier.com/v1/markets/quotes",
            http_status=200,
            payload={},
            response_headers={
                "X-Ratelimit-Allowed": "120",
                "X-Ratelimit-Used": str(len(self.calls)),
                "X-Ratelimit-Available": str(120 - len(self.calls)),
                "X-Ratelimit-Expiry": "1234567890000",
            },
            response_bytes=100 * len(rows),
            elapsed_seconds=0.05,
        )
        return TradierQuoteBatch(
            requested_symbols=requested,
            returned_rows=rows,
            response=response,
        )


def _settings(tmp_path: Path):
    settings = load_settings(ROOT, "development")
    return settings.model_copy(update={"project_root": tmp_path.resolve()})


def test_tradier_source_qualification_contract_has_no_authority() -> None:
    assert TRADIER_SOURCE_QUALIFICATION_CONTRACT_FINGERPRINT == (
        "3a14be911be351d465ad3a99ab6dc7d47e985fbd17005af0bb6faa9c7613305d"
    )
    assert (
        TRADIER_SOURCE_QUALIFICATION_CONTRACT["source_role"]
        == "CANDIDATE_CURRENT_MARKET_DATA_PROVIDER_ONLY"
    )
    authority = TRADIER_SOURCE_QUALIFICATION_CONTRACT["authority"]
    assert authority["provider_policy_change"] is False
    assert authority["current_data_authority"] is False
    assert authority["broker_account_reads"] is False
    assert authority["provider_writes"] is False
    assert authority["broker_writes"] is False
    assert authority["order_creation"] is False
    assert authority["paper"] is False
    assert authority["live"] is False
    assert TRADIER_SOURCE_QUALIFICATION_CONTRACT["stream_probe"]["implemented_in_v1"] is False


def test_deterministic_symbol_sample_keeps_liquid_anchors_first() -> None:
    symbols = [
        "ZZZ",
        "AAPL",
        "QQQ",
        "ABC",
        "SPY",
        "MSFT",
        "NVDA",
        "XYZ",
    ]

    sample = deterministic_symbol_sample(symbols, count=5)

    assert sample == ("SPY", "QQQ", "AAPL", "MSFT", "NVDA")
    assert deterministic_symbol_sample(symbols, count=8) == deterministic_symbol_sample(
        list(reversed(symbols)),
        count=8,
    )


def test_rest_qualification_records_coverage_and_rate_limits(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    client = _FakeTradierClient()

    report = run_tradier_rest_source_qualification(
        settings,
        batch_sizes=(1, 3, 5),
        symbols=("SPY", "QQQ", "AAPL", "MSFT", "NVDA"),
        client=client,
    )

    assert report["status"] == "DIAGNOSTIC_COMPLETE"
    assert report["stage_count"] == 3
    assert report["complete_stage_count"] == 3
    assert len(client.calls) == 3
    assert [len(call) for call in client.calls] == [1, 3, 5]
    for stage in report["stages"]:
        assert stage["coverage_fraction"] == 1.0
        assert stage["unexpected_symbol_count"] == 0
        assert stage["duplicate_symbol_rows"] == 0
        assert stage["rate_limit"]["allowed"] == "120"
    assert report["interpretation"]["streaming_not_yet_qualified"] is True
    assert report["interpretation"]["authoritative_live_provider_policy_changed"] is False
    assert Path(str(report["report_path"])).is_file()


def test_rest_qualification_surfaces_missing_symbols_without_inference(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    client = _FakeTradierClient(missing={"NVDA"})

    report = run_tradier_rest_source_qualification(
        settings,
        batch_sizes=(5,),
        symbols=("SPY", "QQQ", "AAPL", "MSFT", "NVDA"),
        client=client,
    )

    assert report["status"] == "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
    stage = report["stages"][0]
    assert stage["coverage_fraction"] == 0.8
    assert stage["missing_symbols"] == ["NVDA"]
    assert stage["missing_symbol_count"] == 1
    assert report["complete_stage_count"] == 0
