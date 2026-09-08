from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pandas as pd
import pytest

from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    B35DevelopmentScopeError,
    B35DevelopmentSourceError,
)
from packages.data.alpaca_v2_acquisition import (
    ACQUISITION_CONTRACT,
    UNIT_CONTRACT,
    build_native_plan,
)
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import ALPACA_V2_SOURCE_PREFIX


POLICY_SHA = "b" * 64
UNIVERSE_SHA = "c" * 64
NATIVE_UNIT = next(
    item
    for item in build_native_plan(
        symbols=["TEST"],
        start=date(2026, 4, 1),
        cutoff=date(2026, 4, 30),
        universe_sha256=UNIVERSE_SHA,
        policy_sha256=POLICY_SHA,
        batch_size=1,
    )
    if item.canonical_timeframe == "1m"
)
UNIT_ID = NATIVE_UNIT.unit_id


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        project_root=tmp_path,
        data=SimpleNamespace(
            calendar=SimpleNamespace(
                exchange="XNYS",
                market_timezone="America/New_York",
            )
        ),
    )


def _record() -> dict[str, object]:
    # Round-trip through JSON exactly as the persisted acquisition-plan JSONL does:
    # dataclass tuples become JSON arrays/lists before B35 reads the record.
    return json.loads(json.dumps(asdict(NATIVE_UNIT)))


def _paths(layout: V2Layout) -> tuple[Path, Path]:
    partition = Path("year=2026") / "month=04" / "batch=0000"
    prefix = UNIT_ID[:20]
    checkpoint = layout.checkpoints / "native_units" / "1m" / partition / f"{prefix}.json"
    canonical = layout.canonical_minute / partition / f"{prefix}.parquet"
    return checkpoint, canonical


def _write_valid_parquet(
    path: Path,
    *,
    session_segment: str = "regular",
    adjusted: object = False,
    duplicate: bool = False,
) -> None:
    stamp = datetime(2026, 4, 30, 13, 30, tzinfo=UTC)  # 09:30 ET
    rows = [
        {
            "symbol": "TEST",
            "timestamp_utc": stamp,
            "session_date": date(2026, 4, 30),
            "timeframe": "1m",
            "session_segment": session_segment,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000.0,
            "vwap": 100.2,
            "transaction_count": 10,
            "provider": "alpaca",
            "dataset": "stock_minute_aggregates",
            "source_id": ALPACA_V2_SOURCE_PREFIX + UNIT_ID,
            "is_adjusted": adjusted,
            "provider_timestamp_utc": stamp,
        }
    ]
    if duplicate:
        rows.append(dict(rows[0]))
    frame = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        con.register("fixture", frame)
        con.execute("COPY fixture TO ? (FORMAT PARQUET)", [str(path)])
    finally:
        con.close()


