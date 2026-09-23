from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_five_year_options_qualification import array_rows
from packages.data.marketdata_massive_overlap_v1 import (
    _marketdata_date,
    _massive_date,
)
from packages.data.provider_source_qualification import stable_fingerprint
from packages.providers.massive.rest import MassiveRESTClient


CONTRACT = {
    "contract_id": "atlas-marketdata-massive-dia-gap-diagnostic-v1",
    "purpose": (
        "diagnose the frozen V1 disjoint-validation failure caused by missing "
        "Massive daily aggregates for DIA260904C00531000 without altering V1"
    ),
    "failed_validation": {
        "contract_id": "atlas-marketdata-massive-disjoint-validation-v1",
        "run_id": "20260923T211759Z",
        "evidence_fingerprint": (
            "2ab5dc3012bdbda388e6d2648403814999c54aa9ac0d4184295c595072eea145"
        ),
        "status": "VALIDATION_FAILED",
    },
    "target": {
        "root": "DIA",
        "option_symbol": "DIA260904C00531000",
        "massive_ticker": "O:DIA260904C00531000",
        "from_date": "2026-08-03",
        "to_date": "2026-08-13",
        "expected_marketdata_rows": 9,
        "expected_massive_aggregate_rows": 4,
        "expected_overlap_rows": 4,
    },
    "massive_trades_query": {
        "sort": "timestamp",
        "order": "asc",
        "limit": 50000,
        "max_pages_per_missing_date": 3,
    },
    "conditions_query": {
        "asset_class": "options",
        "data_type": "trade",
        "limit": 1000,
        "max_pages": 3,
    },
    "authority": {
        "diagnostic_only": True,
        "may_reinterpret_failed_validation": False,
        "may_widen_frozen_thresholds": False,
        "historical_price_authority": False,
        "historical_bid_ask_authority": False,
        "simulator_authority": False,
        "strategy_evidence": False,
        "paper": False,
        "live": False,
        "orders": False,
        "promotion": False,
    },
}
CONTRACT_FINGERPRINT = stable_fingerprint(CONTRACT)


class DIAGapDiagnosticError(RuntimeError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DIAGapDiagnosticError(f"JSON root is not an object: {path}")
    return payload


def _verify_receipt(receipt: dict[str, Any]) -> Path:
    path = Path(str(receipt.get("path") or ""))
    expected = str(receipt.get("sha256") or "").strip().lower()
    if not path.is_file():
        raise DIAGapDiagnosticError(f"source raw file is missing: {path}")
    actual = _sha256_bytes(path.read_bytes())
    if not expected or actual != expected:
        raise DIAGapDiagnosticError(
            f"source raw hash mismatch for {path}: expected={expected} actual={actual}"
        )
    return path


def _source_report_path(settings: AtlasSettings) -> Path:
    run_id = str(CONTRACT["failed_validation"]["run_id"])
    return (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_massive_validation_v1"
        / run_id
        / "report.json"
    )


def load_failed_validation_report(settings: AtlasSettings) -> dict[str, Any]:
    path = _source_report_path(settings)
    if not path.is_file():
        raise DIAGapDiagnosticError(f"failed validation report is missing: {path}")
    report = _load_json(path)

    expected = CONTRACT["failed_validation"]
    if report.get("contract_id") != expected["contract_id"]:
        raise DIAGapDiagnosticError(
            f"source contract mismatch: {report.get('contract_id')!r}"
        )
    if report.get("run_id") != expected["run_id"]:
        raise DIAGapDiagnosticError(
            f"source run id mismatch: {report.get('run_id')!r}"
        )
    if report.get("status") != expected["status"]:
        raise DIAGapDiagnosticError(
            f"source status mismatch: {report.get('status')!r}"
        )
    if report.get("evidence_fingerprint") != expected["evidence_fingerprint"]:
        raise DIAGapDiagnosticError("source evidence fingerprint mismatch")

    recomputed = stable_fingerprint(
        {
            key: value
            for key, value in report.items()
            if key != "evidence_fingerprint"
        }
    )
    if recomputed != expected["evidence_fingerprint"]:
        raise DIAGapDiagnosticError(
            "source report contents do not reproduce the accepted evidence fingerprint"
        )
    return report


def _target_anchor(report: dict[str, Any]) -> dict[str, Any]:
    target = CONTRACT["target"]
    matches = [
        item
        for item in report.get("anchors", [])
        if isinstance(item, dict)
        and item.get("root") == target["root"]
        and item.get("option_symbol") == target["option_symbol"]
    ]
    if len(matches) != 1:
        raise DIAGapDiagnosticError(
            f"expected exactly one target DIA anchor, found {len(matches)}"
        )
    anchor = matches[0]
    if anchor.get("passed") is not False:
        raise DIAGapDiagnosticError("target DIA anchor is not the failed anchor")
    if int(anchor.get("marketdata_quote_rows") or 0) != int(
        target["expected_marketdata_rows"]
    ):
        raise DIAGapDiagnosticError("target DIA MarketData row count changed")
    if int(anchor.get("massive_aggregate_rows") or 0) != int(
        target["expected_massive_aggregate_rows"]
    ):
        raise DIAGapDiagnosticError("target DIA Massive aggregate row count changed")
    if int(anchor.get("overlap_sessions") or 0) != int(
        target["expected_overlap_rows"]
    ):
        raise DIAGapDiagnosticError("target DIA overlap count changed")
    return anchor


def _persist_raw(
    root: Path,
    *,
    label: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    raw_dir = root / "raw_massive"
    raw_dir.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str) + "\n"
    ).encode("utf-8")
    path = raw_dir / f"{label}.json"
    path.write_bytes(encoded)
    receipt = {
        "path": str(path.resolve()),
        "sha256": _sha256_bytes(encoded),
        "bytes": len(encoded),
    }
    atomic_write_text(
        raw_dir / f"{label}.receipt.json",
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
    )
    return receipt


