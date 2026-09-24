from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_massive_sparse_activity_v1 import (
    _activity_records,
    _persist_raw,
)
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
    "contract_id": "atlas-marketdata-massive-sparse-activity-confirmation-v2",
    "purpose": (
        "fresh disjoint confirmation of MarketData zero/positive-volume EOD activity "
        "against Massive aggregate presence using a less-extreme deterministic OTM selector"
    ),
    "evidence_basis": {
        "v1_sparse_confirmation": {
            "run_id": "20260924T033435Z",
            "evidence_fingerprint": (
                "d7ce4d184d175b6f60233f2a4470e8e4e67a27691ac8a45a082b805b9e3cce6d"
            ),
            "status": "SPARSE_ACTIVITY_CONFIRMATION_FAILED",
            "total_sessions": 105,
            "zero_volume_sessions": 87,
            "zero_volume_anchor_count": 12,
            "positive_volume_sessions": 18,
            "positive_volume_anchor_count": 6,
            "activity_concordance_rate": 1.0,
            "only_failed_gate": "minimum_total_positive_volume_sessions",
        }
    },
    "anchors": [
        {"root": "GLD", "date": "2025-10-20"},
        {"root": "SLV", "date": "2025-11-17"},
        {"root": "GDX", "date": "2025-12-15"},
        {"root": "USO", "date": "2026-01-26"},
        {"root": "XLE", "date": "2026-02-23"},
        {"root": "XLK", "date": "2026-03-23"},
        {"root": "XLY", "date": "2026-04-20"},
        {"root": "XLP", "date": "2026-05-11"},
        {"root": "XLU", "date": "2026-06-22"},
        {"root": "XLI", "date": "2026-07-20"},
        {"root": "XLV", "date": "2026-08-10"},
        {"root": "XLRE", "date": "2026-09-14"},
    ],
    "excluded_prior_roots": [
        "SPY","MSFT","NVDA","QQQ","IWM","AMZN","META","DIA","AAPL","TSLA","AMD",
        "JPM","XLF","TLT","RSP","MDY","IJR","IEF","LQD","XBI","KRE","XRT","XHB",
        "EEM","FXI","EWJ"
    ],
    "excluded_prior_dates": [
        "2026-03-02","2026-05-01","2026-07-01","2026-09-01","2026-02-02",
        "2026-04-01","2026-06-01","2026-08-03","2026-01-05","2026-02-17",
        "2026-03-16","2026-05-18","2026-07-06","2026-08-17","2025-10-06",
        "2025-11-03","2025-12-01","2026-01-12","2026-02-09","2026-03-09",
        "2026-04-06","2026-05-04","2026-06-15","2026-07-13","2026-08-24",
        "2026-09-08"
    ],
    "chain_query": {"dte": 30, "strike_limit": 20, "side": "call"},
    "selector": {
        "rank_from_farthest_otm": 3,
        "tie_break": "optionSymbol ascending",
        "uses_quote_volume": False,
        "uses_massive_data": False,
    },
    "quote_series_days": 10,
    "massive_query": {"adjusted": False, "sort": "asc", "limit": 50},
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


def _report_root(settings: AtlasSettings, run_id: str) -> Path:
    return (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_massive_sparse_activity_v2"
        / run_id
    )


