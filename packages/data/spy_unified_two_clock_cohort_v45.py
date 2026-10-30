from __future__ import annotations

"""V45 unified 09:59 pre-decision / 10:01 order-source SPY quality cohort.

Use V43's immutable original 361-date cohort and V44's alternate OI-recovery
receipts. Fetch only missing pre-decision quotes for the 178 original V43
source-quality passes via V39/V38, then combine with V44's independently
qualified replacement candidates. Never infer actual signals or trades.
"""

from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_source_admission_v43 import (
    MAX_PAIR_SKEW_SECONDS, _number,
)
from packages.data.spy_alternate_oi_contract_recovery_v44 import (
    CONTRACT as V44_CONTRACT, PINNED_V43_FINGERPRINT,
    _quality_for_quote, verified_original_cases,
    PRETRADE_TIME,
)

CONTRACT = "atlas-spy-unified-two-clock-original-plus-alternate-v45"
PINNED_V44_FINGERPRINT = "8dcd06e178fad25ebad6f88b9819dc2dc6479b5bc14fc1f57b694b01f271dbe5"
ORIGINAL_STATUS = "SOURCE_MICROSTRUCTURE_OI_CHECKS_PASS"
ALTERNATE_STATUS = "ALTERNATE_SOURCE_QUALITY_PASSES"
EXPECTED_ORIGINAL_PASSES = 178
EXPECTED_ALTERNATE_PASSES = 161
EXPECTED_RECOVERY_TARGETS = 174


class UnifiedCohortError(ValueError):
    pass


def verified_v43_v44(v43: dict, v44: dict) -> tuple[list[dict], list[dict]]:
    original = verified_original_cases(v43)
    if (not isinstance(v44, dict)
            or v44.get("contract") != V44_CONTRACT
            or v44.get("fingerprint") != PINNED_V44_FINGERPRINT
            or _fingerprint({k: v for k, v in v44.items() if k != "fingerprint"})
               != PINNED_V44_FINGERPRINT
            or v44.get("parent_v43_fingerprint") != PINNED_V43_FINGERPRINT
            or v44.get("original_361_pairs_unchanged") is not True
            or v44.get("quote_1001_cannot_inform_1000_decision") is not True
            or v44.get("selection_uses_post_1000_price_or_outcome") is not False
            or v44.get("original_pass_pairs") != EXPECTED_ORIGINAL_PASSES
            or v44.get("oi_recovery_targets") != EXPECTED_RECOVERY_TARGETS
            or v44.get("actual_historical_profitability") is not None
            or v44.get("true_historical_signals") is not None
            or v44.get("recovery_status_counts") != {
                "ALTERNATE_SOURCE_QUALITY_PASSES": 161,
                "ALTERNATE_SOURCE_QUALITY_UNQUALIFIED": 11,
                "NO_ALTERNATE": 2,
            }):
        raise UnifiedCohortError("V45_V44_PINNED_REPORT_OR_AUTHORITY_DRIFT")
    recovered = v44.get("recovery_cases")
    if not isinstance(recovered, list) or len(recovered) != EXPECTED_RECOVERY_TARGETS:
        raise UnifiedCohortError("V45_V44_RECOVERY_CASE_COUNT_DRIFT")
    original_by_day = {r["date_et"]: r for r in original}
    original_passing = [r for r in original if r["status"] == ORIGINAL_STATUS]
    original_oi_failing = {
        r["date_et"] for r in original
        if "ORIGINAL_CALL_PUT_OI_UNQUALIFIED" in r.get("reason_codes", ())
    }
    if (len(original_passing) != EXPECTED_ORIGINAL_PASSES
            or len(original_oi_failing) != EXPECTED_RECOVERY_TARGETS
            or len({r["date_et"] for r in recovered}) != EXPECTED_RECOVERY_TARGETS
            or {r["date_et"] for r in recovered} != original_oi_failing):
        raise UnifiedCohortError("V45_V43_V44_ORIGINAL_RECOVERY_DATE_DRIFT")
    for row in recovered:
        frozen = original_by_day[row["date_et"]]
        if (row.get("original_expiration") != frozen["expiration"]
                or Decimal(str(row.get("original_strike"))) != Decimal(str(frozen["strike"]))):
            raise UnifiedCohortError("V45_FROZEN_CONTRACT_CHANGED")
        if row.get("status") == ALTERNATE_STATUS:
            if (row.get("real_historical_entry_signal") is not None
                    or row.get("historical_profitability") is not None
                    or row.get("broker_fill_asserted") is not False
                    or row.get("independent_oi_publication_confirmed") is not False
                    or not isinstance(row.get("quote_quality"), dict)
                    or row.get("reason_codes") != []):
                raise UnifiedCohortError("V45_ALTERNATE_PROMOTED_OR_QUALITY_MISSING")
            new_identity = (str(row["expiration"]), Decimal(str(row["strike"])))
            old_identity = (str(frozen["expiration"]), Decimal(str(frozen["strike"])))
            if new_identity == old_identity:
                raise UnifiedCohortError("V45_ALTERNATE_IS_ORIGINAL")
    return original, recovered


