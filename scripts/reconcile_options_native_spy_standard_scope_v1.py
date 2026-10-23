from __future__ import annotations

"""Zero-provider reconciliation of the *already-retained* 2025 SPY quote.

The 264-row SDK-normalized original response remains immutable, and its
OUT_OF_SCOPE_OPTION_EXPIRATION rejection remains binding. The explicit 0–45
DTE view is a nonpromotable diagnostic, not a disguised successful GET.
"""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_quote_scope_reconciliation_v1 import (
    inspect_explicit_dte_projection,
)
from packages.data.options_native_spy_standard_canary_v1 import canary_design
from packages.providers.thetadata.client import ThetaDataResponse, _canonical_bytes
from scripts.review_options_native_spy_standard_expiration_scope_v1 import (
    RETAINED_REL, PINNED_BODY_SHA, inspect_saved_expiration_scope,
)

EXPECTED_DTE_REPORT_PREFIX = "f8194f6d69624e7c"
CONTRACT = "atlas-spy-standard-2025-archived-quote-explicit-dte-diagnostic-v1"


def inspect_saved_projected_pairs(report_path: Path, *, write_report: bool = False) -> dict:
    prior = inspect_saved_expiration_scope(report_path, write_report=False)
    if (
        prior["fingerprint"][:16] != EXPECTED_DTE_REPORT_PREFIX
        or prior["source_sha256"] != PINNED_BODY_SHA
        or prior["raw_rows"] != 264
        or prior["expiration_buckets"] != {
            "over_max_dte": 144, "within_requested_dte": 120
        }
        or prior["distinct_expiration_count"] != 33
        or prior["other_schema_and_clock_anomalies"] != {}
        or prior["provider_requests"] != 0
        or prior["source_accepted"] is not False
    ):
        raise ValueError("ACCEPTED_ORIGINAL_EXPIRATION_INVENTORY_DRIFT")
    design = canary_design()
    raw_dir = report_path.parent / "raw"
    body_path = raw_dir / "single_quote.json"
    receipt_path = raw_dir / "single_quote.receipt.json"
    if (
        body_path.is_symlink() or not body_path.is_file()
        or receipt_path.is_symlink() or not receipt_path.is_file()
    ):
        raise ValueError("ORIGINAL_QUOTE_OR_RECEIPT_MISSING")
    raw = body_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINNED_BODY_SHA:
        raise ValueError("ORIGINAL_PROVIDER_BODY_SHA_CHANGED")
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) != 264 or any(
        not isinstance(x, dict) for x in rows
    ) or _canonical_bytes(rows) != raw:
        raise ValueError("ORIGINAL_PROVIDER_CANONICAL_ROWS_CHANGED")
    receipt = json.loads(receipt_path.read_bytes())
    if (
        receipt.get("body_sha256") != PINNED_BODY_SHA
        or receipt.get("body_bytes") != len(raw)
        or receipt.get("body_path") != str(body_path)
        or receipt.get("query") != design["selected_anchor"]
        or receipt.get("plan_fingerprint") != design["pilot_plan_fingerprint"]
    ):
        raise ValueError("ORIGINAL_PROVIDER_RECEIPT_QUERY_DRIFT")
    source = ThetaDataResponse(
        http_status=receipt["http_status"], rows=tuple(rows),
        headers={}, response_bytes=len(raw), elapsed_seconds=0,
        raw_body=raw, transport=receipt["provider_transport"],
        library_version=receipt["provider_library_version"],
        provider_environment_fingerprint=receipt["provider_environment_fingerprint"],
        evidence_encoding=receipt["evidence_encoding"],
        explicit_no_data=receipt["explicit_no_data"],
    )
    diagnostic = inspect_explicit_dte_projection(source, design["selected_anchor"])
    if (
        diagnostic["full_original_rows"] != 264
        or diagnostic["within_requested_dte_rows"] != 120
        or diagnostic["beyond_requested_dte_rows"] != 144
        or diagnostic["within_requested_dte_calls"] != 60
        or diagnostic["within_requested_dte_puts"] != 60
        or diagnostic["out_of_scope_calls"] != 72
        or diagnostic["out_of_scope_puts"] != 72
        or diagnostic["projected_validator_diagnostic"]["common_30_45_dte_pairs"] != 8
        or diagnostic["source_accepted"] is not False
    ):
        raise ValueError("SAVED_QUOTE_PROJECTION_EXPECTED_COUNTS_CHANGED")
    result = {
        "contract": CONTRACT,
        "status": "OFFLINE_DECLARED_PROJECTION_NOT_PROVIDER_SOURCE_ACCEPTANCE",
        "original_saved_expiration_report_fingerprint": prior["fingerprint"],
        "original_canary_design_fingerprint": design["design_fingerprint"],
        "original_call_source_query_fingerprint": design["selected_anchor"]["query_fingerprint"],
        **diagnostic,
        "original_provider_response_authority": False,
        "independent_expiration_filter_was_performed": True,
        "out_of_scope_quotes_preserved_in_original_receipt": True,
        "greeks_oi_dividend_rates_identity_qualified": False,
        "new_acquisition_authorized": False,
        "note": "Derived 0..45DTE screening is a RESEARCH-only diagnostic. "
                "ThetaData SDK or server max_dte behavior remains unknown; "
                "the original full returned source violates its request.",
    }
    result["fingerprint"] = _fingerprint(result)
    if write_report:
        path = report_path.parent / (
            "offline_declared_45d_view_v1_" + result["fingerprint"][:16] + ".json"
        )
        blob = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if path.is_symlink() or (path.exists()
                                and path.read_text(encoding="utf-8") != blob):
            raise ValueError("SCOPED_AUDIT_REPORT_TARGET_CONFLICT")
        if not path.exists():
            atomic_write_text(path, blob, fsync=True)
        result["saved_report"] = str(path)
    return result


def main() -> int:
    print("ATLAS SPY 2025 DECLARED 45-DTE QUOTE SCREEN — OFFLINE V1", flush=True)
    print("  Original quote and receipt unchanged; zero provider/broker/outcome reads.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        report = inspect_saved_projected_pairs(
            settings.resolved_path(RETAINED_REL), write_report=True
        )
        print(f"  original_sha256={report['full_original_sdk_sha256']} "
              f"original_rows={report['full_original_rows']}", flush=True)
        print(f"  requested_0_to_45_dte_rows={report['within_requested_dte_rows']} "
              f"beyond_45_dte_rows={report['beyond_requested_dte_rows']}", flush=True)
        print(f"  inside_C={report['within_requested_dte_calls']} "
              f"inside_P={report['within_requested_dte_puts']} "
              f"excluded_C={report['out_of_scope_calls']} "
              f"excluded_P={report['out_of_scope_puts']}", flush=True)
        diag = report["projected_validator_diagnostic"]
        print(f"  original_30_45_dte_common_pairs={diag['common_30_45_dte_pairs']} "
              f"clock_liquidity_qualified_pairs={diag['clock_qualified_common_pairs']}",
              flush=True)
        print(f"  projection_sha256={report['explicit_projection_sha256']} "
              f"screen_status={diag['status']}", flush=True)
        print("  source_accepted=False provider_max_dte_semantics_unresolved=True", flush=True)
        print("  retained_report=" + report["saved_report"], flush=True)
        print("  COMPLETE status=OFFLINE_DTE_PROJECTION_NO_TRADING_AUTHORITY "
              "provider_requests=0 protected_outcomes_read=0", flush=True)
        return 0
    except Exception as exc:
        print(f"  STOP type={type(exc).__name__}; "
              "no new provider calls or original-source modifications", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
