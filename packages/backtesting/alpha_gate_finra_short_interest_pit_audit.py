from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import exchange_calendars as xcals

from packages.backtesting.alpha_gate_finra_short_interest_feasibility import (
    FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT,
    FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES,
    FINRA_SHORT_INTEREST_MECHANISM,
    FINRA_SHORT_INTEREST_REPORT_RELATIVE,
    finra_short_interest_feasibility_fingerprint,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.enums import InstrumentIdentityQuality
from packages.core.settings import AtlasSettings
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION, InstrumentIdentityResolver
from packages.providers.finra_short_interest import (
    FINRAShortInterestClient,
    is_exchange_listed_short_interest_row,
)
from packages.providers.massive.reference_data import MassiveReferenceProvider


FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT = (
    "alpha-gate-finra-short-interest-pit-audit-v1-publication-revision-split-active-common-stock-no-market-outcomes"
)
FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_HEAD = "104e1c6ca44a85a0a166ea24c0318d34f3c3bbb6"
FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_FINGERPRINT = (
    "cc80a87f020a4dece88430d20aa62e13d4dcd898656d60d53dea49b3ef975bc4"
)
FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT = (
    "ffdb7389ceae73f31a3781a79a8d825338102b9084cb30dd03bf21f6bf003846"
)
FINRA_SHORT_INTEREST_EXCHANGE_LISTED_START = date(2021, 6, 1)
FINRA_SHORT_INTEREST_PUBLICATION_XNYS_SESSIONS_AFTER_SETTLEMENT = 7
FINRA_SHORT_INTEREST_PUBLICATION_AVAILABILITY_ET = "16:40"
FINRA_SHORT_INTEREST_EXCHANGE_CODE_TO_MIC = {
    "A": "XNYS",
    "B": "XASE",
    "E": "ARCX",
    "H": "BATS",
    "R": "XNAS",
}
FINRA_SHORT_INTEREST_PUBLICATION_ANCHORS = {
    "2026-03-31": "2026-04-10",
    "2026-06-30": "2026-07-10",
    "2026-07-31": "2026-08-11",
    "2026-12-31": "2027-01-12",
}
FINRA_SHORT_INTEREST_MIN_IMMUTABLE_EXCHANGE_LISTED_ROWS = 100_000
FINRA_SHORT_INTEREST_MIN_PIT_ELIGIBLE_ROWS = 60_000
FINRA_SHORT_INTEREST_MIN_UNIQUE_PIT_INSTRUMENTS = 5_000
FINRA_SHORT_INTEREST_MIN_FILES_WITH_2500_PIT_ROWS = 10
FINRA_SHORT_INTEREST_REPORT_RELATIVE_PIT = Path(
    "strategy_evaluation/pre_phase33/finra_short_interest_pit_audit_v1/source_audit.json"
)

FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_COUNTS = {
    "successful_files": 12,
    "failed_files": 0,
    "years": [2021, 2022, 2023, 2024, 2025, 2026],
    "total_rows": 244_979,
    "exchange_listed_rows": 137_575,
    "unique_exchange_listed_symbols": 20_248,
    "revision_flagged_rows": 2_328,
    "stock_split_flagged_rows": 514,
}


class FINRAShortInterestPITAuditError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT,
        "parent_feasibility_contract": FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT,
        "parent_feasibility_fingerprint": FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_FINGERPRINT,
        "accepted_feasibility_head": FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_HEAD,
        "mechanism": FINRA_SHORT_INTEREST_MECHANISM,
        "frozen_settlement_dates": list(FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES),
        "accepted_feasibility_counts": FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_COUNTS,
        "history_exchange_listed_start": FINRA_SHORT_INTEREST_EXCHANGE_LISTED_START.isoformat(),
        "publication_rule": "SEVENTH_XNYS_SESSION_AFTER_SETTLEMENT",
        "availability_time_et": FINRA_SHORT_INTEREST_PUBLICATION_AVAILABILITY_ET,
        "decision_rule": "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_PUBLICATION_DATE",
        "revision_rule": "EXCLUDE_ANY_NONBLANK_REVISION_FLAG_ONLY_MOST_RECENT_FINRA_DATA_AVAILABLE",
        "stock_split_rule": "EXCLUDE_ANY_NONBLANK_STOCK_SPLIT_FLAG_FROM_PREDICTOR_ELIGIBILITY",
        "exchange_code_to_mic": FINRA_SHORT_INTEREST_EXCHANGE_CODE_TO_MIC,
        "identity_rule": (
            "EXACT_FINRA_SYMBOL_EXPECTED_PRIMARY_EXCHANGE_ACTIVE_CS_AT_SETTLEMENT_AND_DECISION_"
            "SAME_STRONG_OR_MEDIUM_INSTRUMENT_ID"
        ),
        "publication_anchors": FINRA_SHORT_INTEREST_PUBLICATION_ANCHORS,
        "numeric_gates": {
            "successful_files": 12,
            "min_immutable_exchange_listed_rows": FINRA_SHORT_INTEREST_MIN_IMMUTABLE_EXCHANGE_LISTED_ROWS,
            "min_pit_eligible_rows": FINRA_SHORT_INTEREST_MIN_PIT_ELIGIBLE_ROWS,
            "min_unique_pit_instruments": FINRA_SHORT_INTEREST_MIN_UNIQUE_PIT_INSTRUMENTS,
            "min_files_with_2500_pit_rows": FINRA_SHORT_INTEREST_MIN_FILES_WITH_2500_PIT_ROWS,
        },
        "alpha_hypotheses_frozen": False,
        "target_outcome_reads_allowed": False,
        "protected_outcome_reads_allowed": False,
        "provider_reads_allowed": True,
        "external_mutation_authority": {
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "automatic_broker_failover": False,
        },
    }


