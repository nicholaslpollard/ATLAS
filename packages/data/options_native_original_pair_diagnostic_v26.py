from __future__ import annotations

"""Read-only matched SPY CALL/PUT source diagnostics, never a strategy backtest.

Compares the ORIGINAL 10:00 weekly quote surfaces with later immutable 10:00
review sources. No trade is selected from future outcomes. ALL entry pairs
meeting simple quote-age/spread screens are retained as the denominator.
Prices are hypothetical ask-to-bid references, NOT historical executions.
"""

from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from statistics import mean, median
from typing import Any
from zoneinfo import ZoneInfo
import zlib

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    PINNED_MANIFEST_FINGERPRINT, _load_full_manifest,
)
from packages.data.hybrid_options_unattended_campaign_v1 import _inspect_attempt
from packages.data.hybrid_options_source_linked_research_reader_v1 import (
    read_selected_original_observations,
)
from packages.data.options_native_exit_source_campaign_v1 import (
    _demand, _path, _receipt, _state, MAX_RESPONSE_BYTES, SpyExitSourceError,
)
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    SPY_ORIGIN, EXPECTED_ENTRIES, EXPECTED_ALL_AT_TIME, _exit_at_time_query,
    _exit_review_sessions, SPY_2025_PRIOR_SAVED,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.strategies.options_native_pilot_v1_contract import MIN_DTE, MAX_DTE

CONTRACT = "atlas-spy-quote-pair-source-observation-economic-diagnostic-v26"
EASTERN = ZoneInfo("America/New_York")
MAX_AGE_SECONDS = 30
MAX_LEG_SKEW_SECONDS = 1
MAX_SPREAD_TO_MID = Decimal("0.15")
FEE_GRID = ("0.00", "0.65", "1.30")
EXIT_ARCHIVE_OK = {"RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", "RAW_ARCHIVED_SCOPE_DIAGNOSTIC"}
ENTRY_ARCHIVE_OK = EXIT_ARCHIVE_OK


class PairDiagnosticError(ValueError):
    pass


def _decimal(x: Any) -> Decimal:
    try:
        d = Decimal(str(x))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PairDiagnosticError("QUOTE_NONNUMERIC_PRICE") from exc
    if not d.is_finite() or d < 0:
        raise PairDiagnosticError("QUOTE_PRICE_NOT_FINITE_NONNEGATIVE")
    return d


def _key(q: dict[str, Any]) -> tuple[str, str, str]:
    exp = date.fromisoformat(str(q["expiration"])[:10]).isoformat()
    strike = _decimal(q["strike"])
    if strike <= 0:
        raise PairDiagnosticError("QUOTE_STRIKE_INVALID")
    right = str(q["right"]).lower()
    if right not in {"call", "put"}:
        raise PairDiagnosticError("QUOTE_RIGHT_INVALID")
    return exp, str(strike.normalize()), right


