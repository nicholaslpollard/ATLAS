from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from packages.backtesting.reference_regime_context import (
    REFERENCE_REGIME_CONTEXT_CONTRACT_VERSION,
    ReferenceMarketRegimeSource,
    ReferenceRegimeContextAdapter,
    ReferenceRegimeContextError,
)
from packages.core.settings import load_settings
from packages.regimes.split_origin_policy import (
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    MARKET_SECTOR_MANIFEST_VERSION,
    MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    SPLIT_ORIGIN_POLICY_VERSION,
)


ROOT = Path(__file__).resolve().parents[2]
START = date(2025, 1, 2)
END = date(2025, 1, 6)
SESSIONS = (START, date(2025, 1, 3), END)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_market(path: Path, rows: list[tuple[date, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=["trading_date", "composite"])
    con = duckdb.connect(":memory:")
    try:
        con.register("market", frame)
        con.execute(
            f"COPY (SELECT * FROM market ORDER BY trading_date) "
            f"TO '{path.as_posix()}' (FORMAT PARQUET)"
        )
    finally:
        con.close()


def _source(
    tmp_path: Path,
    *,
    rows: list[tuple[date, str]] | None = None,
) -> tuple[object, ReferenceMarketRegimeSource]:
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    adapter = ReferenceRegimeContextAdapter(settings)
    source = adapter.discover_source(END)
    _write_market(
        source.market_effective_path,
        rows or [(SESSIONS[0], "BULL"), (SESSIONS[1], "NEUTRAL"), (SESSIONS[2], "BEAR")],
    )
    snapshot = {
        "snapshot_contract_version": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
        "state_policy_contract_version": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
        "split_origin_policy_version": SPLIT_ORIGIN_POLICY_VERSION,
        "as_of_date": END.isoformat(),
    }
    source.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    source.snapshot_path.write_text(json.dumps(snapshot) + "\n", encoding="utf-8")
    manifest = {
        "manifest_version": MARKET_SECTOR_MANIFEST_VERSION,
        "snapshot_contract_version": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
        "state_policy_contract_version": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
        "split_origin_policy_version": SPLIT_ORIGIN_POLICY_VERSION,
        "as_of_date": END.isoformat(),
        "history_origin_date": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
        "dependency_fingerprint": "test-dependency",
        "snapshot_path": str(source.snapshot_path.resolve()),
        "snapshot_sha256": _sha256(source.snapshot_path),
        "history_files": {
            "market_effective": {
                "path": str(source.market_effective_path.resolve()),
                "sha256": _sha256(source.market_effective_path),
            }
        },
    }
    source.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    source.manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    return settings, source


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "instrument_id": ["ins-a", "ins-a", "ins-a"],
            "session_date": list(SESSIONS),
            "signal_available_at_utc": [
                datetime(2025, 1, 2, 21, tzinfo=UTC),
                datetime(2025, 1, 3, 21, tzinfo=UTC),
                datetime(2025, 1, 6, 21, tzinfo=UTC),
            ],
        }
    )


def test_regime_context_joins_exact_market_state_and_preserves_unavailable_context(
    tmp_path: Path,
) -> None:
    settings, source = _source(tmp_path)
    result = ReferenceRegimeContextAdapter(settings).attach(
        _bars(), START, END, source=source
    )

    assert result.report["contract_version"] == REFERENCE_REGIME_CONTEXT_CONTRACT_VERSION
    assert result.bars["market_regime_composite"].tolist() == [
        "BULL",
        "NEUTRAL",
        "BEAR",
    ]
    assert result.bars["market_regime_available_at_utc"].equals(
        result.bars["signal_available_at_utc"]
    )
    assert result.bars["ticker_regime_composite"].eq("UNAVAILABLE").all()
    assert result.bars["sector_regime_composite"].eq("UNAVAILABLE").all()
    assert result.report["future_regime_rows_read"] == 0
    assert result.report["protected_master_return_rows_read"] == 0
    assert result.report["provider_writes"] == result.report["broker_writes"] == 0


def test_regime_context_rejects_hash_drift(tmp_path: Path) -> None:
    settings, source = _source(tmp_path)
    source.market_effective_path.write_bytes(source.market_effective_path.read_bytes() + b"drift")
    with pytest.raises(ReferenceRegimeContextError, match="SHA-256"):
        ReferenceRegimeContextAdapter(settings).attach(_bars(), START, END, source=source)


def test_regime_context_rejects_nonexact_asof_manifest(tmp_path: Path) -> None:
    settings, source = _source(tmp_path)
    payload = json.loads(source.manifest_path.read_text(encoding="utf-8"))
    payload["as_of_date"] = "2025-01-03"
    source.manifest_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ReferenceRegimeContextError, match="as_of_date"):
        ReferenceRegimeContextAdapter(settings).attach(_bars(), START, END, source=source)


def test_regime_context_rejects_nonexchange_close_availability(tmp_path: Path) -> None:
    settings, source = _source(tmp_path)
    bars = _bars()
    bars.loc[0, "signal_available_at_utc"] = datetime(2025, 1, 2, 20, tzinfo=UTC)
    with pytest.raises(ReferenceRegimeContextError, match="exact XNYS regular close"):
        ReferenceRegimeContextAdapter(settings).attach(bars, START, END, source=source)


def test_regime_context_rejects_missing_input_session(tmp_path: Path) -> None:
    settings, source = _source(
        tmp_path,
        rows=[(SESSIONS[0], "BULL"), (SESSIONS[2], "BEAR")],
    )
    with pytest.raises(ReferenceRegimeContextError, match="missing input sessions"):
        ReferenceRegimeContextAdapter(settings).attach(_bars(), START, END, source=source)


def test_regime_context_rejects_future_history_row(tmp_path: Path) -> None:
    settings, source = _source(
        tmp_path,
        rows=[
            (SESSIONS[0], "BULL"),
            (SESSIONS[1], "NEUTRAL"),
            (SESSIONS[2], "BEAR"),
            (date(2025, 1, 7), "BULL"),
        ],
    )
    with pytest.raises(ReferenceRegimeContextError, match="range is not exact"):
        ReferenceRegimeContextAdapter(settings).attach(_bars(), START, END, source=source)
