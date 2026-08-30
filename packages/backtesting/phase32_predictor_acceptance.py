from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

import exchange_calendars as xcals

from packages.backtesting.phase32_policy import (
    PHASE32_CANDIDATES,
    PHASE32_DEVELOPMENT_LAST_SIGNAL,
    PHASE32_INSTRUMENT_ALLOWED_IDENTITY_QUALITIES,
    PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION,
    PHASE32_OUTCOME_HORIZON_SESSIONS,
    PHASE32_PROTECTED_LAST_SIGNAL,
    PHASE32_PROTECTED_START,
    PHASE32_RESEARCH_SIGNAL_START,
    phase32_policy_fingerprint,
)
from packages.backtesting.phase32_predictor_acquisition import (
    PHASE32_ACCEPTED_TAXONOMY_SHA256,
    PHASE32_ACQUISITION_END,
    PHASE32_ACQUISITION_START,
    PHASE32_EVIDENCE_RELATIVE,
    PHASE32_FILING_ENTITY_KEY_RULE,
    PHASE32_FROZEN_POLICY_FINGERPRINT,
    PHASE32_PREDICTOR_ACQUISITION_CONTRACT,
    PHASE32_PREDICTORS_RELATIVE,
    PHASE32_REPORT_RELATIVE,
)
from packages.core.atomic_io import atomic_write_text
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION, InstrumentIdentityResolver


PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT = (
    "phase32-predictor-independent-acceptance-v1-local-immutable-source-only"
)
PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256 = (
    "18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31"
)
PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256 = (
    "c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9"
)
PHASE32_ACCEPTANCE_RELATIVE = Path(
    "strategy_evaluation/phase32/predictor_v1/phase32_predictor_independent_acceptance.json"
)
_ALLOWED_IDENTITY_QUALITIES = set(PHASE32_INSTRUMENT_ALLOWED_IDENTITY_QUALITIES)


