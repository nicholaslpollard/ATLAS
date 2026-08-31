from __future__ import annotations

from types import SimpleNamespace

from packages.backtesting.alpha_gate_finra_short_interest_feasibility import (
    FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT,
    FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES,
    FINRA_SHORT_INTEREST_MECHANISM,
    FINRAShortInterestFeasibility,
    _summarize_files,
)
from packages.providers.finra_short_interest import FINRAShortInterestFile


def _file(settlement_date: str, *, rows: int = 3000) -> FINRAShortInterestFile:
    data = tuple(
        {
            "settlement_date": settlement_date,
            "symbol": f"S{i:04d}",
            "issue_name": f"Issue {i}",
            "current_short_position": 1000 + i,
            "previous_short_position": 900 + i,
            "average_daily_volume": 500.0,
            "days_to_cover": 2.0,
            "exchange_code": "R",
            "market_code": "NMS",
            "revision_flag": None,
            "stock_split_flag": None,
            "change_previous_number": 100.0,
            "change_percent": 10.0,
        }
        for i in range(rows)
    )
    return FINRAShortInterestFile(
        settlement_date=settlement_date,
        source_url=(
            "https://cdn.finra.org/equity/otcmarket/biweekly/shrt"
            + settlement_date.replace("-", "")
            + ".csv"
        ),
        source_sha256="a" * 64,
        delimiter=",",
        resolved_columns={
            "settlement_date": "settlementDate",
            "symbol": "symbolCode",
            "issue_name": "issueName",
            "current_short_position": "currentShortPositionQuantity",
            "previous_short_position": "previousShortPositionQuantity",
            "average_daily_volume": "averageDailyVolumeQuantity",
            "days_to_cover": "daysToCoverQuantity",
            "exchange_code": "issuerServicesGroupExchangeCode",
            "market_code": "marketClassCode",
            "revision_flag": "revisionFlag",
            "stock_split_flag": "stockSplitFlag",
            "change_previous_number": "changePreviousNumber",
            "change_percent": "changePercent",
        },
        rows=data,
    )


def test_frozen_source_family_is_source_only_and_materially_different() -> None:
    assert "FINRA" in FINRA_SHORT_INTEREST_MECHANISM
    assert "POSITIONING_AND_CROWDING" in FINRA_SHORT_INTEREST_MECHANISM
    assert "source-only-no-market-outcomes" in FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT
    assert len(FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES) == 12


def test_source_summary_passes_frozen_numeric_gates() -> None:
    files = [_file(date) for date in FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES]
    summary, gates = _summarize_files(files)
    assert summary["successful_files"] == 12
    assert summary["year_count"] == 6
    assert summary["total_rows"] == 36_000
    assert summary["exchange_listed_rows"] == 36_000
    assert summary["unique_exchange_listed_symbols"] == 3000
    assert all(gates.values())


def test_source_summary_fails_closed_when_exchange_identity_is_not_proven() -> None:
    source = _file("2026-07-31", rows=3000)
    unresolved = FINRAShortInterestFile(
        settlement_date=source.settlement_date,
        source_url=source.source_url,
        source_sha256=source.source_sha256,
        delimiter=source.delimiter,
        resolved_columns={**source.resolved_columns, "exchange_code": None, "market_code": None},
        rows=source.rows,
    )
    _, gates = _summarize_files([unresolved] * 12)
    assert gates["required_schema_semantics"] is False


class _FakeClient:
    def historical_file(self, *, settlement_date: object) -> FINRAShortInterestFile:
        return _file(str(settlement_date))


class _FakeSettings:
    def __init__(self, root):
        self._root = root
        self.data = SimpleNamespace(paths=SimpleNamespace(derived="derived"))

    def resolved_path(self, value):
        assert value == "derived"
        return self._root


def test_runner_report_persists_zero_outcome_authority(tmp_path) -> None:
    study = FINRAShortInterestFeasibility(_FakeSettings(tmp_path), _FakeClient())
    report = study.run()
    assert report["status"] == "FEASIBILITY_PASS"
    assert report["pass"] is True
    assert report["alpha_hypotheses_frozen"] is False
    assert report["performance_evaluated"] is False
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["protected_holdout_consumed"] is False
    assert report["provider_writes_performed"] == 0
    assert report["broker_reads_performed"] == 0
    assert report["broker_writes_performed"] == 0
    assert report["order_writes_performed"] == 0
    assert report["paper_submits_performed"] == 0
    assert report["live_writes_performed"] == 0
    assert report["automation_writes_performed"] == 0
    assert report["automatic_broker_failover"] is False
    assert (tmp_path / "strategy_evaluation/pre_phase33/finra_short_interest_feasibility_v1/source_census.json").is_file()
