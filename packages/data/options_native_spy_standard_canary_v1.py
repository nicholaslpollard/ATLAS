from __future__ import annotations

"""One bounded 2025 SPY 10:00 CALL+PUT quote canary; never historical performance.

Reuses ONE of the frozen 24 options-native SPY source anchors; no changed
pilot plan, no 2018-first entitlement assumption, no repeated or fallback
provider requests. The output is source diagnostics, NOT signal authority.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_thetadata_quote_qualification_v1 import (
    OUTPUT_REL, RAW_RESPONSE_CAP, QUOTE_REQUEST_CAP, PilotQuoteSourceError,
    analyze_pilot_quote_surface, quote_design,
)
from packages.data.thetadata_candidate_surface_qualification_v1 import _persist_raw
from packages.providers.thetadata.client import (
    ThetaDataError, ThetaDataResponse, option_at_time_quote_surface,
)

CONTRACT = "atlas-options-native-spy-standard-single-2025-canary-v1"
SOURCE_ANCHOR = "2025_MIDDLE"
OUTPUT_DIR = OUTPUT_REL + "/standard_2025_one_quote_canary_v1"
REPORT_MAX_BYTES = 64 * 1024


def canary_design() -> dict[str, Any]:
    original = quote_design()
    matches = [x for x in original["quote_source_calls"]
               if x["reason"] == SOURCE_ANCHOR and x["repeat"] is False]
    if len(matches) != 1 or original["quote_method_call_cap"] != QUOTE_REQUEST_CAP:
        raise PilotQuoteSourceError("FROZEN_SINGLE_SOURCE_ANCHOR_CHANGED")
    anchor = matches[0]
    params = anchor["params"]
    if (params.get("symbol") != "SPY" or params.get("right") != "both"
            or params.get("time_of_day") != "10:00:00.000"
            or params.get("max_dte") != 45 or params.get("strike_range") != 2
            or not str(params.get("start_date", "")).startswith("2025")
            or params.get("start_date") != params.get("end_date")):
        raise PilotQuoteSourceError("CANARY_SCOPE_CHANGED")
    body = {
        "contract": CONTRACT, "status": "ONE_ANCHOR_DESIGN_ZERO_READS",
        "source_design_fingerprint": original["design_fingerprint"],
        "pilot_plan_fingerprint": original["plan_fingerprint"],
        "selected_anchor": anchor,
        "maximum_provider_quote_method_calls": 1,
        "repeat_permitted": False,
        "cross_year_fallback_permitted": False,
        "provider_requests": 0, "outcomes_read": 0,
        "protected_outcomes_read": 0, "broker_requests": 0,
        "source_accepted": False, "option_pair_admissible": False,
        "strategy_promotion": False, "historical_replay_authority": False,
        "paid_access_confirmed_by_design": False,
    }
    body["design_fingerprint"] = _fingerprint(body)
    return body


def run_single_canary(
    settings: AtlasSettings, *,
    reader: Callable[..., ThetaDataResponse] = option_at_time_quote_surface,
    authorize_one_standard_quote: bool = False,
    confirm_thetadata_standard: bool = False,
    acknowledge_one_quote_method_call: bool = False,
) -> dict[str, Any]:
    """Fail closed before filesystem or provider reads on incomplete authorization."""
    if not (
        authorize_one_standard_quote is True
        and confirm_thetadata_standard is True
        and acknowledge_one_quote_method_call is True
    ):
        raise PilotQuoteSourceError("ONE_QUOTE_PROVIDER_READ_NOT_AUTHORIZED")
    design = canary_design()
    settings.assert_external_storage_binding("options")
    folder = settings.resolved_path(
        OUTPUT_DIR + "/" + design["design_fingerprint"][:16] + "/" + uuid4().hex
    )
    folder.mkdir(parents=True, exist_ok=False)
    anchor = design["selected_anchor"]
    params = anchor["params"]
    report: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "ONE_QUOTE_SOURCE_DIAGNOSTIC_NOT_ACCEPTED",
        "design_fingerprint": design["design_fingerprint"],
        "source_design_fingerprint": design["source_design_fingerprint"],
        "pilot_plan_fingerprint": design["pilot_plan_fingerprint"],
        "source_anchor_reason": anchor["reason"],
        "source_query_fingerprint": anchor["query_fingerprint"],
        "requested_date_et": params["start_date"],
        "requested_clock_et": params["time_of_day"],
        "requested_right": params["right"],
        "requests_attempted": 1, "request_cap": 1,
        "broker_requests": 0, "outcomes_read": 0,
        "protected_outcomes_read": 0, "source_accepted": False,
        "option_pair_admissible": False, "historical_replay_authority": False,
        "historical_fill_authority": False, "strategy_promotion": False,
        "paper": False, "live": False, "new_acquisition_authorized": False,
        "sdk_normalized_response_bytes_retained": False,
        "original_network_body_retained": False,
    }
    try:
        response = reader(
            symbol="SPY", date_et=params["start_date"],
            time_of_day_et="10:00:00.000",
            right="both", max_dte=45, strike_range=2,
        )
    except ThetaDataError as exc:
        report["provider_result"] = "METHOD_TRANSPORT_OR_ENTITLEMENT_ERROR"
        report["provider_error_type"] = type(exc).__name__
        report["provider_http_status"] = exc.http_status
    else:
        if not isinstance(response, ThetaDataResponse):
            raise PilotQuoteSourceError("CANARY_PROVIDER_RESPONSE_TYPE_CHANGED")
        if (response.response_bytes != len(response.raw_body)
                or not 0 < len(response.raw_body) <= RAW_RESPONSE_CAP):
            raise PilotQuoteSourceError("CANARY_RAW_SIZE_OR_RECEIPT_CHANGED")
        receipt = _persist_raw(
            folder, label="single_quote", response=response,
            query=anchor, plan_fingerprint=design["pilot_plan_fingerprint"],
        )
        report["sdk_normalized_response_bytes_retained"] = True
        report["sdk_normalized_response_sha256"] = receipt["body_sha256"]
        report["source_receipt_path"] = receipt["receipt_path"]
        try:
            diagnosed = analyze_pilot_quote_surface(response, anchor)
        except (PilotQuoteSourceError, ValueError, TypeError) as exc:
            report["provider_result"] = "SOURCE_SCHEMA_OR_CLOCK_UNQUALIFIED"
            report["source_failure_type"] = type(exc).__name__
        else:
            report["provider_result"] = diagnosed.pop("status")
            report["quote_diagnostics"] = diagnosed
    report["report_fingerprint"] = _fingerprint(report)
    text = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if len(text.encode("utf-8")) > REPORT_MAX_BYTES:
        raise PilotQuoteSourceError("CANARY_REPORT_SIZE_CAP")
    target = folder / "summary.json"
    atomic_write_text(target, text, fsync=True)
    report["report_path"] = str(target)
    return report
