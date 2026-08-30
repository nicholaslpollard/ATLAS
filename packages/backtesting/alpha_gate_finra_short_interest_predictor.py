from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import exchange_calendars as xcals

from packages.backtesting.alpha_gate_finra_short_interest_pit_audit import (
    FINRA_SHORT_INTEREST_EXCHANGE_CODE_TO_MIC,
    FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT,
    FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT,
    FINRA_SHORT_INTEREST_REPORT_RELATIVE_PIT,
    _matching,
    _snapshot_index,
    decision_date,
    publication_date,
)
from packages.backtesting.alpha_gate_finra_short_interest_scientific_policy import (
    FINRA_SHORT_INTEREST_BUILD_PERCENTILE_MIN,
    FINRA_SHORT_INTEREST_COVER_PERCENTILE_MAX,
    FINRA_SHORT_INTEREST_CROWDED_PERCENTILE_MIN,
    FINRA_SHORT_INTEREST_DEVELOPMENT_LAST_SIGNAL,
    FINRA_SHORT_INTEREST_HYPOTHESES,
    FINRA_SHORT_INTEREST_MAX_ROWS_PER_CANDIDATE_PER_SETTLEMENT,
    FINRA_SHORT_INTEREST_PERFORMANCE_SIGNAL_START,
    FINRA_SHORT_INTEREST_PROTECTED_LAST_SIGNAL,
    FINRA_SHORT_INTEREST_PROTECTED_MIN_EVENT_ROWS,
    FINRA_SHORT_INTEREST_PROTECTED_MIN_SIGNAL_SESSIONS,
    FINRA_SHORT_INTEREST_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
    FINRA_SHORT_INTEREST_PROTECTED_START,
    FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
    FINRA_SHORT_INTEREST_SELECTION_MIN_EVENT_ROWS,
    FINRA_SHORT_INTEREST_SELECTION_MIN_SIGNAL_SESSIONS,
    FINRA_SHORT_INTEREST_SELECTION_MIN_UNIQUE_INSTRUMENTS,
    FINRA_SHORT_INTEREST_SOURCE_SETTLEMENT_CUTOFF,
    FINRA_SHORT_INTEREST_SOURCE_SETTLEMENT_START,
    finra_short_interest_scientific_fingerprint,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.finra_short_interest import (
    FINRAShortInterestClient,
    is_exchange_listed_short_interest_row,
)
from packages.providers.massive.reference_data import MassiveReferenceProvider


FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT = (
    "alpha-gate-finra-short-interest-predictor-v1-source-only-change-crowding-ranked"
)
FINRA_SHORT_INTEREST_PREDICTOR_ROOT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/finra_short_interest_predictor_v1"
)
FINRA_SHORT_INTEREST_PREDICTOR_ROWS_RELATIVE = (
    FINRA_SHORT_INTEREST_PREDICTOR_ROOT_RELATIVE / "predictor_rows.jsonl"
)
FINRA_SHORT_INTEREST_PREDICTOR_REPORT_RELATIVE = (
    FINRA_SHORT_INTEREST_PREDICTOR_ROOT_RELATIVE / "predictor_report.json"
)


class FINRAShortInterestPredictorError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _month_settlement_dates(start: date, end: date) -> tuple[date, ...]:
    cal = xcals.get_calendar("XNYS")
    out: set[date] = set()
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        month_start = date(year, month, 1)
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        sessions = tuple(
            value.date()
            for value in cal.sessions_in_range(
                month_start, next_month - timedelta(days=1)
            )
        )
        if sessions:
            mid = [value for value in sessions if value.day <= 15]
            if mid:
                out.add(mid[-1])
            out.add(sessions[-1])
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return tuple(sorted(value for value in out if start <= value <= end))


def frozen_settlement_dates() -> tuple[date, ...]:
    return _month_settlement_dates(
        date.fromisoformat(FINRA_SHORT_INTEREST_SOURCE_SETTLEMENT_START),
        date.fromisoformat(FINRA_SHORT_INTEREST_SOURCE_SETTLEMENT_CUTOFF),
    )


def _average_tie_percentiles(values: Iterable[float]) -> tuple[float, ...]:
    seq = tuple(float(value) for value in values)
    if not seq:
        return ()
    if len(seq) == 1:
        return (0.5,)
    indexed = sorted(enumerate(seq), key=lambda item: (item[1], item[0]))
    out = [0.0] * len(seq)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        average_rank = ((i + 1) + j) / 2.0
        percentile = (average_rank - 1.0) / (len(seq) - 1.0)
        for k in range(i, j):
            out[indexed[k][0]] = percentile
        i = j
    return tuple(out)


