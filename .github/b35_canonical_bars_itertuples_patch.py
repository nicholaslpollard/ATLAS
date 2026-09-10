from pathlib import Path

replay_path = Path("packages/backtesting/b35_development_replay.py")
readme_path = Path("README.md")
roadmap_path = Path("docs/roadmap.md")
test_path = Path("tests/unit/test_b35_canonical_bar_conversion.py")

replay = replay_path.read_text(encoding="utf-8")
readme = readme_path.read_text(encoding="utf-8")
roadmap = roadmap_path.read_text(encoding="utf-8")

start = replay.index("def _canonical_bars(frame: pd.DataFrame) -> tuple[CanonicalBar, ...]:\n")
end = replay.index("\n\ndef _premarket_volume(\n", start)
old_converter = replay[start:end]
if 'frame.to_dict(orient="records")' not in old_converter:
    raise SystemExit("canonical converter is not the expected legacy implementation")

new_converter = '''def _canonical_bars(frame: pd.DataFrame) -> tuple[CanonicalBar, ...]:
    # Retain full CanonicalBar validation; only remove the intermediate
    # DataFrame.to_dict allocation from the already source-validated B35 path.
    bars: list[CanonicalBar] = []
    validate = CanonicalBar.model_validate
    isna = pd.isna
    for row in frame.itertuples(index=False):
        vwap = row.vwap
        if isna(vwap):
            vwap = None
        transaction_count = row.transaction_count
        if isna(transaction_count):
            transaction_count = None
        payload: dict[str, object] = {
            "symbol": row.symbol,
            "timestamp_utc": row.timestamp_utc,
            "session_date": row.session_date,
            "timeframe": row.timeframe,
            "session_segment": row.session_segment,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
            "vwap": vwap,
            "transaction_count": transaction_count,
            "provider": row.provider,
            "dataset": row.dataset,
            "source_id": row.source_id,
            "is_adjusted": row.is_adjusted,
            "provider_timestamp_utc": row.provider_timestamp_utc,
        }
        bars.append(validate(payload))
    return tuple(bars)'''
replay = replay[:start] + new_converter + replay[end:]

readme_anchor = (
    "The next staged execution-only probe reuses one in-memory DuckDB connection per persistent replay worker and caches immutable exchange-calendar frames by native month; source/checkpoint reads, canonical SHA-256 verification, the proven dual-query validation/materialization path, and scientific output bytes remain unchanged."
)
readme_replacement = (
    "That worker-resource-reuse probe is now **ACCEPTED** on workstation evidence: the 10 x 1 exact-equivalence run passed **10/10** JSONL SHA-256 comparisons at **2,781.1 source units/hour**, projecting **21.5 hours full / 17.8 hours remaining**, a **3.9% throughput improvement** over the prior 2,676.8-unit/hour 10 x 1 baseline. The retained implementation reuses only process-local DuckDB/calendar infrastructure; source/checkpoint reads, canonical SHA-256 verification, the proven dual-query validation/materialization path, and scientific output bytes remain unchanged. The next staged execution-only probe removes the intermediate Pandas `to_dict(orient=\"records\")` allocation in canonical-bar construction by using `itertuples`, while deliberately retaining full `CanonicalBar.model_validate()` for every minute bar; exact golden-output equivalence remains mandatory before acceptance."
)
if readme.count(readme_anchor) != 1:
    raise SystemExit(f"README worker-reuse anchor count={readme.count(readme_anchor)}")
readme = readme.replace(readme_anchor, readme_replacement, 1)

