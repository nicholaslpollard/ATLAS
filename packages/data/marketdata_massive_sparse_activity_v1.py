from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_massive_overlap_v1 import _finite_number, _marketdata_date, _massive_date
from packages.data.provider_source_qualification import stable_fingerprint
from packages.providers.marketdata_app import (
    MarketDataError,
    array_rows,
    historical_chain,
    historical_quote_series,
    rate_limit_snapshot,
)
from packages.providers.massive.rest import MassiveRESTClient


CONTRACT = {
    "contract_id": "atlas-marketdata-massive-sparse-activity-confirmation-v1",
    "purpose": (
        "targeted disjoint confirmation that MarketData zero-volume EOD option rows "
        "correspond to absence of Massive trade-derived daily aggregates while "
        "positive-volume control sessions retain aggregate presence"
    ),
    "evidence_basis": {
        "v2_validation": {
            "run_id": "20260924T023405Z",
            "evidence_fingerprint": (
                "7461146a5c3f3f021384fea54cdfae1c4f62b509ed64f55f8a61b1b0d8d13dad"
            ),
            "status": "VALIDATION_FAILED",
            "anchor_pass_count": 6,
            "positive_volume_comparisons": 53,
            "zero_volume_sessions": 0,
            "aggregate_exact_last_close_match_rate": 1.0,
            "aggregate_last_inside_range_rate": 1.0,
            "aggregate_median_price_relative_diff": 0.0,
            "aggregate_median_volume_relative_diff": 0.0,
            "aggregate_max_volume_relative_diff": 0.00299850,
            "only_failed_gate": "sparse_case_observed",
        },
        "dia_aggregate_surface": {
            "run_id": "20260923T225713Z",
            "evidence_fingerprint": (
                "dadc60d4eb1bf4f33d123cdd1b8b09d92222f8e53b4fdb3a9a28c48b1d5b1487"
            ),
            "status": "AGGREGATE_SURFACES_CONSISTENT",
            "positive_volume_present_sessions": 4,
            "zero_volume_absent_sessions": 5,
        },
    },
    "anchors": [
        {"root": "RSP", "date": "2025-10-06"},
        {"root": "MDY", "date": "2025-11-03"},
        {"root": "IJR", "date": "2025-12-01"},
        {"root": "IEF", "date": "2026-01-12"},
        {"root": "LQD", "date": "2026-02-09"},
        {"root": "XBI", "date": "2026-03-09"},
        {"root": "KRE", "date": "2026-04-06"},
        {"root": "XRT", "date": "2026-05-04"},
        {"root": "XHB", "date": "2026-06-15"},
        {"root": "EEM", "date": "2026-07-13"},
        {"root": "FXI", "date": "2026-08-24"},
        {"root": "EWJ", "date": "2026-09-08"},
    ],
    "excluded_prior_roots": [
        "SPY", "MSFT", "NVDA", "QQQ", "IWM", "AMZN", "META", "DIA",
        "AAPL", "TSLA", "AMD", "JPM", "XLF", "TLT",
    ],
    "excluded_prior_dates": [
        "2026-03-02", "2026-05-01", "2026-07-01", "2026-09-01",
        "2026-02-02", "2026-04-01", "2026-06-01", "2026-08-03",
        "2026-01-05", "2026-02-17", "2026-03-16", "2026-05-18",
        "2026-07-06", "2026-08-17",
    ],
    "chain_query": {
        "dte": 30,
        "strike_limit": 20,
        "side": "call",
    },
    "selection_rule": (
        "farthest OTM call by strike/underlying ratio among returned calls with "
        "finite positive underlying and strike; deterministic option-symbol tiebreak"
    ),
    "quote_series_days": 10,
    "massive_query": {
        "adjusted": False,
        "sort": "asc",
        "limit": 50,
    },
    "preregistered_thresholds": {
        "required_anchor_count": 12,
        "minimum_marketdata_quote_rows_per_anchor": 5,
        "minimum_total_zero_volume_sessions": 10,
        "minimum_zero_volume_anchor_count": 3,
        "minimum_total_positive_volume_sessions": 20,
        "minimum_positive_volume_anchor_count": 3,
        "required_activity_concordance_rate": 1.0,
        "maximum_zero_volume_with_massive_bar": 0,
        "maximum_positive_volume_missing_massive_bar": 0,
        "maximum_extra_massive_dates": 0,
    },
    "authority_if_passed": {
        "marketdata_massive_sparse_activity_concordance_confirmed": True,
        "marketdata_zero_volume_last_validated": False,
        "marketdata_positive_volume_eod_last_volume_semantics_validated": False,
        "historical_bid_ask_validated": False,
        "historical_intraday_validated": False,
        "execution_price_authority": False,
        "simulator_authority": False,
        "strategy_evidence": False,
        "paper": False,
        "live": False,
        "orders": False,
        "promotion": False,
        "confluence": False,
    },
}
CONTRACT_FINGERPRINT = stable_fingerprint(CONTRACT)


