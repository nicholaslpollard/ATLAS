from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_five_year_options_qualification import (
    _choose_qualification_contract,
)
from packages.data.marketdata_massive_overlap_v1 import (
    MarketDataMassiveOverlapError,
    compare_exact_contract_days,
    summarize_comparisons,
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
    "contract_id": "atlas-marketdata-massive-disjoint-validation-v1",
    "purpose": (
        "preregistered disjoint validation of MarketData historical EOD last/volume "
        "semantics against Massive exact-contract daily aggregates"
    ),
    "calibration_evidence": {
        "contract_id": "atlas-marketdata-massive-option-overlap-diagnostic-v1",
        "run_id": "20260923T205206Z",
        "evidence_fingerprint": (
            "b10d6d8eb2f3bfcb9fa9dad5623d1eb56297bec5222922b2b8f2302fe5324f3a"
        ),
        "overlap_sessions": 31,
        "exact_last_close_match_rate": 0.77419355,
        "median_last_close_abs_diff": 0.0,
        "max_last_close_abs_diff": 0.82,
        "last_inside_massive_range_rate": 1.0,
        "median_volume_relative_diff": 0.00065284,
        "max_volume_relative_diff": 0.14213836,
    },
    "validation_anchors": [
        {"root": "IWM", "date": "2026-02-02"},
        {"root": "AMZN", "date": "2026-04-01"},
        {"root": "META", "date": "2026-06-01"},
        {"root": "DIA", "date": "2026-08-03"},
    ],
    "chain_query": {"dte": 30, "strike_limit": 8},
    "quote_series_days": 10,
    "massive_query": {
        "adjusted": False,
        "sort": "asc",
        "limit": 50,
    },
    "preregistered_thresholds": {
        "required_anchor_count": 4,
        "minimum_marketdata_quote_rows_per_anchor": 5,
        "minimum_overlap_sessions_per_anchor": 5,
        "minimum_overlap_coverage_rate_per_anchor": 1.0,
        "minimum_last_inside_massive_range_rate_per_anchor": 1.0,
        "maximum_median_price_relative_diff_per_anchor": 0.05,
        "maximum_aggregate_median_price_relative_diff": 0.02,
        "maximum_median_volume_relative_diff_per_anchor": 0.15,
        "maximum_aggregate_median_volume_relative_diff": 0.10,
        "exact_last_close_match_rate": "DESCRIPTIVE_ONLY",
    },
    "authority_if_passed": {
        "marketdata_eod_last_volume_semantics_validated": True,
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


class MarketDataMassiveValidationError(RuntimeError):
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
        / "marketdata_massive_validation_v1"
        / run_id
    )


def _threshold_pass(
    value: float | int | None,
    *,
    minimum: float | int | None = None,
    maximum: float | int | None = None,
) -> bool:
    if value is None:
        return False
    numeric = float(value)
    if minimum is not None and numeric < float(minimum):
        return False
    if maximum is not None and numeric > float(maximum):
        return False
    return True


def _anchor_checks(
    *,
    marketdata_rows: int,
    summary: dict[str, Any],
) -> dict[str, bool]:
    thresholds = CONTRACT["preregistered_thresholds"]
    overlap_sessions = int(summary.get("overlap_sessions") or 0)
    coverage = (
        overlap_sessions / marketdata_rows if marketdata_rows > 0 else None
    )
    return {
        "marketdata_quote_rows": _threshold_pass(
            marketdata_rows,
            minimum=thresholds["minimum_marketdata_quote_rows_per_anchor"],
        ),
        "overlap_sessions": _threshold_pass(
            overlap_sessions,
            minimum=thresholds["minimum_overlap_sessions_per_anchor"],
        ),
        "overlap_coverage_rate": _threshold_pass(
            coverage,
            minimum=thresholds["minimum_overlap_coverage_rate_per_anchor"],
        ),
        "last_inside_massive_range_rate": _threshold_pass(
            summary.get("marketdata_last_inside_massive_range_rate"),
            minimum=thresholds[
                "minimum_last_inside_massive_range_rate_per_anchor"
            ],
        ),
        "median_price_relative_diff": _threshold_pass(
            summary.get("median_price_rel_diff"),
            maximum=thresholds["maximum_median_price_relative_diff_per_anchor"],
        ),
        "median_volume_relative_diff": _threshold_pass(
            summary.get("median_volume_rel_diff"),
            maximum=thresholds["maximum_median_volume_relative_diff_per_anchor"],
        ),
    }


def _aggregate_checks(
    *,
    anchor_count: int,
    anchor_pass_count: int,
    aggregate: dict[str, Any],
) -> dict[str, bool]:
    thresholds = CONTRACT["preregistered_thresholds"]
    required = int(thresholds["required_anchor_count"])
    return {
        "required_anchor_count": anchor_count == required,
        "all_anchors_pass": anchor_pass_count == required,
        "aggregate_median_price_relative_diff": _threshold_pass(
            aggregate.get("median_price_rel_diff"),
            maximum=thresholds["maximum_aggregate_median_price_relative_diff"],
        ),
        "aggregate_median_volume_relative_diff": _threshold_pass(
            aggregate.get("median_volume_rel_diff"),
            maximum=thresholds["maximum_aggregate_median_volume_relative_diff"],
        ),
    }


def run_marketdata_massive_disjoint_validation_v1(
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

    for index, anchor in enumerate(CONTRACT["validation_anchors"], start=1):
        underlying = str(anchor["root"])
        anchor_date = str(anchor["date"])
        print(
            f"  [{index}/{len(CONTRACT['validation_anchors'])}] "
            f"{underlying} historical chain @ {anchor_date}",
            flush=True,
        )

        try:
            chain_response = historical_chain(
                underlying,
                date=anchor_date,
                dte=int(CONTRACT["chain_query"]["dte"]),
                strike_limit=int(CONTRACT["chain_query"]["strike_limit"]),
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
        selected = _choose_qualification_contract(chain_rows)
        if not chain_rows or selected is None:
            anchors.append(
                {
                    "root": underlying,
                    "date": anchor_date,
                    "status": "NO_SELECTABLE_CONTRACT",
                    "chain_rows": len(chain_rows),
                    "chain_raw_receipt": chain_receipt,
                    "error": "historical chain returned no selectable call contract",
                }
            )
            continue

        option_symbol = str(selected["optionSymbol"])
        from_date = date.fromisoformat(anchor_date)
        to_date = from_date + timedelta(days=int(CONTRACT["quote_series_days"]))
        print(
            f"      selected {option_symbol}; MarketData quotes "
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
            terminal_error = f"{type(exc).__name__}: {exc}"
            anchors.append(
                {
                    "root": underlying,
                    "date": anchor_date,
                    "option_symbol": option_symbol,
                    "status": "MARKETDATA_QUOTE_ERROR",
                    "error": terminal_error,
                    "chain_raw_receipt": chain_receipt,
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
        if not marketdata_rows:
            anchors.append(
                {
                    "root": underlying,
                    "date": anchor_date,
                    "option_symbol": option_symbol,
                    "status": "MARKETDATA_NO_QUOTE_ROWS",
                    "chain_raw_receipt": chain_receipt,
                    "quote_raw_receipt": quote_receipt,
                    "error": "historical quote series returned no rows",
                }
            )
            continue

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
                    "massive_ticker": massive_ticker,
                    "status": "MASSIVE_ERROR",
                    "error": terminal_error,
                    "chain_raw_receipt": chain_receipt,
                    "quote_raw_receipt": quote_receipt,
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
        massive_results = massive_payload.get("results") or []
        massive_rows = (
            [row for row in massive_results if isinstance(row, dict)]
            if isinstance(massive_results, list)
            else []
        )
        try:
            comparisons = compare_exact_contract_days(marketdata_rows, massive_rows)
        except MarketDataMassiveOverlapError as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            anchors.append(
                {
                    "root": underlying,
                    "date": anchor_date,
                    "option_symbol": option_symbol,
                    "massive_ticker": massive_ticker,
                    "status": "COMPARISON_ERROR",
                    "error": terminal_error,
                    "chain_raw_receipt": chain_receipt,
                    "quote_raw_receipt": quote_receipt,
                    "massive_raw_receipt": massive_receipt,
                }
            )
            print(f"      STOP: {terminal_error}", flush=True)
            break
        summary = summarize_comparisons(comparisons)
        overlap_sessions = int(summary.get("overlap_sessions") or 0)
        coverage = (
            overlap_sessions / len(marketdata_rows)
            if marketdata_rows
            else None
        )
        checks = _anchor_checks(
            marketdata_rows=len(marketdata_rows),
            summary=summary,
        )
        passed = all(checks.values())
        record = {
            "root": underlying,
            "date": anchor_date,
            "option_symbol": option_symbol,
            "selected_strike": selected.get("strike"),
            "selected_underlying_price": selected.get("underlyingPrice"),
            "marketdata_chain_rows": len(chain_rows),
            "marketdata_quote_rows": len(marketdata_rows),
            "massive_aggregate_rows": len(massive_rows),
            "overlap_sessions": overlap_sessions,
            "overlap_coverage_rate": coverage,
            "summary": summary,
            "checks": checks,
            "passed": passed,
            "marketdata_chain_rate_limit": rate_limit_snapshot(
                chain_response.headers
            ),
            "marketdata_quote_rate_limit": rate_limit_snapshot(
                quote_response.headers
            ),
            "chain_raw_receipt": chain_receipt,
            "quote_raw_receipt": quote_receipt,
            "massive_raw_receipt": massive_receipt,
            "comparisons": comparisons,
            "error": None,
        }
        anchors.append(record)
        print(
            f"      md_rows={len(marketdata_rows)} "
            f"massive_rows={len(massive_rows)} "
            f"overlap={overlap_sessions} "
            f"coverage={coverage} "
            f"inside_range={summary.get('marketdata_last_inside_massive_range_rate')} "
            f"median_price_rel={summary.get('median_price_rel_diff')} "
            f"median_volume_rel={summary.get('median_volume_rel_diff')} "
            f"passed={passed}",
            flush=True,
        )

    all_comparisons = [
        comparison
        for anchor in anchors
        for comparison in (
            anchor.get("comparisons")
            if isinstance(anchor.get("comparisons"), list)
            else []
        )
        if isinstance(comparison, dict)
    ]
    aggregate = summarize_comparisons(all_comparisons)
    pass_count = sum(bool(item.get("passed")) for item in anchors)
    aggregate_checks = _aggregate_checks(
        anchor_count=len(anchors),
        anchor_pass_count=pass_count,
        aggregate=aggregate,
    )
    validation_passed = (
        terminal_error is None
        and len(anchors)
        == int(CONTRACT["preregistered_thresholds"]["required_anchor_count"])
        and all(bool(item.get("passed")) for item in anchors)
        and all(aggregate_checks.values())
    )

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
            "VALIDATED_FOR_EOD_LAST_VOLUME_SEMANTICS"
            if validation_passed
            else "VALIDATION_FAILED"
        ),
        "contract_id": CONTRACT["contract_id"],
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "run_id": run_id,
        "generated_at_utc": generated.isoformat(),
        "calibration_evidence": CONTRACT["calibration_evidence"],
        "preregistered_thresholds": CONTRACT["preregistered_thresholds"],
        "anchors": anchors,
        "anchor_pass_count": pass_count,
        "aggregate_summary": aggregate,
        "aggregate_checks": aggregate_checks,
        "observed_marketdata_api_credits_consumed": observed_credit_consumed,
        "last_observed_marketdata_api_credits_remaining": last_remaining,
        "terminal_error": terminal_error,
        "validation_passed": validation_passed,
        "authority": (
            CONTRACT["authority_if_passed"]
            if validation_passed
            else {
                **CONTRACT["authority_if_passed"],
                "marketdata_eod_last_volume_semantics_validated": False,
            }
        ),
        "limitations": {
            "historical_bid_ask_not_independently_validated": True,
            "intraday_option_path_not_validated": True,
            "execution_price_authority_not_created": True,
            "qualification_selector_not_simulator_selector": True,
            "calibration_contracts_not_reused": True,
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
