from datetime import date
from pathlib import Path

from packages.core.enums import DataProvider, InstrumentIdentityQuality
from packages.core.settings import load_settings
from packages.instruments.reference_rekey import rekey_reference_snapshot
from packages.instruments.registry import InstrumentRegistryStore
from packages.schemas.instrument import InstrumentReferenceObservation

ROOT = Path(__file__).resolve().parents[2]


def _legacy_medium_row(ticker: str, as_of_date: date) -> InstrumentReferenceObservation:
    return InstrumentReferenceObservation(
        instrument_id="ins_legacy_collision",
        identity_key="massive:cik:0000070858:exchange:XNYS:type:PFD",
        identity_quality=InstrumentIdentityQuality.MEDIUM,
        provider=DataProvider.MASSIVE,
        as_of_date=as_of_date,
        ticker=ticker,
        name=f"Bank of America {ticker}",
        market="stocks",
        locale="us",
        primary_exchange="XNYS",
        security_type="PFD",
        active=True,
        cik="0000070858",
    )


def test_reference_rekey_splits_legacy_issuer_level_collision(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    store = InstrumentRegistryStore(settings, provider=object())  # type: ignore[arg-type]
    as_of_date = date(2026, 8, 14)
    target = store.paths.reference_snapshot_file(as_of_date)

    store._write_snapshot(  # noqa: SLF001 - test creates a legacy canonical fixture
        [_legacy_medium_row("BACpA", as_of_date), _legacy_medium_row("BACpB", as_of_date)],
        target,
    )

    result = rekey_reference_snapshot(settings, as_of_date)

    assert result.row_count == 2
    assert result.old_instrument_count == 1
    assert result.new_instrument_count == 2
    assert result.changed_row_count == 2
    assert result.old_multi_ticker_id_groups == 1
    assert result.new_multi_ticker_id_groups == 0
    assert result.strong_id_changes == 0