class SparseActivityConfirmationError(RuntimeError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _persist_raw(
    root: Path,
    *,
    provider: str,
    label: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    raw_dir = root / f"raw_{provider}"
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


def _report_root(settings: AtlasSettings, run_id: str) -> Path:
    return (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_massive_sparse_activity_v1"
        / run_id
    )


def _choose_sparse_contract(rows: tuple[dict[str, Any], ...]) -> dict[str, Any] | None:
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for row in rows:
        if str(row.get("side") or "").lower() != "call":
            continue
        symbol = str(row.get("optionSymbol") or "").strip()
        if not symbol:
            continue
        try:
            strike = float(row.get("strike"))
            underlying = float(row.get("underlyingPrice"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(strike) or not math.isfinite(underlying):
            continue
        if strike <= 0 or underlying <= 0:
            continue
        ratio = strike / underlying
        if ratio <= 1.0:
            continue
        candidates.append((ratio, symbol, row))

    if not candidates:
        return None
    max_ratio = max(item[0] for item in candidates)
    tied = [item for item in candidates if abs(item[0] - max_ratio) <= 1e-12]
    return min(tied, key=lambda item: item[1])[2]


def _activity_records(
    marketdata_rows: tuple[dict[str, Any], ...],
    massive_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    md_by_date: dict[str, dict[str, Any]] = {}
    massive_by_date: dict[str, dict[str, Any]] = {}

    for row in marketdata_rows:
        session_date = _marketdata_date(row.get("updated"))
        if session_date in md_by_date:
            raise SparseActivityConfirmationError(
                f"duplicate MarketData row for {session_date}"
            )
        md_by_date[session_date] = row

    for row in massive_rows:
        session_date = _massive_date(row.get("t"))
        if session_date in massive_by_date:
            raise SparseActivityConfirmationError(
                f"duplicate Massive row for {session_date}"
            )
        massive_by_date[session_date] = row

    records: list[dict[str, Any]] = []
    for session_date in sorted(md_by_date):
        volume = _finite_number(md_by_date[session_date].get("volume"))
        massive_present = session_date in massive_by_date
        if volume is None or volume < 0:
            disposition = "MARKETDATA_VOLUME_INVALID_OR_MISSING"
            concordant = False
        elif volume == 0:
            disposition = (
                "ZERO_VOLUME_WITHOUT_MASSIVE_BAR"
                if not massive_present
                else "ZERO_VOLUME_WITH_MASSIVE_BAR"
            )
            concordant = not massive_present
        else:
            disposition = (
                "POSITIVE_VOLUME_WITH_MASSIVE_BAR"
                if massive_present
                else "POSITIVE_VOLUME_MISSING_MASSIVE_BAR"
            )
            concordant = massive_present

        records.append(
            {
                "date": session_date,
                "marketdata_volume": volume,
                "marketdata_last": _finite_number(md_by_date[session_date].get("last")),
                "massive_bar_present": massive_present,
                "concordant": concordant,
                "disposition": disposition,
            }
        )

    extra = sorted(set(massive_by_date).difference(md_by_date))
    return {
        "records": records,
        "extra_massive_dates": extra,
    }


def _summarize(anchors: list[dict[str, Any]]) -> dict[str, Any]:
    records = [
        record
        for anchor in anchors
        for record in (
            anchor.get("activity_records")
            if isinstance(anchor.get("activity_records"), list)
            else []
        )
        if isinstance(record, dict)
    ]
    total = len(records)
    concordant = sum(bool(item.get("concordant")) for item in records)
    zero = [item for item in records if item.get("marketdata_volume") == 0]
    positive = [
        item
        for item in records
        if isinstance(item.get("marketdata_volume"), (int, float))
        and float(item["marketdata_volume"]) > 0
    ]
    zero_mismatch = sum(
        item.get("disposition") == "ZERO_VOLUME_WITH_MASSIVE_BAR" for item in records
    )
    positive_mismatch = sum(
        item.get("disposition") == "POSITIVE_VOLUME_MISSING_MASSIVE_BAR"
        for item in records
    )
    invalid = sum(
        item.get("disposition") == "MARKETDATA_VOLUME_INVALID_OR_MISSING"
        for item in records
    )
    zero_anchor_count = sum(
        any(
            isinstance(record, dict) and record.get("marketdata_volume") == 0
            for record in (anchor.get("activity_records") or [])
        )
        for anchor in anchors
    )
    positive_anchor_count = sum(
        any(
            isinstance(record, dict)
            and isinstance(record.get("marketdata_volume"), (int, float))
            and float(record["marketdata_volume"]) > 0
            for record in (anchor.get("activity_records") or [])
        )
        for anchor in anchors
    )
    extra_count = sum(
        len(anchor.get("extra_massive_dates") or [])
        for anchor in anchors
    )
    return {
        "total_marketdata_sessions": total,
        "concordant_sessions": concordant,
        "activity_concordance_rate": concordant / total if total else None,
        "zero_volume_sessions": len(zero),
        "zero_volume_anchor_count": zero_anchor_count,
        "positive_volume_sessions": len(positive),
        "positive_volume_anchor_count": positive_anchor_count,
        "zero_volume_with_massive_bar": zero_mismatch,
        "positive_volume_missing_massive_bar": positive_mismatch,
        "invalid_volume_sessions": invalid,
        "extra_massive_dates": extra_count,
    }


def _checks(anchors: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, bool]:
    t = CONTRACT["preregistered_thresholds"]
    complete = (
        len(anchors) == int(t["required_anchor_count"])
        and all(item.get("status") == "DIAGNOSED" for item in anchors)
        and all(
            int(item.get("marketdata_quote_rows") or 0)
            >= int(t["minimum_marketdata_quote_rows_per_anchor"])
            for item in anchors
        )
    )
    return {
        "required_anchor_count_and_rows": complete,
        "minimum_total_zero_volume_sessions": int(
            summary.get("zero_volume_sessions") or 0
        ) >= int(t["minimum_total_zero_volume_sessions"]),
        "minimum_zero_volume_anchor_count": int(
            summary.get("zero_volume_anchor_count") or 0
        ) >= int(t["minimum_zero_volume_anchor_count"]),
        "minimum_total_positive_volume_sessions": int(
            summary.get("positive_volume_sessions") or 0
        ) >= int(t["minimum_total_positive_volume_sessions"]),
        "minimum_positive_volume_anchor_count": int(
            summary.get("positive_volume_anchor_count") or 0
        ) >= int(t["minimum_positive_volume_anchor_count"]),
        "activity_concordance_rate": (
            summary.get("activity_concordance_rate")
            == float(t["required_activity_concordance_rate"])
        ),
        "zero_volume_mismatch_count": int(
            summary.get("zero_volume_with_massive_bar") or 0
        ) <= int(t["maximum_zero_volume_with_massive_bar"]),
        "positive_volume_mismatch_count": int(
            summary.get("positive_volume_missing_massive_bar") or 0
        ) <= int(t["maximum_positive_volume_missing_massive_bar"]),
        "invalid_volume_sessions": int(summary.get("invalid_volume_sessions") or 0) == 0,
        "extra_massive_dates": int(summary.get("extra_massive_dates") or 0)
        <= int(t["maximum_extra_massive_dates"]),
    }


def run_sparse_activity_confirmation_v1(
    settings: AtlasSettings,
    *,
    massive_client: MassiveRESTClient | None = None,
) -> dict[str, Any]:
    generated = datetime.now(UTC)
    run_id = generated.strftime("%Y%m%dT%H%M%SZ")
    root = _report_root(settings, run_id)
    root.mkdir(parents=True, exist_ok=True)
    client = massive_client or MassiveRESTClient(settings)

    anchors: list[dict[str, Any]] = []
    terminal_error: str | None = None

    for index, anchor in enumerate(CONTRACT["anchors"], start=1):
        underlying = str(anchor["root"])
        anchor_date = str(anchor["date"])
        print(
            f"  [{index}/{len(CONTRACT['anchors'])}] "
            f"{underlying} sparse chain @ {anchor_date}",
            flush=True,
        )
        try:
            chain_response = historical_chain(
                underlying,
                date=anchor_date,
                dte=int(CONTRACT["chain_query"]["dte"]),
                strike_limit=int(CONTRACT["chain_query"]["strike_limit"]),
                side=str(CONTRACT["chain_query"]["side"]),
            )
        except MarketDataError as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            anchors.append(
                {
                    "root": underlying,
                    "date": anchor_date,
                    "status": "MARKETDATA_CHAIN_ERROR",
                    "error": terminal_error,
                }
            )
            print(f"      STOP: {terminal_error}", flush=True)
            break

        chain_receipt = _persist_raw(
            root,
            provider="marketdata",
            label=f"{index:02d}-{underlying}-{anchor_date}-chain",
            payload=chain_response.payload,
        )
        chain_rows = array_rows(chain_response.payload)
        selected = _choose_sparse_contract(chain_rows)
        if selected is None:
            terminal_error = "no far-OTM call contract selectable under frozen rule"
            anchors.append(
                {
                    "root": underlying,
                    "date": anchor_date,
                    "status": "NO_SELECTABLE_SPARSE_CONTRACT",
                    "marketdata_chain_rows": len(chain_rows),
                    "chain_raw_receipt": chain_receipt,
                    "error": terminal_error,
                }
            )
            print(f"      STOP: {terminal_error}", flush=True)
            break

        option_symbol = str(selected["optionSymbol"])
        from_date = date.fromisoformat(anchor_date)
        to_date = from_date + timedelta(days=int(CONTRACT["quote_series_days"]))
        print(
            f"      selected {option_symbol} strike={selected.get('strike')} "
            f"underlying={selected.get('underlyingPrice')}; "
            f"quotes {from_date.isoformat()}..{to_date.isoformat()}",
            flush=True,
        )

        try:
            quote_response = historical_quote_series(
                option_symbol,
                from_date=from_date.isoformat(),
                to_date=to_date.isoformat(),
            )
        except MarketDataError as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            anchors.append(
                {
                    "root": underlying,
                    "date": anchor_date,
                    "option_symbol": option_symbol,
                    "status": "MARKETDATA_QUOTE_ERROR",
                    "chain_raw_receipt": chain_receipt,
                    "error": terminal_error,
                }
            )
            print(f"      STOP: {terminal_error}", flush=True)
            break

        quote_receipt = _persist_raw(
            root,
            provider="marketdata",
            label=f"{index:02d}-{underlying}-{anchor_date}-quotes",
            payload=quote_response.payload,
        )
        marketdata_rows = array_rows(quote_response.payload)

        massive_ticker = f"O:{option_symbol}"
        print(
            f"      Massive {massive_ticker} "
            f"{from_date.isoformat()}..{to_date.isoformat()}",
            flush=True,
        )
        try:
            massive_payload = client.get_json(
                (
                    f"/v2/aggs/ticker/{massive_ticker}/range/1/day/"
                    f"{from_date.isoformat()}/{to_date.isoformat()}"
                ),
                dict(CONTRACT["massive_query"]),
            )
        except Exception as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            anchors.append(
                {
                    "root": underlying,
                    "date": anchor_date,
                    "option_symbol": option_symbol,
                    "status": "MASSIVE_ERROR",
                    "marketdata_quote_rows": len(marketdata_rows),
                    "chain_raw_receipt": chain_receipt,
                    "quote_raw_receipt": quote_receipt,
                    "error": terminal_error,
                }
            )
            print(f"      STOP: {terminal_error}", flush=True)
            break

        massive_receipt = _persist_raw(
            root,
            provider="massive",
            label=f"{index:02d}-{underlying}-{anchor_date}-{option_symbol}",
            payload=massive_payload,
        )
        raw_results = massive_payload.get("results") or []
        massive_rows = (
            [item for item in raw_results if isinstance(item, dict)]
            if isinstance(raw_results, list)
            else []
        )

        try:
            activity = _activity_records(marketdata_rows, massive_rows)
        except Exception as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            anchors.append(
                {
                    "root": underlying,
                    "date": anchor_date,
                    "option_symbol": option_symbol,
                    "status": "COMPARISON_ERROR",
                    "marketdata_quote_rows": len(marketdata_rows),
                    "massive_aggregate_rows": len(massive_rows),
                    "chain_raw_receipt": chain_receipt,
                    "quote_raw_receipt": quote_receipt,
                    "massive_raw_receipt": massive_receipt,
                    "error": terminal_error,
                }
            )
            print(f"      STOP: {terminal_error}", flush=True)
            break

        zero_count = sum(
            record["marketdata_volume"] == 0
            for record in activity["records"]
        )
        positive_count = sum(
            isinstance(record["marketdata_volume"], (int, float))
            and float(record["marketdata_volume"]) > 0
            for record in activity["records"]
        )
        mismatches = sum(
            not bool(record["concordant"])
            for record in activity["records"]
        )
        record = {
            "root": underlying,
            "date": anchor_date,
            "option_symbol": option_symbol,
            "selected_strike": selected.get("strike"),
            "selected_underlying_price": selected.get("underlyingPrice"),
            "marketdata_chain_rows": len(chain_rows),
            "marketdata_quote_rows": len(marketdata_rows),
            "massive_aggregate_rows": len(massive_rows),
            "zero_volume_sessions": zero_count,
            "positive_volume_sessions": positive_count,
            "activity_mismatches": mismatches,
            "activity_records": activity["records"],
            "extra_massive_dates": activity["extra_massive_dates"],
            "marketdata_chain_rate_limit": rate_limit_snapshot(chain_response.headers),
            "marketdata_quote_rate_limit": rate_limit_snapshot(quote_response.headers),
            "chain_raw_receipt": chain_receipt,
            "quote_raw_receipt": quote_receipt,
            "massive_raw_receipt": massive_receipt,
            "status": "DIAGNOSED",
            "error": None,
        }
        anchors.append(record)
        print(
            f"      md_rows={len(marketdata_rows)} "
            f"zero={zero_count} positive={positive_count} "
            f"massive_rows={len(massive_rows)} mismatches={mismatches} "
            f"extra_massive={len(activity['extra_massive_dates'])}",
            flush=True,
        )

    summary = _summarize(anchors)
    checks = _checks(anchors, summary)
    passed = terminal_error is None and all(checks.values())

    observed_credit_consumed = sum(
        int(rate.get("consumed") or 0)
        for item in anchors
        for rate in (
            item.get("marketdata_chain_rate_limit"),
            item.get("marketdata_quote_rate_limit"),
        )
        if isinstance(rate, dict)
    )
    last_remaining = next(
        (
            int(rate["remaining"])
            for item in reversed(anchors)
            for rate in (
                item.get("marketdata_quote_rate_limit"),
                item.get("marketdata_chain_rate_limit"),
            )
            if isinstance(rate, dict) and rate.get("remaining") is not None
        ),
        None,
    )

    report: dict[str, Any] = {
        "status": (
            "SPARSE_ACTIVITY_CONCORDANCE_CONFIRMED"
            if passed
            else "SPARSE_ACTIVITY_CONFIRMATION_FAILED"
        ),
        "contract_id": CONTRACT["contract_id"],
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "run_id": run_id,
        "generated_at_utc": generated.isoformat(),
        "evidence_basis": CONTRACT["evidence_basis"],
        "selection_rule": CONTRACT["selection_rule"],
        "preregistered_thresholds": CONTRACT["preregistered_thresholds"],
        "anchors": anchors,
        "summary": summary,
        "checks": checks,
        "observed_marketdata_api_credits_consumed": observed_credit_consumed,
        "last_observed_marketdata_api_credits_remaining": last_remaining,
        "terminal_error": terminal_error,
        "passed": passed,
        "authority": (
            CONTRACT["authority_if_passed"]
            if passed
            else {
                **CONTRACT["authority_if_passed"],
                "marketdata_massive_sparse_activity_concordance_confirmed": False,
            }
        ),
        "limitations": {
            "targeted_far_otm_contracts_not_simulator_selector": True,
            "zero_volume_last_not_validated": True,
            "positive_volume_price_semantics_not_granted_by_this_gate": True,
            "raw_trade_presence_not_observed": True,
            "v1_and_v2_failures_remain_immutable": True,
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
