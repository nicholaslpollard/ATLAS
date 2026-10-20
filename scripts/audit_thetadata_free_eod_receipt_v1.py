from __future__ import annotations

"""Offline audit of the *retained* real ThetaData Free EOD SDK receipt.

No ThetaData import, account access, broker, source-plan read, simulation,
or provider request. A provider-normalized EOD dataframe is NOT a 09:35 quote.
"""

import argparse
from datetime import date, datetime, time, timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_DIR = ROOT / "data" / "options" / "diagnostics"
PREFIX = "thetadata_free_eod_shape_probe_v1_"
CONTRACT = "atlas-thetadata-free-eod-shape-probe-v1"
AUDIT_CONTRACT = "atlas-thetadata-free-eod-retained-source-audit-v1"
MAX_INPUT_BYTES = 512_000
EXPECTED_DAY = date(2026, 10, 16)
EXPECTED_EXPIRATION = date(2026, 11, 20)
QUOTE_FIELDS = ("bid", "ask", "bid_size", "ask_size")
PROVIDER_COLUMNS = ("created", "last_trade", "open", "high", "low",
                    "close", "volume", "count", "bid_size", "bid_exchange",
                    "bid", "bid_condition", "ask_size", "ask_exchange",
                    "ask", "ask_condition")
OPTION_COLUMNS = ("symbol", "expiration", "strike", "right") + PROVIDER_COLUMNS


class RetainedReceiptError(ValueError):
    pass


def _sha(body: dict[str, Any]) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise RetainedReceiptError("MISSING_TIMESTAMP_" + name.upper())
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        raise RetainedReceiptError("INVALID_TIMESTAMP_" + name.upper()) from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise RetainedReceiptError("NAIVE_TIMESTAMP_" + name.upper())
    # 2026-10-16 is EDT (UTC-04); a UTC offset cannot be read as ET wall clock.
    if stamp.utcoffset() != timedelta(hours=-4):
        raise RetainedReceiptError("UNEXPECTED_ET_OFFSET_" + name.upper())
    return stamp


def _finite_price(row: dict[str, Any], name: str) -> float:
    value = row.get(name)
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        raise RetainedReceiptError("NONFINITE_PRICE_" + name.upper())
    if value < 0:
        raise RetainedReceiptError("NEGATIVE_PRICE_" + name.upper())
    return float(value)


def _nonnegative_integer(row: dict[str, Any], name: str) -> int:
    value = row.get(name)
    if type(value) is not int or value < 0:
        raise RetainedReceiptError("INVALID_SIZE_OR_COUNT_" + name.upper())
    return value


def verify_receipt(receipt: dict[str, Any]) -> str:
    """Verify exact provider-response evidence identity before interpreting rows."""
    if not isinstance(receipt, dict):
        raise RetainedReceiptError("RECEIPT_NOT_OBJECT")
    expected = receipt.get("fingerprint")
    if (not isinstance(expected, str) or len(expected) != 64
            or any(c not in "0123456789abcdef" for c in expected)):
        raise RetainedReceiptError("RECEIPT_FINGERPRINT_UNAVAILABLE")
    body = {k: v for k, v in receipt.items() if k != "fingerprint"}
    if _sha(body) != expected:
        raise RetainedReceiptError("RECEIPT_FINGERPRINT_MISMATCH")
    if receipt.get("contract") != CONTRACT:
        raise RetainedReceiptError("WRONG_RECEIPT_CONTRACT")
    if receipt.get("status") != "TWO_EOD_DATAFRAMES_RECEIVED":
        raise RetainedReceiptError("RECEIPT_NOT_TWO_SUCCESSFUL_DATAFRAMES")
    if receipt.get("request_attempts") != 2 or receipt.get("request_cap") != 2:
        raise RetainedReceiptError("WRONG_REQUEST_BUDGET")
    return expected