def _validated_quote(
    q: dict[str, Any], day: date,
) -> dict[str, Any] | None:
    stamp = datetime.fromisoformat(str(q["timestamp"]).replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise PairDiagnosticError("QUOTE_CLOCK_NAIVE")
    local = stamp.astimezone(EASTERN)
    clock = datetime.combine(day, datetime.strptime("10:00:00", "%H:%M:%S").time(), EASTERN)
    if local.date() != day or local > clock:
        raise PairDiagnosticError("QUOTE_CLOCK_AFTER_REVIEW")
    age = (clock - local).total_seconds()
    bid, ask = _decimal(q["bid"]), _decimal(q["ask"])
    if bid > ask and bid > 0 and ask > 0:
        raise PairDiagnosticError("QUOTE_CROSSED")
    if (age > MAX_AGE_SECONDS or bid <= 0 or ask <= 0
            or type(q["bid_size"]) is not int or type(q["ask_size"]) is not int
            or q["bid_size"] < 1 or q["ask_size"] < 1):
        return None
    mid = (bid + ask) / 2
    if (ask - bid) / mid > MAX_SPREAD_TO_MID:
        return None
    return {"bid": bid, "ask": ask, "clock": stamp, "source_quote": q}


def _pair_observations(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    day: date, *, entry: bool,
) -> dict[tuple[str, str], dict[str, Any]]:
    two_sided: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    seen: set[tuple[str, str, str]] = set()
    for q in rows:
        key = _key(q)
        if key in seen:
            raise PairDiagnosticError("DUPLICATE_SOURCE_CONTRACT")
        seen.add(key)
        expiry = date.fromisoformat(key[0])
        dte = (expiry - day).days
        # Entry selection is a 30..45 DTE screen. A position originally
        # entered in that range may have <30 DTE on subsequent review days.
        if (not MIN_DTE <= dte <= MAX_DTE) if entry else not 0 <= dte <= MAX_DTE:
            continue
        checked = _validated_quote(q, day)
        if checked is not None:
            two_sided[key[:2]][key[2]] = checked
    result = {}
    for key, sides in two_sided.items():
        if set(sides) != {"call", "put"}:
            continue
        if abs((sides["call"]["clock"] - sides["put"]["clock"]).total_seconds()) > MAX_LEG_SKEW_SECONDS:
            continue
        result[key] = {
            "entry_ask": sides["call"]["ask"] + sides["put"]["ask"],
            "exit_bid": sides["call"]["bid"] + sides["put"]["bid"],
        }
    return result


def _read_verified_exit_source(
    settings: AtlasSettings, req: dict[str, Any], plan_fingerprint: str,
) -> tuple[str, tuple[dict[str, Any], ...] | None]:
    state = _state(settings, req, plan_fingerprint)
    if state not in EXIT_ARCHIVE_OK:
        return state, None
    terminal = _receipt(settings, req, plan_fingerprint, "terminal")
    if terminal is None or not isinstance(terminal.get("archive"), dict):
        raise PairDiagnosticError("EXIT_ORIGINAL_RECEIPT_UNAVAILABLE")
    archive = terminal["archive"]
    compressed = _path(settings, req["query_id"], "sources").read_bytes()
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        raw = decoder.decompress(compressed, MAX_RESPONSE_BYTES + 1)
    except zlib.error as exc:
        raise PairDiagnosticError("EXIT_ORIGINAL_GZIP_UNREADABLE") from exc
    if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
            or len(raw) != archive["original_bytes"]
            or hashlib.sha256(raw).hexdigest() != archive["original_sha256"]):
        raise PairDiagnosticError("EXIT_ORIGINAL_SHA_OR_BOUNDARY_DRIFT")
    data = json.loads(raw)
    if not isinstance(data, list) or len(data) != archive["observed_rows"]:
        raise PairDiagnosticError("EXIT_ORIGINAL_ROW_COUNT_DRIFT")
    return state, tuple(data)


def _stats(xs: list[float]) -> dict[str, float | int | None]:
    if not xs:
        return {"observations": 0, "mean_pct": None, "median_pct": None,
                "positive_fraction": None}
    return {"observations": len(xs), "mean_pct": round(mean(xs) * 100, 6),
            "median_pct": round(median(xs) * 100, 6),
            "positive_fraction": round(sum(x > 0 for x in xs) / len(xs), 6)}


def _evaluate_cohort(
    entries: list[dict[str, Any]],
    source_reader,
) -> dict[str, Any]:
    """Pure date-scoped evaluator: reader gives (source_state, original_rows).

    Each future review is matched to every entry-time eligible contract pair.
    There is deliberately no future-liquidity filter at entry, no contract
    switching, no capital allocation, and NO trade/account return.
    """
    original_entries = 0
    screened_pairs = 0
    no_entry = Counter()
    exit_states = Counter()
    matched = Counter()
    per_fee = {fee: [] for fee in FEE_GRID}
    per_year = defaultdict(lambda: {"entries": 0, "pairs": 0, "matched": 0})
    for record in entries:
        session = date.fromisoformat(record["date_et"])
        original_entries += 1
        year = str(session.year)
        per_year[year]["entries"] += 1
        entry_state, original = source_reader(record["query_id"], record)
        if original is None:
            no_entry[entry_state] += 1
            continue
        pairs = _pair_observations(original, session, entry=True)
        screened_pairs += len(pairs)
        per_year[year]["pairs"] += len(pairs)
        for review_day in _exit_review_sessions(session):
            req = _exit_at_time_query(review_day)
            exit_state, later = source_reader(req["query_id"], req)
            exit_states[exit_state] += 1
            if later is None:
                continue
            review_pairs = _pair_observations(later, review_day, entry=False)
            for key, at_entry in pairs.items():
                match = review_pairs.get(key)
                if match is None:
                    continue
                debit = at_entry["entry_ask"] * 100
                credit = match["exit_bid"] * 100
                matched[str((review_day - session).days)] += 1
                per_year[year]["matched"] += 1
                for fee in FEE_GRID:
                    # Two contracts in and two contracts out.
                    total_fees = _decimal(fee) * 4
                    per_fee[fee].append(float((credit - debit - total_fees) / debit))
    return {
        "entries_evaluated": original_entries,
        "entry_pairs_screened": screened_pairs,
        "missing_entry_source_states": dict(sorted(no_entry.items())),
        "five_session_review_uses_reached": sum(exit_states.values()),
        "review_source_states": dict(sorted(exit_states.items())),
        "matched_pair_review_observations": sum(matched.values()),
        "matched_by_calendar_day_lag": dict(sorted(matched.items(), key=lambda x: int(x[0]))),
        "by_entry_year": dict(sorted(per_year.items())),
        "fee_sensitivity_per_contract_per_side": {fee: _stats(values) for fee, values in per_fee.items()},
    }


