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
    _finite_number,
    _marketdata_date,
    _massive_date,
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
    "contract_id": "atlas-marketdata-massive-disjoint-validation-v2",
    "purpose": (
        "preregistered disjoint validation of MarketData historical EOD last/volume "
        "semantics against Massive trade-derived daily aggregates using activity-aware "
        "coverage learned from the frozen V1 failure diagnostics"
    ),
    "evidence_basis": {
        "v1_failed_validation": {
            "run_id": "20260923T211759Z",
            "evidence_fingerprint": (
                "2ab5dc3012bdbda388e6d2648403814999c54aa9ac0d4184295c595072eea145"
            ),
            "status": "VALIDATION_FAILED",
        },
        "raw_trade_diagnostic": {
            "run_id": "20260923T222933Z",
            "evidence_fingerprint": (
                "48d58cecf4d084f241f8b6b008454427389be609c18d42ffcdcb318a12be4e6a"
            ),
            "status": "DIAGNOSTIC_INCOMPLETE",
            "reason": "Massive raw option trades are not available on the current plan",
        },
        "aggregate_surface_diagnostic": {
            "run_id": "20260923T225713Z",
            "evidence_fingerprint": (
                "dadc60d4eb1bf4f33d123cdd1b8b09d92222f8e53b4fdb3a9a28c48b1d5b1487"
            ),
            "status": "AGGREGATE_SURFACES_CONSISTENT",
            "daily_present_positive_volume_sessions": 4,
            "daily_absent_zero_volume_sessions": 5,
            "minute_volume_matched_marketdata_on_present_sessions": True,
        },
    },
    "validation_anchors": [
        {"root": "AAPL", "date": "2026-01-05"},
        {"root": "TSLA", "date": "2026-02-17"},
        {"root": "AMD", "date": "2026-03-16"},
        {"root": "JPM", "date": "2026-05-18"},
        {"root": "XLF", "date": "2026-07-06"},
        {"root": "TLT", "date": "2026-08-17"},
    ],
    "prior_cross_provider_roots": [
        "SPY",
        "MSFT",
        "NVDA",
        "QQQ",
        "IWM",
        "AMZN",
        "META",
        "DIA",
    ],
    "prior_cross_provider_dates": [
        "2026-03-02",
        "2026-05-01",
        "2026-07-01",
        "2026-09-01",
        "2026-02-02",
        "2026-04-01",
        "2026-06-01",
        "2026-08-03",
    ],
    "chain_query": {"dte": 30, "strike_limit": 8},
    "quote_series_days": 10,
    "massive_query": {
        "adjusted": False,
        "sort": "asc",
        "limit": 50,
    },
    "activity_rule": {
        "marketdata_positive_volume_requires_massive_bar": True,
        "marketdata_zero_volume_requires_massive_bar_absent": True,
        "zero_volume_last_is_price_authority_eligible": False,
    },
    "preregistered_thresholds": {
        "required_anchor_count": 6,
        "minimum_marketdata_quote_rows_per_anchor": 5,
        "minimum_positive_volume_sessions_per_anchor": 5,
        "minimum_activity_concordance_rate_per_anchor": 1.0,
        "minimum_last_inside_massive_range_rate_per_anchor": 1.0,
        "maximum_median_price_relative_diff_per_anchor": 0.05,
        "maximum_aggregate_median_price_relative_diff": 0.02,
        "maximum_median_volume_relative_diff_per_anchor": 0.15,
        "maximum_aggregate_median_volume_relative_diff": 0.10,
        "minimum_zero_volume_sessions_complete_sample": 1,
        "minimum_aggregate_positive_volume_comparisons": 30,
        "exact_last_close_match_rate": "DESCRIPTIVE_ONLY",
    },
    "authority_if_passed": {
        "marketdata_positive_volume_eod_last_volume_semantics_validated": True,
        "marketdata_zero_volume_last_validated": False,
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


class MarketDataMassiveValidationV2Error(RuntimeError):
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
        / "marketdata_massive_validation_v2"
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


def _activity_concordance(
    marketdata_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    massive_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    md_by_date: dict[str, dict[str, Any]] = {}
    massive_by_date: dict[str, dict[str, Any]] = {}

    for row in marketdata_rows:
        session_date = _marketdata_date(row.get("updated"))
        if session_date in md_by_date:
            raise MarketDataMassiveValidationV2Error(
                f"duplicate MarketData row for {session_date}"
            )
        md_by_date[session_date] = row

    for row in massive_rows:
        session_date = _massive_date(row.get("t"))
        if session_date in massive_by_date:
            raise MarketDataMassiveValidationV2Error(
                f"duplicate Massive row for {session_date}"
            )
        massive_by_date[session_date] = row

    records: list[dict[str, Any]] = []
    for session_date in sorted(md_by_date):
        md_volume = _finite_number(md_by_date[session_date].get("volume"))
        positive_volume = md_volume is not None and md_volume > 0
        zero_volume = md_volume == 0
        massive_present = session_date in massive_by_date

        if positive_volume:
            concordant = massive_present
            disposition = (
                "POSITIVE_VOLUME_WITH_MASSIVE_BAR"
                if massive_present
                else "POSITIVE_VOLUME_MISSING_MASSIVE_BAR"
            )
        elif zero_volume:
            concordant = not massive_present
            disposition = (
                "ZERO_VOLUME_WITHOUT_MASSIVE_BAR"
                if not massive_present
                else "ZERO_VOLUME_WITH_MASSIVE_BAR"
            )
        else:
            concordant = False
            disposition = "MARKETDATA_VOLUME_INVALID_OR_MISSING"

        records.append(
            {
                "date": session_date,
                "marketdata_volume": md_volume,
                "massive_bar_present": massive_present,
                "positive_volume": positive_volume,
                "zero_volume": zero_volume,
                "concordant": concordant,
                "disposition": disposition,
            }
        )

    extra_massive_dates = sorted(set(massive_by_date).difference(md_by_date))
    concordant_count = sum(bool(item["concordant"]) for item in records)
    rate = concordant_count / len(records) if records else None
    positive_dates = [
        item["date"] for item in records if item["positive_volume"]
    ]
    zero_dates = [item["date"] for item in records if item["zero_volume"]]

    return {
        "records": records,
        "marketdata_session_count": len(records),
        "positive_volume_session_count": len(positive_dates),
        "zero_volume_session_count": len(zero_dates),
        "positive_volume_dates": positive_dates,
        "zero_volume_dates": zero_dates,
        "concordant_session_count": concordant_count,
        "activity_concordance_rate": rate,
        "extra_massive_dates": extra_massive_dates,
        "passed": (
            bool(records)
            and rate == 1.0
            and not extra_massive_dates
        ),
    }


def _anchor_checks(
    *,
    marketdata_rows: int,
    activity: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, bool]:
    thresholds = CONTRACT["preregistered_thresholds"]
    return {
        "marketdata_quote_rows": _threshold_pass(
            marketdata_rows,
            minimum=thresholds["minimum_marketdata_quote_rows_per_anchor"],
        ),
        "positive_volume_sessions": _threshold_pass(
            activity.get("positive_volume_session_count"),
            minimum=thresholds["minimum_positive_volume_sessions_per_anchor"],
        ),
        "activity_concordance_rate": _threshold_pass(
            activity.get("activity_concordance_rate"),
            minimum=thresholds["minimum_activity_concordance_rate_per_anchor"],
        )
        and not bool(activity.get("extra_massive_dates")),
        "positive_volume_comparisons": (
            int(summary.get("overlap_sessions") or 0)
            == int(activity.get("positive_volume_session_count") or 0)
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
    total_zero_volume_sessions: int,
) -> dict[str, bool]:
    thresholds = CONTRACT["preregistered_thresholds"]
    required = int(thresholds["required_anchor_count"])
    return {
        "required_anchor_count": anchor_count == required,
        "all_anchors_pass": anchor_pass_count == required,
        "sparse_case_observed": _threshold_pass(
            total_zero_volume_sessions,
            minimum=thresholds["minimum_zero_volume_sessions_complete_sample"],
        ),
        "aggregate_positive_volume_comparisons": _threshold_pass(
            aggregate.get("overlap_sessions"),
            minimum=thresholds["minimum_aggregate_positive_volume_comparisons"],
        ),
        "aggregate_median_price_relative_diff": _threshold_pass(
            aggregate.get("median_price_rel_diff"),
            maximum=thresholds["maximum_aggregate_median_price_relative_diff"],
        ),
        "aggregate_median_volume_relative_diff": _threshold_pass(
            aggregate.get("median_volume_rel_diff"),
            maximum=thresholds["maximum_aggregate_median_volume_relative_diff"],
        ),
    }


def run_marketdata_massive_disjoint_validation_v2(
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
            activity = _activity_concordance(marketdata_rows, massive_rows)
            comparisons = compare_exact_contract_days(marketdata_rows, massive_rows)
        except (MarketDataMassiveOverlapError, MarketDataMassiveValidationV2Error) as exc:
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

        positive_dates = set(activity["positive_volume_dates"])
        positive_comparisons = [
            row for row in comparisons if row.get("date") in positive_dates
        ]
        summary = summarize_comparisons(positive_comparisons)
        checks = _anchor_checks(
            marketdata_rows=len(marketdata_rows),
            activity=activity,
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
            "activity": activity,
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
            "comparisons": positive_comparisons,
            "error": None,
        }
        anchors.append(record)
        print(
            f"      md_rows={len(marketdata_rows)} "
            f"md_positive={activity['positive_volume_session_count']} "
            f"md_zero={activity['zero_volume_session_count']} "
            f"massive_rows={len(massive_rows)} "
            f"activity_concordance={activity['activity_concordance_rate']} "
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
    total_zero_volume_sessions = sum(
        int((item.get("activity") or {}).get("zero_volume_session_count") or 0)
        for item in anchors
        if isinstance(item.get("activity"), dict)
    )
    aggregate_checks = _aggregate_checks(
        anchor_count=len(anchors),
        anchor_pass_count=pass_count,
        aggregate=aggregate,
        total_zero_volume_sessions=total_zero_volume_sessions,
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
            "VALIDATED_FOR_POSITIVE_VOLUME_EOD_LAST_VOLUME_SEMANTICS"
            if validation_passed
            else "VALIDATION_FAILED"
        ),
        "contract_id": CONTRACT["contract_id"],
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "run_id": run_id,
        "generated_at_utc": generated.isoformat(),
        "evidence_basis": CONTRACT["evidence_basis"],
        "activity_rule": CONTRACT["activity_rule"],
        "preregistered_thresholds": CONTRACT["preregistered_thresholds"],
        "anchors": anchors,
        "anchor_pass_count": pass_count,
        "total_zero_volume_sessions": total_zero_volume_sessions,
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
                "marketdata_positive_volume_eod_last_volume_semantics_validated": False,
            }
        ),
        "limitations": {
            "zero_volume_marketdata_last_not_independently_validated": True,
            "raw_trade_presence_not_observed": True,
            "historical_bid_ask_not_independently_validated": True,
            "intraday_option_path_not_validated": True,
            "execution_price_authority_not_created": True,
            "qualification_selector_not_simulator_selector": True,
            "v1_failure_remains_immutable": True,
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