def original_predecision_demands(originals: Iterable[dict]) -> Iterable[dict]:
    for row in originals:
        if row["status"] != ORIGINAL_STATUS:
            continue
        day = row["date_et"]
        exp = row["expiration"]
        strike = row["strike"]
        for right in ("call", "put"):
            yield {
                "candidate_id": f"SPY.V45.{day}.{exp}.{strike}",
                "purpose": f"{right}_pretrade_0959_quote",
                "method": "option_at_time_quote",
                "kwargs": {
                    "symbol": "SPY", "expiration": exp, "strike": strike,
                    "right": right, "date_et": day,
                    "time_of_day_et": PRETRADE_TIME + ".000",
                },
            }


def _predecision_quote_receipts(sources: dict) -> tuple[dict, list[str]]:
    pre = {}
    issues = []
    for right in ("call", "put"):
        purpose = f"{right}_pretrade_0959_quote"
        if purpose not in sources:
            pre[right] = {"status": "MISSING"}
            issues.append(f"{right.upper()}_PRETRADE_0959_SOURCE_MISSING")
            continue
        item, source = sources[purpose]
        pre[right] = _quality_for_quote(item, source, PRETRADE_TIME)
        if pre[right].get("status") != "PRETRADE_QUOTE_0959_PASSES":
            issues.append(f"{right.upper()}_PRETRADE_0959_UNQUALIFIED")
    stamps = [pre[right].get("timestamp_et") for right in ("call", "put")]
    if all(stamps):
        skew = abs((datetime.fromisoformat(stamps[0]) -
                    datetime.fromisoformat(stamps[1])).total_seconds())
        if skew > MAX_PAIR_SKEW_SECONDS:
            issues.append("ORIGINAL_PRETRADE_PAIR_SKEW_OVER_1S")
    else:
        skew = None
        issues.append("ORIGINAL_PRETRADE_PAIR_TIMESTAMP_UNQUALIFIED")
    return {**pre, "skew_seconds": skew}, sorted(set(issues))