def _bounded_pages(
    client: MassiveRESTClient,
    *,
    path: str,
    params: dict[str, Any],
    max_pages: int,
    persist_root: Path,
    label_prefix: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    payload = client.get_json(path, params)
    page = 0
    truncated = False

    while True:
        page += 1
        receipts.append(
            _persist_raw(
                persist_root,
                label=f"{label_prefix}-page-{page:02d}",
                payload=payload,
            )
        )
        results = payload.get("results") or []
        if not isinstance(results, list):
            raise DIAGapDiagnosticError(
                f"Massive results were not a list for {label_prefix} page {page}"
            )
        rows.extend(item for item in results if isinstance(item, dict))

        next_url = payload.get("next_url")
        if not next_url:
            break
        if page >= max_pages:
            truncated = True
            break
        payload = client.get_json(str(next_url))

    return rows, receipts, truncated


def _condition_map(
    client: MassiveRESTClient,
    *,
    persist_root: Path,
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]], bool]:
    cfg = CONTRACT["conditions_query"]
    rows, receipts, truncated = _bounded_pages(
        client,
        path="/v3/reference/conditions",
        params={
            "asset_class": cfg["asset_class"],
            "data_type": cfg["data_type"],
            "limit": cfg["limit"],
        },
        max_pages=int(cfg["max_pages"]),
        persist_root=persist_root,
        label_prefix="options-trade-conditions",
    )
    mapped: dict[int, dict[str, Any]] = {}
    for row in rows:
        try:
            condition_id = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        mapped[condition_id] = row
    return mapped, receipts, truncated


def _trade_field_eligibility(
    trade: dict[str, Any],
    conditions: dict[int, dict[str, Any]],
) -> dict[str, bool | None]:
    raw_codes = trade.get("conditions") or []
    codes: list[int] = []
    for value in raw_codes if isinstance(raw_codes, list) else []:
        try:
            codes.append(int(value))
        except (TypeError, ValueError):
            continue

    if not codes:
        return {
            "updates_high_low": True,
            "updates_open_close": True,
            "updates_volume": True,
        }

    fields = ("updates_high_low", "updates_open_close", "updates_volume")
    result: dict[str, bool | None] = {}
    for field in fields:
        values: list[bool | None] = []
        for code in codes:
            metadata = conditions.get(code)
            consolidated = (
                metadata.get("update_rules", {}).get("consolidated", {})
                if isinstance(metadata, dict)
                else {}
            )
            value = consolidated.get(field) if isinstance(consolidated, dict) else None
            values.append(value if isinstance(value, bool) else None)

        if any(value is False for value in values):
            result[field] = False
        elif all(value is True for value in values):
            result[field] = True
        else:
            result[field] = None
    return result