class Phase32PredictorIndependentAcceptanceError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(_canonical_json(row) + "\n" for row in rows)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase32PredictorIndependentAcceptanceError(f"invalid local JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise Phase32PredictorIndependentAcceptanceError(f"local JSON artifact is not an object: {path}")
    return value


def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise Phase32PredictorIndependentAcceptanceError(f"missing local JSONL artifact: {path}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Phase32PredictorIndependentAcceptanceError(
                f"invalid JSONL row: {path}:{line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise Phase32PredictorIndependentAcceptanceError(
                f"JSONL row is not an object: {path}:{line_number}"
            )
        rows.append(value)
    return tuple(rows)


def _normalize_cik(value: object) -> str:
    text = str(value or "").strip()
    if not text.isdigit():
        raise Phase32PredictorIndependentAcceptanceError(f"CIK is not numeric: {value!r}")
    return str(int(text)).zfill(10)


def _nonblank(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise Phase32PredictorIndependentAcceptanceError(f"missing required {field}")
    return text


def _exact_nonblank_text(value: object, *, field: str) -> str:
    """Require content while preserving exact whitespace for byte-level lineage hashes."""

    text = str(value or "")
    if not text.strip():
        raise Phase32PredictorIndependentAcceptanceError(f"missing required {field}")
    return text


def _parse_date(value: object, *, field: str) -> date:
    text = _nonblank(value, field=field)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise Phase32PredictorIndependentAcceptanceError(f"invalid {field}: {text!r}") from exc
    if parsed.isoformat() != text:
        raise Phase32PredictorIndependentAcceptanceError(f"invalid {field}: {text!r}")
    return parsed


def _candidate_taxonomy_map() -> dict[tuple[str, str, str], tuple[str, str]]:
    out: dict[tuple[str, str, str], tuple[str, str]] = {}
    for candidate in PHASE32_CANDIDATES:
        for triple in candidate.taxonomy_triples:
            if triple in out:
                raise Phase32PredictorIndependentAcceptanceError(
                    f"frozen taxonomy triple is assigned twice: {triple}"
                )
            out[triple] = (candidate.candidate_id, candidate.direction)
    return out


def _decision_and_exit_sessions(acceptance_datetime: str) -> tuple[date, date]:
    normalized = acceptance_datetime.strip().replace("Z", "+00:00")
    try:
        accepted = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise Phase32PredictorIndependentAcceptanceError(
            f"invalid SEC acceptance datetime: {acceptance_datetime!r}"
        ) from exc
    if accepted.tzinfo is None:
        raise Phase32PredictorIndependentAcceptanceError("SEC acceptance datetime must be timezone-aware")
    accepted_utc = accepted.astimezone(UTC)
    calendar = xcals.get_calendar("XNYS")
    sessions = calendar.sessions_in_range(accepted.date(), accepted.date() + timedelta(days=14))
    decision = None
    for session in sessions:
        session_open = calendar.session_open(session).to_pydatetime().astimezone(UTC)
        if session_open > accepted_utc:
            decision = session
            break
    if decision is None:
        raise Phase32PredictorIndependentAcceptanceError(
            f"could not resolve decision session after SEC acceptance {acceptance_datetime}"
        )
    exit_session = calendar.session_offset(decision, PHASE32_OUTCOME_HORIZON_SESSIONS)
    return decision.date(), exit_session.date()


def _stage_for_decision(decision: date) -> str:
    development_last = date.fromisoformat(PHASE32_DEVELOPMENT_LAST_SIGNAL)
    protected_start = date.fromisoformat(PHASE32_PROTECTED_START)
    protected_last = date.fromisoformat(PHASE32_PROTECTED_LAST_SIGNAL)
    research_start = date.fromisoformat(PHASE32_RESEARCH_SIGNAL_START)
    if research_start <= decision <= development_last:
        return "development"
    if protected_start <= decision <= protected_last:
        return "protected_predictor_only"
    if development_last < decision < protected_start:
        return "outer_embargo"
    return "outside_frozen_signal_window"


def _safe_cache_token(ticker: str) -> str:
    return hashlib.sha256(ticker.encode("utf-8")).hexdigest()[:24]


def reconcile_massive_text_rows(
    rows: Iterable[dict[str, Any]], *, accession: str, issuer_cik: str
) -> dict[str, Any]:
    matches = [dict(row) for row in rows if str(row.get("accession_number") or "").strip() == accession]
    if not matches:
        raise Phase32PredictorIndependentAcceptanceError(
            f"local Massive Text cache lacks filing entity: {accession} cik={issuer_cik}"
        )
    baseline: dict[str, Any] | None = None
    normalized: list[dict[str, Any]] = []
    for row in matches:
        if _normalize_cik(row.get("cik")) != issuer_cik:
            raise Phase32PredictorIndependentAcceptanceError(
                f"local Massive Text CIK mismatch: {accession} cik={issuer_cik}"
            )
        non_ticker = {key: value for key, value in row.items() if key != "ticker"}
        if baseline is None:
            baseline = non_ticker
        elif non_ticker != baseline:
            raise Phase32PredictorIndependentAcceptanceError(
                f"local Massive Text rows conflict beyond ticker: {accession} cik={issuer_cik}"
            )
        normalized.append(row)
    if baseline is None:  # pragma: no cover
        raise Phase32PredictorIndependentAcceptanceError("Massive Text reconciliation lost baseline")
    ordered = sorted(normalized, key=_canonical_json)
    tickers = sorted(
        {
            str(row.get("ticker") or "").strip()
            for row in ordered
            if str(row.get("ticker") or "").strip()
        }
    )
    return {
        "row_count": len(ordered),
        "tickers": tickers,
        "aggregate_sha256": _sha256_text(_canonical_jsonl(ordered)),
        "non_ticker_sha256": _sha256_text(_canonical_json(baseline)),
    }


def _rebuild_predictors(
    filing_entity_rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    candidates = {candidate.candidate_id: candidate for candidate in PHASE32_CANDIDATES}
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in filing_entity_rows:
        if row.get("eligibility") != "eligible":
            continue
        instrument = row.get("instrument")
        if not isinstance(instrument, dict):
            raise Phase32PredictorIndependentAcceptanceError("eligible filing entity lacks instrument evidence")
        instrument_id = _nonblank(instrument.get("instrument_id"), field="instrument_id")
        decision_session = _nonblank(row.get("decision_session"), field="decision_session")
        for candidate_id in row.get("candidate_ids") or []:
            candidate = candidates.get(str(candidate_id))
            if candidate is None:
                raise Phase32PredictorIndependentAcceptanceError(
                    f"unknown candidate in filing evidence: {candidate_id!r}"
                )
            key = (instrument_id, decision_session, candidate.candidate_id)
            group = grouped.setdefault(
                key,
                {
                    "candidate_id": candidate.candidate_id,
                    "direction": candidate.direction,
                    "instrument_id": instrument_id,
                    "identity_key": instrument.get("identity_key"),
                    "identity_quality": instrument.get("identity_quality"),
                    "decision_session": decision_session,
                    "exit_session": row.get("exit_session"),
                    "stage": row.get("stage"),
                    "issuer_cik": row.get("issuer_cik"),
                    "accession_numbers": [],
                    "provider_tickers": [],
                    "taxonomy_triples": [],
                    "acceptance_datetimes": [],
                    "source_lineage_sha256": [],
                },
            )
            if group["exit_session"] != row.get("exit_session") or group["issuer_cik"] != row.get("issuer_cik"):
                raise Phase32PredictorIndependentAcceptanceError(
                    f"predictor aggregation invariant changed within {key}"
                )
            group["accession_numbers"].append(row.get("accession_number"))
            group["provider_tickers"].extend(row.get("provider_tickers") or [])
            group["taxonomy_triples"].extend(row.get("taxonomy_triples") or [])
            group["acceptance_datetimes"].append(row.get("acceptance_datetime"))
            group["source_lineage_sha256"].extend(
                [row.get("sec_source_record_sha256"), row.get("massive_text_sha256")]
                + list(row.get("supporting_text_sha256") or [])
            )

    directions_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    for group in grouped.values():
        pair = (str(group["instrument_id"]), str(group["decision_session"]))
        directions_by_pair[pair].add(str(group["direction"]))
    contradictory_pairs = {
        pair for pair, directions in directions_by_pair.items() if {"LONG", "SHORT"} <= directions
    }

    predictors: list[dict[str, Any]] = []
    contradictory_group_rows = 0
    for key in sorted(grouped):
        group = grouped[key]
        pair = (str(group["instrument_id"]), str(group["decision_session"]))
        if pair in contradictory_pairs:
            contradictory_group_rows += 1
            continue
        for field in (
            "accession_numbers",
            "provider_tickers",
            "acceptance_datetimes",
            "source_lineage_sha256",
        ):
            group[field] = sorted(set(group[field]))
        group["taxonomy_triples"] = [
            list(value) for value in sorted({tuple(value) for value in group["taxonomy_triples"]})
        ]
        group["policy_fingerprint"] = PHASE32_FROZEN_POLICY_FINGERPRINT
        group["outcome_rows_read"] = 0
        predictors.append(group)
    predictors.sort(
        key=lambda row: (
            str(row["decision_session"]),
            str(row["instrument_id"]),
            str(row["candidate_id"]),
        )
    )
    return predictors, len(contradictory_pairs), contradictory_group_rows


class Phase32PredictorIndependentAcceptance:
    """Independent local-only acceptance of the completed Phase32 predictor source PASS."""

    def __init__(
        self,
        settings: Any,
        *,
        identity_resolver: InstrumentIdentityResolver | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        self.settings = settings
        self.identity = identity_resolver or InstrumentIdentityResolver()
        self.progress_callback = progress_callback
        self.provider_root = settings.resolved_path(settings.data.paths.provider)
        self.derived_root = settings.resolved_path(settings.data.paths.derived)
        self.evidence_root = self.provider_root / PHASE32_EVIDENCE_RELATIVE
        self.report_path = self.derived_root / PHASE32_REPORT_RELATIVE
        self.predictor_path = self.derived_root / PHASE32_PREDICTORS_RELATIVE
        self.filing_entity_path = self.evidence_root / "candidate_filing_entity_records.jsonl"
        self.acceptance_path = self.derived_root / PHASE32_ACCEPTANCE_RELATIVE
        self._reference_cache: dict[tuple[str, str], dict[str, Any] | None] = {}

    def _local_reference(self, *, ticker: str, as_of_date: date) -> dict[str, Any] | None:
        cache_key = (ticker, as_of_date.isoformat())
        if cache_key in self._reference_cache:
            return self._reference_cache[cache_key]
        path = (
            self.evidence_root
            / "massive_reference"
            / as_of_date.isoformat()
            / f"{_safe_cache_token(ticker)}.json"
        )
        wrapper = _read_json(path)
        if wrapper.get("ticker_requested") != ticker:
            raise Phase32PredictorIndependentAcceptanceError(
                f"reference cache ticker mismatch: {path}"
            )
        if wrapper.get("as_of_date") != as_of_date.isoformat():
            raise Phase32PredictorIndependentAcceptanceError(
                f"reference cache date mismatch: {path}"
            )
        status = wrapper.get("status")
        if status == "not_found":
            result = None
        elif status == "ok":
            row = wrapper.get("row")
            if not isinstance(row, dict):
                raise Phase32PredictorIndependentAcceptanceError(
                    f"reference cache row is invalid: {path}"
                )
            if str(row.get("ticker") or "").strip() != ticker:
                raise Phase32PredictorIndependentAcceptanceError(
                    f"reference cache changed provider-native ticker: {path}"
                )
            result = row
        else:
            raise Phase32PredictorIndependentAcceptanceError(
                f"reference cache has unknown status: {path}"
            )
        self._reference_cache[cache_key] = result
        return result

    def _resolve_local_instrument(
        self,
        *,
        tickers: tuple[str, ...],
        issuer_cik: str,
        decision_session: date,
        exit_session: date,
    ) -> tuple[dict[str, Any] | None, str | None]:
        resolved: dict[str, dict[str, Any]] = {}
        mapping_evidence: list[dict[str, Any]] = []
        for ticker in tickers:
            entry = self._local_reference(ticker=ticker, as_of_date=decision_session)
            exit_row = self._local_reference(ticker=ticker, as_of_date=exit_session)
            if entry is None or exit_row is None:
                mapping_evidence.append({"ticker": ticker, "status": "reference_missing"})
                continue
            try:
                entry_cik = _normalize_cik(entry.get("cik"))
                exit_cik = _normalize_cik(exit_row.get("cik"))
            except Phase32PredictorIndependentAcceptanceError:
                mapping_evidence.append({"ticker": ticker, "status": "reference_cik_missing"})
                continue
            if entry_cik != issuer_cik or exit_cik != issuer_cik:
                mapping_evidence.append({"ticker": ticker, "status": "filing_cik_mismatch"})
                continue
            entry_id, entry_key, entry_quality = self.identity.resolve(entry, decision_session)
            exit_id, exit_key, exit_quality = self.identity.resolve(exit_row, exit_session)
            if str(entry_quality) not in _ALLOWED_IDENTITY_QUALITIES or str(exit_quality) not in _ALLOWED_IDENTITY_QUALITIES:
                mapping_evidence.append({"ticker": ticker, "status": "fallback_identity"})
                continue
            if entry_id != exit_id:
                mapping_evidence.append({"ticker": ticker, "status": "identity_interval_changed"})
                continue
            resolved[entry_id] = {
                "instrument_id": entry_id,
                "identity_key": entry_key,
                "identity_quality": str(entry_quality),
                "ticker": ticker,
                "entry_reference_sha256": _sha256_text(_canonical_json(entry)),
                "exit_reference_sha256": _sha256_text(_canonical_json(exit_row)),
                "entry_identity_key": entry_key,
                "exit_identity_key": exit_key,
            }
            mapping_evidence.append({"ticker": ticker, "status": "resolved", "instrument_id": entry_id})
        if not resolved:
            return None, "NO_ELIGIBLE_PIT_INSTRUMENT"
        if len(resolved) != 1:
            return None, "AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS"
        result = next(iter(resolved.values()))
        result["mapping_evidence"] = mapping_evidence
        return result, None

    def run(self) -> dict[str, Any]:
        if phase32_policy_fingerprint() != PHASE32_FROZEN_POLICY_FINGERPRINT:
            raise Phase32PredictorIndependentAcceptanceError("Phase32 frozen policy fingerprint drifted")
        if IDENTITY_CONTRACT_VERSION != PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION:
            raise Phase32PredictorIndependentAcceptanceError("accepted identity contract drifted")

        report = _read_json(self.report_path)
        required_report_values = {
            "contract_version": PHASE32_PREDICTOR_ACQUISITION_CONTRACT,
            "policy_fingerprint": PHASE32_FROZEN_POLICY_FINGERPRINT,
            "identity_contract_version": PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION,
            "filing_entity_key_rule": PHASE32_FILING_ENTITY_KEY_RULE,
            "acquisition_start": PHASE32_ACQUISITION_START.isoformat(),
            "acquisition_end": PHASE32_ACQUISITION_END.isoformat(),
            "taxonomy_sha256": PHASE32_ACCEPTED_TAXONOMY_SHA256,
        }
        for field, expected in required_report_values.items():
            if report.get(field) != expected:
                raise Phase32PredictorIndependentAcceptanceError(
                    f"acquisition report {field} drifted: {report.get(field)!r} != {expected!r}"
                )
        if report.get("pass") is not True:
            raise Phase32PredictorIndependentAcceptanceError("acquisition report is not PASS")

        zero_fields = (
            "target_outcome_rows_read",
            "protected_return_rows_read",
            "stock_price_rows_read",
            "spy_price_rows_read",
            "options_rows_read",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
            "automation_writes",
        )
        for field in zero_fields:
            if report.get(field) != 0:
                raise Phase32PredictorIndependentAcceptanceError(
                    f"forbidden acquisition counter is nonzero: {field}={report.get(field)!r}"
                )

        filing_sha = _sha256_file(self.filing_entity_path)
        predictor_sha = _sha256_file(self.predictor_path)
        if filing_sha != PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256:
            raise Phase32PredictorIndependentAcceptanceError(
                f"filing-entity evidence SHA-256 differs from target-machine PASS: {filing_sha}"
            )
        if predictor_sha != PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256:
            raise Phase32PredictorIndependentAcceptanceError(
                f"predictor SHA-256 differs from target-machine PASS: {predictor_sha}"
            )
        if report.get("candidate_filing_entity_evidence_sha256") != filing_sha:
            raise Phase32PredictorIndependentAcceptanceError("report filing-entity SHA-256 does not match artifact")
        if report.get("predictor_rows_sha256") != predictor_sha:
            raise Phase32PredictorIndependentAcceptanceError("report predictor SHA-256 does not match artifact")

        taxonomy_path = self.evidence_root / "taxonomy.jsonl"
        if _sha256_file(taxonomy_path) != PHASE32_ACCEPTED_TAXONOMY_SHA256:
            raise Phase32PredictorIndependentAcceptanceError("local taxonomy hash differs from accepted semantic V2")
        taxonomy_rows = _load_jsonl(taxonomy_path)
        frozen_map = _candidate_taxonomy_map()
        observed_taxonomy = {
            (
                str(row.get("primary_category") or ""),
                str(row.get("secondary_category") or ""),
                str(row.get("tertiary_category") or ""),
            )
            for row in taxonomy_rows
        }
        if set(frozen_map) - observed_taxonomy:
            raise Phase32PredictorIndependentAcceptanceError("local taxonomy is missing frozen candidate triples")

        month_reports = report.get("monthly_windows")
        if not isinstance(month_reports, list) or not month_reports:
            raise Phase32PredictorIndependentAcceptanceError("acquisition report lacks monthly source windows")
        all_index: list[dict[str, Any]] = []
        all_disclosures: list[dict[str, Any]] = []
        seen_months: set[str] = set()
        for window in month_reports:
            if not isinstance(window, dict):
                raise Phase32PredictorIndependentAcceptanceError("monthly source window is not an object")
            month = _nonblank(window.get("month"), field="month")
            if month in seen_months:
                raise Phase32PredictorIndependentAcceptanceError(f"duplicate monthly source window: {month}")
            seen_months.add(month)
            start = _parse_date(window.get("start_date"), field="window start_date")
            end = _parse_date(window.get("end_date"), field="window end_date")
            if start > end:
                raise Phase32PredictorIndependentAcceptanceError(f"reversed monthly source window: {month}")
            index_rows = _load_jsonl(self.evidence_root / "massive_index" / f"{month}.jsonl")
            disclosure_rows = _load_jsonl(self.evidence_root / "massive_disclosures" / f"{month}.jsonl")
            if len(index_rows) != window.get("index_rows") or len(disclosure_rows) != window.get("disclosure_rows"):
                raise Phase32PredictorIndependentAcceptanceError(
                    f"monthly source row count differs from report: {month}"
                )
            for row in index_rows:
                filing_date = _parse_date(row.get("filing_date"), field="index filing_date")
                if not start <= filing_date <= end:
                    raise Phase32PredictorIndependentAcceptanceError(
                        f"index row falls outside monthly window: {month}"
                    )
            for row in disclosure_rows:
                filing_date = _parse_date(row.get("filing_date"), field="disclosure filing_date")
                if not start <= filing_date <= end:
                    raise Phase32PredictorIndependentAcceptanceError(
                        f"disclosure row falls outside monthly window: {month}"
                    )
            all_index.extend(index_rows)
            all_disclosures.extend(disclosure_rows)

        if len(all_index) != report.get("total_index_rows"):
            raise Phase32PredictorIndependentAcceptanceError("independent index total differs from report")
        if len(all_disclosures) != report.get("total_disclosure_rows"):
            raise Phase32PredictorIndependentAcceptanceError("independent disclosure total differs from report")

        index_by_accession: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in all_index:
            index_by_accession[_nonblank(row.get("accession_number"), field="index accession")].append(row)
        disclosures_by_accession: dict[str, list[dict[str, Any]]] = defaultdict(list)
        candidate_by_accession: dict[str, list[tuple[dict[str, Any], str, str]]] = defaultdict(list)
        for row in all_disclosures:
            accession = _nonblank(row.get("accession_number"), field="disclosure accession")
            disclosures_by_accession[accession].append(row)
            triple = (
                str(row.get("primary_category") or ""),
                str(row.get("secondary_category") or ""),
                str(row.get("tertiary_category") or ""),
            )
            assignment = frozen_map.get(triple)
            if assignment is not None:
                candidate_by_accession[accession].append((row, assignment[0], assignment[1]))

        source_accessions = sorted(candidate_by_accession)
        if len(source_accessions) != report.get("frozen_candidate_source_accessions"):
            raise Phase32PredictorIndependentAcceptanceError(
                "independent frozen-candidate accession count differs from report"
            )
        multi_filer_accessions = sum(
            1
            for accession in source_accessions
            if len({_normalize_cik(row.get("cik")) for row in disclosures_by_accession[accession]}) > 1
        )
        if multi_filer_accessions != report.get("multi_filer_candidate_accessions"):
            raise Phase32PredictorIndependentAcceptanceError(
                "independent multi-filer accession count differs from report"
            )

        filing_rows = list(_load_jsonl(self.filing_entity_path))
        if len(filing_rows) != report.get("candidate_filing_entity_records"):
            raise Phase32PredictorIndependentAcceptanceError("filing-entity record count differs from report")
        seen_keys: set[str] = set()
        source_stage_counts: Counter[str] = Counter()
        base_exclusion_counts: Counter[str] = Counter()

        for completed, row in enumerate(filing_rows, start=1):
            accession = _nonblank(row.get("accession_number"), field="filing accession")
            issuer_cik = _normalize_cik(row.get("issuer_cik"))
            filing_date = _parse_date(row.get("filing_date"), field="filing filing_date")
            key = f"{accession}|{issuer_cik}|{filing_date.isoformat()}"
            if row.get("filing_entity_key") != key or row.get("filing_entity_key_rule") != PHASE32_FILING_ENTITY_KEY_RULE:
                raise Phase32PredictorIndependentAcceptanceError(f"filing-entity key mismatch: {key}")
            if key in seen_keys:
                raise Phase32PredictorIndependentAcceptanceError(f"duplicate filing-entity key: {key}")
            seen_keys.add(key)

            accession_disclosures = disclosures_by_accession.get(accession) or []
            if not accession_disclosures:
                raise Phase32PredictorIndependentAcceptanceError(f"filing evidence lacks disclosure source: {key}")
            disclosure_dates = {
                _parse_date(item.get("filing_date"), field="disclosure filing_date")
                for item in accession_disclosures
            }
            if disclosure_dates != {filing_date}:
                raise Phase32PredictorIndependentAcceptanceError(f"accession-wide filing date mismatch: {key}")
            all_candidate_assignments = candidate_by_accession.get(accession) or []
            entity_assignments = [
                item for item in all_candidate_assignments if _normalize_cik(item[0].get("cik")) == issuer_cik
            ]
            if not entity_assignments:
                raise Phase32PredictorIndependentAcceptanceError(f"filing entity has no frozen assignment: {key}")
            entity_disclosures = [item[0] for item in entity_assignments]
            candidate_ids = sorted({item[1] for item in entity_assignments})
            directions = sorted({item[2] for item in entity_assignments})
            triples = sorted(
                {
                    (
                        str(item.get("primary_category") or ""),
                        str(item.get("secondary_category") or ""),
                        str(item.get("tertiary_category") or ""),
                    )
                    for item in entity_disclosures
                }
            )
            support_hashes: list[str] = []
            for item in entity_disclosures:
                support = str(item.get("supporting_text") or "")
                if not support.strip():
                    raise Phase32PredictorIndependentAcceptanceError(
                        f"frozen semantic disclosure lacks supporting text: {key}"
                    )
                support_hashes.append(_sha256_text(support))
            support_hashes = sorted(set(support_hashes))
            disclosure_filer_ciks = sorted({_normalize_cik(item.get("cik")) for item in accession_disclosures})
            candidate_disclosure_filer_ciks = sorted(
                {_normalize_cik(item[0].get("cik")) for item in all_candidate_assignments}
            )
            expected_disclosure_fields = {
                "accession_disclosure_row_count": len(accession_disclosures),
                "disclosure_row_count": len(entity_disclosures),
                "candidate_disclosure_filer_ciks": candidate_disclosure_filer_ciks,
                "disclosure_filer_ciks": disclosure_filer_ciks,
                "co_filer_disclosure_ciks": sorted(set(disclosure_filer_ciks) - {issuer_cik}),
                "candidate_ids": candidate_ids,
                "directions": directions,
                "taxonomy_triples": [list(value) for value in triples],
                "supporting_text_sha256": support_hashes,
            }
            for field, expected in expected_disclosure_fields.items():
                if _canonical_json(row.get(field)) != _canonical_json(expected):
                    raise Phase32PredictorIndependentAcceptanceError(
                        f"filing disclosure provenance mismatch: {key} field={field}"
                    )

            index_rows = index_by_accession.get(accession) or []
            if not index_rows:
                raise Phase32PredictorIndependentAcceptanceError(f"filing evidence lacks index source: {key}")
            index_filer_ciks: set[str] = set()
            issuer_index_rows: list[dict[str, Any]] = []
            for item in index_rows:
                item_cik = _normalize_cik(item.get("cik"))
                index_filer_ciks.add(item_cik)
                if _parse_date(item.get("filing_date"), field="index filing_date") != filing_date:
                    raise Phase32PredictorIndependentAcceptanceError(f"index filing-date mismatch: {key}")
                if item.get("form_type") != "8-K":
                    raise Phase32PredictorIndependentAcceptanceError(f"index form mismatch: {key}")
                if item_cik == issuer_cik:
                    issuer_index_rows.append(item)
            if not issuer_index_rows:
                raise Phase32PredictorIndependentAcceptanceError(f"index lacks issuer-CIK row: {key}")
            expected_index_fields = {
                "index_row_count": len(index_rows),
                "issuer_index_row_count": len(issuer_index_rows),
                "co_filer_index_row_count": len(index_rows) - len(issuer_index_rows),
                "index_filer_ciks": sorted(index_filer_ciks),
                "co_filer_index_ciks": sorted(index_filer_ciks - {issuer_cik}),
            }
            for field, expected in expected_index_fields.items():
                if _canonical_json(row.get(field)) != _canonical_json(expected):
                    raise Phase32PredictorIndependentAcceptanceError(
                        f"filing index provenance mismatch: {key} field={field}"
                    )

            sec_path = self.evidence_root / "sec_submissions" / issuer_cik / f"{accession}.json"
            sec = _read_json(sec_path)
            if _nonblank(sec.get("accession_number"), field="SEC accession") != accession:
                raise Phase32PredictorIndependentAcceptanceError(f"SEC accession mismatch: {key}")
            if _normalize_cik(sec.get("issuer_cik")) != issuer_cik:
                raise Phase32PredictorIndependentAcceptanceError(f"SEC CIK mismatch: {key}")
            if _parse_date(sec.get("filing_date"), field="SEC filing_date") != filing_date:
                raise Phase32PredictorIndependentAcceptanceError(f"SEC filing-date mismatch: {key}")
            if sec.get("form") != "8-K":
                raise Phase32PredictorIndependentAcceptanceError(f"SEC form mismatch: {key}")
            source_record_json = _exact_nonblank_text(
                sec.get("source_record_json"), field="SEC source_record_json"
            )
            source_record_sha = _sha256_text(source_record_json)
            if sec.get("source_record_sha256") != source_record_sha or row.get("sec_source_record_sha256") != source_record_sha:
                raise Phase32PredictorIndependentAcceptanceError(f"SEC source-record hash mismatch: {key}")
            acceptance = _nonblank(sec.get("acceptance_datetime"), field="SEC acceptance_datetime")
            decision_session, exit_session = _decision_and_exit_sessions(acceptance)
            stage = _stage_for_decision(decision_session)
            if row.get("acceptance_datetime") != acceptance:
                raise Phase32PredictorIndependentAcceptanceError(f"SEC acceptance lineage mismatch: {key}")
            if row.get("decision_session") != decision_session.isoformat() or row.get("exit_session") != exit_session.isoformat():
                raise Phase32PredictorIndependentAcceptanceError(f"decision/exit chronology mismatch: {key}")
            if row.get("stage") != stage:
                raise Phase32PredictorIndependentAcceptanceError(f"source-stage mismatch: {key}")
            source_stage_counts[stage] += 1

            text_path = self.evidence_root / "massive_text" / issuer_cik / f"{filing_date.isoformat()}.jsonl"
            text_evidence = reconcile_massive_text_rows(
                _load_jsonl(text_path), accession=accession, issuer_cik=issuer_cik
            )
            expected_text_fields = {
                "massive_text_sha256": text_evidence["aggregate_sha256"],
                "massive_text_row_count": text_evidence["row_count"],
                "massive_text_tickers": text_evidence["tickers"],
                "massive_text_non_ticker_sha256": text_evidence["non_ticker_sha256"],
            }
            for field, expected in expected_text_fields.items():
                if _canonical_json(row.get(field)) != _canonical_json(expected):
                    raise Phase32PredictorIndependentAcceptanceError(
                        f"Massive Text provenance mismatch: {key} field={field}"
                    )

            tickers: set[str] = set()
            for item in entity_disclosures:
                values = item.get("tickers")
                if isinstance(values, list):
                    tickers.update(str(value).strip() for value in values if str(value).strip())
            for item in issuer_index_rows:
                ticker = item.get("ticker")
                if isinstance(ticker, str) and ticker.strip():
                    tickers.add(ticker.strip())
            tickers.update(str(value) for value in text_evidence["tickers"])
            provider_tickers = tuple(sorted(tickers))
            if _canonical_json(row.get("provider_tickers")) != _canonical_json(list(provider_tickers)):
                raise Phase32PredictorIndependentAcceptanceError(f"provider ticker union mismatch: {key}")

            expected_eligibility = "eligible"
            expected_exclusion: str | None = None
            expected_instrument: dict[str, Any] | None = None
            if stage not in {"development", "protected_predictor_only"}:
                expected_eligibility = "excluded"
                expected_exclusion = stage.upper()
            elif not provider_tickers:
                expected_eligibility = "excluded"
                expected_exclusion = "NO_PROVIDER_TICKER_MAPPING"
            else:
                expected_instrument, expected_exclusion = self._resolve_local_instrument(
                    tickers=provider_tickers,
                    issuer_cik=issuer_cik,
                    decision_session=decision_session,
                    exit_session=exit_session,
                )
                if expected_instrument is None:
                    expected_eligibility = "excluded"
            if row.get("eligibility") != expected_eligibility:
                raise Phase32PredictorIndependentAcceptanceError(f"eligibility mismatch: {key}")
            if expected_eligibility == "excluded":
                if row.get("exclusion_reason") != expected_exclusion:
                    raise Phase32PredictorIndependentAcceptanceError(f"exclusion reason mismatch: {key}")
                base_exclusion_counts[str(expected_exclusion)] += 1
                if "instrument" in row:
                    raise Phase32PredictorIndependentAcceptanceError(
                        f"excluded filing entity unexpectedly contains instrument evidence: {key}"
                    )
            else:
                if row.get("exclusion_reason") is not None:
                    raise Phase32PredictorIndependentAcceptanceError(
                        f"eligible filing entity unexpectedly contains exclusion reason: {key}"
                    )
                if _canonical_json(row.get("instrument")) != _canonical_json(expected_instrument):
                    raise Phase32PredictorIndependentAcceptanceError(
                        f"PIT instrument evidence mismatch: {key}"
                    )

            if self.progress_callback is not None:
                self.progress_callback(completed, len(filing_rows))

        rebuilt_predictors, contradictory_sessions, contradictory_group_rows = _rebuild_predictors(filing_rows)
        rebuilt_text = _canonical_jsonl(rebuilt_predictors)
        actual_predictor_text = self.predictor_path.read_text(encoding="utf-8")
        if rebuilt_text != actual_predictor_text:
            raise Phase32PredictorIndependentAcceptanceError(
                "independently rebuilt predictor rows differ byte-for-byte from acquisition output"
            )
        if contradictory_sessions != report.get("contradictory_instrument_sessions"):
            raise Phase32PredictorIndependentAcceptanceError(
                "independent contradictory instrument-session count differs from report"
            )

        exclusion_counts = Counter(base_exclusion_counts)
        exclusion_counts["CONTRADICTORY_LONG_SHORT_INSTRUMENT_SESSION"] += contradictory_group_rows
        exclusion_counts = +exclusion_counts
        candidate_counts = Counter(str(row["candidate_id"]) for row in rebuilt_predictors)
        stage_counts = Counter(str(row["stage"]) for row in rebuilt_predictors)
        expected_report_counts = {
            "eligible_predictor_rows": len(rebuilt_predictors),
            "candidate_predictor_counts": dict(sorted(candidate_counts.items())),
            "stage_predictor_counts": dict(sorted(stage_counts.items())),
            "source_stage_filing_entity_counts": dict(sorted(source_stage_counts.items())),
            "exclusion_counts": dict(sorted(exclusion_counts.items())),
        }
        for field, expected in expected_report_counts.items():
            if _canonical_json(report.get(field)) != _canonical_json(expected):
                raise Phase32PredictorIndependentAcceptanceError(
                    f"independent report reconciliation mismatch: field={field}"
                )

        acceptance_payload: dict[str, Any] = {
            "contract_version": PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT,
            "status": "PASS",
            "policy_fingerprint": PHASE32_FROZEN_POLICY_FINGERPRINT,
            "acquisition_contract_version": PHASE32_PREDICTOR_ACQUISITION_CONTRACT,
            "identity_contract_version": PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION,
            "filing_entity_key_rule": PHASE32_FILING_ENTITY_KEY_RULE,
            "acquisition_start": PHASE32_ACQUISITION_START.isoformat(),
            "acquisition_end": PHASE32_ACQUISITION_END.isoformat(),
            "taxonomy_sha256": PHASE32_ACCEPTED_TAXONOMY_SHA256,
            "source_report_sha256": _sha256_file(self.report_path),
            "candidate_filing_entity_evidence_sha256": filing_sha,
            "predictor_rows_sha256": predictor_sha,
            "total_index_rows": len(all_index),
            "total_disclosure_rows": len(all_disclosures),
            "frozen_candidate_source_accessions": len(source_accessions),
            "multi_filer_candidate_accessions": multi_filer_accessions,
            "candidate_filing_entity_records": len(filing_rows),
            "eligible_predictor_rows": len(rebuilt_predictors),
            "candidate_predictor_counts": dict(sorted(candidate_counts.items())),
            "stage_predictor_counts": dict(sorted(stage_counts.items())),
            "source_stage_filing_entity_counts": dict(sorted(source_stage_counts.items())),
            "exclusion_counts": dict(sorted(exclusion_counts.items())),
            "contradictory_instrument_sessions": contradictory_sessions,
            "independent_network_reads": 0,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "stock_price_rows_read": 0,
            "spy_price_rows_read": 0,
            "options_rows_read": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
        }
        acceptance_fingerprint = _sha256_text(_canonical_json(acceptance_payload))
        acceptance_payload["acceptance_fingerprint"] = acceptance_fingerprint
        acceptance_payload["pass"] = True
        atomic_write_text(
            self.acceptance_path,
            json.dumps(acceptance_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result = dict(acceptance_payload)
        result["acceptance_path"] = str(self.acceptance_path)
        return result