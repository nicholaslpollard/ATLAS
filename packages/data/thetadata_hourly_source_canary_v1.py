from __future__ import annotations

"""One historical SPY hourly option-quote source canary, not a backtest.

Default design is zero-provider. An authorized invocation makes at most one
option_history_quote method request, without retries or year fallback. Receipts
are immutable. Original rows are never filtered or silently promoted.
"""

from collections import Counter
from datetime import date, datetime
import gzip
import hashlib
import json
import shutil
from typing import Any, Callable
from uuid import uuid4

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_qualification_v1 import _persist_raw
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataError, ThetaDataResponse, option_history_hourly_quote_surface,
)

CONTRACT = "atlas-thetadata-spy-hourly-source-one-request-canary-v1"
OUTPUT_REL = "data/options/provider_qualification/thetadata_hourly_spy_v1"
DATE_ET = "2025-06-09"
MAX_DTE = 45
RAW_CAP_BYTES = 24 * 1024 * 1024
MIN_FREE_BYTES = 40 * 1024**3
REPORT_MAX_BYTES = 64 * 1024


class HourlySourceCanaryError(ValueError):
    pass


def design() -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "ONE_HOURLY_ANCHOR_DESIGN_ZERO_REQUESTS",
        "scope": {
            "symbol": "SPY", "date_et": DATE_ET, "right": "both",
            "expiration": "*", "interval": "1h", "start_time": "09:30:00",
            "end_time": "16:00:00", "max_dte": MAX_DTE,
            "strike_range": 2,
        },
        "method_cap": 1, "retries_permitted": False,
        "cross_year_fallback": False, "provider_requests": 0,
        "source_accepted": False, "simulation_authorized": False,
        "paper_authorized": False, "live_authorized": False,
    }
    body["design_fingerprint"] = _fingerprint(body)
    return body


def _source_summary(response: ThetaDataResponse) -> dict[str, Any]:
    """Describe ALL rows, including extra DTE, without excluding anything."""
    rights: Counter[str] = Counter()
    dte_outside = 0
    invalid_expirations = 0
    invalid_clocks = 0
    unique_clocks: set[str] = set()
    missing = 0
    for row in response.rows:
        rights[str(row.get("right", "MISSING")).upper()] += 1
        if not {"symbol", "expiration", "strike", "right", "timestamp",
                "bid", "ask", "bid_size", "ask_size"}.issubset(row):
            missing += 1
        try:
            expiry = date.fromisoformat(str(row["expiration"])[:10])
            dte = (expiry - date.fromisoformat(DATE_ET)).days
            if not (0 <= dte <= MAX_DTE):
                dte_outside += 1
        except (KeyError, TypeError, ValueError):
            invalid_expirations += 1
        try:
            stamp = datetime.fromisoformat(
                str(row["timestamp"]).replace("Z", "+00:00")
            )
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                invalid_clocks += 1
            else:
                unique_clocks.add(stamp.isoformat())
        except (KeyError, TypeError, ValueError):
            invalid_clocks += 1
    return {
        "rows": len(response.rows),
        "rights": dict(sorted(rights.items())),
        "out_of_requested_dte_rows": dte_outside,
        "invalid_expiration_rows": invalid_expirations,
        "missing_required_quote_fields": missing,
        "invalid_or_naive_timestamps": invalid_clocks,
        "unique_reported_quote_timestamps": len(unique_clocks),
        "observed_quote_time_min": min(unique_clocks, default=None),
        "observed_quote_time_max": max(unique_clocks, default=None),
        "hours_of_interval_verified": False,
        "decision_time_quote_verified": False,
        "source_accepted": False,
    }