def _classify_day(
    trades: list[dict[str, Any]],
    conditions: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    condition_counts: Counter[int] = Counter()
    no_condition_count = 0
    price_eligible = 0
    volume_eligible = 0
    aggregate_ineligible = 0
    aggregate_unresolved = 0
    trade_size = 0.0

    for trade in trades:
        raw_codes = trade.get("conditions") or []
        codes: list[int] = []
        if isinstance(raw_codes, list):
            for value in raw_codes:
                try:
                    code = int(value)
                except (TypeError, ValueError):
                    continue
                codes.append(code)
                condition_counts[code] += 1
        if not codes:
            no_condition_count += 1

        try:
            trade_size += float(trade.get("size") or 0.0)
        except (TypeError, ValueError):
            pass

        fields = _trade_field_eligibility(trade, conditions)
        high_low = fields["updates_high_low"]
        open_close = fields["updates_open_close"]
        volume = fields["updates_volume"]

        if high_low is True or open_close is True:
            price_eligible += 1
        if volume is True:
            volume_eligible += 1

        values = [high_low, open_close, volume]
        if all(value is False for value in values):
            aggregate_ineligible += 1
        elif any(value is None for value in values):
            aggregate_unresolved += 1

    if not trades:
        disposition = "NO_RAW_TRADES"
    elif price_eligible > 0:
        disposition = "PRICE_ELIGIBLE_RAW_TRADES_WITHOUT_DAILY_BAR"
    elif aggregate_unresolved > 0:
        disposition = "RAW_TRADES_PRESENT_ELIGIBILITY_UNRESOLVED"
    else:
        disposition = "NO_PRICE_ELIGIBLE_RAW_TRADES"

    condition_details = []
    for code, count in sorted(condition_counts.items()):
        meta = conditions.get(code, {})
        condition_details.append(
            {
                "id": code,
                "count": count,
                "name": meta.get("name") if isinstance(meta, dict) else None,
                "type": meta.get("type") if isinstance(meta, dict) else None,
                "update_rules": (
                    meta.get("update_rules") if isinstance(meta, dict) else None
                ),
            }
        )

    return {
        "raw_trade_count": len(trades),
        "raw_trade_size_sum": trade_size,
        "no_condition_trade_count": no_condition_count,
        "price_eligible_trade_count": price_eligible,
        "volume_eligible_trade_count": volume_eligible,
        "aggregate_ineligible_trade_count": aggregate_ineligible,
        "aggregate_eligibility_unresolved_trade_count": aggregate_unresolved,
        "condition_counts": dict(sorted(condition_counts.items())),
        "condition_details": condition_details,
        "disposition": disposition,
    }


def _report_root(settings: AtlasSettings, run_id: str) -> Path:
    return (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_massive_dia_gap_v1"
        / run_id
    )


def run_marketdata_massive_dia_gap_diagnostic_v1(
    settings: AtlasSettings,
    *,
    massive_client: MassiveRESTClient | None = None,
) -> dict[str, Any]:
    source = load_failed_validation_report(settings)
    anchor = _target_anchor(source)

    quote_receipt = anchor.get("quote_raw_receipt")
    aggregate_receipt = anchor.get("massive_raw_receipt")
    if not isinstance(quote_receipt, dict) or not isinstance(aggregate_receipt, dict):
        raise DIAGapDiagnosticError("target DIA anchor lacks required raw receipts")

    marketdata_path = _verify_receipt(quote_receipt)
    massive_path = _verify_receipt(aggregate_receipt)
    marketdata_payload = _load_json(marketdata_path)
    massive_payload = _load_json(massive_path)
    marketdata_rows = array_rows(marketdata_payload)

    massive_results = massive_payload.get("results") or []
    massive_rows = (
        [item for item in massive_results if isinstance(item, dict)]
        if isinstance(massive_results, list)
        else []
    )

    md_by_date: dict[str, dict[str, Any]] = {}
    for row in marketdata_rows:
        session_date = _marketdata_date(row.get("updated"))
        if session_date in md_by_date:
            raise DIAGapDiagnosticError(
                f"duplicate MarketData DIA EOD row for {session_date}"
            )
        md_by_date[session_date] = row

    massive_dates: set[str] = set()
    for row in massive_rows:
        session_date = _massive_date(row.get("t"))
        if session_date in massive_dates:
            raise DIAGapDiagnosticError(
                f"duplicate Massive DIA daily aggregate for {session_date}"
            )
        massive_dates.add(session_date)

    missing_dates = sorted(set(md_by_date).difference(massive_dates))
    if len(missing_dates) != (
        int(CONTRACT["target"]["expected_marketdata_rows"])
        - int(CONTRACT["target"]["expected_overlap_rows"])
    ):
        raise DIAGapDiagnosticError(
            f"unexpected DIA missing-date count: {len(missing_dates)}"
        )

    generated = datetime.now(UTC)
    run_id = generated.strftime("%Y%m%dT%H%M%SZ")
    root = _report_root(settings, run_id)
    root.mkdir(parents=True, exist_ok=True)
    client = massive_client or MassiveRESTClient(settings)

    conditions, condition_receipts, conditions_truncated = _condition_map(
        client,
        persist_root=root,
    )

    day_records: list[dict[str, Any]] = []
    terminal_error: str | None = None
    trade_cfg = CONTRACT["massive_trades_query"]

    for index, session_date in enumerate(missing_dates, start=1):
        md_row = md_by_date[session_date]
        print(
            f"  [{index}/{len(missing_dates)}] {CONTRACT['target']['massive_ticker']} "
            f"raw trades @ {session_date}",
            flush=True,
        )
        try:
            trades, receipts, truncated = _bounded_pages(
                client,
                path=f"/v3/trades/{CONTRACT['target']['massive_ticker']}",
                params={
                    "timestamp": session_date,
                    "sort": trade_cfg["sort"],
                    "order": trade_cfg["order"],
                    "limit": trade_cfg["limit"],
                },
                max_pages=int(trade_cfg["max_pages_per_missing_date"]),
                persist_root=root,
                label_prefix=f"{index:02d}-{session_date}-trades",
            )
        except Exception as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            day_records.append(
                {
                    "date": session_date,
                    "status": "MASSIVE_TRADES_ERROR",
                    "marketdata_last": md_row.get("last"),
                    "marketdata_volume": md_row.get("volume"),
                    "marketdata_bid": md_row.get("bid"),
                    "marketdata_ask": md_row.get("ask"),
                    "error": terminal_error,
                }
            )
            print(f"      STOP: {terminal_error}", flush=True)
            break

        analysis = _classify_day(trades, conditions)
        record = {
            "date": session_date,
            "status": "DIAGNOSED",
            "marketdata_last": md_row.get("last"),
            "marketdata_volume": md_row.get("volume"),
            "marketdata_bid": md_row.get("bid"),
            "marketdata_ask": md_row.get("ask"),
            "massive_trade_pages": len(receipts),
            "massive_trade_pages_truncated": truncated,
            "massive_trade_raw_receipts": receipts,
            **analysis,
            "error": None,
        }
        day_records.append(record)
        print(
            f"      md_volume={record['marketdata_volume']} "
            f"raw_trades={record['raw_trade_count']} "
            f"price_eligible={record['price_eligible_trade_count']} "
            f"volume_eligible={record['volume_eligible_trade_count']} "
            f"ineligible={record['aggregate_ineligible_trade_count']} "
            f"unresolved={record['aggregate_eligibility_unresolved_trade_count']} "
            f"disposition={record['disposition']}",
            flush=True,
        )

    complete = (
        terminal_error is None
        and len(day_records) == len(missing_dates)
        and not conditions_truncated
        and all(
            item.get("status") == "DIAGNOSED"
            and item.get("massive_trade_pages_truncated") is False
            for item in day_records
        )
    )

    disposition_counts = Counter(
        str(item.get("disposition"))
        for item in day_records
        if item.get("disposition")
    )

    report: dict[str, Any] = {
        "status": "DIAGNOSTIC_COMPLETE" if complete else "DIAGNOSTIC_INCOMPLETE",
        "contract_id": CONTRACT["contract_id"],
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "run_id": run_id,
        "generated_at_utc": generated.isoformat(),
        "failed_validation": CONTRACT["failed_validation"],
        "target": CONTRACT["target"],
        "source_validation_passed": source.get("validation_passed"),
        "source_anchor_pass_count": source.get("anchor_pass_count"),
        "marketdata_dates": sorted(md_by_date),
        "massive_aggregate_dates": sorted(massive_dates),
        "missing_aggregate_dates": missing_dates,
        "condition_metadata_count": len(conditions),
        "conditions_pages_truncated": conditions_truncated,
        "conditions_raw_receipts": condition_receipts,
        "days": day_records,
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "terminal_error": terminal_error,
        "authority": CONTRACT["authority"],
        "limitations": {
            "failed_v1_validation_remains_failed": True,
            "diagnostic_does_not_change_frozen_thresholds": True,
            "raw_trade_condition_interpretation_uses_provider_update_rules": True,
            "historical_bid_ask_not_independently_validated": True,
        },
    }
    report["evidence_fingerprint"] = stable_fingerprint(report)
    report_path = root / "report.json"
    atomic_write_text(
        report_path,
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
    )
    report["report_path"] = str(report_path.resolve())
    return report
