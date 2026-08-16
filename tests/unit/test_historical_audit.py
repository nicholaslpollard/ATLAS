from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from packages.core.enums import DatasetType
from packages.data.historical_audit import HistoricalLakeAuditor
from packages.schemas.history import HistoryLayerAudit, ProviderDatasetAudit


def test_historical_audit_preserves_quarantine_symbol_case(tmp_path: Path, monkeypatch):
    session = date(2026, 8, 14)
    registry = tmp_path / "symbol_quarantine" / "2026" / "2026-08-14.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"symbols": ["TPC", "TpC", "BCPC", "BCpC"]}), encoding="utf-8")

    class FakeCalendar:
        @staticmethod
        def sessions_in_range(start_date, end_date):
            return [session]

    class FakePaths:
        @staticmethod
        def symbol_quarantine_registry(trading_date):
            assert trading_date == session
            return registry

    auditor = HistoricalLakeAuditor.__new__(HistoricalLakeAuditor)
    auditor.calendar = FakeCalendar()
    auditor.paths = FakePaths()

    def provider_stub(self, dataset, sessions, *, deep_validate):
        return ProviderDatasetAudit(
            name=dataset.value,
            dataset=dataset,
            expected_sessions=1,
            present_sessions=1,
            bytes_on_disk=1,
        )

    def layer_stub(self, name, sessions, path_for):
        return HistoryLayerAudit(
            name=name,
            expected_sessions=1,
            present_sessions=1,
            bytes_on_disk=1,
        )

    monkeypatch.setattr(HistoricalLakeAuditor, "_provider", provider_stub)
    monkeypatch.setattr(HistoricalLakeAuditor, "_layer", layer_stub)

    report = auditor.audit(session, session)

    assert report.quarantine_sessions == [session]
    assert report.quarantined_symbols == ["BCPC", "BCpC", "TPC", "TpC"]


def test_historical_audit_persist_writes_json_atomically(tmp_path: Path):
    session = date(2026, 8, 14)
    layer = HistoryLayerAudit(
        name="canonical_1d",
        expected_sessions=1,
        present_sessions=1,
        bytes_on_disk=123,
    )
    provider = ProviderDatasetAudit(
        name=DatasetType.STOCK_DAILY_AGGREGATES.value,
        dataset=DatasetType.STOCK_DAILY_AGGREGATES,
        expected_sessions=1,
        present_sessions=1,
        bytes_on_disk=456,
    )

    from packages.schemas.history import HistoricalLakeAuditReport
    from datetime import UTC, datetime

    report = HistoricalLakeAuditReport(
        start_date=session,
        end_date=session,
        generated_at_utc=datetime.now(UTC),
        exchange_sessions=[session],
        provider={"1d": provider, "1m": provider.model_copy(update={"dataset": DatasetType.STOCK_MINUTE_AGGREGATES})},
        canonical={"1d": layer, "1m": layer.model_copy(update={"name": "canonical_1m"})},
        derived={
            "15m": layer.model_copy(update={"name": "derived_15m"}),
            "1h": layer.model_copy(update={"name": "derived_1h"}),
            "4h": layer.model_copy(update={"name": "derived_4h"}),
        },
        total_bytes_on_disk=579,
    )

    target = tmp_path / "audit.json"
    HistoricalLakeAuditor.persist(report, target)

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["start_date"] == "2026-08-14"
    assert payload["total_bytes_on_disk"] == 579
    assert list(tmp_path.glob("audit.json.*.tmp")) == []
