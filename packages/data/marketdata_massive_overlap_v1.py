from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_five_year_options_qualification import array_rows
from packages.data.provider_source_qualification import stable_fingerprint
from packages.providers.massive.rest import MassiveRESTClient


EASTERN = ZoneInfo("America/New_York")

CONTRACT = {
    "contract_id": "atlas-marketdata-massive-option-overlap-diagnostic-v1",
    "purpose": (
        "independent semantic calibration of accepted MarketData Starter Trial "
        "option EOD evidence against Massive exact-contract daily aggregates"
    ),
    "marketdata_source": {
        "contract_id": "atlas-marketdata-five-year-historical-options-v1",
        "run_id": "20260923T203419Z",
        "evidence_fingerprint": (
            "facd9289fc56279a14294c442f8a1f256388cfd152662be1bc06f600d1bf914a"
        ),
        "required_status": "QUALIFIED_FOR_STARTER_TRIAL_CAPABILITY",
    },
    "massive_source": {
        "endpoint": "/v2/aggs/ticker/{optionsTicker}/range/1/day/{from}/{to}",
        "ticker_prefix": "O:",
        "adjusted": False,
        "sort": "asc",
        "limit": 50,
        "documented_basic_history": "2 years",
        "comparison_roots": ["SPY", "MSFT", "NVDA", "QQQ"],
        "excluded_trial_anchor": {
            "root": "AAPL",
            "date": "2021-10-01",
            "reason": "outside current Massive Options Basic two-year REST history",
        },
    },
    "comparison_fields": {
        "marketdata": ["last", "volume", "updated"],
        "massive": ["o", "h", "l", "c", "v", "t"],
    },
    "interpretation": {
        "marketdata_last_vs_massive_close": "semantic calibration only",
        "volume_comparison": "diagnostic only because aggregate trade conditions may differ",
        "bid_ask_cross_validation": False,
        "thresholded_price_authority": False,
    },
    "authority": {
        "provider_reads": True,
        "provider_writes": False,
        "historical_price_authority": False,
        "strategy_evidence": False,
        "paper": False,
        "live": False,
        "orders": False,
        "promotion": False,
    },
}
CONTRACT_FINGERPRINT = stable_fingerprint(CONTRACT)


