from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.provider_source_qualification import stable_fingerprint
from packages.providers.marketdata_app import (
    MarketDataError,
    array_rows,
    historical_chain,
    historical_quote_series,
    rate_limit_snapshot,
)


CONTRACT = {
    "contract_id": "atlas-marketdata-five-year-historical-options-v1",
    "provider": "marketdata.app",
    "plan_target": "Starter",
    "price_target_usd_monthly": 30,
    "historical_window": "rolling 5 years",
    "anchors": [
        {"root": "SPY", "date": "2021-10-01"},
        {"root": "AAPL", "date": "2022-10-03"},
        {"root": "MSFT", "date": "2023-10-02"},
        {"root": "NVDA", "date": "2024-10-01"},
        {"root": "QQQ", "date": "2025-10-01"},
        {"root": "SPY", "date": "2026-09-01"},
    ],
    "starter_trial_anchors": [
        {"root": "AAPL", "date": "2021-10-01", "scope": "deep_aapl"},
        {"root": "SPY", "date": "2026-03-02", "scope": "one_year_multi_ticker"},
        {"root": "MSFT", "date": "2026-05-01", "scope": "one_year_multi_ticker"},
        {"root": "NVDA", "date": "2026-07-01", "scope": "one_year_multi_ticker"},
        {"root": "QQQ", "date": "2026-09-01", "scope": "one_year_multi_ticker"},
    ],
    "chain_query": {"dte": 30, "strike_limit": 8},
    "quote_series_days": 10,
    "required_chain_fields": [
        "optionSymbol",
        "underlying",
        "expiration",
        "side",
        "strike",
        "firstTraded",
        "dte",
        "bid",
        "ask",
        "mid",
        "last",
        "volume",
        "openInterest",
        "underlyingPrice",
        "updated",
    ],
    "required_quote_fields": [
        "optionSymbol",
        "bid",
        "ask",
        "mid",
        "last",
        "volume",
        "openInterest",
        "underlyingPrice",
        "updated",
    ],
    "historical_greeks_expected_null": [
        "iv",
        "delta",
        "gamma",
        "theta",
        "vega",
    ],
    "authority": {
        "provider_reads": True,
        "provider_writes": False,
        "historical_price_authority": False,
        "strategy_evidence": False,
        "paper": False,
        "live": False,
        "orders": False,
    },
}
CONTRACT_FINGERPRINT = stable_fingerprint(CONTRACT)


def _raw_root(settings: AtlasSettings, run_id: str) -> Path:
    return (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_app"
        / "historical_options_v1"
        / run_id
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _persist_raw(
    root: Path,
    *,
    label: str,
    payload: dict[str, Any],
) -> dict[str, object]:
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        + "\n"
    ).encode("utf-8")
    path = raw_dir / f"{label}.json"
    path.write_bytes(encoded)
    digest = _sha256_bytes(encoded)
    receipt = {
        "path": str(path.resolve()),
        "sha256": digest,
        "bytes": len(encoded),
    }
    atomic_write_text(
        raw_dir / f"{label}.receipt.json",
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
    )
    return receipt


def _choose_contract(rows: tuple[dict[str, Any], ...]) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rows
        if str(row.get("side") or "").lower() == "call"
        and row.get("optionSymbol")
        and row.get("strike") is not None
    ]
    if not candidates:
        return None

    def distance(row: dict[str, Any]) -> tuple[float, str]:
        try:
            underlying = float(row.get("underlyingPrice"))
            strike = float(row.get("strike"))
            value = abs(strike - underlying)
        except (TypeError, ValueError):
            value = float("inf")
        return value, str(row.get("optionSymbol"))

    return min(candidates, key=distance)


def _required_fields_present(
    rows: tuple[dict[str, Any], ...],
    fields: list[str],
) -> dict[str, bool]:
    return {
        field: any(field in row for row in rows)
        for field in fields
    }


def _nonnull_count(rows: tuple[dict[str, Any], ...], field: str) -> int:
    return sum(row.get(field) is not None for row in rows)


