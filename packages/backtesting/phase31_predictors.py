from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import MarketCalendar, get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.providers.massive.phase31 import parse_form4_date

from .phase31_acquisition import phase31_month_shards
from .phase31_acquisition_v3 import PHASE31_ACQUISITION_V3_CONTRACT_VERSION
from .phase31_policy import (
    PHASE31_ACCESSION_CODE_PURITY_REQUIRED,
    PHASE31_ALLOW_AFF_10B5_ONE_FALSE_OR_NULL,
    PHASE31_CLUSTER_LOOKBACK_SESSIONS,
    PHASE31_CLUSTER_MIN_DISTINCT_ACCESSIONS,
    PHASE31_CLUSTER_MIN_DISTINCT_OWNERS,
    PHASE31_CONTRADICTORY_TICKER_SESSION_POLICY,
    PHASE31_DEVELOPMENT_LAST_SIGNAL,
    PHASE31_ELIGIBLE_FORM_TYPE,
    PHASE31_ELIGIBLE_RECORD_TYPE,
    PHASE31_ELIGIBLE_SECURITY_TYPE_VALUES,
    PHASE31_ELIGIBLE_TRANSACTION_CODES,
    PHASE31_EVENT_UNIT,
    PHASE31_EXCLUDE_AFF_10B5_ONE_TRUE,
    PHASE31_EXCLUDE_EQUITY_SWAP_TRUE,
    PHASE31_EXCLUDE_NOT_SUBJECT_TO_SECTION16_TRUE,
    PHASE31_OUTCOME_HORIZON_SESSIONS,
    PHASE31_PROTECTED_LAST_SIGNAL,
    PHASE31_PROTECTED_START,
    PHASE31_PURCHASE_ACQUIRED_DISPOSED,
    PHASE31_REQUIRE_ANY_SECTION16_ROLE,
    PHASE31_REQUIRE_EXACTLY_ONE_PROVIDER_NATIVE_TICKER,
    PHASE31_REQUIRE_POSITIVE_PRICE,
    PHASE31_REQUIRE_POSITIVE_SHARES,
    PHASE31_REQUIRED_TRANSACTION_TIMELINESS,
    PHASE31_RESEARCH_SIGNAL_START,
    PHASE31_SALE_ACQUIRED_DISPOSED,
    PHASE31_SOURCE_HISTORY_START,
    PHASE31_PROTECTED_OUTCOME_END,
    phase31_policy_fingerprint,
)


PHASE31_PREDICTOR_REPORT_CONTRACT_VERSION = (
    "phase31-predictor-report-v1-form4-pure-open-market-pit-identity-no-market-outcomes"
)
PHASE31_DEVELOPMENT_PREDICTOR_CONTRACT_VERSION = (
    "phase31-development-form4-events-v1-pit-identity-no-market-outcomes"
)
PHASE31_PROTECTED_PREDICTOR_CONTRACT_VERSION = (
    "phase31-protected-form4-events-v1-pit-identity-no-market-outcomes"
)

# Frozen from the first accepted full-history acquisition on 2026-08-28.
PHASE31_ACCEPTED_FULL_HISTORY_RAW_ROWS = 2_993_648
PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS = 2_992_608
PHASE31_ACCEPTED_FULL_HISTORY_QUARANTINED_ROWS = 1_040
PHASE31_ACCEPTED_FULL_HISTORY_CONTAMINATED_ACCESSIONS = 187
PHASE31_ACCEPTED_FULL_HISTORY_CHRONOLOGY_SEEDS = 233
PHASE31_ACCEPTED_FULL_HISTORY_MISSING_CODE_SEEDS = 15
PHASE31_ACCEPTED_FULL_HISTORY_MONTH_SHARDS = 62

PHASE31_PREDICTOR_FIELDS = (
    "contract_version",
    "phase31_policy_fingerprint",
    "ticker",
    "instrument_id",
    "composite_figi",
    "direction",
    "event_direction",
    "decision_session",
    "exit_session",
    "broad_candidate_id",
    "cluster_candidate_id",
    "is_clustered",
    "event_accession_count",
    "event_owner_count",
    "cluster_accession_count",
    "cluster_owner_count",
    "accession_numbers_json",
    "owner_ciks_json",
    "issuer_ciks_json",
    "filing_dates_json",
    "transaction_row_count",
    "transaction_shares_sum",
    "transaction_gross_value_sum",
)