def _choose_third_farthest_otm(
    rows: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
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
        if strike <= underlying or underlying <= 0:
            continue
        candidates.append((strike / underlying, symbol, row))

    if len(candidates) < int(CONTRACT["selector"]["rank_from_farthest_otm"]):
        return None

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[int(CONTRACT["selector"]["rank_from_farthest_otm"]) - 1][2]


def _summarize(anchors: list[dict[str, Any]]) -> dict[str, Any]:
    records = [
        record
        for anchor in anchors
        for record in (anchor.get("activity_records") or [])
        if isinstance(record, dict)
    ]
    total = len(records)
    zero = [r for r in records if r.get("marketdata_volume") == 0]
    positive = [
        r for r in records
        if isinstance(r.get("marketdata_volume"), (int, float))
        and float(r["marketdata_volume"]) > 0
    ]
    concordant = sum(bool(r.get("concordant")) for r in records)
    return {
        "total_marketdata_sessions": total,
        "zero_volume_sessions": len(zero),
        "zero_volume_anchor_count": sum(
            any(r.get("marketdata_volume") == 0 for r in (a.get("activity_records") or []))
            for a in anchors
        ),
        "positive_volume_sessions": len(positive),
        "positive_volume_anchor_count": sum(
            any(
                isinstance(r.get("marketdata_volume"), (int, float))
                and float(r["marketdata_volume"]) > 0
                for r in (a.get("activity_records") or [])
            )
            for a in anchors
        ),
        "activity_concordance_rate": concordant / total if total else None,
        "zero_volume_with_massive_bar": sum(
            r.get("disposition") == "ZERO_VOLUME_WITH_MASSIVE_BAR" for r in records
        ),
        "positive_volume_missing_massive_bar": sum(
            r.get("disposition") == "POSITIVE_VOLUME_MISSING_MASSIVE_BAR"
            for r in records
        ),
        "invalid_volume_sessions": sum(
            r.get("disposition") == "MARKETDATA_VOLUME_INVALID_OR_MISSING"
            for r in records
        ),
        "extra_massive_dates": sum(len(a.get("extra_massive_dates") or []) for a in anchors),
    }


def _checks(anchors: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, bool]:
    t = CONTRACT["preregistered_thresholds"]
    return {
        "required_anchor_count_and_rows": (
            len(anchors) == int(t["required_anchor_count"])
            and all(a.get("status") == "DIAGNOSED" for a in anchors)
            and all(
                int(a.get("marketdata_quote_rows") or 0)
                >= int(t["minimum_marketdata_quote_rows_per_anchor"])
                for a in anchors
            )
        ),
        "minimum_total_zero_volume_sessions": int(summary["zero_volume_sessions"])
        >= int(t["minimum_total_zero_volume_sessions"]),
        "minimum_zero_volume_anchor_count": int(summary["zero_volume_anchor_count"])
        >= int(t["minimum_zero_volume_anchor_count"]),
        "minimum_total_positive_volume_sessions": int(summary["positive_volume_sessions"])
        >= int(t["minimum_total_positive_volume_sessions"]),
        "minimum_positive_volume_anchor_count": int(summary["positive_volume_anchor_count"])
        >= int(t["minimum_positive_volume_anchor_count"]),
        "activity_concordance_rate": summary["activity_concordance_rate"]
        == float(t["required_activity_concordance_rate"]),
        "zero_volume_mismatch_count": int(summary["zero_volume_with_massive_bar"])
        <= int(t["maximum_zero_volume_with_massive_bar"]),
        "positive_volume_mismatch_count": int(summary["positive_volume_missing_massive_bar"])
        <= int(t["maximum_positive_volume_missing_massive_bar"]),
        "invalid_volume_sessions": int(summary["invalid_volume_sessions"]) == 0,
        "extra_massive_dates": int(summary["extra_massive_dates"])
        <= int(t["maximum_extra_massive_dates"]),
    }


def run_sparse_activity_confirmation_v2(
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
        print(f"  [{index}/12] {underlying} mixed-activity chain @ {anchor_date}", flush=True)

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
            anchors.append({"root": underlying, "date": anchor_date, "status": "MARKETDATA_CHAIN_ERROR", "error": terminal_error})
            break

        chain_receipt = _persist_raw(
            root,
            provider="marketdata",
            label=f"{index:02d}-{underlying}-{anchor_date}-chain",
            payload=chain_response.payload,
        )
        chain_rows = array_rows(chain_response.payload)
        selected = _choose_third_farthest_otm(chain_rows)
        if selected is None:
            terminal_error = "fewer than three selectable OTM calls under frozen rule"
            anchors.append({
                "root": underlying,
                "date": anchor_date,
                "status": "NO_SELECTABLE_CONTRACT",
                "marketdata_chain_rows": len(chain_rows),
                "chain_raw_receipt": chain_receipt,
                "error": terminal_error,
            })
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
            anchors.append({
                "root": underlying,
                "date": anchor_date,
                "option_symbol": option_symbol,
                "status": "MARKETDATA_QUOTE_ERROR",
                "chain_raw_receipt": chain_receipt,
                "error": terminal_error,
            })
            break

        quote_receipt = _persist_raw(
            root,
            provider="marketdata",
            label=f"{index:02d}-{underlying}-{anchor_date}-quotes",
            payload=quote_response.payload,
        )
        marketdata_rows = array_rows(quote_response.payload)

        massive_ticker = f"O:{option_symbol}"
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
            anchors.append({
                "root": underlying,
                "date": anchor_date,
                "option_symbol": option_symbol,
                "status": "MASSIVE_ERROR",
                "marketdata_quote_rows": len(marketdata_rows),
                "chain_raw_receipt": chain_receipt,
                "quote_raw_receipt": quote_receipt,
                "error": terminal_error,
            })
            break

        massive_receipt = _persist_raw(
            root,
            provider="massive",
            label=f"{index:02d}-{underlying}-{anchor_date}-{option_symbol}",
            payload=massive_payload,
        )
        raw_results = massive_payload.get("results") or []
        massive_rows = [r for r in raw_results if isinstance(r, dict)] if isinstance(raw_results, list) else []

        try:
            activity = _activity_records(marketdata_rows, massive_rows)
        except Exception as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            anchors.append({
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
            })
            print(f"      STOP: {terminal_error}", flush=True)
            break

        zero_count = sum(r["marketdata_volume"] == 0 for r in activity["records"])
        positive_count = sum(
            isinstance(r["marketdata_volume"], (int, float))
            and float(r["marketdata_volume"]) > 0
            for r in activity["records"]
        )
        mismatch_count = sum(not bool(r["concordant"]) for r in activity["records"])
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
            "activity_mismatches": mismatch_count,
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
            f"      md_rows={len(marketdata_rows)} zero={zero_count} positive={positive_count} "
            f"massive_rows={len(massive_rows)} mismatches={mismatch_count} "
            f"extra_massive={len(activity['extra_massive_dates'])}",
            flush=True,
        )

    summary = _summarize(anchors)
    checks = _checks(anchors, summary)
    passed = terminal_error is None and all(checks.values())

    observed_credit_consumed = sum(
        int(rate.get("consumed") or 0)
        for item in anchors
        for rate in (item.get("marketdata_chain_rate_limit"), item.get("marketdata_quote_rate_limit"))
        if isinstance(rate, dict)
    )
    last_remaining = next(
        (
            int(rate["remaining"])
            for item in reversed(anchors)
            for rate in (item.get("marketdata_quote_rate_limit"), item.get("marketdata_chain_rate_limit"))
            if isinstance(rate, dict) and rate.get("remaining") is not None
        ),
        None,
    )

    report: dict[str, Any] = {
        "status": "SPARSE_ACTIVITY_CONCORDANCE_CONFIRMED" if passed else "SPARSE_ACTIVITY_CONFIRMATION_FAILED",
        "contract_id": CONTRACT["contract_id"],
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "run_id": run_id,
        "generated_at_utc": generated.isoformat(),
        "evidence_basis": CONTRACT["evidence_basis"],
        "selector": CONTRACT["selector"],
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
            "targeted_selector_not_simulator_selector": True,
            "zero_volume_last_not_validated": True,
            "positive_volume_price_semantics_not_granted_by_this_gate": True,
            "v1_sparse_failure_remains_immutable": True,
            "v1_and_v2_cross_provider_validation_failures_remain_immutable": True,
        },
    }
    report["evidence_fingerprint"] = stable_fingerprint(report)
    report_path = root / "report.json"
    atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
    report["report_path"] = str(report_path.resolve())
    return report