def _greeks_null(rows: tuple[dict[str, Any], ...]) -> dict[str, bool]:
    return {
        field: all(row.get(field) is None for row in rows)
        for field in CONTRACT["historical_greeks_expected_null"]
    }


def run_marketdata_five_year_options_qualification_v1(
    settings: AtlasSettings,
    *,
    starter_trial: bool = False,
) -> dict[str, object]:
    generated = datetime.now(UTC)
    run_id = generated.strftime("%Y%m%dT%H%M%SZ")
    root = _raw_root(settings, run_id)
    root.mkdir(parents=True, exist_ok=True)

    active_anchors = (
        list(CONTRACT["starter_trial_anchors"])
        if starter_trial
        else list(CONTRACT["anchors"])
    )

    anchors: list[dict[str, object]] = []
    terminal_error: str | None = None

    for index, anchor in enumerate(active_anchors, start=1):
        symbol = str(anchor["root"])
        anchor_date = str(anchor["date"])
        print(
            f"  [{index}/{len(active_anchors)}] "
            f"{symbol} historical chain @ {anchor_date}",
            flush=True,
        )
        try:
            chain_response = historical_chain(
                symbol,
                date=anchor_date,
                dte=int(CONTRACT["chain_query"]["dte"]),
                strike_limit=int(CONTRACT["chain_query"]["strike_limit"]),
            )
        except MarketDataError as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            anchors.append(
                {
                    "root": symbol,
                    "date": anchor_date,
                    "chain_status": "ERROR",
                    "error": terminal_error,
                }
            )
            print(f"      STOP: {terminal_error}", flush=True)
            break

        chain_receipt = _persist_raw(
            root,
            label=f"{index:02d}-{symbol}-{anchor_date}-chain",
            payload=chain_response.payload,
        )
        chain_rows = array_rows(chain_response.payload)
        selected = _choose_contract(chain_rows)
        chain_fields = _required_fields_present(
            chain_rows,
            list(CONTRACT["required_chain_fields"]),
        )
        chain_oi = _nonnull_count(chain_rows, "openInterest")
        chain_greeks_null = _greeks_null(chain_rows)

        record: dict[str, object] = {
            "root": symbol,
            "date": anchor_date,
            "chain_http_status": chain_response.http_status,
            "chain_rows": len(chain_rows),
            "chain_required_fields": chain_fields,
            "chain_open_interest_nonnull": chain_oi,
            "chain_historical_greeks_null": chain_greeks_null,
            "chain_rate_limit": rate_limit_snapshot(chain_response.headers),
            "chain_raw_receipt": chain_receipt,
            "selected_option_symbol": (
                str(selected.get("optionSymbol")) if selected else None
            ),
            "selected_strike": selected.get("strike") if selected else None,
            "selected_underlying_price": (
                selected.get("underlyingPrice") if selected else None
            ),
        }

        if not chain_rows or selected is None:
            record["quote_status"] = "NOT_RUN"
            record["error"] = "historical chain returned no selectable call contract"
            anchors.append(record)
            print("      no selectable historical contract", flush=True)
            continue

        from_date = date.fromisoformat(anchor_date)
        to_date = from_date + timedelta(days=int(CONTRACT["quote_series_days"]))
        option_symbol = str(selected["optionSymbol"])
        print(
            f"      selected {option_symbol}; quote series "
            f"{from_date.isoformat()}..{to_date.isoformat()}",
            flush=True,
        )
        try:
            quote_response = historical_quote_series(
                option_symbol,
                from_date=from_date.isoformat(),
                to_date=to_date.isoformat(),
            )
        except MarketDataError as exc:
            record["quote_status"] = "ERROR"
            record["error"] = f"{type(exc).__name__}: {exc}"
            anchors.append(record)
            print(f"      quote error: {record['error']}", flush=True)
            continue

        quote_receipt = _persist_raw(
            root,
            label=f"{index:02d}-{symbol}-{anchor_date}-quotes",
            payload=quote_response.payload,
        )
        quote_rows = array_rows(quote_response.payload)
        record.update(
            {
                "quote_status": "OK" if quote_rows else "NO_DATA",
                "quote_http_status": quote_response.http_status,
                "quote_rows": len(quote_rows),
                "quote_required_fields": _required_fields_present(
                    quote_rows,
                    list(CONTRACT["required_quote_fields"]),
                ),
                "quote_open_interest_nonnull": _nonnull_count(
                    quote_rows,
                    "openInterest",
                ),
                "quote_historical_greeks_null": _greeks_null(quote_rows),
                "quote_rate_limit": rate_limit_snapshot(quote_response.headers),
                "quote_raw_receipt": quote_receipt,
            }
        )
        anchors.append(record)
        print(
            f"      chain_rows={len(chain_rows):,} "
            f"chain_oi={chain_oi:,} "
            f"quote_rows={len(quote_rows):,} "
            f"quote_oi={record['quote_open_interest_nonnull']}",
            flush=True,
        )

    all_anchor_chains = (
        len(anchors) == len(active_anchors)
        and all(int(item.get("chain_rows") or 0) > 0 for item in anchors)
    )
    all_quote_series = (
        len(anchors) == len(active_anchors)
        and all(int(item.get("quote_rows") or 0) > 0 for item in anchors)
    )
    all_oi = (
        len(anchors) == len(active_anchors)
        and all(
            int(item.get("chain_open_interest_nonnull") or 0) > 0
            and int(item.get("quote_open_interest_nonnull") or 0) > 0
            for item in anchors
        )
    )
    oldest_anchor_ok = bool(
        anchors
        and anchors[0].get("date") == "2021-10-01"
        and int(anchors[0].get("chain_rows") or 0) > 0
        and int(anchors[0].get("quote_rows") or 0) > 0
    )

    if starter_trial:
        status = (
            "QUALIFIED_FOR_STARTER_TRIAL_CAPABILITY"
            if all_anchor_chains and all_quote_series and all_oi and oldest_anchor_ok
            else "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
            if anchors
            else "FAIL"
        )
    else:
        status = (
            "QUALIFIED_FOR_FIVE_YEAR_EOD_ECONOMICS_CHALLENGER"
            if all_anchor_chains and all_quote_series and all_oi and oldest_anchor_ok
            else "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
            if anchors
            else "FAIL"
        )

    observed_credit_consumed = sum(
        int(rate.get("consumed") or 0)
        for item in anchors
        for rate in (
            item.get("chain_rate_limit"),
            item.get("quote_rate_limit"),
        )
        if isinstance(rate, dict)
    )
    last_remaining = next(
        (
            int(rate["remaining"])
            for item in reversed(anchors)
            for rate in (
                item.get("quote_rate_limit"),
                item.get("chain_rate_limit"),
            )
            if isinstance(rate, dict) and rate.get("remaining") is not None
        ),
        None,
    )

    report: dict[str, object] = {
        "status": status,
        "contract_id": CONTRACT["contract_id"],
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "run_id": run_id,
        "generated_at_utc": generated.isoformat(),
        "provider": CONTRACT["provider"],
        "plan_target": "Starter Trial" if starter_trial else CONTRACT["plan_target"],
        "starter_trial": starter_trial,
        "broad_five_year_entitlement_proven": False if starter_trial else oldest_anchor_ok,
        "oldest_anchor_proven": oldest_anchor_ok,
        "all_anchor_chains_nonempty": all_anchor_chains,
        "all_quote_series_nonempty": all_quote_series,
        "open_interest_present_across_anchors": all_oi,
        "observed_api_credits_consumed": observed_credit_consumed,
        "last_observed_api_credits_remaining": last_remaining,
        "anchors": anchors,
        "terminal_error": terminal_error,
        "authority": CONTRACT["authority"],
        "limitations": {
            "historical_greeks_not_stored": True,
            "historical_data_as_traded_not_corporate_action_adjusted": True,
            "cross_provider_validation_still_required": True,
            "simulator_authority_not_created": True,
            "starter_trial_general_ticker_history_limited_to_one_year": starter_trial,
            "starter_trial_deep_history_test_uses_aapl_exception": starter_trial,
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