def original_two_clock_result(original: dict, sources: dict) -> dict:
    if original["status"] != ORIGINAL_STATUS:
        raise UnifiedCohortError("V45_NON_QUALITY_ORIGINAL_PROMOTED")
    pretrade, issues = _predecision_quote_receipts(sources)
    order = {
        "call": original["source_10_01_call"],
        "put": original["source_10_01_put"],
        "skew_seconds": original["call_put_quote_time_skew_seconds"],
    }
    # V43 itself already qualified both order legs and their skew. Preserve
    # original identifiers instead of requesting the same 10:01 receipts again.
    if (order["call"]["status"] != "QUOTE_MICROSTRUCTURE_PASSES"
            or order["put"]["status"] != "QUOTE_MICROSTRUCTURE_PASSES"
            or order["skew_seconds"] is None
            or order["skew_seconds"] > MAX_PAIR_SKEW_SECONDS
            or original["source_decision_morning_oi"]["status"] != "OI_SOURCE_FILTER_PASSES"):
        raise UnifiedCohortError("V45_V43_ORIGINAL_1001_OR_OI_GATE_DRIFT")
    return {
        "date_et": original["date_et"], "cohort_origin": "ORIGINAL_V43",
        "status": ("TWO_CLOCK_SOURCE_QUALITY_PASSES" if not issues
                   else "TWO_CLOCK_SOURCE_QUALITY_UNQUALIFIED"),
        "expiration": original["expiration"], "strike": original["strike"],
        "spot_0959": _number(original["source_original_spy_spot_0959"]),
        "oi_quality": original["source_decision_morning_oi"],
        "quote_quality": {"pretrade_0959": pretrade, "execution_1001": order},
        "reason_codes": issues,
        "retrospective_volatility_is_pit": False,
        "original_2026_outcomes_used": False,
        "historically_executable_fill": None,
        "historical_pit_american_iv": None,
        "actual_strategy_pnl": None,
    }


def alternate_two_clock_result(original: dict, alternate: dict) -> dict:
    if alternate["status"] != ALTERNATE_STATUS:
        raise UnifiedCohortError("V45_UNQUALIFIED_ALTERNATE_PROMOTED")
    return {
        "date_et": original["date_et"], "cohort_origin": "V44_OI_ALTERNATE_VARIANT",
        "status": "TWO_CLOCK_SOURCE_QUALITY_PASSES",
        "expiration": alternate["expiration"], "strike": alternate["strike"],
        "spot_0959": alternate["spot_0959"],
        "oi_quality": {
            "call_open_interest": alternate["call_open_interest"],
            "put_open_interest": alternate["put_open_interest"],
            "call_message_et": alternate["call_oi_message_et"],
            "put_message_et": alternate["put_oi_message_et"],
            "source_query_id": alternate["source_oi_query_id"],
            "source_sha256": alternate["source_oi_sha256"],
            "independent_publication_confirmed": False,
        },
        "quote_quality": alternate["quote_quality"],
        "reason_codes": [],
        "retrospective_volatility_is_pit": False,
        "original_2026_outcomes_used": False,
        "historically_executable_fill": None,
        "historical_pit_american_iv": None,
        "actual_strategy_pnl": None,
    }