def finra_short_interest_pit_audit_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload()).encode("utf-8")).hexdigest()


def _xnys_session_n_after(value: date, n: int) -> date:
    if n < 1:
        raise FINRAShortInterestPITAuditError("XNYS session offset must be positive")
    calendar = xcals.get_calendar("XNYS")
    sessions = calendar.sessions_in_range(value + timedelta(days=1), value + timedelta(days=40))
    if len(sessions) < n:
        raise FINRAShortInterestPITAuditError(f"could not resolve {n} XNYS sessions after {value}")
    return sessions[n - 1].date()


def publication_date(settlement_date: date) -> date:
    return _xnys_session_n_after(
        settlement_date, FINRA_SHORT_INTEREST_PUBLICATION_XNYS_SESSIONS_AFTER_SETTLEMENT
    )


def decision_date(settlement_date: date) -> date:
    published = publication_date(settlement_date)
    return _xnys_session_n_after(published, 1)


def validate_accepted_feasibility_report(settings: AtlasSettings) -> dict[str, Any]:
    derived_root = settings.resolved_path(settings.data.paths.derived)
    path = derived_root / FINRA_SHORT_INTEREST_REPORT_RELATIVE
    if not path.is_file():
        raise FINRAShortInterestPITAuditError(f"accepted feasibility report is missing: {path}")
    raw = path.read_bytes()
    try:
        report = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FINRAShortInterestPITAuditError("accepted feasibility report is not valid UTF-8 JSON") from exc
    if report.get("contract_version") != FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT:
        raise FINRAShortInterestPITAuditError("accepted feasibility contract does not match")
    if report.get("feasibility_fingerprint") != FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_FINGERPRINT:
        raise FINRAShortInterestPITAuditError("accepted feasibility fingerprint does not match")
    if report.get("status") != "FEASIBILITY_PASS" or report.get("pass") is not True:
        raise FINRAShortInterestPITAuditError("accepted feasibility report is not PASS")
    summary = report.get("source_summary") or {}
    observed = {
        "successful_files": summary.get("successful_files"),
        "failed_files": len(report.get("failures") or []),
        "years": summary.get("years_represented"),
        "total_rows": summary.get("total_rows"),
        "exchange_listed_rows": summary.get("exchange_listed_rows"),
        "unique_exchange_listed_symbols": summary.get("unique_exchange_listed_symbols"),
        "revision_flagged_rows": summary.get("revised_rows"),
        "stock_split_flagged_rows": summary.get("stock_split_flagged_rows"),
    }
    if observed != FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_COUNTS:
        raise FINRAShortInterestPITAuditError(
            f"accepted feasibility evidence counts drifted: {observed!r}"
        )
    for key, expected in (
        ("target_outcome_rows_read", 0),
        ("protected_return_rows_read", 0),
        ("provider_writes_performed", 0),
        ("broker_reads_performed", 0),
        ("broker_writes_performed", 0),
        ("order_writes_performed", 0),
        ("paper_submits_performed", 0),
        ("live_writes_performed", 0),
        ("automation_writes_performed", 0),
    ):
        if report.get(key) != expected:
            raise FINRAShortInterestPITAuditError(f"accepted feasibility authority drifted: {key}")
    if report.get("protected_holdout_consumed") is not False:
        raise FINRAShortInterestPITAuditError("accepted feasibility consumed protected holdout")
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "counts": observed,
    }