def _candidate(change_pct: float, crowding_pct: float) -> tuple[str, str] | None:
    crowded = crowding_pct >= FINRA_SHORT_INTEREST_CROWDED_PERCENTILE_MIN
    if change_pct >= FINRA_SHORT_INTEREST_BUILD_PERCENTILE_MIN:
        return (
            (
                "rapid_short_build_crowded_short"
                if crowded
                else "rapid_short_build_non_crowded_short"
            ),
            "SHORT",
        )
    if change_pct <= FINRA_SHORT_INTEREST_COVER_PERCENTILE_MAX:
        return (
            (
                "rapid_short_cover_crowded_long"
                if crowded
                else "rapid_short_cover_non_crowded_long"
            ),
            "LONG",
        )
    return None


def _stage(decision: date) -> str | None:
    if (
        date.fromisoformat(FINRA_SHORT_INTEREST_PERFORMANCE_SIGNAL_START)
        <= decision
        <= date.fromisoformat(FINRA_SHORT_INTEREST_DEVELOPMENT_LAST_SIGNAL)
    ):
        return "DEVELOPMENT"
    if (
        date.fromisoformat(FINRA_SHORT_INTEREST_PROTECTED_START)
        <= decision
        <= date.fromisoformat(FINRA_SHORT_INTEREST_PROTECTED_LAST_SIGNAL)
    ):
        return "PROTECTED"
    return None