def audit_original_spy_pair_observations(
    settings: AtlasSettings, manifest: Path, candidate_plan: Path,
) -> dict[str, Any]:
    settings.assert_external_storage_binding("options")
    frozen = _load_full_manifest(settings, manifest, candidate_plan)
    plan = _demand(frozen)
    entries = sorted(
        (item for item in frozen["requests"] if item["origin"] == SPY_ORIGIN),
        key=lambda v: (v["date_et"], v["query_id"]),
    )
    if (len(entries) != EXPECTED_ENTRIES or
            frozen["source_request_count"] != EXPECTED_ALL_AT_TIME or
            frozen["manifest_fingerprint"] != PINNED_MANIFEST_FINGERPRINT):
        raise PairDiagnosticError("FROZEN_SOURCE_PLAN_CHANGED")
    known_entry = {r["query_id"]: r for r in entries}
    exit_req = {r["query_id"]: r for r in plan["requests"]}
    seen: dict[str, tuple[str, tuple[dict[str, Any], ...] | None]] = {}

    def fetch(qid: str, row: dict[str, Any]):
        if qid in seen:
            return seen[qid]
        if qid in known_entry:
            if qid != row["query_id"]:
                raise PairDiagnosticError("ORIGINAL_ENTRY_REQUEST_DRIFT")
            if row["date_et"] == SPY_2025_PRIOR_SAVED:
                outcome = ("LEGACY_2025_EXTERNALLY_SAVED_UNADMITTED", None)
            else:
                state = _inspect_attempt(settings, qid)
                if state not in ENTRY_ARCHIVE_OK:
                    outcome = (state, None)
                else:
                    source = read_selected_original_observations(settings, known_entry[qid])
                    outcome = (state, source["selected_quotes"])
        else:
            if qid not in exit_req or exit_req[qid]["query_id"] != row["query_id"]:
                raise PairDiagnosticError("EXIT_REQUEST_OUTSIDE_FROZEN_PLAN")
            outcome = _read_verified_exit_source(settings, exit_req[qid], plan["plan_fingerprint"])
        seen[qid] = outcome
        return outcome

    values = _evaluate_cohort(entries, fetch)
    result = {
        "contract": CONTRACT,
        "status": "RETROSPECTIVE_SOURCE_MATCH_DIAGNOSTIC_ONLY",
        "original_411_entry_plan": len(entries),
        "distinct_new_exit_request_plan": len(exit_req),
        "observed_source_identities_loaded": len(seen),
        "source_plan_fingerprint": plan["plan_fingerprint"],
        "note": "Every matching candidate pair included; not the frozen strategy selector; future match availability conditions the return sample.",
        "pricing": "10:00 observed ASK entry / 10:00 observed BID review; 100 multiplier hypothetical; no 10:01 fill proof, option OI, PIT spot, dividend or contract settlement.",
        "fee_grid_is_model_assumption": True,
        "provider_requests": 0, "broker_requests": 0,
        "simulations_run": 0, "account_pnl_reported": False,
        "historical_execution_qualified": False,
        "protected_outcomes_read": 0, "strategy_promotion": False,
        **values,
    }
    result["fingerprint"] = _fingerprint(result)
    return result