def run_one_hourly_source_canary(
    settings: AtlasSettings, *,
    reader: Callable[..., ThetaDataResponse] = option_history_hourly_quote_surface,
    authorize_one_hourly_quote: bool = False,
    confirm_thetadata_standard: bool = False,
    acknowledge_one_quote_method_call: bool = False,
) -> dict[str, Any]:
    if not (authorize_one_hourly_quote is True
            and confirm_thetadata_standard is True
            and acknowledge_one_quote_method_call is True):
        raise HourlySourceCanaryError("ONE_HOURLY_PROVIDER_READ_NOT_AUTHORIZED")
    settings.assert_external_storage_binding("options")
    root = settings.resolved_path("data/options")
    if not root.is_dir() or shutil.disk_usage(root).free < MIN_FREE_BYTES:
        raise HourlySourceCanaryError("SECONDARY_STORAGE_HEADROOM_UNQUALIFIED")

    planned = design()
    folder = settings.resolved_path(
        OUTPUT_REL + "/" + planned["design_fingerprint"][:16]
        + "/" + uuid4().hex
    )
    folder.mkdir(parents=True, exist_ok=False)
    atomic_write_text(
        folder / "attempt.json",
        json.dumps({
            "contract": CONTRACT, "request": planned["scope"],
            "design_fingerprint": planned["design_fingerprint"],
            "attempt_reserved": True, "attempt_count_cap": 1,
            "no_retry": True,
        }, sort_keys=True, indent=2) + "\n",
        fsync=True,
    )
    report: dict[str, Any] = {
        "contract": CONTRACT,
        "design_fingerprint": planned["design_fingerprint"],
        "status": "HOURLY_SOURCE_DIAGNOSTIC_NO_PROMOTION",
        "requested": planned["scope"],
        "requests_attempted": 1, "request_cap": 1,
        "original_network_body_retained": False,
        "sdk_normalized_response_retained": False,
        "source_accepted": False, "historical_replay_authority": False,
        "historical_fill_authority": False,
        "protected_outcomes_read": 0, "broker_requests": 0,
        "paper_authority": False, "live_authority": False,
        "full_acquisition_authorized": False,
    }

    try:
        response = reader(
            symbol="SPY", date_et=DATE_ET, right="both",
            max_dte=MAX_DTE, strike_range=2,
        )
    except ThetaDataError as exc:
        report["provider_result"] = "METHOD_TRANSPORT_OR_ENTITLEMENT_ERROR"
        report["provider_error_type"] = type(exc).__name__
        report["provider_http_status"] = exc.http_status
    else:
        if not isinstance(response, ThetaDataResponse):
            raise HourlySourceCanaryError("PROVIDER_RESPONSE_TYPE_CHANGED")
        if (response.transport != TRANSPORT
                or response.library_version != TARGET_LIBRARY_VERSION
                or response.evidence_encoding != EVIDENCE_ENCODING
                or not isinstance(response.provider_environment_fingerprint, str)
                or len(response.provider_environment_fingerprint) != 64):
            raise HourlySourceCanaryError("PROVIDER_PROVENANCE_CHANGED")
        if (response.response_bytes != len(response.raw_body)
                or len(response.raw_body) > RAW_CAP_BYTES
                or response.raw_body != (
                    json.dumps(list(response.rows), sort_keys=True,
                               separators=(",", ":"), ensure_ascii=False,
                               allow_nan=False) + "\n"
                ).encode("utf-8")):
            raise HourlySourceCanaryError("PROVIDER_CANONICAL_SOURCE_OR_SIZE_CHANGED")
        if response.explicit_no_data and response.rows:
            raise HourlySourceCanaryError("CONTRADICTORY_NO_DATA")
        receipt = _persist_raw(
            folder, label="hourly_quote", response=response,
            query=planned["scope"],
            plan_fingerprint=planned["design_fingerprint"],
        )
        report["sdk_normalized_response_retained"] = True
        report["sdk_normalized_sha256"] = hashlib.sha256(response.raw_body).hexdigest()
        report["receipt_path"] = receipt["receipt_path"]
        report["source_bytes"] = len(response.raw_body)
        report["gzip_9_size_bytes"] = len(gzip.compress(response.raw_body, compresslevel=9))
        report["elapsed_seconds"] = response.elapsed_seconds
        report["source_diagnostics"] = _source_summary(response)
        if response.explicit_no_data:
            report["provider_result"] = "EXPLICIT_NO_HOURLY_DATA"
        elif not response.rows:
            report["provider_result"] = "EMPTY_WITHOUT_EXPLICIT_NO_DATA"
        elif (report["source_diagnostics"]["out_of_requested_dte_rows"]
              or report["source_diagnostics"]["invalid_expiration_rows"]):
            report["provider_result"] = "OBSERVED_HOURLY_DTE_SCOPE_DISCREPANCY"
        elif (report["source_diagnostics"]["missing_required_quote_fields"]
              or report["source_diagnostics"]["invalid_or_naive_timestamps"]):
            report["provider_result"] = "OBSERVED_HOURLY_SCHEMA_OR_CLOCK_UNQUALIFIED"
        else:
            report["provider_result"] = "OBSERVED_HOURLY_ROWS_SOURCE_DIAGNOSTIC"

    report["report_fingerprint"] = _fingerprint(report)
    serialized = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if len(serialized.encode("utf-8")) > REPORT_MAX_BYTES:
        raise HourlySourceCanaryError("HOURLY_REPORT_SIZE_CAP")
    target = folder / "summary.json"
    atomic_write_text(target, serialized, fsync=True)
    report["report_path"] = str(target)
    return report
