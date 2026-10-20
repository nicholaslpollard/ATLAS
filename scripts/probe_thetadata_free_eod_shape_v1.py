from __future__ import annotations

"""Two-request Free-tier ThetaData EOD connectivity and dataframe-shape probe.

Run ONLY in the isolated ThetaData Python environment. Deliberately separate
from ATLAS's historical intraday quote/OI qualification and frozen plan.

- one stock EOD call and one narrowly scoped option EOD call, max two total
- no retries, Greeks, intraday endpoints, broker operations or simulation
- record provider-returned dataframe rows, column types and timestamp fields
- do not log credentials or raw provider exception messages
"""

import argparse
from datetime import date, datetime
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "atlas-thetadata-free-eod-shape-probe-v1"
PINNED_THETADATA = "1.0.12"
MAX_ROWS_PER_RESPONSE = 200
MAX_REPORT_BYTES = 512_000
REPORT_DIR = ROOT / "data" / "options" / "diagnostics"
SAMPLE_DAY = date(2026, 10, 16)
OPTION_EXPIRATION = date(2026, 11, 20)

STOCK_KWARGS = {
    "symbol": "SPY",
    "start_date": SAMPLE_DAY,
    "end_date": SAMPLE_DAY,
}
OPTION_KWARGS = {
    "symbol": "SPY",
    "start_date": SAMPLE_DAY,
    "end_date": SAMPLE_DAY,
    "expiration": OPTION_EXPIRATION,
    "strike": "*",
    "right": "call",
    "strike_range": 2,
}
READS = (
    ("stock_history_eod", STOCK_KWARGS),
    ("option_history_eod", OPTION_KWARGS),
)


def _auth_present() -> bool:
    """Determine key presence without disclosing any secret or length."""
    if str(os.environ.get("THETADATA_API_KEY", "")).strip():
        return True
    from dotenv import dotenv_values

    values = dotenv_values(ROOT / ".env")
    return bool(str(values.get("THETADATA_API_KEY") or "").strip())