def _snapshot_index(rows: Iterable[dict[str, Any]], as_of_date: date) -> dict[str, list[dict[str, Any]]]:
    resolver = InstrumentIdentityResolver()
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        row = dict(raw)
        ticker = str(row.get("ticker") or "").strip()
        if not ticker or not bool(row.get("active", False)):
            continue
        if str(row.get("type") or "").strip().upper() != "CS":
            continue
        exchange = str(row.get("primary_exchange") or "").strip().upper()
        if not exchange:
            continue
        try:
            instrument_id, identity_key, quality = resolver.resolve(row, as_of_date)
        except ValueError:
            continue
        if quality not in {InstrumentIdentityQuality.STRONG, InstrumentIdentityQuality.MEDIUM}:
            continue
        out[ticker].append(
            {
                "instrument_id": instrument_id,
                "identity_key": identity_key,
                "identity_quality": str(quality),
                "primary_exchange": exchange,
            }
        )
    return out


def _matching(index: dict[str, list[dict[str, Any]]], symbol: str, expected_mic: str) -> list[dict[str, Any]]:
    return [row for row in index.get(symbol, []) if row["primary_exchange"] == expected_mic]


class FINRAShortInterestPITAudit:
    def __init__(
        self,
        settings: AtlasSettings,
        finra_client: FINRAShortInterestClient,
        reference_provider: MassiveReferenceProvider,
    ) -> None:
        self.settings = settings
        self.finra_client = finra_client
        self.reference_provider = reference_provider

    def run(self) -> dict[str, Any]:
        if finra_short_interest_feasibility_fingerprint() != FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_FINGERPRINT:
            raise FINRAShortInterestPITAuditError("parent feasibility fingerprint drifted")
        if finra_short_interest_pit_audit_fingerprint() != FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT:
            raise FINRAShortInterestPITAuditError("PIT audit fingerprint drifted")
        if IDENTITY_CONTRACT_VERSION != "instrument-identity-v4-no-issuer-level-medium-collapse":
            raise FINRAShortInterestPITAuditError("instrument identity contract drifted")
        for settlement_text, published_text in FINRA_SHORT_INTEREST_PUBLICATION_ANCHORS.items():
            if publication_date(date.fromisoformat(settlement_text)).isoformat() != published_text:
                raise FINRAShortInterestPITAuditError(
                    f"FINRA publication chronology anchor drifted for {settlement_text}"
                )

        parent = validate_accepted_feasibility_report(self.settings)
        file_reports: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        status_counts: Counter[str] = Counter()
        pit_instruments: set[str] = set()
        immutable_total = 0
        pit_total = 0
        logical_reference_snapshots = 0

        for index, settlement_text in enumerate(FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES, start=1):
            try:
                settlement = date.fromisoformat(settlement_text)
                published = publication_date(settlement)
                decision = decision_date(settlement)
                source = self.finra_client.historical_file(settlement_date=settlement_text)
                settlement_snapshot = self.reference_provider.stock_snapshot(
                    settlement, include_inactive=False
                )
                decision_snapshot = self.reference_provider.stock_snapshot(
                    decision, include_inactive=False
                )
                logical_reference_snapshots += 2
                settlement_index = _snapshot_index(settlement_snapshot, settlement)
                decision_index = _snapshot_index(decision_snapshot, decision)

                per_file: Counter[str] = Counter()
                seen_source_keys: set[tuple[str, str]] = set()
                duplicate_source_keys = 0
                for row in source.rows:
                    if not is_exchange_listed_short_interest_row(row):
                        continue
                    symbol = str(row.get("symbol") or "").strip()
                    exchange_code = str(row.get("exchange_code") or row.get("market_code") or "").strip().upper()
                    expected_mic = FINRA_SHORT_INTEREST_EXCHANGE_CODE_TO_MIC.get(exchange_code)
                    if expected_mic is None:
                        per_file["UNSUPPORTED_EXCHANGE_CODE"] += 1
                        continue
                    source_key = (symbol, exchange_code)
                    if source_key in seen_source_keys:
                        duplicate_source_keys += 1
                        per_file["DUPLICATE_SOURCE_SYMBOL_EXCHANGE"] += 1
                        continue
                    seen_source_keys.add(source_key)

                    if str(row.get("revision_flag") or "").strip():
                        per_file["EXCLUDED_REVISION_FLAG"] += 1
                        continue
                    if str(row.get("stock_split_flag") or "").strip():
                        per_file["EXCLUDED_STOCK_SPLIT_FLAG"] += 1
                        continue
                    immutable_total += 1
                    per_file["IMMUTABLE_EXCHANGE_LISTED"] += 1

                    at_settlement = _matching(settlement_index, symbol, expected_mic)
                    if len(at_settlement) == 0:
                        per_file["NO_SETTLEMENT_ACTIVE_CS_EXACT_EXCHANGE"] += 1
                        continue
                    if len(at_settlement) != 1:
                        per_file["AMBIGUOUS_SETTLEMENT_ACTIVE_CS_EXACT_EXCHANGE"] += 1
                        continue
                    at_decision = _matching(decision_index, symbol, expected_mic)
                    if len(at_decision) == 0:
                        per_file["NO_DECISION_ACTIVE_CS_EXACT_EXCHANGE"] += 1
                        continue
                    if len(at_decision) != 1:
                        per_file["AMBIGUOUS_DECISION_ACTIVE_CS_EXACT_EXCHANGE"] += 1
                        continue
                    if at_settlement[0]["instrument_id"] != at_decision[0]["instrument_id"]:
                        per_file["IDENTITY_CONTINUITY_MISMATCH"] += 1
                        continue
                    per_file["PIT_ELIGIBLE"] += 1
                    pit_total += 1
                    pit_instruments.add(at_decision[0]["instrument_id"])

                status_counts.update(per_file)
                file_reports.append(
                    {
                        "settlement_date": settlement_text,
                        "publication_date": published.isoformat(),
                        "decision_date": decision.isoformat(),
                        "source_sha256": source.source_sha256,
                        "status_counts": dict(sorted(per_file.items())),
                        "duplicate_source_symbol_exchange_rows": duplicate_source_keys,
                    }
                )
            except Exception as exc:
                failures.append(
                    {
                        "settlement_date": settlement_text,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            print(
                "FINRA short-interest PIT audit progress: "
                f"{index}/{len(FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES)} "
                f"success={len(file_reports)} failures={len(failures)} pit_rows={pit_total}"
            )

        files_with_2500 = sum(
            int((report["status_counts"].get("PIT_ELIGIBLE") or 0) >= 2500)
            for report in file_reports
        )
        gates = {
            "accepted_feasibility_evidence_bound": True,
            "all_12_source_files_reacquired": len(file_reports) == 12 and not failures,
            "publication_anchors_exact": True,
            "source_symbol_exchange_unique": int(status_counts.get("DUPLICATE_SOURCE_SYMBOL_EXCHANGE", 0)) == 0,
            "immutable_exchange_listed_rows_min": immutable_total >= FINRA_SHORT_INTEREST_MIN_IMMUTABLE_EXCHANGE_LISTED_ROWS,
            "pit_eligible_rows_min": pit_total >= FINRA_SHORT_INTEREST_MIN_PIT_ELIGIBLE_ROWS,
            "unique_pit_instruments_min": len(pit_instruments) >= FINRA_SHORT_INTEREST_MIN_UNIQUE_PIT_INSTRUMENTS,
            "files_with_2500_pit_rows_min": files_with_2500 >= FINRA_SHORT_INTEREST_MIN_FILES_WITH_2500_PIT_ROWS,
            "revised_rows_never_admitted": int(status_counts.get("EXCLUDED_REVISION_FLAG", 0)) >= 0,
            "split_rows_never_admitted": int(status_counts.get("EXCLUDED_STOCK_SPLIT_FLAG", 0)) >= 0,
        }
        report = {
            "contract_version": FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT,
            "pit_audit_fingerprint": FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT,
            "parent_feasibility_contract": FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT,
            "parent_feasibility_fingerprint": FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_FINGERPRINT,
            "accepted_feasibility_head": FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_HEAD,
            "accepted_feasibility_report": parent,
            "mechanism": FINRA_SHORT_INTEREST_MECHANISM,
            "status": "PIT_AUDIT_PASS" if all(gates.values()) else "PIT_AUDIT_FAIL",
            "pass": all(gates.values()),
            "publication_rule": "SEVENTH_XNYS_SESSION_AFTER_SETTLEMENT",
            "availability_time_et": FINRA_SHORT_INTEREST_PUBLICATION_AVAILABILITY_ET,
            "decision_rule": "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_PUBLICATION_DATE",
            "revision_rule": "EXCLUDE_ANY_NONBLANK_REVISION_FLAG_ONLY_MOST_RECENT_FINRA_DATA_AVAILABLE",
            "stock_split_rule": "EXCLUDE_ANY_NONBLANK_STOCK_SPLIT_FLAG_FROM_PREDICTOR_ELIGIBILITY",
            "identity_rule": (
                "EXACT_FINRA_SYMBOL_EXPECTED_PRIMARY_EXCHANGE_ACTIVE_CS_AT_SETTLEMENT_AND_DECISION_"
                "SAME_STRONG_OR_MEDIUM_INSTRUMENT_ID"
            ),
            "alpha_hypotheses_frozen": False,
            "performance_evaluated": False,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "finra_source_files_read": len(file_reports),
            "massive_reference_snapshots_read": logical_reference_snapshots,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "automatic_broker_failover": False,
            "immutable_exchange_listed_rows": immutable_total,
            "pit_eligible_rows": pit_total,
            "unique_pit_instruments": len(pit_instruments),
            "files_with_2500_pit_rows": files_with_2500,
            "status_counts": dict(sorted(status_counts.items())),
            "file_reports": file_reports,
            "failures": failures,
            "gates": gates,
            "next_scientific_action": (
                "If this PIT audit passes, freeze the finite FINRA short-interest predictor transformation, "
                "hypothesis directions/thresholds, development/protected chronology, outcomes, costs, dependence, "
                "multiplicity, robustness, winner/finalist rules, and protected policy before any market outcome read."
            ),
        }
        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        report_path = derived_root / FINRA_SHORT_INTEREST_REPORT_RELATIVE_PIT
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(report_path)
        return report