def audit_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    fingerprint = verify_receipt(receipt)
    responses = receipt.get("responses")
    if not isinstance(responses, list) or len(responses) != 2:
        raise RetainedReceiptError("EXPECTED_TWO_RESPONSES")
    summaries: list[dict[str, Any]] = []
    all_contracts = set()
    for idx, (response, method, required_fields) in enumerate((
        (responses[0], "stock_history_eod", PROVIDER_COLUMNS),
        (responses[1], "option_history_eod", OPTION_COLUMNS),
    )):
        if not isinstance(response, dict) or response.get("method") != method:
            raise RetainedReceiptError("METHOD_ORDER_MISMATCH")
        if response.get("status") != "RECEIVED":
            raise RetainedReceiptError("EOD_DATAFRAME_NOT_RECEIVED")
        query = response.get("query")
        if not isinstance(query, dict):
            raise RetainedReceiptError("QUERY_MISSING")
        if (query.get("symbol") != "SPY"
                or query.get("start_date") != EXPECTED_DAY.isoformat()
                or query.get("end_date") != EXPECTED_DAY.isoformat()):
            raise RetainedReceiptError("SOURCE_SCOPE_MISMATCH")
        if idx == 1 and (
            query.get("expiration") != EXPECTED_EXPIRATION.isoformat()
            or query.get("right") != "call"
            or query.get("strike") != "*"
            or query.get("strike_range") != 2
        ):
            raise RetainedReceiptError("OPTION_SCOPE_MISMATCH")
        rows = response.get("normalized_rows")
        columns = response.get("columns")
        dtypes = response.get("dtypes")
        if not isinstance(rows, list) or not (0 < len(rows) <= 200):
            raise RetainedReceiptError("UNBOUNDED_OR_EMPTY_RECEIPT")
        if response.get("rows") != len(rows):
            raise RetainedReceiptError("EOD_ROW_COUNT_MISMATCH")
        if (not isinstance(columns, list)
                or not isinstance(dtypes, dict)
                or len(set(columns)) != len(columns)
                or not set(required_fields).issubset(columns)
                or set(dtypes) != set(columns)):
            raise RetainedReceiptError("EOD_SCHEMA_MISMATCH")

        option_table = []
        after_regular_trade = 0
        after_regular_creation = 0
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(columns):
                raise RetainedReceiptError("EOD_ROW_COLUMNS_MISMATCH")
            created = _timestamp(row["created"], "created")
            last_trade = _timestamp(row["last_trade"], "last_trade")
            if created.date() != EXPECTED_DAY or last_trade.date() != EXPECTED_DAY:
                raise RetainedReceiptError("EOD_REPORT_DATE_MISMATCH")
            if created.time() > time(16, 0):
                after_regular_creation += 1
            if last_trade.time() > time(16, 0):
                after_regular_trade += 1
            bid = _finite_price(row, "bid")
            ask = _finite_price(row, "ask")
            size_bid = _nonnegative_integer(row, "bid_size")
            size_ask = _nonnegative_integer(row, "ask_size")
            _nonnegative_integer(row, "volume")
            _nonnegative_integer(row, "count")
            if bid > ask:
                raise RetainedReceiptError("EOD_CROSSED_QUOTE")
            if idx == 1:
                if (row.get("symbol") != "SPY"
                        or row.get("expiration") != EXPECTED_EXPIRATION.isoformat()
                        or str(row.get("right")).upper() != "CALL"):
                    raise RetainedReceiptError("WRONG_OPTION_CONTRACT")
                strike = _finite_price(row, "strike")
                if strike <= 0:
                    raise RetainedReceiptError("NONPOSITIVE_STRIKE")
                identity = (strike, row["expiration"], str(row["right"]).upper())
                if identity in all_contracts:
                    raise RetainedReceiptError("DUPLICATE_CONTRACT_IDENTITY")
                all_contracts.add(identity)
                midpoint = (bid + ask) / 2
                option_table.append({
                    "strike": strike,
                    "right": "call",
                    "bid": bid,
                    "ask": ask,
                    "bid_size": size_bid,
                    "ask_size": size_ask,
                    "spread_to_mid": ((ask - bid) / midpoint) if midpoint > 0 else None,
                    "volume": row["volume"],
                    "count": row["count"],
                    "created_et": created.isoformat(),
                    "last_trade_et": last_trade.isoformat(),
                    "last_trade_after_16_et": last_trade.time() > time(16, 0),
                })
        summaries.append({
            "method": method, "rows": len(rows),
            "columns": columns, "dtypes": dtypes,
            "created_after_16_et_rows": after_regular_creation,
            "last_trade_after_16_et_rows": after_regular_trade,
            "contract_diagnostics": sorted(option_table, key=lambda v: v["strike"]),
        })

    return {
        "contract": AUDIT_CONTRACT,
        "status": "EOD_SHAPE_AUDITED_NOT_INTRADAY_EVIDENCE",
        "retained_source_fingerprint": fingerprint,
        "sdk_version": receipt.get("thetadata_version"),
        "provider_requests_by_audit": 0,
        "source_data_requests_reported": 2,
        "regular_session_close_et": "16:00:00",
        "warning": (
            "Provider EOD creation/last-trade timestamps after 16:00 are "
            "not 09:35 decision-available quotes; displayed size and NBBO "
            "do not prove executable fills. Condition/exchange codes unqualified."
        ),
        "response_audits": summaries,
    }


