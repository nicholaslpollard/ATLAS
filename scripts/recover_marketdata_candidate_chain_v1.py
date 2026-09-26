from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, _fingerprint, _paths, _rows_match_explicit_request,
    _sha256, verify_candidate_plan,
)
from packages.providers.marketdata_app import array_rows


RECOVERY_CONTRACT = "atlas-marketdata-chain-offline-recovery-v1"


def recover(plan_path: Path, request_identity: str, *, authorize: bool = False) -> dict:
    """Offline only. Never edits raw body, original receipt, or attempt marker."""
    plan = verify_candidate_plan(json.loads(plan_path.read_text(encoding="utf-8")))
    matches = [r for r in plan["requests"] if r["request_identity"] == request_identity]
    if len(matches) != 1:
        raise CandidateChainCacheError("request identity absent or duplicated in verified plan")
    request = matches[0]
    paths = _paths(load_settings(PROJECT_ROOT, "development"), request_identity)
    if not all(p.is_file() and not p.is_symlink() for p in (paths.body, paths.receipt, paths.attempt)):
        raise CandidateChainCacheError("exact original raw body, receipt and attempt are required")
    raw = paths.body.read_bytes()
    receipt = json.loads(paths.receipt.read_text(encoding="utf-8"))
    attempt = json.loads(paths.attempt.read_text(encoding="utf-8"))
    original = dict(receipt)
    fingerprint = original.pop("receipt_fingerprint", None)
    if (
        fingerprint != _fingerprint(original)
        or receipt.get("status") != "QUARANTINED"
        or receipt.get("failure") != "chain rows violate ticker, expiry, strike or identity envelope"
        or receipt.get("request_identity") != request_identity
        or receipt.get("endpoint") != request["endpoint"]
        or receipt.get("params") != request["params"]
        or receipt.get("body_sha256") != _sha256(raw)
        or receipt.get("body_bytes") != len(raw)
        or receipt.get("http_status") not in {200, 203}
        or receipt.get("raw_http_body_exact") is not True
        or receipt.get("rate_limit", {}).get("consumed") is None
        or receipt.get("rate_limit", {}).get("remaining") is None
        or attempt.get("request_identity") != request_identity
        or attempt.get("plan_fingerprint") != plan["plan_fingerprint"]
        or attempt.get("automatic_retry_permitted") is not False
    ):
        raise CandidateChainCacheError("original quarantine/attempt evidence mismatch")
    payload = json.loads(raw.decode("utf-8"))
    rows = array_rows(payload)
    if (payload.get("s") != "ok" or not 1 <= len(rows) <= 1000
            or receipt.get("row_count") != len(rows)
            or not _rows_match_explicit_request(rows, request)):
        raise CandidateChainCacheError("saved response fails corrected identity validation")
    proof = {
        "contract": RECOVERY_CONTRACT,
        "status": "RECOVERED_VERIFIED",
        "request_identity": request_identity,
        "plan_fingerprint": plan["plan_fingerprint"],
        "body_sha256": _sha256(raw),
        "original_receipt_fingerprint": fingerprint,
        "row_count": len(rows),
        "provider_calls_performed": 0,
        "additional_credits_consumed": 0,
        "no_execution_price_or_option_pnl_authority": True,
    }
    proof["recovery_fingerprint"] = _fingerprint(proof)
    if paths.recovery.exists():
        if json.loads(paths.recovery.read_text(encoding="utf-8")) != proof:
            raise CandidateChainCacheError("existing recovery proof differs; never overwrite")
        return {**proof, "action": "VERIFIED_EXISTING"}
    if authorize:
        atomic_write_text(paths.recovery, json.dumps(proof, sort_keys=True, indent=2) + "\n")
        return {**proof, "action": "RECOVERED_OFFLINE"}
    return {**proof, "action": "PREVIEW_ONLY"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Zero-network, immutable MarketData chain quarantine recovery")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--request-identity", required=True)
    parser.add_argument("--authorize-offline-recovery", action="store_true")
    args = parser.parse_args()
    try:
        result = recover(args.plan, args.request_identity, authorize=args.authorize_offline_recovery)
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        return 0
    except (OSError, ValueError, TypeError, CandidateChainCacheError) as exc:
        print(f"OFFLINE RECOVERY BLOCKED: {type(exc).__name__}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
