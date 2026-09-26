from __future__ import annotations

"""Offline, metadata-only inspector for the frozen 2025 candidate chain pilot.

Never imports provider transport, resolves credentials, reads remote APIs, deletes
quarantined evidence or edits the original plan/cache/checkpoint. Raw response
bodies are read only to verify checksums and extract a small allowlisted status.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CONTRACT, CandidateChainCacheError, _fingerprint, _paths, _valid_receipt, _no_data_path,
)
from scripts.run_marketdata_candidate_2025_pilot import (
    PLAN_FINGERPRINT, preflight,
)

SAFE_PAYLOAD_STATUS = frozenset({"ok", "no_data", "error", "not_found"})
SAFE_FAILURE = frozenset({
    "provider response arrays inconsistent",
    "unexpected provider response status",
    "historical chain empty or oversized",
    "required chain identity fields missing",
    "chain rows violate ticker, expiry, strike or identity envelope",
    "required provider credit headers missing",
    "invalid provider credit headers",
})


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _verified_attempt(path: Path, request: dict[str, Any], plan_fingerprint: str) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        fingerprint = value.pop("intent_fingerprint")
        return (
            fingerprint == _fingerprint(value)
            and value.get("contract") == CONTRACT
            and value.get("request_identity") == request["request_identity"]
            and value.get("endpoint") == request["endpoint"]
            and value.get("params") == request["params"]
            and value.get("plan_fingerprint") == plan_fingerprint
            and value.get("automatic_retry_permitted") is False
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _inspect_request(settings: Any, request: dict[str, Any],
                     plan_fingerprint: str) -> dict[str, Any]:
    paths = _paths(settings, request["request_identity"])
    result: dict[str, Any] = {
        "ticker": request["ticker"],
        "snapshot_date": request["params"]["date"],
        "expiration": request["params"]["expiration"],
        "strike": request["params"]["strike"],
        "request_identity": request["request_identity"],
        "status": "PENDING_NEVER_ATTEMPTED",
    }
    exists = {name: getattr(paths, name).exists()
              for name in ("body", "receipt", "attempt", "recovery")}
    if not exists["body"] and not exists["receipt"]:
        if exists["attempt"]:
            result["status"] = "UNRESOLVED_ATTEMPT_PRESERVE"
            result["attempt_verified"] = _verified_attempt(
                paths.attempt, request, plan_fingerprint,
            )
        return result
    if not exists["body"] or not exists["receipt"]:
        result["status"] = "INCOMPLETE_CACHE_PAIR_PRESERVE"
        return result
    if paths.body.is_symlink() or paths.receipt.is_symlink():
        result["status"] = "UNEXPECTED_FILE_LINK_PRESERVE"
        return result

    try:
        receipt = json.loads(paths.receipt.read_text(encoding="utf-8"))
        raw = paths.body.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        recorded = dict(receipt)
        receipt_hash = recorded.pop("receipt_fingerprint")
    except (OSError, ValueError, TypeError, KeyError):
        result["status"] = "UNREADABLE_EVIDENCE_PRESERVE"
        return result

    if (
        not isinstance(payload, dict)
        or receipt.get("contract") != CONTRACT
        or receipt.get("request_identity") != request["request_identity"]
        or receipt.get("endpoint") != request["endpoint"]
        or receipt.get("params") != request["params"]
        or receipt.get("body_sha256") != _sha(raw)
        or receipt.get("body_bytes") != len(raw)
        or receipt_hash != _fingerprint(recorded)
        or receipt.get("raw_http_body_exact") is not True
    ):
        result["status"] = "EVIDENCE_INTEGRITY_MISMATCH_PRESERVE"
        return result

    if receipt.get("status") == "COMPLETE" or exists["recovery"]:
        try:
            verified = _valid_receipt(paths, request)
        except CandidateChainCacheError:
            result["status"] = "RECEIPT_VALIDATION_FAILED_PRESERVE"
            return result
        if verified is None:
            result["status"] = "RECEIPT_VALIDATION_FAILED_PRESERVE"
            return result
        result.update({
            "status": "REUSED_VERIFIED",
            "raw_bytes": len(raw),
            "rows": verified.get("row_count"),
            "offline_recovery": bool(verified.get("offline_recovery", False)),
        })
        return result

    if receipt.get("status") != "QUARANTINED":
        result["status"] = "UNKNOWN_RECEIPT_STATUS_PRESERVE"
        return result
    if _no_data_path(paths).exists():
        try:
            verified = _valid_receipt(paths, request)
        except CandidateChainCacheError:
            result["status"] = "NO_DATA_PROOF_INVALID_PRESERVE"
            return result
        if verified is None or verified.get("status") != "VERIFIED_NO_DATA":
            result["status"] = "NO_DATA_PROOF_INVALID_PRESERVE"
            return result
        result.update({
            "status": "SOURCE_NO_DATA_VERIFIED",
            "raw_bytes": len(raw),
            "body_sha256": verified["body_sha256"],
            "no_data_proof": verified["no_data_proof"],
        })
        return result

    status = payload.get("s")
    rates = receipt.get("rate_limit")
    if not isinstance(rates, dict):
        rates = {}
    failure = receipt.get("failure")
    result.update({
        "status": "QUARANTINED_VERIFIED_REVIEW_REQUIRED",
        "http_status": receipt.get("http_status")
                       if type(receipt.get("http_status")) is int else None,
        "payload_status": status if isinstance(status, str) and status in SAFE_PAYLOAD_STATUS else "OTHER_OR_ABSENT",
        "row_count_recorded": receipt.get("row_count")
                              if type(receipt.get("row_count")) is int else None,
        "raw_bytes": len(raw),
        "body_sha256": _sha(raw),
        "failure_category": failure if isinstance(failure, str) and failure in SAFE_FAILURE else "OTHER",
        "credit_consumed_in_response_headers": rates.get("consumed")
                    if type(rates.get("consumed")) is int else None,
        "credits_remaining_in_response_headers": rates.get("remaining")
                    if type(rates.get("remaining")) is int else None,
        "attempt_verified": _verified_attempt(
            paths.attempt, request, plan_fingerprint,
        ),
        "has_error_text": any(
            isinstance(payload.get(k), str) and bool(payload[k])
            for k in ("errmsg", "error", "message")
        ),
    })
    return result


def inspect_pilot(settings: Any, plan: dict[str, Any]) -> dict[str, Any]:
    rows = [
        _inspect_request(settings, item, plan["plan_fingerprint"])
        for item in plan["requests"]
    ]
    statuses = [item["status"] for item in rows]
    checkpoint_path = settings.resolved_path(
        "data/options/manifests/"
        f"marketdata_candidate_chain_cache_v1_{PLAN_FINGERPRINT[:16]}.json"
    )
    checkpoint: dict[str, Any] | None = None
    if checkpoint_path.is_file() and not checkpoint_path.is_symlink():
        try:
            value = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            signature = value.pop("report_fingerprint")
            if signature == _fingerprint(value) and value.get("plan_fingerprint") == PLAN_FINGERPRINT:
                checkpoint = {
                    "status": value.get("status"),
                    "provider_attempts_this_saved_run": value.get("provider_reads"),
                    "new_complete_this_saved_run": value.get("new_complete"),
                    "observed_credits_consumed_this_saved_run":
                        value.get("observed_credits_consumed_this_run"),
                    "credit_consumption_uncertain_in_saved_run":
                        value.get("credits_unknown_after_failed_request"),
                    "last_observed_provider_credits_remaining":
                        value.get("last_observed_provider_credits_remaining"),
                }
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return {
        "contract": "atlas-marketdata-candidate-2025-offline-inspection-v1",
        "plan_fingerprint": plan["plan_fingerprint"],
        "verified_complete": statuses.count("REUSED_VERIFIED"),
        "verified_no_data": statuses.count("SOURCE_NO_DATA_VERIFIED"),
        "verified_quarantined": statuses.count("QUARANTINED_VERIFIED_REVIEW_REQUIRED"),
        "never_attempted": statuses.count("PENDING_NEVER_ATTEMPTED"),
        "requires_review": any(s not in {"REUSED_VERIFIED", "SOURCE_NO_DATA_VERIFIED", "PENDING_NEVER_ATTEMPTED"} for s in statuses),
        "requests": rows,
        "latest_saved_run_observation_only": checkpoint,
        "provider_reads_this_inspection": 0,
        "provider_credits_spent_this_inspection": 0,
        "no_recovery_or_retry_authority": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only physical receipt/metadata inspection of the frozen 2025 pilot; zero provider calls."
    )
    parser.parse_args(argv)
    try:
        settings = load_settings(ROOT, "development")
        plan, source = preflight(settings)
        result = inspect_pilot(settings, plan)
    except (OSError, ValueError, CandidateChainCacheError) as exc:
        print(f"OFFLINE INSPECTION BLOCKED: {type(exc).__name__}: {exc}", flush=True)
        return 3

    print("ATLAS MarketData Accepted 2025 Pilot — Offline Receipt Inspection")
    print(f"  exact source verified at: {source}")
    print(f"  plan fingerprint: {result['plan_fingerprint']}")
    for index, row in enumerate(result["requests"], 1):
        print(
            f"  {index:2d}/12 {row['ticker']:<5} {row['status']} "
            f"snapshot={row['snapshot_date']} expiry={row['expiration']} "
            f"strike={row['strike']}"
        )
        if row["status"] == "QUARANTINED_VERIFIED_REVIEW_REQUIRED":
            for key in (
                "request_identity", "http_status", "payload_status",
                "row_count_recorded", "raw_bytes", "body_sha256",
                "failure_category", "credit_consumed_in_response_headers",
                "credits_remaining_in_response_headers", "attempt_verified",
                "has_error_text",
            ):
                print(f"      {key}: {row[key]}")
        elif row["status"] == "SOURCE_NO_DATA_VERIFIED":
            print(f"      exact-query no-data proof: {row['no_data_proof']}")
        elif row["status"] not in {"REUSED_VERIFIED", "PENDING_NEVER_ATTEMPTED"}:
            print(f"      request_identity: {row['request_identity']}")
            if "attempt_verified" in row:
                print(f"      attempt_verified: {row['attempt_verified']}")
    print(
        f"  totals: complete={result['verified_complete']} "
        f"exact_query_no_data={result['verified_no_data']} "
        f"quarantined={result['verified_quarantined']} "
        f"never_attempted={result['never_attempted']} "
        f"review_required={result['requires_review']}"
    )
    print("  latest checkpoint is observation-only; physical receipts determine current status.")
    print("  saved run metadata: " + json.dumps(
        result["latest_saved_run_observation_only"], sort_keys=True,
    ))
    print("  provider reads: 0; credits spent: 0; raw payload/error message not displayed.")
    print("  preserve originals; no recovery, deletion, plan change or paid retry authorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
