from __future__ import annotations

"""Offline inspection of the single saved ThetaData 2025 SPY quote canary.

No network calls, broker access, retries, option outcomes or trading authority.
Only the already-retained SDK-normalized response and its SHA-bound receipt.
"""

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_standard_canary_v1 import (
    OUTPUT_DIR, CONTRACT as ORIGINAL_CONTRACT, canary_design,
)
from packages.data.options_native_spy_thetadata_quote_qualification_v1 import (
    RAW_RESPONSE_CAP, REQUIRED_FIELDS, analyze_pilot_quote_surface,
)
from packages.providers.thetadata.client import ThetaDataResponse, _canonical_bytes
from packages.core.atomic_io import atomic_write_text

RETAINED_REL = (
    OUTPUT_DIR + "/a38cc7e30aa3b169/"
    "74ba3957780c4a9a88de056bd92ec72c/summary.json"
)
EXPECTED_DESIGN = "a38cc7e30aa3b169c06df91c469a60111b2c74fe0a96a93df211e3a73b7b4959"
KNOWN_CLOCK_FIELDS = ("timestamp", "created", "last_trade", "time")
SAFE_REASONS = (
    "QUOTE_REQUIRED_FIELDS_MISSING", "FUTURE_OR_WRONG_SESSION_QUOTE",
    "UNQUALIFIED_NAIVE_QUOTE_CLOCK", "INVALID_QUOTE_TIMESTAMP",
    "CROSSED_QUOTE", "DUPLICATE_EXACT_CONTRACT_RIGHT",
    "UNEXPECTED_OPTION_ROOT", "UNEXPECTED_OPTION_RIGHT",
    "OUT_OF_SCOPE_OPTION_EXPIRATION", "INVALID_OPTION_EXPIRATION",
    "QUOTE_RAW_RECEIPT_OR_SIZE_CHANGED", "UNQUALIFIED_PROVIDER_STATUS",
)


def _object(path: Path, cap: int) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= cap:
        raise ValueError("PINNED_FILE_UNAVAILABLE_OR_OVERSIZE")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("PINNED_JSON_NOT_OBJECT")
    return value