PHASE31_FORBIDDEN_MARKET_FIELDS = (
    "entry_open",
    "exit_close",
    "stock_return",
    "spy_return",
    "forward_return",
    "directional_return",
    "alpha_return",
    "future_close",
)


class Phase31PredictorError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class QualifiedAccession:
    accession_number: str
    filing_date: date
    ticker: str
    direction: str
    owner_cik: str
    issuer_cik: str
    transaction_row_count: int
    transaction_shares_sum: float
    transaction_gross_value_sum: float


@dataclass(frozen=True, slots=True)
class IdentityInterval:
    instrument_id: str
    ticker: str
    valid_from_date: date
    valid_to_date_exclusive: date | None
    composite_figi: str


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase31PredictorError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase31PredictorError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase31PredictorError(f"{label} must be a JSON object: {path}")
    return payload


def _nonblank(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _finite_positive(value: object) -> float | None:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or result <= 0.0:
        return None
    return result


def classify_accession(
    rows: Iterable[dict[str, Any]],
) -> tuple[QualifiedAccession | None, str | None]:
    materialized = tuple(rows)
    if not materialized:
        return None, "EMPTY_ACCESSION"

    transaction_rows = tuple(
        row for row in materialized if row.get("record_type") == PHASE31_ELIGIBLE_RECORD_TYPE
    )
    if not transaction_rows:
        return None, "NO_TRANSACTION_ROWS"

    accession_values = {_nonblank(row.get("accession_number")) for row in transaction_rows}
    if None in accession_values or len(accession_values) != 1:
        return None, "ACCESSION_ID_INCONSISTENT"
    accession = next(iter(accession_values))
    assert accession is not None

    if any(row.get("form_type") != PHASE31_ELIGIBLE_FORM_TYPE for row in transaction_rows):
        return None, "FORM_TYPE_INELIGIBLE"

    codes = {_nonblank(row.get("transaction_code")) for row in transaction_rows}
    if None in codes or len(codes) != 1 or next(iter(codes)) not in PHASE31_ELIGIBLE_TRANSACTION_CODES:
        return None, "TRANSACTION_CODE_NOT_PURE_P_OR_S"
    if not PHASE31_ACCESSION_CODE_PURITY_REQUIRED:
        raise Phase31PredictorError("Phase31 accession-code purity unexpectedly disabled")
    code = next(iter(codes))
    assert code is not None
    direction = "PURCHASE" if code == "P" else "SALE"
    required_acquired_disposed = (
        PHASE31_PURCHASE_ACQUIRED_DISPOSED if direction == "PURCHASE" else PHASE31_SALE_ACQUIRED_DISPOSED
    )

    filing_dates: set[date] = set()
    ticker_values: set[str] = set()
    owner_values: set[str] = set()
    issuer_values: set[str] = set()
    shares_sum = 0.0
    gross_value_sum = 0.0
    any_role = False

    for row in transaction_rows:
        try:
            filing_dates.add(parse_form4_date(row.get("filing_date"), field="filing_date"))
        except Exception:
            return None, "FILING_DATE_INVALID"

        if row.get("security_type") not in PHASE31_ELIGIBLE_SECURITY_TYPE_VALUES:
            return None, "SECURITY_TYPE_INELIGIBLE"
        if row.get("transaction_acquired_disposed") != required_acquired_disposed:
            return None, "ACQUIRED_DISPOSED_MISMATCH"

        shares = _finite_positive(row.get("transaction_shares"))
        price = _finite_positive(row.get("transaction_price_per_share"))
        if PHASE31_REQUIRE_POSITIVE_SHARES and shares is None:
            return None, "SHARES_NOT_POSITIVE"
        if PHASE31_REQUIRE_POSITIVE_PRICE and price is None:
            return None, "PRICE_NOT_POSITIVE"
        assert shares is not None and price is not None
        shares_sum += shares
        gross_value_sum += shares * price

        if row.get("transaction_timeliness") != PHASE31_REQUIRED_TRANSACTION_TIMELINESS:
            return None, "TRANSACTION_NOT_TIMELY_O"

        aff = row.get("aff_10b5_one")
        if PHASE31_EXCLUDE_AFF_10B5_ONE_TRUE and aff is True:
            return None, "AFF_10B5_ONE_TRUE"
        if PHASE31_ALLOW_AFF_10B5_ONE_FALSE_OR_NULL and aff not in (False, None):
            return None, "AFF_10B5_ONE_NOT_FALSE_OR_NULL"
        if PHASE31_EXCLUDE_EQUITY_SWAP_TRUE and row.get("equity_swap_involved") is True:
            return None, "EQUITY_SWAP_TRUE"
        if (
            PHASE31_EXCLUDE_NOT_SUBJECT_TO_SECTION16_TRUE
            and row.get("not_subject_to_section_16") is True
        ):
            return None, "NOT_SUBJECT_TO_SECTION16_TRUE"

        any_role = any_role or any(
            row.get(field) is True
            for field in ("is_officer", "is_director", "is_ten_percent_owner")
        )

        tickers = row.get("tickers")
        if (
            PHASE31_REQUIRE_EXACTLY_ONE_PROVIDER_NATIVE_TICKER
            and (not isinstance(tickers, list) or len(tickers) != 1)
        ):
            return None, "TICKER_ASSOCIATION_NOT_EXACTLY_ONE"
        if not isinstance(tickers, list) or len(tickers) != 1:
            return None, "TICKER_ASSOCIATION_NOT_EXACTLY_ONE"
        ticker = _nonblank(tickers[0])
        if ticker is None:
            return None, "TICKER_ASSOCIATION_INVALID"
        ticker_values.add(ticker)

        owner = _nonblank(row.get("owner_cik"))
        issuer = _nonblank(row.get("issuer_cik"))
        if owner is None or issuer is None:
            return None, "CIK_MISSING"
        owner_values.add(owner)
        issuer_values.add(issuer)

    if PHASE31_REQUIRE_ANY_SECTION16_ROLE and not any_role:
        return None, "NO_SECTION16_ROLE"
    if len(filing_dates) != 1:
        return None, "FILING_DATE_INCONSISTENT"
    if len(ticker_values) != 1:
        return None, "ACCESSION_TICKER_INCONSISTENT"
    if len(owner_values) != 1:
        return None, "OWNER_CIK_INCONSISTENT"
    if len(issuer_values) != 1:
        return None, "ISSUER_CIK_INCONSISTENT"

    return (
        QualifiedAccession(
            accession_number=accession,
            filing_date=next(iter(filing_dates)),
            ticker=next(iter(ticker_values)),
            direction=direction,
            owner_cik=next(iter(owner_values)),
            issuer_cik=next(iter(issuer_values)),
            transaction_row_count=len(transaction_rows),
            transaction_shares_sum=shares_sum,
            transaction_gross_value_sum=gross_value_sum,
        ),
        None,
    )


def resolve_identity_interval(
    *,
    ticker: str,
    decision_session: date,
    exit_session: date,
    intervals: dict[str, tuple[IdentityInterval, ...]],
) -> tuple[IdentityInterval | None, str | None]:
    candidates = [
        item
        for item in intervals.get(ticker, ())
        if item.valid_from_date <= decision_session
        and (item.valid_to_date_exclusive is None or decision_session < item.valid_to_date_exclusive)
    ]
    if not candidates:
        return None, "PIT_IDENTITY_NOT_RESOLVED"
    identities = {item.instrument_id for item in candidates}
    if len(candidates) != 1 or len(identities) != 1:
        return None, "PIT_IDENTITY_AMBIGUOUS"
    item = candidates[0]
    if item.valid_to_date_exclusive is not None and exit_session >= item.valid_to_date_exclusive:
        return None, "PIT_IDENTITY_INTERVAL_DOES_NOT_COVER_EXIT"
    return item, None


def _write_immutable_parquet(
    settings: AtlasSettings,
    *,
    records: list[dict[str, Any]],
    target: Path,
) -> tuple[str, bool]:
    target.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame.from_records(records, columns=list(PHASE31_PREDICTOR_FIELDS))
    temp = atomic_target(target)
    temp.unlink(missing_ok=True)
    con = connect_utc(":memory:")
    try:
        con.register("phase31_predictor_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"""
            COPY (
                SELECT * FROM phase31_predictor_write
                ORDER BY decision_session, ticker, direction
            ) TO {sql_string(temp)}
            (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
            """
        )
    finally:
        con.close()
    new_sha = sha256_file(temp)
    if target.is_file():
        existing = sha256_file(target)
        if existing != new_sha:
            temp.unlink(missing_ok=True)
            raise Phase31PredictorError(f"immutable Phase31 predictor evidence drifted: {target}")
        temp.unlink(missing_ok=True)
        return existing, True
    promote(temp, target)
    actual = sha256_file(target)
    if actual != new_sha:
        raise Phase31PredictorError(f"Phase31 predictor hash mismatch after write: {target}")
    return actual, False


class Phase31Form4PredictorBuilder:
    """Construct frozen Form-4 predictors without reading market outcomes."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.paths = MarketDataPaths(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.phase_root = derived / "strategy_evaluation" / "phase31" / "v1"
        self.history_root = self.phase_root / "form4_history"
        self.authoritative_root = self.history_root / "authoritative"
        self.predictor_root = self.phase_root / "predictors"

    def acquisition_report_path(self) -> Path:
        return self.history_root / "phase31_form4_acquisition.json"

    def development_path(self) -> Path:
        return self.predictor_root / "development_form4_events.parquet"

    def protected_path(self) -> Path:
        return self.predictor_root / "protected_form4_events.parquet"

    def report_path(self) -> Path:
        return self.predictor_root / "predictor_report.json"

    def _validate_acquisition(self) -> tuple[dict[str, Any], str]:
        report = _read_json(self.acquisition_report_path(), label="Phase31 acquisition report")
        exact = {
            "contract": report.get("contract_version") == PHASE31_ACQUISITION_V3_CONTRACT_VERSION,
            "policy": report.get("phase31_policy_fingerprint") == phase31_policy_fingerprint(),
            "pass": report.get("pass") is True,
            "months": int(report.get("month_shards", -1)) == PHASE31_ACCEPTED_FULL_HISTORY_MONTH_SHARDS,
            "raw": int(report.get("raw_rows", -1)) == PHASE31_ACCEPTED_FULL_HISTORY_RAW_ROWS,
            "authoritative": int(report.get("authoritative_rows", -1))
            == PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS,
            "quarantine": int(report.get("quarantined_rows", -1))
            == PHASE31_ACCEPTED_FULL_HISTORY_QUARANTINED_ROWS,
            "contaminated": int(report.get("contaminated_accessions", -1))
            == PHASE31_ACCEPTED_FULL_HISTORY_CONTAMINATED_ACCESSIONS,
            "chronology_seeds": int(report.get("chronology_violation_seed_rows", -1))
            == PHASE31_ACCEPTED_FULL_HISTORY_CHRONOLOGY_SEEDS,
            "missing_code_seeds": int(report.get("missing_transaction_code_seed_rows", -1))
            == PHASE31_ACCEPTED_FULL_HISTORY_MISSING_CODE_SEEDS,
            "target_outcomes": int(report.get("target_outcome_rows_read", -1)) == 0,
            "protected_candidates": int(report.get("protected_candidate_rows_read", -1)) == 0,
            "protected_returns": int(report.get("protected_return_rows_read", -1)) == 0,
            "provider_writes": int(report.get("provider_writes", -1)) == 0,
            "broker_reads": int(report.get("broker_reads", -1)) == 0,
            "broker_writes": int(report.get("broker_writes", -1)) == 0,
            "orders": int(report.get("order_writes", -1)) == 0,
            "paper": int(report.get("paper_submits", -1)) == 0,
            "live": int(report.get("live_writes", -1)) == 0,
            "automation": int(report.get("automation_writes", -1)) == 0,
        }
        if not all(exact.values()):
            failed = sorted(name for name, ok in exact.items() if not ok)
            raise Phase31PredictorError("Phase31 acquisition lineage failed closed: " + ", ".join(failed))

        shard_records = report.get("shards")
        if not isinstance(shard_records, list) or len(shard_records) != 62:
            raise Phase31PredictorError("Phase31 acquisition shard lineage is incomplete")
        expected_labels = tuple(item.label for item in phase31_month_shards())
        hasher = hashlib.sha256()
        for expected, item in zip(expected_labels, shard_records, strict=True):
            if not isinstance(item, dict) or item.get("label") != expected:
                raise Phase31PredictorError("Phase31 acquisition shard order drifted")
            expected_sha = str(item.get("authoritative_sha256") or "")
            expected_rows = int(item.get("authoritative_rows", -1))
            path = self.authoritative_root / f"{expected}.jsonl"
            if not path.is_file() or len(expected_sha) != 64:
                raise Phase31PredictorError(f"missing authoritative Phase31 shard: {expected}")
            actual_sha = sha256_file(path)
            if actual_sha != expected_sha:
                raise Phase31PredictorError(f"authoritative Phase31 shard hash mismatch: {expected}")
            if expected_rows < 0:
                raise Phase31PredictorError(f"invalid authoritative row count: {expected}")
            hasher.update(expected.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(expected_sha.encode("ascii"))
            hasher.update(b"\0")
            hasher.update(str(expected_rows).encode("ascii"))
            hasher.update(b"\n")
        return report, hasher.hexdigest()

    def _session_grid(self) -> tuple[tuple[date, ...], dict[date, int]]:
        start = date.fromisoformat(PHASE31_SOURCE_HISTORY_START)
        end = date.fromisoformat(PHASE31_PROTECTED_OUTCOME_END)
        sessions = tuple(self.calendar.sessions_in_range(start, end))
        if not sessions:
            raise Phase31PredictorError("Phase31 XNYS session grid is empty")
        return sessions, {session: index for index, session in enumerate(sessions)}

    def _identity_intervals(self) -> tuple[dict[str, tuple[IdentityInterval, ...]], str]:
        path = self.paths.authoritative_ticker_intervals_file()
        if not path.is_file():
            raise Phase31PredictorError(
                "missing authoritative ticker intervals; Phase31 refuses exact-ticker fallback identity"
            )
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT instrument_id, ticker, valid_from_date, valid_to_date_exclusive,
                       query_identifier, query_identifier_type, continuity_authority, evidence_source
                FROM read_parquet({sql_string(path)})
                WHERE continuity_authority = true
                  AND query_identifier_type = 'composite_figi'
                  AND evidence_source = 'massive_ticker_events'
                ORDER BY ticker, valid_from_date, instrument_id
                """
            ).fetchall()
        finally:
            con.close()
        by_ticker: dict[str, list[IdentityInterval]] = defaultdict(list)
        for instrument_id, ticker, valid_from, valid_to, query_id, _, _, _ in rows:
            ticker_text = _nonblank(ticker)
            figi = _nonblank(query_id)
            if ticker_text is None or figi is None:
                continue
            by_ticker[ticker_text].append(
                IdentityInterval(
                    instrument_id=str(instrument_id),
                    ticker=ticker_text,
                    valid_from_date=valid_from,
                    valid_to_date_exclusive=valid_to,
                    composite_figi=figi,
                )
            )
        return {key: tuple(value) for key, value in by_ticker.items()}, sha256_file(path)

    def _qualified_accessions(
        self,
    ) -> tuple[list[QualifiedAccession], Counter[str], int]:
        qualified: list[QualifiedAccession] = []
        exclusions: Counter[str] = Counter()
        rows_seen = 0
        seen_accessions: set[str] = set()

        for shard in phase31_month_shards():
            path = self.authoritative_root / f"{shard.label}.jsonl"
            groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            try:
                handle = path.open("r", encoding="utf-8")
            except OSError as exc:
                raise Phase31PredictorError(f"cannot read authoritative shard: {path}") from exc
            with handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise Phase31PredictorError(
                            f"invalid JSON in authoritative shard {shard.label}:{line_number}"
                        ) from exc
                    if not isinstance(row, dict):
                        raise Phase31PredictorError(
                            f"non-object row in authoritative shard {shard.label}:{line_number}"
                        )
                    accession = _nonblank(row.get("accession_number"))
                    if accession is None:
                        raise Phase31PredictorError("authoritative Form-4 row lacks accession_number")
                    groups[accession].append(row)
                    rows_seen += 1

            overlap = seen_accessions.intersection(groups)
            if overlap:
                raise Phase31PredictorError(
                    "Form-4 accession spans monthly filing-date shards; predictor refuses implicit merge: "
                    + sorted(overlap)[0]
                )
            seen_accessions.update(groups)
            for accession in sorted(groups):
                result, reason = classify_accession(groups[accession])
                if result is None:
                    exclusions[reason or "UNKNOWN_ACCESSION_EXCLUSION"] += 1
                else:
                    qualified.append(result)

        if rows_seen != PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS:
            raise Phase31PredictorError(
                f"authoritative row scan mismatch: {rows_seen} != {PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS}"
            )
        return qualified, exclusions, rows_seen

    def run(self) -> dict[str, Any]:
        _, authoritative_lineage_sha = self._validate_acquisition()
        sessions, session_index = self._session_grid()
        intervals, identity_sha = self._identity_intervals()
        qualified, exclusions, rows_seen = self._qualified_accessions()

        research_start = date.fromisoformat(PHASE31_RESEARCH_SIGNAL_START)
        development_last = date.fromisoformat(PHASE31_DEVELOPMENT_LAST_SIGNAL)
        protected_start = date.fromisoformat(PHASE31_PROTECTED_START)
        protected_last = date.fromisoformat(PHASE31_PROTECTED_LAST_SIGNAL)

        grouped: dict[tuple[str, date, str], list[QualifiedAccession]] = defaultdict(list)
        for item in qualified:
            decision_pos = bisect_right(sessions, item.filing_date)
            if decision_pos >= len(sessions):
                exclusions["NO_DECISION_SESSION_IN_FROZEN_GRID"] += 1
                continue
            decision = sessions[decision_pos]
            exit_pos = decision_pos + PHASE31_OUTCOME_HORIZON_SESSIONS
            if exit_pos >= len(sessions):
                exclusions["NO_T20_EXIT_IN_FROZEN_GRID"] += 1
                continue
            if decision > protected_last:
                exclusions["DECISION_AFTER_LAST_COMPLETE_SIGNAL"] += 1
                continue
            grouped[(item.ticker, decision, item.direction)].append(item)

        contradictory = {
            (ticker, decision)
            for ticker, decision, _ in grouped
            if len({direction for t, d, direction in grouped if t == ticker and d == decision}) > 1
        }
        if PHASE31_CONTRADICTORY_TICKER_SESSION_POLICY != "EXCLUDE":
            raise Phase31PredictorError("Phase31 contradictory ticker/session policy drifted")

        resolved_events: list[dict[str, Any]] = []
        for (ticker, decision, direction), accessions in sorted(
            grouped.items(), key=lambda item: (item[0][1], item[0][0], item[0][2])
        ):
            if (ticker, decision) in contradictory:
                exclusions["CONTRADICTORY_PURCHASE_SALE_TICKER_SESSION"] += 1
                continue
            dpos = session_index[decision]
            exit_session = sessions[dpos + PHASE31_OUTCOME_HORIZON_SESSIONS]
            identity, reason = resolve_identity_interval(
                ticker=ticker,
                decision_session=decision,
                exit_session=exit_session,
                intervals=intervals,
            )
            if identity is None:
                exclusions[reason or "PIT_IDENTITY_EXCLUDED"] += 1
                continue

            accession_ids = sorted({item.accession_number for item in accessions})
            owners = sorted({item.owner_cik for item in accessions})
            issuers = sorted({item.issuer_cik for item in accessions})
            filing_dates = sorted({item.filing_date.isoformat() for item in accessions})
            tx_rows = sum(item.transaction_row_count for item in accessions)
            shares = sum(item.transaction_shares_sum for item in accessions)
            gross = sum(item.transaction_gross_value_sum for item in accessions)
            resolved_events.append(
                {
                    "ticker": ticker,
                    "instrument_id": identity.instrument_id,
                    "composite_figi": identity.composite_figi,
                    "direction": "LONG" if direction == "PURCHASE" else "SHORT",
                    "event_direction": direction,
                    "decision_session": decision,
                    "decision_index": dpos,
                    "exit_session": exit_session,
                    "accession_numbers": accession_ids,
                    "owner_ciks": owners,
                    "issuer_ciks": issuers,
                    "filing_dates": filing_dates,
                    "transaction_row_count": tx_rows,
                    "transaction_shares_sum": shares,
                    "transaction_gross_value_sum": gross,
                }
            )

        history: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        development_records: list[dict[str, Any]] = []
        protected_records: list[dict[str, Any]] = []
        candidate_counts: Counter[str] = Counter()
        policy_fp = phase31_policy_fingerprint()

        for event in resolved_events:
            key = (str(event["ticker"]), str(event["event_direction"]))
            current_index = int(event["decision_index"])
            lower = current_index - PHASE31_CLUSTER_LOOKBACK_SESSIONS + 1
            prior = [item for item in history[key] if int(item["decision_index"]) >= lower]
            cluster_accessions = set(event["accession_numbers"])
            cluster_owners = set(event["owner_ciks"])
            for item in prior:
                cluster_accessions.update(item["accession_numbers"])
                cluster_owners.update(item["owner_ciks"])
            clustered = (
                len(cluster_owners) >= PHASE31_CLUSTER_MIN_DISTINCT_OWNERS
                and len(cluster_accessions) >= PHASE31_CLUSTER_MIN_DISTINCT_ACCESSIONS
            )

            if event["event_direction"] == "PURCHASE":
                broad_id = "open_market_purchase_long"
                cluster_id = "clustered_open_market_purchase_long" if clustered else None
            else:
                broad_id = "open_market_sale_short"
                cluster_id = "clustered_open_market_sale_short" if clustered else None

            decision = event["decision_session"]
            contract = None
            target_list: list[dict[str, Any]] | None = None
            if research_start <= decision <= development_last:
                contract = PHASE31_DEVELOPMENT_PREDICTOR_CONTRACT_VERSION
                target_list = development_records
            elif protected_start <= decision <= protected_last:
                contract = PHASE31_PROTECTED_PREDICTOR_CONTRACT_VERSION
                target_list = protected_records

            if target_list is not None and contract is not None:
                record = {
                    "contract_version": contract,
                    "phase31_policy_fingerprint": policy_fp,
                    "ticker": event["ticker"],
                    "instrument_id": event["instrument_id"],
                    "composite_figi": event["composite_figi"],
                    "direction": event["direction"],
                    "event_direction": event["event_direction"],
                    "decision_session": decision.isoformat(),
                    "exit_session": event["exit_session"].isoformat(),
                    "broad_candidate_id": broad_id,
                    "cluster_candidate_id": cluster_id,
                    "is_clustered": clustered,
                    "event_accession_count": len(event["accession_numbers"]),
                    "event_owner_count": len(event["owner_ciks"]),
                    "cluster_accession_count": len(cluster_accessions),
                    "cluster_owner_count": len(cluster_owners),
                    "accession_numbers_json": json.dumps(event["accession_numbers"], separators=(",", ":")),
                    "owner_ciks_json": json.dumps(event["owner_ciks"], separators=(",", ":")),
                    "issuer_ciks_json": json.dumps(event["issuer_ciks"], separators=(",", ":")),
                    "filing_dates_json": json.dumps(event["filing_dates"], separators=(",", ":")),
                    "transaction_row_count": event["transaction_row_count"],
                    "transaction_shares_sum": event["transaction_shares_sum"],
                    "transaction_gross_value_sum": event["transaction_gross_value_sum"],
                }
                if tuple(record) != PHASE31_PREDICTOR_FIELDS:
                    raise Phase31PredictorError("Phase31 predictor field order drifted")
                if any(field in record for field in PHASE31_FORBIDDEN_MARKET_FIELDS):
                    raise Phase31PredictorError("Phase31 predictor contains a forbidden market field")
                target_list.append(record)
                candidate_counts[broad_id] += 1
                if cluster_id:
                    candidate_counts[cluster_id] += 1

            history[key].append(event)
            history[key] = [
                item
                for item in history[key]
                if int(item["decision_index"]) > current_index - PHASE31_CLUSTER_LOOKBACK_SESSIONS
            ]

        dev_sha, dev_reused = _write_immutable_parquet(
            self.settings, records=development_records, target=self.development_path()
        )
        protected_sha, protected_reused = _write_immutable_parquet(
            self.settings, records=protected_records, target=self.protected_path()
        )

        checks = {
            "acquisition_exactly_matches_accepted_full_history": rows_seen
            == PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS,
            "event_unit_frozen": PHASE31_EVENT_UNIT == "ONE_EXACT_TICKER_DECISION_SESSION_DIRECTION",
            "cluster_window_frozen_20": PHASE31_CLUSTER_LOOKBACK_SESSIONS == 20,
            "cluster_owner_min_frozen_2": PHASE31_CLUSTER_MIN_DISTINCT_OWNERS == 2,
            "cluster_accession_min_frozen_2": PHASE31_CLUSTER_MIN_DISTINCT_ACCESSIONS == 2,
            "development_predictors_nonempty": bool(development_records),
            "protected_predictors_nonempty": bool(protected_records),
            "predictor_rows_have_no_market_fields": all(
                not any(field in row for field in PHASE31_FORBIDDEN_MARKET_FIELDS)
                for row in development_records + protected_records
            ),
            "identity_is_composite_figi_authoritative": bool(intervals),
            "target_outcomes_unread": True,
            "protected_returns_unread": True,
            "provider_reads_zero": True,
            "provider_writes_zero": True,
            "broker_order_paper_live_zero": True,
        }
        report: dict[str, Any] = {
            "contract_version": PHASE31_PREDICTOR_REPORT_CONTRACT_VERSION,
            "phase31_policy_fingerprint": policy_fp,
            "accepted_full_history": {
                "raw_rows": PHASE31_ACCEPTED_FULL_HISTORY_RAW_ROWS,
                "authoritative_rows": PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS,
                "quarantined_rows": PHASE31_ACCEPTED_FULL_HISTORY_QUARANTINED_ROWS,
                "contaminated_accessions": PHASE31_ACCEPTED_FULL_HISTORY_CONTAMINATED_ACCESSIONS,
                "chronology_seed_rows": PHASE31_ACCEPTED_FULL_HISTORY_CHRONOLOGY_SEEDS,
                "missing_transaction_code_seed_rows": PHASE31_ACCEPTED_FULL_HISTORY_MISSING_CODE_SEEDS,
                "month_shards": PHASE31_ACCEPTED_FULL_HISTORY_MONTH_SHARDS,
            },
            "authoritative_lineage_sha256": authoritative_lineage_sha,
            "identity_interval_sha256": identity_sha,
            "authoritative_rows_scanned": rows_seen,
            "qualified_accessions_before_session_identity": len(qualified),
            "resolved_noncontradictory_events_all_signal_history": len(resolved_events),
            "development_predictor_rows": len(development_records),
            "protected_predictor_rows": len(protected_records),
            "candidate_membership_rows": dict(sorted(candidate_counts.items())),
            "exclusion_counts": dict(sorted(exclusions.items())),
            "development_sha256": dev_sha,
            "protected_sha256": protected_sha,
            "development_artifact_reused": dev_reused,
            "protected_artifact_reused": protected_reused,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "checks": checks,
            "pass": all(checks.values()),
        }
        if not report["pass"]:
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase31PredictorError("Phase31 predictor construction failed: " + ", ".join(failed))

        self.predictor_root.mkdir(parents=True, exist_ok=True)
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if self.report_path().is_file():
            existing = self.report_path().read_text(encoding="utf-8")
            # Reuse flags may differ on a deterministic rerun; normalize them before
            # comparing scientific content.
            old = json.loads(existing)
            old["development_artifact_reused"] = report["development_artifact_reused"]
            old["protected_artifact_reused"] = report["protected_artifact_reused"]
            if old != report:
                raise Phase31PredictorError("immutable Phase31 predictor report drifted")
        else:
            atomic_write_text(self.report_path(), text)
        report["report_path"] = str(self.report_path().resolve())
        return report
