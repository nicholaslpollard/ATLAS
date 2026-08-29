from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

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
from packages.core.atomic_io import atomic_write_text
from packages.core.enums import InstrumentIdentityQuality
from packages.core.exceptions import ProviderError
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION, InstrumentIdentityResolver


PHASE32_PREDICTOR_ACQUISITION_CONTRACT = (
    "phase32-predictor-source-acquisition-v1-resumable-no-market-outcomes"
)
PHASE32_FROZEN_POLICY_FINGERPRINT = (
    "4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7"
)
PHASE32_ACCEPTED_TAXONOMY_SHA256 = (
    "b1bcb0037d2d17a36f1b72b8e260b32a611a81b36b831af5c5a6423e660d28a6"
)
PHASE32_ACQUISITION_START = date.fromisoformat(PHASE32_RESEARCH_SIGNAL_START)
PHASE32_ACQUISITION_END = date(2026, 8, 11)
PHASE32_DEVELOPMENT_LAST_SIGNAL_DATE = date.fromisoformat(PHASE32_DEVELOPMENT_LAST_SIGNAL)
PHASE32_PROTECTED_START_DATE = date.fromisoformat(PHASE32_PROTECTED_START)
PHASE32_PROTECTED_LAST_SIGNAL_DATE = date.fromisoformat(PHASE32_PROTECTED_LAST_SIGNAL)
PHASE32_EVIDENCE_RELATIVE = Path("phase32_sec_8k_predictor_acquisition/v1")
PHASE32_REPORT_RELATIVE = Path(
    "strategy_evaluation/phase32/predictor_v1/phase32_predictor_source_acquisition.json"
)
PHASE32_PREDICTORS_RELATIVE = Path(
    "strategy_evaluation/phase32/predictor_v1/phase32_predictor_rows.jsonl"
)
_ALLOWED_IDENTITY_QUALITIES = set(PHASE32_INSTRUMENT_ALLOWED_IDENTITY_QUALITIES)


class Phase32PredictorAcquisitionError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(_canonical_json(row) + "\n" for row in rows)


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_cik(value: object) -> str:
    text = str(value or "").strip()
    if not text.isdigit():
        raise Phase32PredictorAcquisitionError(f"CIK is not numeric: {value!r}")
    return str(int(text)).zfill(10)