def combined_report(
    v43: dict, v44: dict, original: list[dict], recovered: list[dict],
    original_source_results: dict, acquisition: dict,
) -> dict:
    if (len(original) != 361 or len(recovered) != EXPECTED_RECOVERY_TARGETS
            or acquisition["source_uses_requested"] != EXPECTED_ORIGINAL_PASSES * 2):
        raise UnifiedCohortError("V45_REPLAY_SOURCE_COVERAGE_DRIFT")
    recovered_by_day = {r["date_et"]: r for r in recovered}
    cases = []
    for row in original:
        day = row["date_et"]
        if row["status"] == ORIGINAL_STATUS:
            case = original_two_clock_result(
                row, original_source_results.get(day, {}),
            )
        elif day in recovered_by_day and recovered_by_day[day]["status"] == ALTERNATE_STATUS:
            case = alternate_two_clock_result(row, recovered_by_day[day])
        else:
            alternate = recovered_by_day.get(day)
            case = {
                "date_et": day, "cohort_origin": "NO_SOURCE_QUALITY_ELIGIBLE_PAIR",
                "status": "SOURCE_QUALITY_NOT_ELIGIBLE",
                "original_v43_reasons": row.get("reason_codes", []),
                "alternate_v44_status": alternate.get("status") if alternate else None,
                "alternate_v44_reasons": alternate.get("reason_codes", []) if alternate else [],
                "historical_pit_american_iv": None,
                "actual_strategy_pnl": None,
            }
        cases.append(case)
    if len(cases) != 361 or len({c["date_et"] for c in cases}) != 361:
        raise UnifiedCohortError("V45_COMBINED_361_COVERAGE_DRIFT")
    status_counts = Counter(c["status"] for c in cases)
    origin_counts = Counter(c["cohort_origin"] for c in cases)
    fail_reasons = Counter(reason for c in cases
                           for reason in c.get("reason_codes", ()))
    by_year = defaultdict(Counter)
    for c in cases:
        by_year[c["date_et"][:4]][c["status"]] += 1
    anomalies = []
    for c in cases:
        if c["status"] != "TWO_CLOCK_SOURCE_QUALITY_PASSES":
            continue
        for clock in ("pretrade_0959", "execution_1001"):
            q = c["quote_quality"][clock]
            call, put = q["call"], q["put"]
            if (call.get("bid") is not None
                    and call.get("bid") == put.get("bid")
                    and call.get("ask") == put.get("ask")):
                anomalies.append({
                    "date_et": c["date_et"], "cohort_origin": c["cohort_origin"],
                    "clock": clock,
                    "reason": "EQUAL_CALL_PUT_BID_ASK_REQUIRES_MANUAL_SOURCE_IDENTITY_REVIEW",
                })
    out = {
        "contract": CONTRACT,
        "status": "SOURCE_QUALITY_TWO_CLOCK_COHORT_NOT_HISTORICAL_SIGNAL",
        "source_v43_fingerprint": v43["fingerprint"],
        "source_v44_fingerprint": v44["fingerprint"],
        "original_selected_weekly_clocks": 361,
        "original_abstentions_unchanged": 50,
        "total_original_weekly_clocks": 411,
        "original_v43_passing_1001_only": EXPECTED_ORIGINAL_PASSES,
        "alternate_v44_passing_two_clocks": EXPECTED_ALTERNATE_PASSES,
        "cohort_status_counts": dict(sorted(status_counts.items())),
        "cohort_origin_counts": dict(sorted(origin_counts.items())),
        "source_quality_by_year": {
            k: dict(sorted(v.items())) for k, v in sorted(by_year.items())
        },
        "two_clock_failure_reasons": dict(sorted(fail_reasons.items())),
        "suspicious_equal_call_put_quotes": anomalies,
        "original_0959_quote_acquisition": acquisition,
        "cases": cases,
        "required_next_gates": [
            "PIT_SOURCE_PUBLICATION_AT_0959_AND_1000_READINESS",
            "PIT_SOFR_RATE_BY_DECISION_DATE",
            "PIT_DISCRETE_SPY_EX_DATE_DIVIDEND_MODEL",
            "PIT_OCC_CONTRACT_DELIVERABLE_STANDARD_100_SHARE",
            "PIT_20_CONTIGUOUS_ECONOMIC_LOG_RETURN_PROVENANCE",
            "AMERICAN_101_STEP_LR_IV_WITH_APPROPRIATE_DIVIDEND_MODEL",
            "CAUSAL_VARIANCE_SCREEN_AND_1001_ENTRY_DECISION",
            "INDEPENDENT_EXIT_SOURCE_AND_ACCOUNT_EVENT_REPLAY",
        ],
        "pretrade_0959_quotes_never_substituted_from_1001": True,
        "alternate_selection_never_uses_1001_quotes": True,
        "historical_source_presence_is_not_independent_publication_proof": True,
        "american_iv_computed": False,
        "historically_executed_orders": None,
        "historical_profitability": None,
        "frozen_original_pair_mutations": 0,
        "protected_2026_outcomes_read": 0,
    }
    out["fingerprint"] = _fingerprint(out)
    return out
