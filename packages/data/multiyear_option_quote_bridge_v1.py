from __future__ import annotations

"""Source-only bridge: accepted stock/news cases -> PIT structural OCC -> quote demand.

Read only D:-bound original signed case/chain evidence; no provider or price
request, future option liquidity, simulated fill or result. The existing quote
cache owns separate, explicitly authorized missing-series GETs.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    _fingerprint, _paths, _valid_receipt,
)
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object
from packages.data.multiyear_chain_campaign_v1 import (
    DEMAND_FP, OVERLAP_FP, read_accepted_source,
)
from packages.providers.marketdata_app.client import array_rows

CONTRACT = "atlas-multiyear-selected-pit-option-quote-bridge-v1"
NATIVE_REL = (
    "data/research/evidence/"
    "multiyear_native_raw_stock_open_v1_0f42e41403183724.json"
)
CROSSWALK_REL = (
    "data/options/manifests/"
    "multiyear_original_option_source_crosswalk_v1_8fe80351a13f328a.json"
)
OUTPUT_REL = "data/options/manifests/multiyear_pit_selected_option_quotes_v1"
NATIVE_FP = "e0b29569ece159208cfa0303b7d94b596b6e08299a509367d0b0538939ae8e64"
CROSSWALK_FP = "45bb0490a38d2b0b5657115fc3dbc3e973dee2328da459c4ce427d92dd8ce682"
OCC = re.compile(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$")
RIGHTS = {"call": "C", "put": "P"}
MAX_ROWS = 14902


class MultiYearQuoteBridgeError(ValueError):
    pass


def _signed(settings: AtlasSettings, rel: str, field: str, expected: str) -> dict[str, Any]:
    value = _read_object(settings.resolved_path(rel))
    body = dict(value)
    if body.pop(field, None) != expected or _fingerprint(body) != expected:
        raise MultiYearQuoteBridgeError("accepted native/crosswalk evidence signature changed")
    return value


def read_accepted_cases(
    settings: AtlasSettings,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    settings.assert_external_storage_binding("options")
    demand, overlap = read_accepted_source(settings)
    native = _signed(settings, NATIVE_REL, "source_fingerprint", NATIVE_FP)
    crosswalk = _signed(settings, CROSSWALK_REL, "crosswalk_fingerprint", CROSSWALK_FP)
    if (
        native.get("case_denominator") != MAX_ROWS
        or crosswalk.get("case_denominator") != MAX_ROWS
        or len(native.get("rows", [])) != MAX_ROWS
        or len(crosswalk.get("cases", [])) != MAX_ROWS
        or crosswalk.get("source_inventory_fingerprint")
            != demand.get("source_inventory_fingerprint")
        or demand.get("accepted_native_stock_source_fingerprint") != NATIVE_FP
        or native.get("protected_outcomes_read") != 0
        or crosswalk.get("provider_requests") != 0
    ):
        raise MultiYearQuoteBridgeError("accepted full case denominator/lineage changed")
    return native, crosswalk, demand, overlap


def _positive(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean underlying/strike")
    try:
        n = Decimal(str(value))
        if n.is_finite() and n > 0:
            return n
    except (ValueError, TypeError, InvalidOperation):
        pass
    raise ValueError("underlying or strike is not positive finite raw-as-traded value")


def _occ(symbol: object, ticker: str, expiry: str, right: str) -> bool:
    match = OCC.fullmatch(symbol) if isinstance(symbol, str) else None
    if match is None or match.group(1) != ticker or match.group(3) != RIGHTS[right]:
        return False
    try:
        parsed = date(2000 + int(match.group(2)[:2]), int(match.group(2)[2:4]),
                      int(match.group(2)[4:6]))
    except ValueError:
        return False
    return parsed.isoformat() == expiry


def select_structural_option(
    rows: tuple[dict[str, Any], ...], *, ticker: str, expiry: str,
    right: str, raw_open: Decimal,
) -> dict[str, str] | None:
    """Deterministic nearest ATM rank, no bid/ask, volume, OI, or future fields."""
    if right not in RIGHTS:
        raise MultiYearQuoteBridgeError("invalid option right")
    candidates: list[tuple[tuple[Decimal, int, Decimal, str], dict[str, str]]] = []
    for row in rows:
        if row.get("side") != right:
            continue
        symbol = row.get("optionSymbol")
        if not _occ(symbol, ticker, expiry, right):
            raise MultiYearQuoteBridgeError("source contains inconsistent OCC/right/expiry")
        strike = _positive(row.get("strike"))
        if Decimal(OCC.fullmatch(symbol).group(4)) / 1000 != strike:
            raise MultiYearQuoteBridgeError("OCC strike differs from observed source row")
        # Exactly equidistant strikes prefer OTM (CALL higher, PUT lower).
        otm = strike >= raw_open if right == "call" else strike <= raw_open
        key = (abs(strike - raw_open), 0 if otm else 1, strike, symbol)
        candidates.append((key, {"option_symbol": symbol, "strike": str(strike)}))
    if not candidates:
        return None
    candidates.sort(key=lambda value: value[0])
    return candidates[0][1]


def _verified_chain(
    settings: AtlasSettings, identity: str, *, ticker: str, signal: str,
    expiry: str, expected_sha: str | None,
    memo: dict[str, tuple[str, tuple[dict[str, Any], ...], str | None]],
) -> tuple[str, tuple[dict[str, Any], ...], str | None]:
    if identity in memo:
        return memo[identity]
    paths = _paths(settings, identity)
    if not paths.receipt.exists() and not paths.body.exists() and not paths.attempt.exists():
        result = ("MISSING_CHAIN_SOURCE", (), None)
        memo[identity] = result
        return result
    if not paths.receipt.is_file() or paths.receipt.is_symlink():
        result = ("UNRESOLVED_CHAIN_SOURCE_EVIDENCE", (), None)
        memo[identity] = result
        return result
    try:
        metadata = _read_object(paths.receipt)
        params = metadata["params"]
        if (
            metadata["request_identity"] != identity
            or metadata["endpoint"] != f"options/chain/{ticker}/"
            or params["date"] != signal
            or params["expiration"] != expiry
            or set(params) != {"date", "expiration", "strike"}
        ):
            raise MultiYearQuoteBridgeError("original cache key/source mismatch")
        request = {
            "request_identity": identity, "ticker": ticker,
            "endpoint": metadata["endpoint"], "params": params,
            "bounded_query": True,
        }
        valid = _valid_receipt(paths, request)
        if valid is None:
            raise MultiYearQuoteBridgeError("unresolved original physical request")
        if valid["status"] == "VERIFIED_NO_DATA":
            result = ("EXACT_QUERY_NO_DATA", (), valid["body_sha256"])
        elif valid["status"] == "COMPLETE":
            if expected_sha is not None and valid["body_sha256"] != expected_sha:
                raise MultiYearQuoteBridgeError("original source SHA pointer mismatch")
            raw = paths.body.read_bytes()
            parsed = json.loads(raw.decode("utf-8"))
            rows = array_rows(parsed)
            result = ("VERIFIED_PIT_CHAIN", rows, valid["body_sha256"])
        else:
            raise MultiYearQuoteBridgeError("chain source status is not complete")
    except (OSError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        raise MultiYearQuoteBridgeError(
            f"local physical source {identity} invalid or ambiguous; no fallback GET"
        ) from exc
    memo[identity] = result
    return result


def _pointer(
    case: dict[str, Any], right: str,
) -> tuple[str | None, str | None, str | None]:
    pointer = case.get("original_source_pointer") or {}
    if not isinstance(pointer, dict):
        raise MultiYearQuoteBridgeError("original source pointer malformed")
    if right == "call":
        symbol = (
            case.get("original_2022_option_symbol_pointer")
            or pointer.get("original_provisional_call_symbol")
        )
    else:
        symbol = None
    identity = (
        pointer.get("chain_request_identity")
        or pointer.get("original_chain_request_identity")
    )
    sha = (
        case.get("original_2022_chain_body_sha256_pointer")
        or pointer.get("original_chain_body_sha256")
    )
    return symbol, identity, sha


def assemble_case_selections(
    native: dict[str, Any], crosswalk: dict[str, Any],
    demand: dict[str, Any], overlap: dict[str, Any], *,
    right: str,
    source_reader: Callable[..., tuple[str, tuple[dict[str, Any], ...], str | None]],
    expected_case_denominator: int = MAX_ROWS,
    expected_physical_source_count: int = 7646,
) -> dict[str, Any]:
    """Pure full-denominator join; source_reader enforces local SHA/receipt identity."""
    if right not in (*RIGHTS, "both"):
        raise MultiYearQuoteBridgeError("invalid right policy")
    if (demand["demand_fingerprint"] != DEMAND_FP
        or overlap["overlap_fingerprint"] != OVERLAP_FP
        or native["source_fingerprint"] != NATIVE_FP
        or crosswalk["crosswalk_fingerprint"] != CROSSWALK_FP):
        raise MultiYearQuoteBridgeError("not the accepted frozen research cohort")
    raw_by_id = {x["case_id"]: x for x in native["rows"]}
    old_by_id = {x["case_id"]: x for x in crosswalk["cases"]}
    if (len(raw_by_id) != expected_case_denominator
        or len(old_by_id) != expected_case_denominator
        or set(raw_by_id) != set(old_by_id)):
        raise MultiYearQuoteBridgeError("full source case mapping changed")
    physical: dict[str, dict[str, Any]] = {}
    for ticket in demand["requests"]:
        for case_id in ticket["member_case_ids"]:
            if case_id in physical:
                raise MultiYearQuoteBridgeError("duplicate physical membership")
            physical[case_id] = ticket
    overlap_by_id = {x["physical_request_identity"]: x for x in overlap["rows"]}
    if len(overlap_by_id) != expected_physical_source_count:
        raise MultiYearQuoteBridgeError("accepted physical source count changed")
    rights = tuple(RIGHTS) if right == "both" else (right,)
    selected: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    memo: dict[str, tuple[str, tuple[dict[str, Any], ...], str | None]] = {}
    for case_id in sorted(raw_by_id):
        row = raw_by_id[case_id]
        old = old_by_id[case_id]
        if (row["ticker"] != old["ticker"]
            or row["signal_session"] != old["signal_session"]
            or row["entry_session"] != old["entry_session"]
            or row["expiration"] != old["expiration"]
            or row["planned_option_decision_at_utc"] != old["decision_at_utc"]):
            raise MultiYearQuoteBridgeError("accepted native/crosswalk chronology differs")
        signal = date.fromisoformat(row["signal_session"])
        decision = datetime.fromisoformat(old["decision_at_utc"])
        expiry_text = row["expiration"]
        eligible = expiry_text is not None and row["raw_underlying_price"] is not None
        if (decision.tzinfo is None
            or decision.astimezone(UTC).date() != date.fromisoformat(row["entry_session"])
            or not signal < date.fromisoformat(row["entry_session"])):
            raise MultiYearQuoteBridgeError("accepted case decision chronology invalid")
        for side in rights:
            status = None
            chosen = None
            source_id = source_sha = None
            if row["native_source_status"] == "DEFERRED_ENTRY_2026_NATIVE_SOURCE_NOT_READ":
                status = "PROTECTED_2026_ENTRY_NOT_REPLAYED"
            elif not eligible:
                status = "NO_FROZEN_EXPIRATION_OR_RAW_OPEN"
            elif (expiry := date.fromisoformat(expiry_text)) <= signal:
                raise MultiYearQuoteBridgeError("expiry predates original signal")
            elif not 7 <= (expiry - signal).days <= 75:
                status = "EXPIRY_OUTSIDE_FROZEN_QUOTE_DEMAND_RULE"
            elif old["source_disposition"] == "DECISION_OUTSIDE_ROLLING_PROVIDER_WINDOW":
                status = "ORIGINAL_2021_PRE_FIVE_YEAR_SOURCE_GAP"
            else:
                raw = _positive(row["raw_underlying_price"])
                pointer_symbol, pointer_id, pointer_sha = _pointer(old, side)
                ticket = physical.get(case_id)
                if (side == "call" and pointer_symbol
                    and old["original_reconciliation"] in {
                        "ORIGINAL_2022_PREFERRED_CALL_PLAN_POINTER_REUSED",
                        "ORIGINAL_2025_PILOT_PREFERRED_CALL_POINTER_REUSED",
                    }):
                    if not _occ(pointer_symbol, row["ticker"], expiry_text, side):
                        raise MultiYearQuoteBridgeError("frozen original CALL pointer invalid")
                    if (old["year"] == "2022"
                        and old.get("original_2022_chain_body_sha256_pointer") is None):
                        raise MultiYearQuoteBridgeError("unbound original 2022 source")
                    chosen = {
                        "option_symbol": pointer_symbol,
                        "strike": str(Decimal(OCC.fullmatch(pointer_symbol).group(4)) / 1000),
                    }
                    source_id, source_sha = pointer_id, pointer_sha
                    status = "SELECTED_ACCEPTED_ORIGINAL_PIT_CALL_POINTER"
                elif ticket is not None:
                    identity = ticket["physical_request_identity"]
                    audited = overlap_by_id[identity]
                    if audited["source_status"] == "REUSED_VERIFIED_LOCAL_COMPLETE_CHAIN_FULL_STRIKE_COVERAGE":
                        source_id = audited["reused_physical_source"]["source_request_identity"]
                        source_sha = audited["reused_physical_source"]["source_body_sha256"]
                    else:
                        source_id = identity
                    source_status, rows, verified_sha = source_reader(
                        source_id, ticker=row["ticker"], signal=signal.isoformat(),
                        expiry=expiry_text, expected_sha=source_sha, memo=memo,
                    )
                    if source_status == "VERIFIED_PIT_CHAIN":
                        chosen = select_structural_option(
                            rows, ticker=row["ticker"], expiry=expiry_text,
                            right=side, raw_open=raw,
                        )
                        status = ("SELECTED_VERIFIED_PIT_CHAIN"
                                  if chosen else "VERIFIED_CHAIN_NO_MATCHING_RIGHT")
                        source_sha = verified_sha
                    else:
                        status = source_status
                elif pointer_id is not None:
                    source_id = pointer_id
                    source_status, rows, verified_sha = source_reader(
                        source_id, ticker=row["ticker"], signal=signal.isoformat(),
                        expiry=expiry_text, expected_sha=pointer_sha, memo=memo,
                    )
                    if source_status == "VERIFIED_PIT_CHAIN":
                        chosen = select_structural_option(
                            rows, ticker=row["ticker"], expiry=expiry_text,
                            right=side, raw_open=raw,
                        )
                        source_sha = verified_sha
                        status = ("SELECTED_VERIFIED_ORIGINAL_PIT_CHAIN"
                                  if chosen else "VERIFIED_CHAIN_NO_MATCHING_RIGHT")
                    else:
                        status = source_status
                else:
                    status = "NO_ORIGINAL_PHYSICAL_CHAIN_IDENTITY"
            counts[status] += 1
            coverage.append({
                "case_id": case_id, "signal_year": row["signal_session"][:4],
                "right": side, "status": status, "option_symbol": (
                    chosen["option_symbol"] if chosen else None
                ), "source_request_identity": source_id,
            })
            if chosen:
                selected.append({
                    "case_id": f"{case_id}:{RIGHTS[side]}",
                    "original_case_id": case_id,
                    "ticker": row["ticker"],
                    "option_symbol": chosen["option_symbol"],
                    "right": side,
                    "expiration": expiry_text,
                    "decision_at_utc": old["decision_at_utc"],
                    "selected_at_utc": old["decision_at_utc"],
                    "accepted_stock_source_sha256": NATIVE_FP,
                    "frozen_native_raw_open": row["raw_underlying_price"],
                    "frozen_structural_strike": chosen["strike"],
                    "source_request_identity": source_id,
                    "source_body_sha256": source_sha,
                    "prior_24h_news_count": old["news_prior_24h"],
                    "prior_7d_news_count": old["news_prior_7d"],
                    "source_selection_status": status,
                    "not_an_option_fill_or_validated_deliverable": True,
                })
    report = {
        "contract": CONTRACT,
        "status": "OFFLINE_PIT_CONTRACT_IDENTITIES_ONLY",
        "original_case_denominator": expected_case_denominator,
        "right_policy": right,
        "original_right_memberships": expected_case_denominator * len(rights),
        "signed_native_source": NATIVE_FP,
        "signed_original_crosswalk": CROSSWALK_FP,
        "signed_physical_source_demand": DEMAND_FP,
        "signed_original_global_overlap": OVERLAP_FP,
        "source_only_selection_policy": "NEAREST_RAW_STOCK_OPEN_ATM_TIE_OTM",
        "selected_case_right_memberships": len(selected),
        "by_status": dict(sorted(counts.items())),
        "cases": selected,
        "coverage": coverage,
        "provider_requests": 0,
        "historical_0935_option_bid_ask_verified": False,
        "verified_standard_deliverable_or_option_pnl": False,
        "2026_protected_outcomes_read": 0,
        "strategy_authority": False,
    }
    report["selection_fingerprint"] = _fingerprint(report)
    return report


def build_local_bridge(settings: AtlasSettings, *, right: str = "both") -> dict[str, Any]:
    native, crosswalk, demand, overlap = read_accepted_cases(settings)
    return assemble_case_selections(
        native, crosswalk, demand, overlap, right=right,
        source_reader=lambda identity, **kwargs: _verified_chain(
            settings, identity, **kwargs,
        ),
    )


def write_local_bridge(settings: AtlasSettings, report: dict[str, Any]) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    signature = report["selection_fingerprint"]
    unsigned = dict(report)
    unsigned.pop("selection_fingerprint")
    if signature != _fingerprint(unsigned):
        raise MultiYearQuoteBridgeError("selection signature changed before persistence")
    path = settings.resolved_path(f"{OUTPUT_REL}_{signature[:16]}.json")
    if path.exists() or path.is_symlink():
        if _read_object(path) != report:
            raise MultiYearQuoteBridgeError("frozen prior selection differs")
        return path, "REUSED_IDENTICAL_PIT_SOURCE_SELECTION"
    _exclusive(path, report)
    return path, "WRITTEN_IMMUTABLE_PIT_SOURCE_SELECTION"