roadmap_anchor = (
    "The next staged execution-only probe therefore reuses one in-memory DuckDB connection per persistent worker and caches immutable month calendar frames, eliminating repeated process-local setup work without caching source bytes, checkpoint bindings, canonical hashes, or validation results."
)
roadmap_replacement = (
    "That worker-resource-reuse probe is now **ACCEPTED**: the workstation 10 x 1 verifier passed **10/10** exact JSONL SHA-256 comparisons at **2,781.1 source units/hour**, projecting **21.5 hours full / 17.8 hours remaining**, a **3.9% gain** over the prior 2,676.8-unit/hour baseline. It remains execution-only and caches no source bytes, checkpoint bindings, canonical hashes, or validation results. The next staged execution-only probe replaces the intermediate Pandas `to_dict(orient=\"records\")` allocation in `_canonical_bars` with `itertuples` while retaining full `CanonicalBar.model_validate()` for every minute bar; the authoritative source validator, strategies, outcomes, receipts, hashes, and exact-equivalence gate are unchanged."
)
if roadmap.count(roadmap_anchor) != 1:
    raise SystemExit(f"roadmap worker-reuse anchor count={roadmap.count(roadmap_anchor)}")
roadmap = roadmap.replace(roadmap_anchor, roadmap_replacement, 1)

test_content = '''from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd

from packages.backtesting.b35_development_replay import _canonical_bars
from packages.schemas.market import CanonicalBar

_FIELDS = (
    "symbol", "timestamp_utc", "session_date", "timeframe", "session_segment",
    "open", "high", "low", "close", "volume", "vwap", "transaction_count",
    "provider", "dataset", "source_id", "is_adjusted", "provider_timestamp_utc",
)


def _legacy_reference(frame: pd.DataFrame) -> tuple[CanonicalBar, ...]:
    bars: list[CanonicalBar] = []
    for record in frame.to_dict(orient="records"):
        payload: dict[str, object] = {}
        for field in _FIELDS:
            value = record.get(field)
            if field in {"vwap", "transaction_count"} and pd.isna(value):
                value = None
            payload[field] = value
        bars.append(CanonicalBar.model_validate(payload))
    return tuple(bars)


def test_canonical_bars_itertuples_matches_legacy_validated_conversion() -> None:
    premarket_stamp = datetime(2026, 4, 30, 12, 0, tzinfo=UTC)
    regular_stamp = datetime(2026, 4, 30, 13, 30, tzinfo=UTC)
    frame = pd.DataFrame([
        {
            "symbol": "TpC", "timestamp_utc": premarket_stamp,
            "session_date": date(2026, 4, 30), "timeframe": "1m",
            "session_segment": "premarket", "open": 10.0, "high": 10.2,
            "low": 9.9, "close": 10.1, "volume": 100.0, "vwap": None,
            "transaction_count": None, "provider": "alpaca",
            "dataset": "stock_minute_aggregates", "source_id": "test-source-1",
            "is_adjusted": False, "provider_timestamp_utc": premarket_stamp,
        },
        {
            "symbol": "TEST", "timestamp_utc": regular_stamp,
            "session_date": date(2026, 4, 30), "timeframe": "1m",
            "session_segment": "regular", "open": 20.0, "high": 20.5,
            "low": 19.8, "close": 20.3, "volume": 250.0, "vwap": 20.2,
            "transaction_count": 7, "provider": "alpaca",
            "dataset": "stock_minute_aggregates", "source_id": "test-source-2",
            "is_adjusted": False, "provider_timestamp_utc": regular_stamp,
        },
    ])

    expected = _legacy_reference(frame)
    actual = _canonical_bars(frame)
    assert [item.model_dump(mode="python") for item in actual] == [
        item.model_dump(mode="python") for item in expected
    ]
    assert [type(item.session_segment) for item in actual] == [
        type(item.session_segment) for item in expected
    ]
    assert [type(item.timeframe) for item in actual] == [
        type(item.timeframe) for item in expected
    ]
    assert [item.symbol for item in actual] == ["TpC", "TEST"]
'''

replay_path.write_text(replay, encoding="utf-8")
readme_path.write_text(readme, encoding="utf-8")
roadmap_path.write_text(roadmap, encoding="utf-8")
test_path.write_text(test_content, encoding="utf-8")
