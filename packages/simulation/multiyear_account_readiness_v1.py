from __future__ import annotations

"""Fail-closed admission census for accepted dated but unsynchronized sources.

No conversion from source-only casebook to executable positions is permitted.
The synthetic account mechanics live in a separate, fixture-only module.
"""

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import _write_new
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.multiyear_verified_stock_option_source_casebook_v1 import (
    CONTRACT as CASEBOOK_CONTRACT, SOURCE_PAIR, STOCK_GAP, NO_PAIR,
    PROTECTED_2026_WITHHELD,
)

CONTRACT = "atlas-multiyear-account-replay-source-readiness-v1"
OUTPUT_REL = "data/options/derived/multiyear_account_replay_source_readiness_v1"
EXPECTED_SOURCE_FP = "176aa0427a9ec34fcfbc318a8a7d2a4af00320c889b55bf519d119fadb22033a"


class AccountReadinessError(ValueError):
    pass


def build_replay_readiness(
    casebook: dict[str, Any], *, expected_cases: int = 14902,
    expected_source_fp: str | None = EXPECTED_SOURCE_FP,
) -> dict[str, Any]:
    _check_signature(casebook, "casebook_fingerprint")
    original = casebook["original_case_denominator"]
    expected_slots = expected_cases * 2
    rows = casebook.get("rows")
    if (
        casebook.get("contract") != CASEBOOK_CONTRACT
        or casebook.get("status") != "FULL_COHORT_DATED_SOURCE_CASEBOOK_NOT_TRADE_REPLAY"
        or (expected_source_fp is not None and
            casebook["casebook_fingerprint"] != expected_source_fp)
        or original != expected_cases
        or casebook.get("original_right_memberships") != expected_slots
        or not isinstance(rows, list) or len(rows) != expected_slots
        or casebook.get("provider_requests") != 0
        or casebook.get("protected_2026_outcomes_read") != 0
        or casebook.get("synchronized_clock_pairs_proven") != 0
        or casebook.get("option_fills_verified") != 0
        or casebook.get("account_pnl_authority") is not False
    ):
        raise AccountReadinessError("accepted source lineage or replay authority changed")
    by_case: dict[str, set[str]] = defaultdict(set)
    by_year: dict[str, Counter[str]] = {
        str(y): Counter() for y in range(2021, 2027)
    }
    counts: Counter[str] = Counter()
    seen = set()
    readiness_rows = []
    for row in rows:
        cid, case, right, year = (
            row["case_right_id"], row["original_case_id"], row["right"], row["year"]
        )
        if (
            not isinstance(case, str) or not case
            or cid != case + (":C" if right == "call" else ":P")
            or cid in seen or year not in ("2021", "2022", "2023", "2024", "2025")
            or row.get("same_session_evidence_is_not_same_clock_evidence") is not True
            or row.get("deliverable_and_multiplier_verified") is not False
            or row.get("executable_fill_or_account_pnl_authority") is not False
        ):
            raise AccountReadinessError("source case/right or timing authority drifted")
        seen.add(cid)
        by_case[case].add(right)
        status = row["source_join_status"]
        if status == SOURCE_PAIR:
            if (
                not row.get("first_later_option_source")
                or not row.get("next_later_option_source")
                or not row.get("entry_session_native_source")
                or not row.get("next_session_native_source")
                or row["entry_session_native_source"]["status"] != "VERIFIED_NATIVE_RAW_EOD_CLOSE"
                or row["next_session_native_source"]["status"] != "VERIFIED_NATIVE_RAW_EOD_CLOSE"
            ):
                raise AccountReadinessError("dated paired source was altered")
            blocker = "SOURCE_DATES_PAIRED_BUT_CLOCK_DELIVERABLE_AND_FILL_UNPROVEN"
        elif status == STOCK_GAP:
            blocker = "EXACT_NATIVE_DAILY_PRICE_GAP"
        elif status == PROTECTED_2026_WITHHELD:
            if (
                not row.get("first_later_option_source")
                or not row.get("next_later_option_source")
                or not row.get("entry_session_native_source")
                or not row.get("next_session_native_source")
                or not any(
                    x.get("status")
                    == "PROTECTED_2026_NATIVE_CLOSE_WITHHELD_NOT_READ"
                    for x in (
                        row["entry_session_native_source"],
                        row["next_session_native_source"],
                    )
                )
            ):
                raise AccountReadinessError("protected 2026 native withholding changed")
            blocker = "PROTECTED_2026_NATIVE_CLOSE_WITHHELD"
        elif status == NO_PAIR:
            if row["option_symbol"] is None:
                blocker = "NO_PIT_SELECTED_CONTRACT"
            elif row["original_quote_history_status"] == "QUOTE_HISTORY_NOT_ACQUIRED":
                blocker = "EXACT_OPTION_QUOTE_HISTORY_NOT_ACQUIRED"
            elif row["original_quote_history_status"] == (
                "QUOTE_HISTORY_OUTSIDE_CURRENT_PROVIDER_WINDOW"
            ):
                blocker = "OPTION_QUOTE_HISTORY_OUTSIDE_CURRENT_PROVIDER_WINDOW"
            elif row["original_quote_history_status"] == (
                "QUOTE_HISTORY_AFTER_LAST_COMPLETED_SESSION"
            ):
                blocker = "OPTION_QUOTE_HISTORY_AFTER_LAST_COMPLETED_SESSION"
            elif row["original_quote_history_status"] == (
                "QUOTE_HISTORY_NO_CLOSED_SOURCE_PERIOD"
            ):
                blocker = "OPTION_QUOTE_HISTORY_NO_CLOSED_SOURCE_PERIOD"
            else:
                blocker = "INSUFFICIENT_LATER_VALID_OPTION_QUOTE_OBSERVATIONS"
        else:
            raise AccountReadinessError("unknown source status")
        by_year[year][blocker] += 1
        counts[blocker] += 1
        readiness_rows.append({
            "case_right_id": cid, "original_case_id": case,
            "year": year, "right": right, "ticker": row["ticker"],
            "option_symbol": row["option_symbol"],
            "source_join_status": status, "replay_blocker": blocker,
            "historical_trade_admitted": False,
        })
    if (
        len(seen) != expected_slots
        or len(by_case) != expected_cases
        or any(rights != {"call", "put"} for rights in by_case.values())
        or counts["SOURCE_DATES_PAIRED_BUT_CLOCK_DELIVERABLE_AND_FILL_UNPROVEN"]
            != casebook.get("dated_option_and_stock_source_rights")
        or sum(counts.values()) != expected_slots
    ):
        raise AccountReadinessError("full source denominator or dated pair count changed")
    output = {
        "contract": CONTRACT,
        "status": "HISTORICAL_SOURCE_ADMISSION_BLOCKED_EXPLICIT_GAPS",
        "source_casebook_fingerprint": casebook["casebook_fingerprint"],
        "original_case_denominator": expected_cases,
        "original_right_memberships": expected_slots,
        "dated_option_stock_source_rights": casebook["dated_option_and_stock_source_rights"],
        "actual_same_clock_qualified_rights": 0,
        "actual_executable_option_trades": 0,
        "by_blocker": dict(sorted(counts.items())),
        "rows": sorted(readiness_rows, key=lambda x: x["case_right_id"]),
        "by_year": {
            str(y): {"original_right_slots": sum(by_year[str(y)].values()),
                     "blockers": dict(sorted(by_year[str(y)].items()))}
            for y in range(2021, 2027)
        },
        "provider_requests": 0,
        "historical_account_pnl": None,
        "historical_account_pnl_authority": False,
        "protected_holdout_is_fresh": False,
        "paper": False, "live": False,
    }
    output["readiness_fingerprint"] = _fingerprint(output)
    return output


def persist_replay_readiness(
    settings: AtlasSettings, report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "readiness_fingerprint")
    path = settings.resolved_path(
        f"{OUTPUT_REL}_{report['readiness_fingerprint'][:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != report:
            raise AccountReadinessError("previous immutable readiness output differs")
        return path, "REUSED_IDENTICAL_SOURCE_READINESS"
    _write_new(path, report)
    return path, "WRITTEN_IMMUTABLE_SOURCE_READINESS"