def _nonblank(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise Phase32PredictorAcquisitionError(f"missing required {field}")
    return text


def _parse_date(value: object, *, field: str) -> date:
    text = _nonblank(value, field=field)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise Phase32PredictorAcquisitionError(f"invalid {field}: {text!r}") from exc


def _month_windows(start: date, end: date) -> tuple[tuple[date, date], ...]:
    if start > end:
        raise ValueError("start must be <= end")
    windows: list[tuple[date, date]] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        next_month = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        window_start = max(start, cursor)
        window_end = min(end, next_month - timedelta(days=1))
        windows.append((window_start, window_end))
        cursor = next_month
    return tuple(windows)


def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Phase32PredictorAcquisitionError(
                f"cached JSONL row is not an object: {path}:{line_number}"
            )
        rows.append(value)
    return tuple(rows)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    atomic_write_text(path, _canonical_jsonl(rows), encoding="utf-8")


def _safe_cache_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _candidate_taxonomy_map() -> dict[tuple[str, str, str], tuple[str, str]]:
    out: dict[tuple[str, str, str], tuple[str, str]] = {}
    for candidate in PHASE32_CANDIDATES:
        for triple in candidate.taxonomy_triples:
            if triple in out:
                raise Phase32PredictorAcquisitionError(
                    f"frozen taxonomy triple is assigned to multiple candidates: {triple}"
                )
            out[triple] = (candidate.candidate_id, candidate.direction)
    return out


def _decision_and_exit_sessions(acceptance_datetime: str) -> tuple[date, date]:
    normalized = acceptance_datetime.strip().replace("Z", "+00:00")
    try:
        accepted = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise Phase32PredictorAcquisitionError(
            f"invalid SEC acceptance datetime: {acceptance_datetime!r}"
        ) from exc
    if accepted.tzinfo is None:
        raise Phase32PredictorAcquisitionError("SEC acceptance datetime must be timezone-aware")
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
        raise Phase32PredictorAcquisitionError(
            f"could not resolve decision session after SEC acceptance {acceptance_datetime}"
        )
    exit_session = calendar.session_offset(decision, PHASE32_OUTCOME_HORIZON_SESSIONS)
    return decision.date(), exit_session.date()


def _stage_for_decision(decision: date) -> str:
    if PHASE32_ACQUISITION_START <= decision <= PHASE32_DEVELOPMENT_LAST_SIGNAL_DATE:
        return "development"
    if PHASE32_PROTECTED_START_DATE <= decision <= PHASE32_PROTECTED_LAST_SIGNAL_DATE:
        return "protected_predictor_only"
    if PHASE32_DEVELOPMENT_LAST_SIGNAL_DATE < decision < PHASE32_PROTECTED_START_DATE:
        return "outer_embargo"
    return "outside_frozen_signal_window"


def _record_dict(value: object) -> dict[str, Any]:
    if is_dataclass(value):
        raw = asdict(value)
    elif isinstance(value, dict):
        raw = dict(value)
    else:
        raw = {
            key: getattr(value, key)
            for key in (
                "accession_number",
                "issuer_cik",
                "filing_date",
                "acceptance_datetime",
                "form",
                "item_codes",
                "primary_document",
                "source_url",
                "source_record_json",
                "source_record_sha256",
            )
            if hasattr(value, key)
        }
    if isinstance(raw.get("item_codes"), tuple):
        raw["item_codes"] = list(raw["item_codes"])
    return raw


def _reference_missing(exc: ProviderError) -> bool:
    text = str(exc)
    return "HTTP 404" in text or "HTTP 400" in text


class Phase32PredictorSourceAcquisition:
    """Resumable, source-only Phase32 full-history predictor builder."""

    def __init__(
        self,
        settings: Any,
        index_client: Any,
        semantic_client: Any,
        sec_client: Any,
        reference_provider: Any,
        *,
        identity_resolver: InstrumentIdentityResolver | None = None,
    ) -> None:
        self.settings = settings
        self.index_client = index_client
        self.semantic_client = semantic_client
        self.sec_client = sec_client
        self.reference_provider = reference_provider
        self.identity = identity_resolver or InstrumentIdentityResolver()
        self.provider_root = settings.resolved_path(settings.data.paths.provider)
        self.derived_root = settings.resolved_path(settings.data.paths.derived)
        self.evidence_root = self.provider_root / PHASE32_EVIDENCE_RELATIVE
        self.report_path = self.derived_root / PHASE32_REPORT_RELATIVE
        self.predictor_path = self.derived_root / PHASE32_PREDICTORS_RELATIVE
        self.cache_hits: Counter[str] = Counter()
        self.network_reads: Counter[str] = Counter()

    def _cached_taxonomy(self) -> tuple[dict[str, Any], ...]:
        path = self.evidence_root / "taxonomy.jsonl"
        if path.is_file():
            self.cache_hits["taxonomy"] += 1
            rows = _load_jsonl(path)
        else:
            self.network_reads["taxonomy"] += 1
            result = self.semantic_client.taxonomy()
            rows = tuple(dict(row) for row in result.rows)
            _write_jsonl(path, rows)
        actual = _sha256_file(path)
        if actual != PHASE32_ACCEPTED_TAXONOMY_SHA256:
            raise Phase32PredictorAcquisitionError(
                "Massive semantic taxonomy hash differs from accepted semantic V2 evidence"
            )
        return rows

    def _cached_month_rows(
        self,
        *,
        kind: str,
        start_date: date,
        end_date: date,
    ) -> tuple[dict[str, Any], ...]:
        path = self.evidence_root / kind / f"{start_date:%Y-%m}.jsonl"
        if path.is_file():
            self.cache_hits[kind] += 1
            rows = _load_jsonl(path)
        else:
            self.network_reads[kind] += 1
            if kind == "massive_index":
                result = self.index_client.eight_k_window(start_date=start_date, end_date=end_date)
            elif kind == "massive_disclosures":
                result = self.semantic_client.eight_k_disclosures(
                    start_date=start_date, end_date=end_date
                )
            else:  # pragma: no cover
                raise ValueError(f"unknown monthly cache kind {kind}")
            rows = tuple(dict(row) for row in result.rows)
            _write_jsonl(path, rows)
        for row in rows:
            filing_date = _parse_date(row.get("filing_date"), field="filing_date")
            if filing_date < start_date or filing_date > end_date:
                raise Phase32PredictorAcquisitionError(
                    f"cached {kind} row is outside {start_date}..{end_date}"
                )
        return rows

    def _cached_text(self, cik: str, filing_date: date) -> tuple[dict[str, Any], ...]:
        path = self.evidence_root / "massive_text" / cik / f"{filing_date.isoformat()}.jsonl"
        if path.is_file():
            self.cache_hits["massive_text"] += 1
            return _load_jsonl(path)
        self.network_reads["massive_text"] += 1
        rows = tuple(
            dict(row)
            for row in self.semantic_client.eight_k_text(cik=cik, filing_date=filing_date)
        )
        _write_jsonl(path, rows)
        return rows

    def _cached_sec(
        self, *, cik: str, accession: str, filing_date: date
    ) -> dict[str, Any]:
        path = self.evidence_root / "sec_submissions" / cik / f"{accession}.json"
        if path.is_file():
            self.cache_hits["sec_submissions"] += 1
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise Phase32PredictorAcquisitionError(f"cached SEC record is invalid: {path}")
            return value
        self.network_reads["sec_submissions"] += 1
        record = self.sec_client.filing_metadata(
            cik=cik, accession_number=accession, filing_date=filing_date.isoformat()
        )
        value = _record_dict(record)
        atomic_write_text(path, _canonical_json(value) + "\n", encoding="utf-8")
        return value

    def _cached_reference(self, *, ticker: str, as_of_date: date) -> dict[str, Any] | None:
        token = _safe_cache_token(ticker)
        path = self.evidence_root / "massive_reference" / as_of_date.isoformat() / f"{token}.json"
        if path.is_file():
            self.cache_hits["massive_reference"] += 1
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("ticker_requested") != ticker:
                raise Phase32PredictorAcquisitionError(f"cached reference evidence is invalid: {path}")
            if value.get("status") == "not_found":
                return None
            result = value.get("row")
            if not isinstance(result, dict):
                raise Phase32PredictorAcquisitionError(f"cached reference row is invalid: {path}")
            return result
        self.network_reads["massive_reference"] += 1
        try:
            row = dict(self.reference_provider.ticker_overview(ticker, as_of_date))
        except ProviderError as exc:
            if not _reference_missing(exc):
                raise
            atomic_write_text(
                path,
                _canonical_json(
                    {
                        "ticker_requested": ticker,
                        "as_of_date": as_of_date.isoformat(),
                        "status": "not_found",
                        "provider_error": str(exc),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            return None
        if str(row.get("ticker") or "").strip() != ticker:
            raise Phase32PredictorAcquisitionError(
                f"Massive ticker overview changed exact provider-native ticker: requested={ticker!r} actual={row.get('ticker')!r}"
            )
        atomic_write_text(
            path,
            _canonical_json(
                {
                    "ticker_requested": ticker,
                    "as_of_date": as_of_date.isoformat(),
                    "status": "ok",
                    "row": row,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return row

    def _resolve_instrument(
        self,
        *,
        tickers: tuple[str, ...],
        issuer_cik: str,
        decision_session: date,
        exit_session: date,
    ) -> tuple[dict[str, Any] | None, str | None]:
        resolved: dict[str, dict[str, Any]] = {}
        evidence: list[dict[str, Any]] = []
        for ticker in tickers:
            entry = self._cached_reference(ticker=ticker, as_of_date=decision_session)
            exit_row = self._cached_reference(ticker=ticker, as_of_date=exit_session)
            if entry is None or exit_row is None:
                evidence.append({"ticker": ticker, "status": "reference_missing"})
                continue
            try:
                entry_cik = _normalize_cik(entry.get("cik"))
                exit_cik = _normalize_cik(exit_row.get("cik"))
            except Phase32PredictorAcquisitionError:
                evidence.append({"ticker": ticker, "status": "reference_cik_missing"})
                continue
            if entry_cik != issuer_cik or exit_cik != issuer_cik:
                evidence.append({"ticker": ticker, "status": "filing_cik_mismatch"})
                continue
            entry_id, entry_key, entry_quality = self.identity.resolve(entry, decision_session)
            exit_id, exit_key, exit_quality = self.identity.resolve(exit_row, exit_session)
            entry_quality_text = str(entry_quality)
            exit_quality_text = str(exit_quality)
            if (
                entry_quality_text not in _ALLOWED_IDENTITY_QUALITIES
                or exit_quality_text not in _ALLOWED_IDENTITY_QUALITIES
            ):
                evidence.append({"ticker": ticker, "status": "fallback_identity"})
                continue
            if entry_id != exit_id:
                evidence.append({"ticker": ticker, "status": "identity_interval_changed"})
                continue
            resolved[entry_id] = {
                "instrument_id": entry_id,
                "identity_key": entry_key,
                "identity_quality": entry_quality_text,
                "ticker": ticker,
                "entry_reference_sha256": _sha256_text(_canonical_json(entry)),
                "exit_reference_sha256": _sha256_text(_canonical_json(exit_row)),
                "entry_identity_key": entry_key,
                "exit_identity_key": exit_key,
            }
            evidence.append({"ticker": ticker, "status": "resolved", "instrument_id": entry_id})
        if not resolved:
            return None, "NO_ELIGIBLE_PIT_INSTRUMENT"
        if len(resolved) != 1:
            return None, "AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS"
        row = next(iter(resolved.values()))
        row["mapping_evidence"] = evidence
        return row, None

    def run(self) -> dict[str, Any]:
        if phase32_policy_fingerprint() != PHASE32_FROZEN_POLICY_FINGERPRINT:
            raise Phase32PredictorAcquisitionError("Phase32 frozen policy fingerprint drifted")
        if IDENTITY_CONTRACT_VERSION != PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION:
            raise Phase32PredictorAcquisitionError("accepted instrument identity contract drifted")

        taxonomy = self._cached_taxonomy()
        frozen_triples = _candidate_taxonomy_map()
        observed_taxonomy = {
            (
                str(row.get("primary_category") or ""),
                str(row.get("secondary_category") or ""),
                str(row.get("tertiary_category") or ""),
            )
            for row in taxonomy
        }
        missing_frozen = sorted(set(frozen_triples) - observed_taxonomy)
        if missing_frozen:
            raise Phase32PredictorAcquisitionError(
                f"accepted taxonomy no longer contains frozen candidate triples: {missing_frozen}"
            )

        all_index: list[dict[str, Any]] = []
        all_disclosures: list[dict[str, Any]] = []
        month_reports: list[dict[str, Any]] = []
        for start_date, end_date in _month_windows(PHASE32_ACQUISITION_START, PHASE32_ACQUISITION_END):
            index_rows = self._cached_month_rows(
                kind="massive_index", start_date=start_date, end_date=end_date
            )
            disclosure_rows = self._cached_month_rows(
                kind="massive_disclosures", start_date=start_date, end_date=end_date
            )
            all_index.extend(index_rows)
            all_disclosures.extend(disclosure_rows)
            month_reports.append(
                {
                    "month": f"{start_date:%Y-%m}",
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "index_rows": len(index_rows),
                    "disclosure_rows": len(disclosure_rows),
                }
            )

        index_by_accession: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in all_index:
            index_by_accession[_nonblank(row.get("accession_number"), field="accession_number")].append(row)

        candidate_rows_by_accession: dict[str, list[tuple[dict[str, Any], str, str]]] = defaultdict(list)
        for row in all_disclosures:
            triple = (
                str(row.get("primary_category") or ""),
                str(row.get("secondary_category") or ""),
                str(row.get("tertiary_category") or ""),
            )
            assignment = frozen_triples.get(triple)
            if assignment is None:
                continue
            accession = _nonblank(row.get("accession_number"), field="accession_number")
            candidate_rows_by_accession[accession].append((row, assignment[0], assignment[1]))

        source_accessions = sorted(candidate_rows_by_accession)
        accession_records: list[dict[str, Any]] = []
        exclusion_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()

        for accession in source_accessions:
            assignments = candidate_rows_by_accession[accession]
            disclosure_rows = [item[0] for item in assignments]
            disclosure_ciks = {_normalize_cik(row.get("cik")) for row in disclosure_rows}
            disclosure_dates = {_parse_date(row.get("filing_date"), field="filing_date") for row in disclosure_rows}
            if len(disclosure_ciks) != 1 or len(disclosure_dates) != 1:
                raise Phase32PredictorAcquisitionError(
                    f"candidate disclosure accession has inconsistent CIK/date: {accession}"
                )
            issuer_cik = next(iter(disclosure_ciks))
            filing_date = next(iter(disclosure_dates))

            index_rows = index_by_accession.get(accession, [])
            if not index_rows:
                raise Phase32PredictorAcquisitionError(
                    f"candidate disclosure accession is absent from original-8-K index: {accession}"
                )
            for row in index_rows:
                if _normalize_cik(row.get("cik")) != issuer_cik:
                    raise Phase32PredictorAcquisitionError(
                        f"candidate accession CIK differs between disclosure and index: {accession}"
                    )
                if _parse_date(row.get("filing_date"), field="filing_date") != filing_date:
                    raise Phase32PredictorAcquisitionError(
                        f"candidate accession filing date differs between disclosure and index: {accession}"
                    )
                if row.get("form_type") != "8-K":
                    raise Phase32PredictorAcquisitionError(
                        f"candidate accession is not original 8-K in index: {accession}"
                    )

            sec = self._cached_sec(cik=issuer_cik, accession=accession, filing_date=filing_date)
            if _nonblank(sec.get("accession_number"), field="SEC accession_number") != accession:
                raise Phase32PredictorAcquisitionError(f"SEC accession mismatch: {accession}")
            if _normalize_cik(sec.get("issuer_cik")) != issuer_cik:
                raise Phase32PredictorAcquisitionError(f"SEC CIK mismatch: {accession}")
            if _parse_date(sec.get("filing_date"), field="SEC filing_date") != filing_date:
                raise Phase32PredictorAcquisitionError(f"SEC filing-date mismatch: {accession}")
            if sec.get("form") != "8-K":
                raise Phase32PredictorAcquisitionError(f"SEC original-form mismatch: {accession}")
            acceptance = _nonblank(sec.get("acceptance_datetime"), field="SEC acceptance_datetime")
            decision_session, exit_session = _decision_and_exit_sessions(acceptance)
            stage = _stage_for_decision(decision_session)

            text_rows = self._cached_text(issuer_cik, filing_date)
            matching_text = [
                row for row in text_rows if str(row.get("accession_number") or "").strip() == accession
            ]
            if len(matching_text) != 1:
                raise Phase32PredictorAcquisitionError(
                    f"candidate accession requires exactly one Massive Text row: {accession} count={len(matching_text)}"
                )
            text_row = matching_text[0]
            if _normalize_cik(text_row.get("cik")) != issuer_cik:
                raise Phase32PredictorAcquisitionError(f"Massive Text CIK mismatch: {accession}")

            tickers: set[str] = set()
            for row in disclosure_rows:
                values = row.get("tickers")
                if isinstance(values, list):
                    tickers.update(str(value).strip() for value in values if str(value).strip())
            for row in index_rows:
                value = row.get("ticker")
                if isinstance(value, str) and value.strip():
                    tickers.add(value.strip())
            text_ticker = text_row.get("ticker")
            if isinstance(text_ticker, str) and text_ticker.strip():
                tickers.add(text_ticker.strip())
            provider_tickers = tuple(sorted(tickers))

            candidate_ids = sorted({candidate_id for _, candidate_id, _ in assignments})
            directions = sorted({direction for _, _, direction in assignments})
            taxonomy_triples = sorted(
                {
                    (
                        str(row.get("primary_category") or ""),
                        str(row.get("secondary_category") or ""),
                        str(row.get("tertiary_category") or ""),
                    )
                    for row in disclosure_rows
                }
            )
            support_sha256 = sorted(
                {
                    _sha256_text(str(row.get("supporting_text") or ""))
                    for row in disclosure_rows
                }
            )

            base = {
                "accession_number": accession,
                "issuer_cik": issuer_cik,
                "filing_date": filing_date.isoformat(),
                "acceptance_datetime": acceptance,
                "decision_session": decision_session.isoformat(),
                "exit_session": exit_session.isoformat(),
                "stage": stage,
                "candidate_ids": candidate_ids,
                "directions": directions,
                "taxonomy_triples": [list(value) for value in taxonomy_triples],
                "provider_tickers": list(provider_tickers),
                "supporting_text_sha256": support_sha256,
                "sec_source_record_sha256": sec.get("source_record_sha256"),
                "massive_text_sha256": _sha256_text(_canonical_json(text_row)),
                "index_row_count": len(index_rows),
                "disclosure_row_count": len(disclosure_rows),
            }
            source_counts[stage] += 1

            if stage not in {"development", "protected_predictor_only"}:
                base["eligibility"] = "excluded"
                base["exclusion_reason"] = stage.upper()
                exclusion_counts[stage.upper()] += 1
                accession_records.append(base)
                continue
            if not provider_tickers:
                base["eligibility"] = "excluded"
                base["exclusion_reason"] = "NO_PROVIDER_TICKER_MAPPING"
                exclusion_counts["NO_PROVIDER_TICKER_MAPPING"] += 1
                accession_records.append(base)
                continue

            resolved, exclusion = self._resolve_instrument(
                tickers=provider_tickers,
                issuer_cik=issuer_cik,
                decision_session=decision_session,
                exit_session=exit_session,
            )
            if resolved is None:
                base["eligibility"] = "excluded"
                base["exclusion_reason"] = exclusion
                exclusion_counts[str(exclusion)] += 1
            else:
                base["eligibility"] = "eligible"
                base["instrument"] = resolved
            accession_records.append(base)

        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in accession_records:
            if row.get("eligibility") != "eligible":
                continue
            instrument = row["instrument"]
            instrument_id = str(instrument["instrument_id"])
            decision_session = str(row["decision_session"])
            for candidate_id in row["candidate_ids"]:
                candidate = next(item for item in PHASE32_CANDIDATES if item.candidate_id == candidate_id)
                key = (instrument_id, decision_session, candidate_id)
                group = grouped.setdefault(
                    key,
                    {
                        "candidate_id": candidate_id,
                        "direction": candidate.direction,
                        "instrument_id": instrument_id,
                        "identity_key": instrument["identity_key"],
                        "identity_quality": instrument["identity_quality"],
                        "decision_session": decision_session,
                        "exit_session": str(row["exit_session"]),
                        "stage": row["stage"],
                        "issuer_cik": row["issuer_cik"],
                        "accession_numbers": [],
                        "provider_tickers": [],
                        "taxonomy_triples": [],
                        "acceptance_datetimes": [],
                        "source_lineage_sha256": [],
                    },
                )
                if group["exit_session"] != row["exit_session"] or group["issuer_cik"] != row["issuer_cik"]:
                    raise Phase32PredictorAcquisitionError(
                        f"grouped predictor invariant changed within {key}"
                    )
                group["accession_numbers"].append(row["accession_number"])
                group["provider_tickers"].extend(row["provider_tickers"])
                group["taxonomy_triples"].extend(row["taxonomy_triples"])
                group["acceptance_datetimes"].append(row["acceptance_datetime"])
                group["source_lineage_sha256"].extend(
                    [row["sec_source_record_sha256"], row["massive_text_sha256"]]
                    + row["supporting_text_sha256"]
                )

        contradictory_pairs: set[tuple[str, str]] = set()
        directions_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
        for group in grouped.values():
            pair = (str(group["instrument_id"]), str(group["decision_session"]))
            directions_by_pair[pair].add(str(group["direction"]))
        for pair, directions in directions_by_pair.items():
            if "LONG" in directions and "SHORT" in directions:
                contradictory_pairs.add(pair)

        predictors: list[dict[str, Any]] = []
        for key in sorted(grouped):
            group = grouped[key]
            pair = (str(group["instrument_id"]), str(group["decision_session"]))
            if pair in contradictory_pairs:
                exclusion_counts["CONTRADICTORY_LONG_SHORT_INSTRUMENT_SESSION"] += 1
                continue
            for list_field in (
                "accession_numbers",
                "provider_tickers",
                "acceptance_datetimes",
                "source_lineage_sha256",
            ):
                group[list_field] = sorted(set(group[list_field]))
            group["taxonomy_triples"] = sorted(
                {tuple(value) for value in group["taxonomy_triples"]}
            )
            group["taxonomy_triples"] = [list(value) for value in group["taxonomy_triples"]]
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
        _write_jsonl(self.predictor_path, predictors)
        accession_path = self.evidence_root / "candidate_accession_records.jsonl"
        _write_jsonl(accession_path, accession_records)

        candidate_counts = Counter(str(row["candidate_id"]) for row in predictors)
        stage_counts = Counter(str(row["stage"]) for row in predictors)
        report: dict[str, Any] = {
            "contract_version": PHASE32_PREDICTOR_ACQUISITION_CONTRACT,
            "policy_fingerprint": PHASE32_FROZEN_POLICY_FINGERPRINT,
            "identity_contract_version": PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION,
            "acquisition_start": PHASE32_ACQUISITION_START.isoformat(),
            "acquisition_end": PHASE32_ACQUISITION_END.isoformat(),
            "taxonomy_sha256": PHASE32_ACCEPTED_TAXONOMY_SHA256,
            "monthly_windows": month_reports,
            "total_index_rows": len(all_index),
            "total_disclosure_rows": len(all_disclosures),
            "frozen_candidate_source_accessions": len(source_accessions),
            "candidate_accession_records": len(accession_records),
            "eligible_predictor_rows": len(predictors),
            "candidate_predictor_counts": dict(sorted(candidate_counts.items())),
            "stage_predictor_counts": dict(sorted(stage_counts.items())),
            "source_stage_accession_counts": dict(sorted(source_counts.items())),
            "exclusion_counts": dict(sorted(exclusion_counts.items())),
            "contradictory_instrument_sessions": len(contradictory_pairs),
            "cache_hits": dict(sorted(self.cache_hits.items())),
            "network_reads": dict(sorted(self.network_reads.items())),
            "candidate_accession_evidence_sha256": _sha256_file(accession_path),
            "predictor_rows_sha256": _sha256_file(self.predictor_path),
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
            "pass": True,
        }
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path)
        report["predictor_path"] = str(self.predictor_path)
        return report