def _read_receipt(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RetainedReceiptError("RECEIPT_FILE_UNAVAILABLE")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise RetainedReceiptError("RECEIPT_TOO_LARGE")
    return json.loads(path.read_text(encoding="utf-8"))


def persist_audit(report: dict[str, Any], root: Path = RECEIPT_DIR) -> Path:
    fp = _sha(report)
    raw = (json.dumps({**report, "fingerprint": fp}, sort_keys=True, indent=2,
                      allow_nan=False) + "\n").encode("utf-8")
    root.mkdir(parents=True, exist_ok=True)
    path = root / ("thetadata_free_eod_retained_audit_v1_" + fp[:16] + ".json")
    try:
        with path.open("xb") as f:
            f.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise RetainedReceiptError("AUDIT_OUTPUT_COLLISION")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    print("ATLAS THETADATA RETAINED FREE EOD SOURCE AUDIT V1", flush=True)
    print("  ZERO provider requests. Read-only local source audit.", flush=True)
    try:
        if args.receipt is not None:
            path = args.receipt
        else:
            candidates = sorted(RECEIPT_DIR.glob(PREFIX + "*.json"))
            if len(candidates) != 1:
                raise RetainedReceiptError(
                    "EXPECTED_ONE_RETAINED_RECEIPT_FOUND_" + str(len(candidates))
                )
            path = candidates[0]
        report = audit_receipt(_read_receipt(path))
        saved = persist_audit(report)
        print("  source_fingerprint=" + report["retained_source_fingerprint"][:16])
        for item in report["response_audits"]:
            print(
                "  method={method} rows={rows} created_after_16={created_after_16_et_rows} "
                "last_trade_after_16={last_trade_after_16_et_rows}".format(**item)
            )
            for contract in item["contract_diagnostics"]:
                print(
                    "    CALL strike={strike:g} bid={bid:.2f} ask={ask:.2f} "
                    "spread_to_mid={spread_to_mid:.4%} sizes={bid_size}/{ask_size} "
                    "volume={volume} last_trade_after_16={last_trade_after_16_et}"
                    .format(**contract)
                )
        print("  retained_audit=" + str(saved))
        print("  COMPLETE status=" + report["status"] + " provider_requests=0")
        return 0
    except Exception as exc:
        print("  STOP type=" + type(exc).__name__)
        if isinstance(exc, RetainedReceiptError):
            print("  reason=" + str(exc))
        print("  ZERO provider requests; original EOD receipt preserved")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