def _write_fixture(
    tmp_path: Path,
    *,
    write_checkpoint: bool = True,
    session_segment: str = "regular",
    adjusted: object = False,
    duplicate: bool = False,
) -> B35DevelopmentMinuteSource:
    source = B35DevelopmentMinuteSource(_settings(tmp_path))
    layout = source.layout
    layout.create()
    checkpoint, canonical = _paths(layout)
    _write_valid_parquet(
        canonical,
        session_segment=session_segment,
        adjusted=adjusted,
        duplicate=duplicate,
    )
    canonical_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
    record = _record()
    if write_checkpoint:
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(
            json.dumps(
                {
                    "contract": UNIT_CONTRACT,
                    "status": "COMPLETE",
                    "unit_id": UNIT_ID,
                    "unit": record,
                    "policy_sha256": POLICY_SHA,
                    "universe_sha256": UNIVERSE_SHA,
                    "canonical": {"path": str(canonical), "sha256": canonical_sha},
                    "raw_bundle": {
                        "path": "not-opened-by-b35",
                        "sha256": "d" * 64,
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    raw = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    plan_path = layout.manifests / "native_acquisition_plan.jsonl.gz"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(gzip.compress(raw, mtime=0))
    manifest = {
        "contract": ACQUISITION_CONTRACT,
        "status": "FROZEN",
        "v1_ancestry": "FORBIDDEN",
        "plan_path": str(plan_path),
        "plan_sha256": hashlib.sha256(raw).hexdigest(),
        "plan_file_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
    }
    (layout.manifests / "native_acquisition_plan.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return source


def test_scope_rejects_consumed_master_and_future_blind() -> None:
    with pytest.raises(B35DevelopmentScopeError, match="cannot pass 2026-04-30"):
        B35DevelopmentMinuteSource.validate_scope(
            date(2026, 4, 1), date(2026, 5, 12)
        )
    with pytest.raises(B35DevelopmentScopeError, match="cannot pass 2026-04-30"):
        B35DevelopmentMinuteSource.validate_scope(
            date(2026, 9, 8), date(2026, 9, 8)
        )


def test_plan_requires_exact_expected_checkpoint(tmp_path: Path) -> None:
    source = _write_fixture(tmp_path, write_checkpoint=False)
    with pytest.raises(FileNotFoundError, match="minute checkpoint"):
        source.plan(date(2026, 4, 1), date(2026, 4, 30))


def test_plan_binds_exact_native_writer_paths(tmp_path: Path) -> None:
    source = _write_fixture(tmp_path)
    plan = source.plan(date(2026, 4, 1), date(2026, 4, 30))
    assert len(plan.units) == 1
    binding = plan.units[0]
    checkpoint, canonical = _paths(source.layout)
    assert binding.batch_index == 0
    assert binding.checkpoint_path == checkpoint.absolute()
    assert binding.canonical_path == canonical.absolute()
    assert binding.unit_id == UNIT_ID
    assert binding.policy_sha256 == POLICY_SHA
    assert binding.universe_sha256 == UNIVERSE_SHA


def test_verify_unit_refuses_may_before_touching_file(tmp_path: Path) -> None:
    source = _write_fixture(tmp_path)
    binding = source.plan(date(2026, 4, 1), date(2026, 4, 30)).units[0]
    forbidden = replace(
        binding,
        year=2026,
        month=5,
        window_start=date(2026, 5, 1),
        window_end_exclusive=date(2026, 6, 1),
        canonical_path=tmp_path / "must-not-open.parquet",
    )
    with pytest.raises(B35DevelopmentSourceError, match="in or after May 2026"):
        source.verify_unit(forbidden)
    assert not forbidden.canonical_path.exists()


def test_verify_unit_rejects_external_hash_matching_path(tmp_path: Path) -> None:
    source = _write_fixture(tmp_path)
    binding = source.plan(date(2026, 4, 1), date(2026, 4, 30)).units[0]
    external = tmp_path / "outside.parquet"
    external.write_bytes(binding.canonical_path.read_bytes())
    with pytest.raises(B35DevelopmentSourceError, match="exact frozen native-unit path"):
        source.verify_unit(replace(binding, canonical_path=external))


def test_verify_unit_rejects_hash_drift(tmp_path: Path) -> None:
    source = _write_fixture(tmp_path)
    binding = source.plan(date(2026, 4, 1), date(2026, 4, 30)).units[0]
    binding.canonical_path.write_bytes(b"drifted")
    with pytest.raises(B35DevelopmentSourceError, match="SHA-256 drifted"):
        source.verify_unit(binding)


def test_load_unit_accepts_exact_valid_physical_rows(tmp_path: Path) -> None:
    source = _write_fixture(tmp_path)
    binding = source.plan(date(2026, 4, 1), date(2026, 4, 30)).units[0]
    frame = source.load_unit(
        binding,
        start_session=date(2026, 4, 1),
        end_session=date(2026, 4, 30),
    )
    assert len(frame) == 1
    assert frame.iloc[0]["symbol"] == "TEST"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"session_segment": "after_hours"}, "incorrect session labels"),
        ({"adjusted": None}, "is_adjusted must be BOOLEAN"),
        ({"adjusted": "false"}, "is_adjusted must be BOOLEAN"),
        ({"duplicate": True}, "duplicate minute keys"),
    ],
)
def test_load_unit_rejects_malformed_physical_rows(
    tmp_path: Path,
    kwargs: dict[str, object],
    message: str,
) -> None:
    source = _write_fixture(tmp_path, **kwargs)
    binding = source.plan(date(2026, 4, 1), date(2026, 4, 30)).units[0]
    with pytest.raises(B35DevelopmentSourceError, match=message):
        source.load_unit(
            binding,
            start_session=date(2026, 4, 1),
            end_session=date(2026, 4, 30),
        )