class MarketDataMassiveOverlapError(RuntimeError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MarketDataMassiveOverlapError(f"JSON root is not an object: {path}")
    return payload


def _verify_receipt(receipt: dict[str, Any]) -> Path:
    raw_path = Path(str(receipt.get("path") or ""))
    expected = str(receipt.get("sha256") or "").strip().lower()
    if not raw_path.is_file():
        raise MarketDataMassiveOverlapError(f"raw source file is missing: {raw_path}")
    actual = _sha256_bytes(raw_path.read_bytes())
    if not expected or actual != expected:
        raise MarketDataMassiveOverlapError(
            f"raw source hash mismatch for {raw_path}: expected={expected} actual={actual}"
        )
    return raw_path


def _source_report_path(settings: AtlasSettings) -> Path:
    run_id = str(CONTRACT["marketdata_source"]["run_id"])
    return (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_app"
        / "historical_options_v1"
        / run_id
        / "report.json"
    )


def load_accepted_marketdata_trial_report(settings: AtlasSettings) -> dict[str, Any]:
    path = _source_report_path(settings)
    if not path.is_file():
        raise MarketDataMassiveOverlapError(
            f"accepted MarketData trial report is missing: {path}"
        )
    report = _load_json(path)
    expected_status = str(CONTRACT["marketdata_source"]["required_status"])
    expected_fingerprint = str(CONTRACT["marketdata_source"]["evidence_fingerprint"])
    expected_contract = str(CONTRACT["marketdata_source"]["contract_id"])
    expected_run_id = str(CONTRACT["marketdata_source"]["run_id"])
    if report.get("contract_id") != expected_contract:
        raise MarketDataMassiveOverlapError(
            f"MarketData source contract mismatch: {report.get('contract_id')!r}"
        )
    if report.get("run_id") != expected_run_id:
        raise MarketDataMassiveOverlapError(
            f"MarketData source run id mismatch: {report.get('run_id')!r}"
        )
    if report.get("status") != expected_status:
        raise MarketDataMassiveOverlapError(
            f"MarketData source status mismatch: {report.get('status')!r}"
        )
    if report.get("evidence_fingerprint") != expected_fingerprint:
        raise MarketDataMassiveOverlapError(
            "MarketData source evidence fingerprint does not match the accepted trial"
        )
    recomputed = stable_fingerprint(
        {
            key: value
            for key, value in report.items()
            if key != "evidence_fingerprint"
        }
    )
    if recomputed != expected_fingerprint:
        raise MarketDataMassiveOverlapError(
            "MarketData source report contents do not reproduce the accepted evidence fingerprint"
        )
    if report.get("starter_trial") is not True:
        raise MarketDataMassiveOverlapError(
            "MarketData source report is not marked as Starter Trial evidence"
        )
    return report


def _marketdata_date(updated: Any) -> str:
    try:
        stamp = float(updated)
    except (TypeError, ValueError) as exc:
        raise MarketDataMassiveOverlapError(
            f"invalid MarketData updated timestamp: {updated!r}"
        ) from exc
    return datetime.fromtimestamp(stamp, tz=UTC).astimezone(EASTERN).date().isoformat()


def _massive_date(timestamp_ms: Any) -> str:
    try:
        stamp = float(timestamp_ms) / 1000.0
    except (TypeError, ValueError) as exc:
        raise MarketDataMassiveOverlapError(
            f"invalid Massive aggregate timestamp: {timestamp_ms!r}"
        ) from exc
    return datetime.fromtimestamp(stamp, tz=UTC).astimezone(EASTERN).date().isoformat()


def _unique_by_date(
    rows: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    *,
    date_fn,
    source: str,
) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = date_fn(row)
        if key in mapped:
            raise MarketDataMassiveOverlapError(
                f"{source} produced duplicate daily row for {key}"
            )
        mapped[key] = row
    return mapped


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def compare_exact_contract_days(
    marketdata_rows: tuple[dict[str, Any], ...],
    massive_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    md_by_date = _unique_by_date(
        marketdata_rows,
        date_fn=lambda row: _marketdata_date(row.get("updated")),
        source="MarketData",
    )
    massive_by_date = _unique_by_date(
        massive_rows,
        date_fn=lambda row: _massive_date(row.get("t")),
        source="Massive",
    )

    comparisons: list[dict[str, Any]] = []
    for session_date in sorted(set(md_by_date).intersection(massive_by_date)):
        md = md_by_date[session_date]
        mv = massive_by_date[session_date]
        md_last = _finite_number(md.get("last"))
        massive_close = _finite_number(mv.get("c"))
        md_volume = _finite_number(md.get("volume"))
        massive_volume = _finite_number(mv.get("v"))
        massive_low = _finite_number(mv.get("l"))
        massive_high = _finite_number(mv.get("h"))

        price_abs_diff = (
            abs(md_last - massive_close)
            if md_last is not None and massive_close is not None
            else None
        )
        price_rel_diff = (
            price_abs_diff / max(abs(md_last), abs(massive_close), 1e-12)
            if price_abs_diff is not None
            else None
        )
        volume_abs_diff = (
            abs(md_volume - massive_volume)
            if md_volume is not None and massive_volume is not None
            else None
        )
        volume_rel_diff = (
            volume_abs_diff / max(abs(md_volume), abs(massive_volume), 1.0)
            if volume_abs_diff is not None
            else None
        )
        inside_range = (
            massive_low <= md_last <= massive_high
            if md_last is not None
            and massive_low is not None
            and massive_high is not None
            else None
        )
        comparisons.append(
            {
                "date": session_date,
                "marketdata_last": md_last,
                "massive_open": _finite_number(mv.get("o")),
                "massive_high": massive_high,
                "massive_low": massive_low,
                "massive_close": massive_close,
                "price_abs_diff": price_abs_diff,
                "price_rel_diff": price_rel_diff,
                "marketdata_volume": md_volume,
                "massive_volume": massive_volume,
                "volume_abs_diff": volume_abs_diff,
                "volume_rel_diff": volume_rel_diff,
                "marketdata_last_inside_massive_range": inside_range,
            }
        )
    return comparisons


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def summarize_comparisons(rows: list[dict[str, Any]]) -> dict[str, Any]:
    price_abs = [
        float(row["price_abs_diff"])
        for row in rows
        if row.get("price_abs_diff") is not None
    ]
    price_rel = [
        float(row["price_rel_diff"])
        for row in rows
        if row.get("price_rel_diff") is not None
    ]
    volume_rel = [
        float(row["volume_rel_diff"])
        for row in rows
        if row.get("volume_rel_diff") is not None
    ]
    inside = [
        bool(row["marketdata_last_inside_massive_range"])
        for row in rows
        if row.get("marketdata_last_inside_massive_range") is not None
    ]
    exact_price = [value <= 1e-12 for value in price_abs]
    return {
        "overlap_sessions": len(rows),
        "price_comparable_sessions": len(price_abs),
        "exact_price_match_sessions": sum(exact_price),
        "exact_price_match_rate": (
            sum(exact_price) / len(exact_price) if exact_price else None
        ),
        "median_price_abs_diff": _median(price_abs),
        "mean_price_abs_diff": _mean(price_abs),
        "max_price_abs_diff": max(price_abs) if price_abs else None,
        "median_price_rel_diff": _median(price_rel),
        "mean_price_rel_diff": _mean(price_rel),
        "max_price_rel_diff": max(price_rel) if price_rel else None,
        "marketdata_last_inside_massive_range_sessions": sum(inside),
        "marketdata_last_inside_massive_range_rate": (
            sum(inside) / len(inside) if inside else None
        ),
        "volume_comparable_sessions": len(volume_rel),
        "median_volume_rel_diff": _median(volume_rel),
        "mean_volume_rel_diff": _mean(volume_rel),
        "max_volume_rel_diff": max(volume_rel) if volume_rel else None,
    }


def _persist_raw(root: Path, *, label: str, payload: dict[str, Any]) -> dict[str, Any]:
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


def _report_root(settings: AtlasSettings, run_id: str) -> Path:
    return (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "marketdata_massive_overlap_v1"
        / run_id
    )


def run_marketdata_massive_overlap_diagnostic_v1(
    settings: AtlasSettings,
    *,
    massive_client: MassiveRESTClient | None = None,
) -> dict[str, Any]:
    source = load_accepted_marketdata_trial_report(settings)
    client = massive_client or MassiveRESTClient(settings)
    generated = datetime.now(UTC)
    run_id = generated.strftime("%Y%m%dT%H%M%SZ")
    root = _report_root(settings, run_id)
    root.mkdir(parents=True, exist_ok=True)

    allowed_roots = set(CONTRACT["massive_source"]["comparison_roots"])
    source_anchors = [
        dict(item)
        for item in source.get("anchors", [])
        if isinstance(item, dict) and str(item.get("root")) in allowed_roots
    ]

    anchors: list[dict[str, Any]] = []
    terminal_error: str | None = None
    for index, anchor in enumerate(source_anchors, start=1):
        root_symbol = str(anchor["root"])
        source_date = str(anchor["date"])
        option_symbol = str(anchor.get("selected_option_symbol") or "")
        quote_receipt = anchor.get("quote_raw_receipt")
        if not option_symbol or not isinstance(quote_receipt, dict):
            terminal_error = (
                f"accepted MarketData anchor {root_symbol} lacks selected contract/raw quote receipt"
            )
            anchors.append(
                {
                    "root": root_symbol,
                    "date": source_date,
                    "status": "SOURCE_EVIDENCE_INCOMPLETE",
                    "error": terminal_error,
                }
            )
            continue

        raw_path = _verify_receipt(quote_receipt)
        marketdata_payload = _load_json(raw_path)
        marketdata_rows = array_rows(marketdata_payload)
        from_date = source_date
        to_date = max(
            (_marketdata_date(row.get("updated")) for row in marketdata_rows),
            default=source_date,
        )
        massive_ticker = f"O:{option_symbol}"

        print(
            f"  [{index}/{len(source_anchors)}] {root_symbol} {massive_ticker} "
            f"{from_date}..{to_date}",
            flush=True,
        )
        try:
            massive_payload = client.get_json(
                (
                    f"/v2/aggs/ticker/{massive_ticker}/range/1/day/"
                    f"{from_date}/{to_date}"
                ),
                {
                    "adjusted": False,
                    "sort": "asc",
                    "limit": int(CONTRACT["massive_source"]["limit"]),
                },
            )
        except Exception as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            anchors.append(
                {
                    "root": root_symbol,
                    "date": source_date,
                    "option_symbol": option_symbol,
                    "massive_ticker": massive_ticker,
                    "status": "MASSIVE_ERROR",
                    "error": terminal_error,
                }
            )
            print(f"      ERROR: {terminal_error}", flush=True)
            continue

        raw_receipt = _persist_raw(
            root,
            label=f"{index:02d}-{root_symbol}-{source_date}-{option_symbol}",
            payload=massive_payload,
        )
        massive_results = massive_payload.get("results") or []
        massive_rows = [
            row for row in massive_results if isinstance(row, dict)
        ] if isinstance(massive_results, list) else []
        comparisons = compare_exact_contract_days(marketdata_rows, massive_rows)
        summary = summarize_comparisons(comparisons)
        status = "OVERLAP_OBSERVED" if comparisons else "NO_OVERLAP"
        anchors.append(
            {
                "root": root_symbol,
                "date": source_date,
                "option_symbol": option_symbol,
                "massive_ticker": massive_ticker,
                "status": status,
                "marketdata_quote_rows": len(marketdata_rows),
                "massive_aggregate_rows": len(massive_rows),
                "summary": summary,
                "comparisons": comparisons,
                "massive_raw_receipt": raw_receipt,
                "error": None,
            }
        )
        print(
            f"      marketdata_rows={len(marketdata_rows)} "
            f"massive_rows={len(massive_rows)} "
            f"overlap={summary['overlap_sessions']} "
            f"exact_price_rate={summary['exact_price_match_rate']}",
            flush=True,
        )

    expected_anchor_count = len(allowed_roots)
    all_expected = len(source_anchors) == expected_anchor_count
    all_overlap = (
        len(anchors) == expected_anchor_count
        and all(item.get("status") == "OVERLAP_OBSERVED" for item in anchors)
    )
    total_overlap = sum(
        int((item.get("summary") or {}).get("overlap_sessions") or 0)
        for item in anchors
        if isinstance(item.get("summary"), dict)
    )
    all_comparisons = [
        row
        for item in anchors
        for row in (
            item.get("comparisons")
            if isinstance(item.get("comparisons"), list)
            else []
        )
        if isinstance(row, dict)
    ]
    aggregate = summarize_comparisons(all_comparisons)

    status = (
        "DIAGNOSTIC_COMPLETE"
        if all_expected and all_overlap and total_overlap > 0
        else "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
        if anchors
        else "FAIL"
    )

    report: dict[str, Any] = {
        "status": status,
        "contract_id": CONTRACT["contract_id"],
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "run_id": run_id,
        "generated_at_utc": generated.isoformat(),
        "marketdata_source_run_id": source.get("run_id"),
        "marketdata_source_evidence_fingerprint": source.get("evidence_fingerprint"),
        "massive_expected_anchor_count": expected_anchor_count,
        "massive_source_anchor_count": len(source_anchors),
        "all_expected_anchors_present": all_expected,
        "all_expected_anchors_overlap": all_overlap,
        "total_overlap_sessions": total_overlap,
        "aggregate_summary": aggregate,
        "anchors": anchors,
        "excluded_trial_anchor": CONTRACT["massive_source"]["excluded_trial_anchor"],
        "terminal_error": terminal_error,
        "authority": CONTRACT["authority"],
        "limitations": {
            "exploratory_semantic_calibration_only": True,
            "no_predeclared_price_acceptance_threshold": True,
            "massive_basic_does_not_cross_validate_historical_bid_ask": True,
            "deep_2021_aapl_not_cross_validated": True,
            "historical_price_authority_created": False,
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