def _sample_key(row: dict[str, Any]) -> str:
    payload = "|".join(
        (
            str(row["candidate_id"]),
            str(row["instrument_id"]),
            str(row["settlement_date"]),
            FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class FINRAShortInterestPredictorBuilder:
    """Build the full source-only FINRA predictor population before any outcome read."""

    def __init__(
        self,
        settings: AtlasSettings,
        finra_client: FINRAShortInterestClient,
        reference_provider: MassiveReferenceProvider,
        *,
        progress_callback: Any | None = None,
    ) -> None:
        self.settings = settings
        self.finra_client = finra_client
        self.reference_provider = reference_provider
        self.progress_callback = progress_callback
        self.derived_root = settings.resolved_path(settings.data.paths.derived)

    def _progress(self, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(message)

    def _validate_pit_evidence(self) -> str:
        path = self.derived_root / FINRA_SHORT_INTEREST_REPORT_RELATIVE_PIT
        if not path.is_file():
            raise FINRAShortInterestPredictorError(
                f"accepted PIT audit report is missing: {path}"
            )
        if sha256_file(path) != (
            "4fb3abc3e561fd4187efbf60967127230f14d37204d21b5ccb910c40a4469845"
        ):
            raise FINRAShortInterestPredictorError(
                "accepted PIT audit report SHA-256 drifted"
            )
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("contract_version") != FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT:
            raise FINRAShortInterestPredictorError("accepted PIT audit contract drifted")
        if report.get("pit_audit_fingerprint") != FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT:
            raise FINRAShortInterestPredictorError("accepted PIT audit fingerprint drifted")
        if report.get("status") != "PIT_AUDIT_PASS" or report.get("pass") is not True:
            raise FINRAShortInterestPredictorError("accepted PIT audit is not PASS")
        if int(report.get("target_outcome_rows_read", -1)) != 0:
            raise FINRAShortInterestPredictorError("accepted PIT audit read target outcomes")
        if int(report.get("protected_return_rows_read", -1)) != 0:
            raise FINRAShortInterestPredictorError("accepted PIT audit read protected returns")
        if report.get("protected_holdout_consumed") is not False:
            raise FINRAShortInterestPredictorError(
                "accepted PIT audit consumed protected holdout"
            )
        return str(path)

    def run(self) -> dict[str, Any]:
        if (
            finra_short_interest_scientific_fingerprint()
            != FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT
        ):
            raise FINRAShortInterestPredictorError(
                "frozen FINRA scientific fingerprint drifted"
            )
        pit_report_path = self._validate_pit_evidence()
        settlement_dates = frozen_settlement_dates()
        if not settlement_dates:
            raise FINRAShortInterestPredictorError(
                "frozen FINRA settlement schedule is empty"
            )

        diagnostics: Counter[str] = Counter()
        source_rows = 0
        logical_reference_snapshots = 0
        candidate_rows: list[dict[str, Any]] = []
        candidate_ids = {spec.candidate_id for spec in FINRA_SHORT_INTEREST_HYPOTHESES}

        for index, settlement in enumerate(settlement_dates, start=1):
            source = self.finra_client.historical_file(
                settlement_date=settlement.isoformat()
            )
            published = publication_date(settlement)
            decision = decision_date(settlement)
            settlement_snapshot = self.reference_provider.stock_snapshot(
                settlement, include_inactive=False
            )
            decision_snapshot = self.reference_provider.stock_snapshot(
                decision, include_inactive=False
            )
            logical_reference_snapshots += 2
            settlement_index = _snapshot_index(settlement_snapshot, settlement)
            decision_index = _snapshot_index(decision_snapshot, decision)
            ready: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()

            for row in source.rows:
                source_rows += 1
                if not is_exchange_listed_short_interest_row(row):
                    diagnostics["NON_EXCHANGE_LISTED"] += 1
                    continue
                symbol = str(row.get("symbol") or "").strip()
                exchange_code = str(
                    row.get("exchange_code") or row.get("market_code") or ""
                ).strip().upper()
                expected_mic = FINRA_SHORT_INTEREST_EXCHANGE_CODE_TO_MIC.get(
                    exchange_code
                )
                if not symbol or expected_mic is None:
                    diagnostics["UNSUPPORTED_SOURCE_IDENTITY"] += 1
                    continue
                source_key = (symbol, exchange_code)
                if source_key in seen:
                    diagnostics["DUPLICATE_SOURCE_SYMBOL_EXCHANGE"] += 1
                    continue
                seen.add(source_key)
                if str(row.get("revision_flag") or "").strip():
                    diagnostics["EXCLUDED_REVISION_FLAG"] += 1
                    continue
                if str(row.get("stock_split_flag") or "").strip():
                    diagnostics["EXCLUDED_STOCK_SPLIT_FLAG"] += 1
                    continue
                previous = row.get("previous_short_position")
                days_to_cover = row.get("days_to_cover")
                if previous is None:
                    diagnostics["MISSING_PREVIOUS_SHORT"] += 1
                    continue
                try:
                    dtc = float(days_to_cover)
                except (TypeError, ValueError):
                    diagnostics["MISSING_DAYS_TO_COVER"] += 1
                    continue
                if not math.isfinite(dtc) or dtc <= 0:
                    diagnostics["INVALID_DAYS_TO_COVER"] += 1
                    continue
                at_settlement = _matching(settlement_index, symbol, expected_mic)
                at_decision = _matching(decision_index, symbol, expected_mic)
                if len(at_settlement) != 1:
                    diagnostics["NO_OR_AMBIGUOUS_SETTLEMENT_IDENTITY"] += 1
                    continue
                if len(at_decision) != 1:
                    diagnostics["NO_OR_AMBIGUOUS_DECISION_IDENTITY"] += 1
                    continue
                if at_settlement[0]["instrument_id"] != at_decision[0]["instrument_id"]:
                    diagnostics["IDENTITY_CONTINUITY_MISMATCH"] += 1
                    continue
                current = int(row["current_short_position"])
                previous_int = int(previous)
                feature = math.log((current + 1.0) / (previous_int + 1.0))
                ready.append(
                    {
                        "symbol": symbol,
                        "exchange_code": exchange_code,
                        "primary_exchange": expected_mic,
                        "instrument_id": at_decision[0]["instrument_id"],
                        "identity_quality": at_decision[0]["identity_quality"],
                        "current_short_position": current,
                        "previous_short_position": previous_int,
                        "position_change_log_ratio": feature,
                        "days_to_cover": dtc,
                    }
                )

            if len(ready) >= 2:
                change_ranks = _average_tie_percentiles(
                    item["position_change_log_ratio"] for item in ready
                )
                crowding_ranks = _average_tie_percentiles(
                    item["days_to_cover"] for item in ready
                )
                stage = _stage(decision)
                buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
                if stage is not None:
                    for item, change_pct, crowd_pct in zip(
                        ready, change_ranks, crowding_ranks, strict=True
                    ):
                        classified = _candidate(change_pct, crowd_pct)
                        if classified is None:
                            diagnostics["OUTSIDE_FROZEN_CHANGE_TAILS"] += 1
                            continue
                        candidate_id, direction = classified
                        if candidate_id not in candidate_ids:
                            raise FINRAShortInterestPredictorError(
                                "candidate classification drifted"
                            )
                        record = {
                            "contract_version": FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT,
                            "scientific_fingerprint": FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
                            "candidate_id": candidate_id,
                            "direction": direction,
                            "stage": stage,
                            "settlement_date": settlement.isoformat(),
                            "publication_date": published.isoformat(),
                            "decision_session": decision.isoformat(),
                            "ticker": item["symbol"],
                            "instrument_id": item["instrument_id"],
                            "identity_quality": item["identity_quality"],
                            "primary_exchange": item["primary_exchange"],
                            "current_short_position": item["current_short_position"],
                            "previous_short_position": item["previous_short_position"],
                            "position_change_log_ratio": item["position_change_log_ratio"],
                            "days_to_cover": item["days_to_cover"],
                            "change_percentile": change_pct,
                            "crowding_percentile": crowd_pct,
                        }
                        buckets[candidate_id].append(record)
                for candidate_id, rows in buckets.items():
                    rows.sort(key=_sample_key)
                    selected = rows[
                        :FINRA_SHORT_INTEREST_MAX_ROWS_PER_CANDIDATE_PER_SETTLEMENT
                    ]
                    diagnostics[f"SAMPLED_{candidate_id}"] += len(selected)
                    candidate_rows.extend(selected)

            self._progress(
                f"FINRA predictor reconstruction: {index}/{len(settlement_dates)} "
                f"rows={len(candidate_rows)}"
            )

        candidate_rows.sort(
            key=lambda row: (
                row["decision_session"],
                row["candidate_id"],
                row["instrument_id"],
                row["ticker"],
            )
        )
        if not candidate_rows:
            raise FINRAShortInterestPredictorError(
                "FINRA source-only predictor population is empty"
            )

        stage_counts = Counter(str(row["stage"]) for row in candidate_rows)
        candidate_counts = Counter(str(row["candidate_id"]) for row in candidate_rows)
        source_gates: dict[str, dict[str, bool]] = {}
        for spec in FINRA_SHORT_INTEREST_HYPOTHESES:
            dev = [
                row
                for row in candidate_rows
                if row["candidate_id"] == spec.candidate_id
                and row["stage"] == "DEVELOPMENT"
            ]
            protected = [
                row
                for row in candidate_rows
                if row["candidate_id"] == spec.candidate_id
                and row["stage"] == "PROTECTED"
            ]
            source_gates[spec.candidate_id] = {
                "development_min_rows": len(dev)
                >= FINRA_SHORT_INTEREST_SELECTION_MIN_EVENT_ROWS,
                "development_min_signal_sessions": len(
                    {row["decision_session"] for row in dev}
                )
                >= FINRA_SHORT_INTEREST_SELECTION_MIN_SIGNAL_SESSIONS,
                "development_min_unique_instruments": len(
                    {row["instrument_id"] for row in dev}
                )
                >= FINRA_SHORT_INTEREST_SELECTION_MIN_UNIQUE_INSTRUMENTS,
                "protected_min_rows": len(protected)
                >= FINRA_SHORT_INTEREST_PROTECTED_MIN_EVENT_ROWS,
                "protected_min_signal_sessions": len(
                    {row["decision_session"] for row in protected}
                )
                >= FINRA_SHORT_INTEREST_PROTECTED_MIN_SIGNAL_SESSIONS,
                "protected_min_unique_instruments": len(
                    {row["instrument_id"] for row in protected}
                )
                >= FINRA_SHORT_INTEREST_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
            }
        source_pass = all(all(gates.values()) for gates in source_gates.values())

        rows_path = self.derived_root / FINRA_SHORT_INTEREST_PREDICTOR_ROWS_RELATIVE
        rows_text = "".join(_canonical_json(row) + "\n" for row in candidate_rows)
        atomic_write_text(rows_path, rows_text)
        report = {
            "contract_version": FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT,
            "scientific_fingerprint": FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
            "status": (
                "SOURCE_ONLY_PREDICTOR_PASS"
                if source_pass
                else "SOURCE_ONLY_PREDICTOR_FAIL"
            ),
            "pass": source_pass,
            "accepted_pit_audit_report_path": pit_report_path,
            "accepted_pit_audit_report_sha256": (
                "4fb3abc3e561fd4187efbf60967127230f14d37204d21b5ccb910c40a4469845"
            ),
            "settlement_dates": [value.isoformat() for value in settlement_dates],
            "finra_source_files_read": len(settlement_dates),
            "massive_reference_snapshots_read": logical_reference_snapshots,
            "source_rows_seen": source_rows,
            "predictor_rows": len(candidate_rows),
            "stage_counts": dict(sorted(stage_counts.items())),
            "candidate_counts": dict(sorted(candidate_counts.items())),
            "diagnostics": dict(sorted(diagnostics.items())),
            "source_only_gates": source_gates,
            "predictor_rows_sha256": hashlib.sha256(
                rows_text.encode("utf-8")
            ).hexdigest(),
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "automatic_broker_failover": False,
            "phase33_signal_to_trade_authority": False,
        }
        report_path = self.derived_root / FINRA_SHORT_INTEREST_PREDICTOR_REPORT_RELATIVE
        atomic_write_text(
            report_path, json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        report["report_path"] = str(report_path)
        report["predictor_rows_path"] = str(rows_path)
        return report
