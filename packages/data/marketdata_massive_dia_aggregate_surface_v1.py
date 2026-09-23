from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_massive_dia_gap_diagnostic_v1 import (
    DIAGapDiagnosticError,
    _load_json,
    _persist_raw,
    _target_anchor,
    _verify_receipt,
    load_failed_validation_report,
)
from packages.data.marketdata_massive_overlap_v1 import _marketdata_date, _massive_date
from packages.data.provider_source_qualification import stable_fingerprint
from packages.providers.marketdata_app import array_rows
from packages.providers.massive.rest import MassiveRESTClient


CONTRACT = {
    "contract_id": "atlas-marketdata-massive-dia-aggregate-surface-diagnostic-v1",
    "purpose": (
        "test whether the frozen DIA missing-day failure is consistent across "
        "Massive daily and minute aggregate surfaces available on Options Basic"
    ),
    "triggering_diagnostic": {
        "contract_id": "atlas-marketdata-massive-dia-gap-diagnostic-v1",
        "run_id": "20260923T222933Z",
        "evidence_fingerprint": (
            "48d58cecf4d084f241f8b6b008454427389be609c18d42ffcdcb318a12be4e6a"
        ),
        "status": "DIAGNOSTIC_INCOMPLETE",
        "terminal_error": "ProviderError: Massive REST request failed with HTTP 403",
    },
    "target": {
        "root": "DIA",
        "option_symbol": "DIA260904C00531000",
        "massive_ticker": "O:DIA260904C00531000",
        "from_date": "2026-08-03",
        "to_date": "2026-08-13",
        "expected_marketdata_rows": 9,
        "expected_massive_daily_rows": 4,
        "expected_missing_daily_rows": 5,
    },
    "minute_query": {
        "multiplier": 1,
        "timespan": "minute",
        "adjusted": False,
        "sort": "asc",
        "limit": 50000,
        "expected_calls": 9,
    },
    "authority": {
        "diagnostic_only": True,
        "raw_trade_presence_proven": False,
        "trade_condition_eligibility_proven": False,
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


def _report_root(settings: AtlasSettings, run_id: str) -> Path:
    return (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_massive_dia_aggregate_surface_v1"
        / run_id
    )


def _classify_surface(*, daily_present: bool, minute_rows: int) -> str:
    if daily_present and minute_rows > 0:
        return "DAILY_AND_MINUTE_AGGREGATES_PRESENT"
    if daily_present:
        return "DAILY_PRESENT_MINUTE_ABSENT"
    if minute_rows > 0:
        return "DAILY_ABSENT_MINUTE_PRESENT"
    return "DAILY_AND_MINUTE_AGGREGATES_ABSENT"


def _surface_consistent(records: list[dict[str, Any]]) -> bool:
    if not records:
        return False
    return all(
        item.get("disposition")
        in {
            "DAILY_AND_MINUTE_AGGREGATES_PRESENT",
            "DAILY_AND_MINUTE_AGGREGATES_ABSENT",
        }
        for item in records
    )


def run_marketdata_massive_dia_aggregate_surface_v1(
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

    daily_by_date: dict[str, dict[str, Any]] = {}
    for row in massive_rows:
        session_date = _massive_date(row.get("t"))
        if session_date in daily_by_date:
            raise DIAGapDiagnosticError(
                f"duplicate Massive DIA daily aggregate for {session_date}"
            )
        daily_by_date[session_date] = row

    target = CONTRACT["target"]
    if len(md_by_date) != int(target["expected_marketdata_rows"]):
        raise DIAGapDiagnosticError("target DIA MarketData row count changed")
    if len(daily_by_date) != int(target["expected_massive_daily_rows"]):
        raise DIAGapDiagnosticError("target DIA Massive daily row count changed")

    missing_dates = sorted(set(md_by_date).difference(daily_by_date))
    if len(missing_dates) != int(target["expected_missing_daily_rows"]):
        raise DIAGapDiagnosticError("target DIA missing-day count changed")

    generated = datetime.now(UTC)
    run_id = generated.strftime("%Y%m%dT%H%M%SZ")
    root = _report_root(settings, run_id)
    root.mkdir(parents=True, exist_ok=True)
    client = massive_client or MassiveRESTClient(settings)
    cfg = CONTRACT["minute_query"]

    records: list[dict[str, Any]] = []
    terminal_error: str | None = None
    dates = sorted(md_by_date)

    for index, session_date in enumerate(dates, start=1):
        md_row = md_by_date[session_date]
        daily_present = session_date in daily_by_date
        print(
            f"  [{index}/{len(dates)}] {target['massive_ticker']} "
            f"1-minute aggregates @ {session_date} "
            f"(daily_present={daily_present})",
            flush=True,
        )
        try:
            payload = client.get_json(
                (
                    f"/v2/aggs/ticker/{target['massive_ticker']}/range/"
                    f"{cfg['multiplier']}/{cfg['timespan']}/"
                    f"{session_date}/{session_date}"
                ),
                {
                    "adjusted": cfg["adjusted"],
                    "sort": cfg["sort"],
                    "limit": cfg["limit"],
                },
            )
            receipt = _persist_raw(
                root,
                label=f"{index:02d}-{session_date}-minute-aggs",
                payload=payload,
            )
            raw_results = payload.get("results") or []
            if not isinstance(raw_results, list):
                raise DIAGapDiagnosticError(
                    f"Massive minute results were not a list for {session_date}"
                )
            minute_rows = [item for item in raw_results if isinstance(item, dict)]
        except Exception as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            records.append(
                {
                    "date": session_date,
                    "status": "MASSIVE_MINUTE_AGG_ERROR",
                    "daily_present": daily_present,
                    "marketdata_last": md_row.get("last"),
                    "marketdata_volume": md_row.get("volume"),
                    "error": terminal_error,
                }
            )
            print(f"      STOP: {terminal_error}", flush=True)
            break

        minute_volume = 0.0
        for row in minute_rows:
            try:
                minute_volume += float(row.get("v") or 0.0)
            except (TypeError, ValueError):
                pass

        disposition = _classify_surface(
            daily_present=daily_present,
            minute_rows=len(minute_rows),
        )
        record = {
            "date": session_date,
            "status": "DIAGNOSED",
            "daily_present": daily_present,
            "marketdata_last": md_row.get("last"),
            "marketdata_volume": md_row.get("volume"),
            "marketdata_bid": md_row.get("bid"),
            "marketdata_ask": md_row.get("ask"),
            "massive_daily_volume": (
                daily_by_date[session_date].get("v") if daily_present else None
            ),
            "minute_aggregate_rows": len(minute_rows),
            "minute_aggregate_volume_sum": minute_volume,
            "minute_raw_receipt": receipt,
            "disposition": disposition,
            "error": None,
        }
        records.append(record)
        print(
            f"      md_volume={record['marketdata_volume']} "
            f"minute_rows={record['minute_aggregate_rows']} "
            f"minute_volume={record['minute_aggregate_volume_sum']} "
            f"disposition={record['disposition']}",
            flush=True,
        )

    complete = terminal_error is None and len(records) == len(dates)
    consistent = complete and _surface_consistent(records)
    counts = Counter(
        str(item.get("disposition"))
        for item in records
        if item.get("disposition")
    )

    if not complete:
        status = "DIAGNOSTIC_INCOMPLETE"
    elif consistent:
        status = "AGGREGATE_SURFACES_CONSISTENT"
    else:
        status = "AGGREGATE_SURFACE_INCONSISTENCY"

    report: dict[str, Any] = {
        "status": status,
        "contract_id": CONTRACT["contract_id"],
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "run_id": run_id,
        "generated_at_utc": generated.isoformat(),
        "triggering_diagnostic": CONTRACT["triggering_diagnostic"],
        "failed_validation": CONTRACT["target"],
        "marketdata_dates": dates,
        "massive_daily_dates": sorted(daily_by_date),
        "missing_daily_dates": missing_dates,
        "records": records,
        "disposition_counts": dict(sorted(counts.items())),
        "surface_consistent": consistent,
        "terminal_error": terminal_error,
        "authority": CONTRACT["authority"],
        "limitations": {
            "raw_trades_endpoint_not_used": True,
            "cannot_distinguish_no_raw_trades_from_ineligible_raw_trades": True,
            "failed_v1_validation_remains_failed": True,
            "raw_trade_diagnostic_remains_incomplete": True,
            "diagnostic_does_not_change_frozen_thresholds": True,
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