def inspect_free_eod_contract(client_type: type) -> dict[str, str]:
    """Inspect method signatures without constructing/authenticating a client."""
    status = {}
    for name, kwargs in READS:
        method = getattr(client_type, name, None)
        if not callable(method):
            raise RuntimeError("FREE_EOD_SDK_METHOD_MISSING_" + name)
        try:
            params = inspect.signature(method).parameters
        except (TypeError, ValueError) as exc:
            raise RuntimeError("FREE_EOD_SDK_SIGNATURE_UNINSPECTABLE") from None
        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in params.values()
        )
        explicit = {
            key for key, param in params.items()
            if param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
        missing = set(kwargs) - explicit
        if missing and not accepts_kwargs:
            raise RuntimeError("FREE_EOD_SDK_KEYWORDS_NOT_ACCEPTED_" + name)
        status[name] = (
            "EXPLICIT_ARGUMENTS" if not missing
            else "DYNAMIC_KWARGS_SEMANTICS_UNVERIFIED"
        )
    return status


def _value(item: Any) -> Any:
    """Convert provider dataframe scalars to strict, JSON-safe values."""
    import pandas as pd

    if item is None:
        return None
    if isinstance(item, (date, datetime)):
        return item.isoformat()
    try:
        if bool(pd.isna(item)):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(item, (str, bool, int)):
        return item
    if isinstance(item, float):
        return item if math.isfinite(item) else None
    if hasattr(item, "item"):
        return _value(item.item())
    if hasattr(item, "isoformat"):
        return item.isoformat()
    raise TypeError("FREE_EOD_UNSUPPORTED_SCALAR_" + type(item).__name__)


def summarize_frame(frame: Any) -> dict[str, Any]:
    """Retain normalized SDK DataFrame rows, never pretend these are wire bytes."""
    if not hasattr(frame, "columns") or not hasattr(frame, "to_dict"):
        raise TypeError("FREE_EOD_NOT_A_DATAFRAME")
    columns = [str(x) for x in frame.columns]
    if len(columns) != len(set(columns)) or len(columns) > 64:
        raise ValueError("FREE_EOD_COLUMNS_INVALID")
    count = len(frame)
    if count > MAX_ROWS_PER_RESPONSE:
        raise ValueError("FREE_EOD_RESPONSE_EXCEEDS_BOUNDED_SHAPE")
    records = frame.to_dict(orient="records")
    rows = [{str(k): _value(v) for k, v in row.items()} for row in records]
    dtypes = {str(k): str(v) for k, v in frame.dtypes.items()}
    return {"rows": count, "columns": columns, "dtypes": dtypes,
            "sample_rows": rows[:3], "normalized_rows": rows}


def collect_free_eod_shape(
    client_type: type, client_factory: Callable[[], Any]
) -> dict[str, Any]:
    """Authorize no reads here; caller must enforce CLI flag and local key."""
    signatures = inspect_free_eod_contract(client_type)
    client = client_factory()
    result: dict[str, Any] = {
        "contract": CONTRACT,
        "purpose": "FREE_EOD_SCHEMA_DIAGNOSTIC_ONLY",
        "not_intraday_or_execution_evidence": True,
        "request_cap": 2,
        "request_attempts": 0,
        "sdk_method_contracts": signatures,
        "responses": [],
    }
    for name, kwargs in READS:
        result["request_attempts"] += 1
        try:
            frame = getattr(client, name)(**kwargs)
        except Exception as exc:
            # Never include provider exception text (may contain auth context).
            result["responses"].append({
                "method": name, "status": "SDK_EXCEPTION",
                "error_type": type(exc).__name__,
            })
            break
        shape = summarize_frame(frame)
        result["responses"].append({
            "method": name,
            "status": "RECEIVED" if shape["rows"] else "EMPTY",
            "query": {
                k: (v.isoformat() if isinstance(v, date) else v)
                for k, v in kwargs.items()
            },
            **shape,
        })
    result["status"] = (
        "TWO_EOD_DATAFRAMES_RECEIVED"
        if len(result["responses"]) == 2
        and all(x["status"] == "RECEIVED" for x in result["responses"])
        else "SOURCE_SHAPE_INCOMPLETE"
    )
    return result


def persist_report(report: dict[str, Any], directory: Path = REPORT_DIR) -> Path:
    payload = dict(report)
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":"),
                   allow_nan=False).encode("utf-8")
    ).hexdigest()
    raw = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
           + "\n").encode("utf-8")
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError("FREE_EOD_REPORT_EXCEEDS_SIZE_BOUND")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("thetadata_free_eod_shape_probe_v1_"
                        + payload["fingerprint"][:16] + ".json")
    try:
        with path.open("xb") as file:
            file.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError("FREE_EOD_RECEIPT_COLLISION")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorize-two-free-eod-reads", action="store_true")
    args = parser.parse_args(argv)

    print("ATLAS THETADATA FREE EOD SDK SHAPE PROBE V1", flush=True)
    if not args.authorize_two_free_eod_reads:
        print("  BLOCKED: explicit --authorize-two-free-eod-reads required")
        return 2
    if Path.cwd().resolve() != ROOT.resolve():
        print("  BLOCKED: run from ATLAS repository root")
        return 2
    if not _auth_present():
        print("  BLOCKED: THETADATA_API_KEY not observed (value not printed)")
        return 2
    try:
        version = importlib.metadata.version("thetadata")
        if version != PINNED_THETADATA:
            print("  BLOCKED: SDK version differs from tested 1.0.12")
            return 2
        from thetadata import ThetaClient

        # SDK interface discovery precedes ThetaClient initialization and GETs.
        contract = inspect_free_eod_contract(ThetaClient)
        print("  SDK signature:", json.dumps(contract, sort_keys=True))
        print(
            "  SCOPE: SPY 2026-10-16 EOD stock + 2026-11-20 "
            "CALL expiration, 2 neighboring strikes on either side"
        )
        print(
            "  Max two Free-tier EOD requests, no retries, "
            "no intraday/Greeks/broker calls",
            flush=True,
        )
        result = collect_free_eod_shape(
            ThetaClient, lambda: ThetaClient(dataframe_type="pandas")
        )
        result["thetadata_version"] = version
        path = persist_report(result)
        for item in result["responses"]:
            print(
                "  method={method} status={status} rows={rows}".format(
                    method=item["method"], status=item["status"],
                    rows=item.get("rows", "unknown")
                )
            )
            if "columns" in item:
                print("  columns=" + json.dumps(item["columns"]))
                print("  dtypes=" + json.dumps(item["dtypes"], sort_keys=True))
                print(
                    "  sample_rows=" + json.dumps(item["sample_rows"],
                                                   sort_keys=True)
                )
            if "error_type" in item:
                print("  error_type=" + item["error_type"])
        print("  retained_report=" + str(path))
        print(
            "  COMPLETE status={status} provider_request_attempts={n}".format(
                status=result["status"], n=result["request_attempts"]
            )
        )
        return 0 if result["status"] == "TWO_EOD_DATAFRAMES_RECEIVED" else 4
    except Exception as exc:
        print("  STOP error_type=" + type(exc).__name__)
        print("  No automatic retry or additional provider requests")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