def audit_saved_quote(path: Path, *, write: bool = False) -> dict:
    """Reconstruct the rejection from saved bytes, never request market data."""
    design = canary_design()
    if design["design_fingerprint"] != EXPECTED_DESIGN:
        raise ValueError("FROZEN_SOURCE_DESIGN_DRIFT")
    summary = _object(path, 65536)
    anchor = design["selected_anchor"]
    if (
        summary.get("contract") != ORIGINAL_CONTRACT
        or summary.get("provider_result") != "SOURCE_SCHEMA_OR_CLOCK_UNQUALIFIED"
        or summary.get("source_accepted") is not False
        or summary.get("requests_attempted") != 1
        or summary.get("request_cap") != 1
        or summary.get("requested_date_et") != "20250609"
        or summary.get("requested_right") != "both"
        or summary.get("design_fingerprint") != EXPECTED_DESIGN
        or summary.get("source_query_fingerprint") != anchor["query_fingerprint"]
    ):
        raise ValueError("ORIGINAL_CANARY_SCOPE_OR_STATUS_DRIFT")
    if summary.get("report_fingerprint") != _fingerprint({
        k: v for k,v in summary.items() if k != "report_fingerprint"
    }):
        raise ValueError("ORIGINAL_CANARY_FINGERPRINT_DRIFT")
    folder = path.parent / "raw"
    rpath = folder / "single_quote.receipt.json"
    body = folder / "single_quote.json"
    receipt = _object(rpath, 16384)
    if (
        summary.get("source_receipt_path") != str(rpath)
        or receipt.get("body_path") != str(body)
        or receipt.get("query") != anchor
        or receipt.get("plan_fingerprint") != design["pilot_plan_fingerprint"]
        or receipt.get("body_sha256") != summary.get("sdk_normalized_response_sha256")
    ):
        raise ValueError("ORIGINAL_PROVIDER_RECEIPT_BINDING_DRIFT")
    if body.is_symlink() or not body.is_file() or not 0 < body.stat().st_size <= RAW_RESPONSE_CAP:
        raise ValueError("ORIGINAL_PROVIDER_BODY_UNAVAILABLE")
    raw = body.read_bytes()
    if (
        len(raw) != receipt.get("body_bytes")
        or hashlib.sha256(raw).hexdigest() != receipt.get("body_sha256")
    ):
        raise ValueError("ORIGINAL_PROVIDER_BODY_SHA_DRIFT")
    rows = json.loads(raw)
    if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
        raise ValueError("ORIGINAL_PROVIDER_ROWS_INVALID")
    if _canonical_bytes(rows) != raw:
        raise ValueError("ORIGINAL_PROVIDER_CANONICAL_BYTES_DRIFT")
    response = ThetaDataResponse(
        http_status=receipt["http_status"], rows=tuple(rows),
        headers={}, response_bytes=len(raw), elapsed_seconds=0,
        raw_body=raw, transport=receipt["provider_transport"],
        library_version=receipt["provider_library_version"],
        provider_environment_fingerprint=receipt["provider_environment_fingerprint"],
        evidence_encoding=receipt["evidence_encoding"],
        explicit_no_data=receipt["explicit_no_data"],
    )
    try:
        analyze_pilot_quote_surface(response, anchor)
    except (ValueError, TypeError, KeyError) as exc:
        error_text = str(exc)
        if error_text.startswith("ThetaData response missing fields:"):
            reason = "QUOTE_REQUIRED_FIELDS_MISSING"
        else:
            reason = next((x for x in SAFE_REASONS if error_text.startswith(x)),
                          "OTHER_VALIDATOR_REJECTION")
        replay = "REPRODUCED"
    else:
        reason, replay = "NONE", "VALIDATOR_CHANGED_NO_PROMOTION"
    columns = sorted(set().union(*(x.keys() for x in rows))) if rows else []
    times = {}
    for field in KNOWN_CLOCK_FIELDS:
        values = []
        for row in rows:
            if field not in row or row[field] is None:
                continue
            value = row[field]
            if isinstance(value, str) and len(value) < 65:
                try:
                    datetime.fromisoformat(value.replace("Z","+00:00"))
                    values.append(value)
                except ValueError:
                    values.append("NON_ISO_VALUE")
            else:
                values.append("NON_TEXT_VALUE")
            if len(values) == 3:
                break
        times[field] = {"count": sum(field in x and x[field] is not None for x in rows),
                        "first_three": values}
    report = {
        "contract": "atlas-retained-standard-spy-quote-schema-audit-v1",
        "status": "SOURCE_ONLY_DIAGNOSTIC_NOT_ACCEPTED",
        "original_report_fingerprint": summary["report_fingerprint"],
        "original_sha256": receipt["body_sha256"],
        "original_rejection_type": summary.get("source_failure_type"),
        "replay": replay, "replay_reason": reason,
        "rows": len(rows), "columns": columns[:64],
        "additional_column_count": max(0, len(columns)-64),
        "missing_required": sorted(set(REQUIRED_FIELDS)-set(columns)),
        "rights": dict(sorted(Counter(str(r.get("right","MISSING")).upper()
                                       for r in rows).items())),
        "clock_columns": times, "provider_requests": 0,
        "protected_outcomes_read": 0, "source_accepted": False,
        "additional_paid_requests_authorized": False,
    }
    report["fingerprint"] = _fingerprint(report)
    if write:
        output = path.parent / ("offline_schema_review_v1_" +
                                report["fingerprint"][:16] + ".json")
        data = json.dumps(report,indent=2,sort_keys=True,allow_nan=False) + "\n"
        if output.is_symlink() or (output.exists() and output.read_text(encoding="utf-8") != data):
            raise ValueError("OFFLINE_AUDIT_OUTPUT_CONFLICT")
        if not output.exists():
            atomic_write_text(output, data, fsync=True)
        report["saved_report"] = str(output)
    return report


def main() -> int:
    print("ATLAS STANDARD 2025 RETAINED QUOTE SCHEMA AUDIT V1",flush=True)
    print("  ZERO provider calls, retries, option outcomes or data acquisitions.",flush=True)
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        report = audit_saved_quote(settings.resolved_path(RETAINED_REL),write=True)
        print(f"  source_sha256={report['original_sha256']} rows={report['rows']}",flush=True)
        print(f"  replay={report['replay']} reason={report['replay_reason']}",flush=True)
        print(f"  columns={report['columns']}",flush=True)
        print(f"  missing_required={report['missing_required']}",flush=True)
        print(f"  rights={report['rights']}",flush=True)
        for name,item in report["clock_columns"].items():
            if item["count"]:
                print(f"  {name}_count={item['count']} examples={item['first_three']}",flush=True)
        print(f"  retained_audit={report['saved_report']}",flush=True)
        print("  COMPLETE status=OFFLINE_SOURCE_ONLY provider_requests=0 source_accepted=False",
              flush=True)
        return 0
    except Exception as exc:
        print(f"  STOP category={type(exc).__name__} provider_requests=0",flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
