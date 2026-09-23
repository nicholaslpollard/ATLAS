from __future__ import annotations

import hashlib
import json
from datetime import datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from packages.data import marketdata_massive_dia_gap_diagnostic_v1 as diagnostic


EASTERN = ZoneInfo("America/New_York")


def _epoch_seconds(date_text: str) -> int:
    d = datetime.fromisoformat(date_text).date()
    return int(datetime.combine(d, time(16, 0), tzinfo=EASTERN).timestamp())


def _epoch_millis(date_text: str) -> int:
    d = datetime.fromisoformat(date_text).date()
    return int(datetime.combine(d, time(0, 0), tzinfo=EASTERN).timestamp() * 1000)


def _write_raw(path, payload):
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


def test_trade_field_eligibility_respects_false_precedence() -> None:
    conditions = {
        1: {
            "update_rules": {
                "consolidated": {
                    "updates_high_low": True,
                    "updates_open_close": True,
                    "updates_volume": True,
                }
            }
        },
        2: {
            "update_rules": {
                "consolidated": {
                    "updates_high_low": False,
                    "updates_open_close": False,
                    "updates_volume": True,
                }
            }
        },
    }
    result = diagnostic._trade_field_eligibility(
        {"conditions": [1, 2]},
        conditions,
    )
    assert result == {
        "updates_high_low": False,
        "updates_open_close": False,
        "updates_volume": True,
    }


def test_classify_day_distinguishes_no_trades_and_eligible_trades() -> None:
    assert diagnostic._classify_day([], {})["disposition"] == "NO_RAW_TRADES"

    result = diagnostic._classify_day(
        [{"size": 2, "conditions": []}],
        {},
    )
    assert result["price_eligible_trade_count"] == 1
    assert result["volume_eligible_trade_count"] == 1
    assert result["disposition"] == "PRICE_ELIGIBLE_RAW_TRADES_WITHOUT_DAILY_BAR"


class _FakeMassive:
    def __init__(self):
        self.calls = []

    def get_json(self, path, params=None):
        self.calls.append((path, params))
        if path == "/v3/reference/conditions":
            return {
                "status": "OK",
                "results": [
                    {
                        "id": 99,
                        "name": "Synthetic Ineligible",
                        "type": "sale_condition",
                        "update_rules": {
                            "consolidated": {
                                "updates_high_low": False,
                                "updates_open_close": False,
                                "updates_volume": False,
                            }
                        },
                    }
                ],
            }
        if path.startswith("/v3/trades/"):
            session_date = str((params or {}).get("timestamp"))
            if session_date.endswith("04"):
                return {"status": "OK", "results": []}
            return {
                "status": "OK",
                "results": [
                    {
                        "price": 1.0,
                        "size": 1,
                        "conditions": [99],
                        "sip_timestamp": 1,
                    }
                ],
            }
        raise AssertionError(path)


def test_end_to_end_gap_diagnostic_preserves_failed_v1(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    run_id = diagnostic.CONTRACT["failed_validation"]["run_id"]
    source_root = (
        tmp_path
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_massive_validation_v1"
        / run_id
    )
    dates = [
        "2026-08-03",
        "2026-08-04",
        "2026-08-05",
        "2026-08-06",
        "2026-08-07",
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
        "2026-08-13",
    ]
    aggregate_dates = {
        "2026-08-03",
        "2026-08-05",
        "2026-08-10",
        "2026-08-12",
    }
    quote_receipt = _write_raw(
        source_root / "raw_marketdata" / "dia-quotes.json",
        {
            "s": "ok",
            "optionSymbol": [diagnostic.CONTRACT["target"]["option_symbol"]] * 9,
            "last": [1.0] * 9,
            "volume": [0, 0, 2, 0, 3, 0, 4, 0, 5],
            "bid": [0.9] * 9,
            "ask": [1.1] * 9,
            "updated": [_epoch_seconds(d) for d in dates],
        },
    )
    aggregate_receipt = _write_raw(
        source_root / "raw_massive" / "dia-aggs.json",
        {
            "status": "OK",
            "results": [
                {
                    "t": _epoch_millis(d),
                    "o": 1.0,
                    "h": 1.1,
                    "l": 0.9,
                    "c": 1.0,
                    "v": 1,
                }
                for d in sorted(aggregate_dates)
            ],
        },
    )
    report = {
        "contract_id": diagnostic.CONTRACT["failed_validation"]["contract_id"],
        "run_id": run_id,
        "status": "VALIDATION_FAILED",
        "validation_passed": False,
        "anchor_pass_count": 3,
        "anchors": [
            {
                "root": "DIA",
                "option_symbol": diagnostic.CONTRACT["target"]["option_symbol"],
                "passed": False,
                "marketdata_quote_rows": 9,
                "massive_aggregate_rows": 4,
                "overlap_sessions": 4,
                "quote_raw_receipt": quote_receipt,
                "massive_raw_receipt": aggregate_receipt,
            }
        ],
    }
    fingerprint = diagnostic.stable_fingerprint(report)
    monkeypatch.setitem(
        diagnostic.CONTRACT["failed_validation"],
        "evidence_fingerprint",
        fingerprint,
    )
    report["evidence_fingerprint"] = fingerprint
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "report.json").write_text(json.dumps(report), encoding="utf-8")

    fake = _FakeMassive()
    result = diagnostic.run_marketdata_massive_dia_gap_diagnostic_v1(
        SimpleNamespace(project_root=tmp_path),
        massive_client=fake,
    )

    assert result["status"] == "DIAGNOSTIC_COMPLETE"
    assert result["source_validation_passed"] is False
    assert len(result["missing_aggregate_dates"]) == 5
    assert len(result["days"]) == 5
    assert result["authority"]["may_reinterpret_failed_validation"] is False
    assert result["limitations"]["failed_v1_validation_remains_failed"] is True
    assert any(
        item["disposition"] == "NO_RAW_TRADES"
        for item in result["days"]
    )
    assert any(
        item["disposition"] == "NO_PRICE_ELIGIBLE_RAW_TRADES"
        for item in result["days"]
    )
