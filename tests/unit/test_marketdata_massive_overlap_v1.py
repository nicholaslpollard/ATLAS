from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data import marketdata_massive_overlap_v1 as overlap


def _epoch_seconds(date_text: str) -> int:
    dt = datetime.fromisoformat(date_text + "T16:00:00-04:00")
    return int(dt.timestamp())


def _epoch_millis(date_text: str) -> int:
    dt = datetime.fromisoformat(date_text + "T00:00:00-04:00")
    return int(dt.timestamp() * 1000)


def test_compare_exact_contract_days_maps_eastern_dates() -> None:
    md = (
        {
            "updated": _epoch_seconds("2026-09-01"),
            "last": 3.10,
            "volume": 100,
        },
        {
            "updated": _epoch_seconds("2026-09-02"),
            "last": 3.25,
            "volume": 120,
        },
    )
    massive = [
        {
            "t": _epoch_millis("2026-09-01"),
            "o": 3.0,
            "h": 3.2,
            "l": 2.9,
            "c": 3.10,
            "v": 100,
        },
        {
            "t": _epoch_millis("2026-09-02"),
            "o": 3.1,
            "h": 3.4,
            "l": 3.0,
            "c": 3.20,
            "v": 118,
        },
    ]

    rows = overlap.compare_exact_contract_days(md, massive)
    assert [row["date"] for row in rows] == ["2026-09-01", "2026-09-02"]
    assert rows[0]["price_abs_diff"] == pytest.approx(0.0)
    assert rows[1]["price_abs_diff"] == pytest.approx(0.05)
    assert rows[0]["marketdata_last_inside_massive_range"] is True
    assert rows[1]["marketdata_last_inside_massive_range"] is True

    summary = overlap.summarize_comparisons(rows)
    assert summary["overlap_sessions"] == 2
    assert summary["exact_price_match_sessions"] == 1
    assert summary["exact_price_match_rate"] == pytest.approx(0.5)
    assert summary["marketdata_last_inside_massive_range_rate"] == pytest.approx(1.0)


def test_duplicate_daily_rows_fail_closed() -> None:
    md = (
        {"updated": _epoch_seconds("2026-09-01"), "last": 1.0, "volume": 1},
        {"updated": _epoch_seconds("2026-09-01"), "last": 1.1, "volume": 2},
    )
    with pytest.raises(overlap.MarketDataMassiveOverlapError, match="duplicate"):
        overlap.compare_exact_contract_days(md, [])


class _FakeMassive:
    def __init__(self) -> None:
        self.calls = []

    def get_json(self, path, params):
        self.calls.append((path, params))
        return {
            "status": "OK",
            "results": [
                {
                    "t": _epoch_millis("2026-09-01"),
                    "o": 1.0,
                    "h": 1.2,
                    "l": 0.9,
                    "c": 1.1,
                    "v": 10,
                }
            ],
        }


def _write_raw(path: Path, payload: dict) -> dict:
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
    }


def test_end_to_end_reuses_accepted_marketdata_raw_without_marketdata_reads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = overlap.CONTRACT["marketdata_source"]["run_id"]
    root = (
        tmp_path
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_app"
        / "historical_options_v1"
        / run_id
    )
    anchors = []
    for index, root_symbol in enumerate(["SPY", "MSFT", "NVDA", "QQQ"], start=1):
        raw = _write_raw(
            root / "raw" / f"{index:02d}-{root_symbol}-quotes.json",
            {
                "s": "ok",
                "optionSymbol": [f"{root_symbol}261016C00100000"],
                "last": [1.1],
                "volume": [10],
                "updated": [_epoch_seconds("2026-09-01")],
            },
        )
        anchors.append(
            {
                "root": root_symbol,
                "date": "2026-09-01",
                "selected_option_symbol": f"{root_symbol}261016C00100000",
                "quote_raw_receipt": raw,
            }
        )
    anchors.insert(
        0,
        {
            "root": "AAPL",
            "date": "2021-10-01",
            "selected_option_symbol": "AAPL211029C00143000",
            "quote_raw_receipt": {},
        },
    )
    report = {
        "status": "QUALIFIED_FOR_STARTER_TRIAL_CAPABILITY",
        "evidence_fingerprint": overlap.CONTRACT["marketdata_source"][
            "evidence_fingerprint"
        ],
        "starter_trial": True,
        "run_id": run_id,
        "anchors": anchors,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "report.json").write_text(json.dumps(report), encoding="utf-8")

    fake = _FakeMassive()
    result = overlap.run_marketdata_massive_overlap_diagnostic_v1(
        SimpleNamespace(project_root=tmp_path),
        massive_client=fake,
    )

    assert result["status"] == "DIAGNOSTIC_COMPLETE"
    assert result["massive_source_anchor_count"] == 4
    assert result["total_overlap_sessions"] == 4
    assert len(fake.calls) == 4
    assert all("adjusted" in params and params["adjusted"] is False for _, params in fake.calls)
    assert all(path.startswith("/v2/aggs/ticker/O:") for path, _ in fake.calls)
    assert result["limitations"]["historical_price_authority_created"] is False


def test_source_report_fingerprint_mismatch_fails_closed(tmp_path: Path) -> None:
    run_id = overlap.CONTRACT["marketdata_source"]["run_id"]
    root = (
        tmp_path
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_app"
        / "historical_options_v1"
        / run_id
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "report.json").write_text(
        json.dumps(
            {
                "status": "QUALIFIED_FOR_STARTER_TRIAL_CAPABILITY",
                "evidence_fingerprint": "0" * 64,
                "starter_trial": True,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(overlap.MarketDataMassiveOverlapError, match="fingerprint"):
        overlap.load_accepted_marketdata_trial_report(
            SimpleNamespace(project_root=tmp_path)
        )
