from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping

import duckdb

from packages.core.atomic_io import atomic_write_text
from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar import (
    SECEDGARClient,
    SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP,
    sec_company_submissions_url,
    sec_submission_shard_url,
)
from packages.providers.sec_edgar_archive import (
    SECEDGARArchiveClient,
    sec_archive_submission_url,
)

from .literature_momseason_adjusted_predictor_source import _clean_symbol
from .literature_momseason_development import MomSeasonDevelopmentResearch
from .literature_momseason_source import canonical_json


LIT01_DEVELOPMENT_IDENTITY_REPAIR_VERSION = (
    "lit01-development-target-identity-v5-active-pit-figi-events-sec-8k-continuity"
)
LIT01_IDENTITY_EVIDENCE_CONTRACT = (
    "lit01-development-target-continuity-evidence-v1-massive-composite-figi-pre-outcome"
)
LIT01_SEC_IDENTITY_EVIDENCE_CONTRACT = (
    "lit01-development-target-continuity-evidence-v1-sec-8k-explicit-ticker-change-pre-outcome"
)
LIT01_SEC_TICKER_CHANGE_LOOKBACK_DAYS = 31
LIT01_SEC_TICKER_CHANGE_MAX_FILINGS = 24
_SAFE_IDENTITY_QUALITIES = frozenset({"strong", "medium"})

_MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MONTH_PATTERN = "|".join(name.title() for name in _MONTH_NAMES)
_WEEKDAY_PATTERN = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
_EFFECTIVE_DATE_RE = re.compile(
    rf"(?i:\b(?:effective|commencing|beginning)(?:\s+(?:on|as\s+of))?\s+)"
    rf"(?:(?i:{_WEEKDAY_PATTERN})\s*,?\s*)?"
    rf"(?P<month>{_MONTH_PATTERN})\s+(?P<day>\d{{1,2}}),\s+(?P<year>\d{{4}})"
)
_EFFECTIVE_ISO_DATE_RE = re.compile(
    r"(?i:\b(?:effective|commencing|beginning)(?:\s+(?:on|as\s+of))?\s+)"
    r"(?P<iso>\d{4}-\d{2}-\d{2})"
)


def _safe_ticker_sets(
    rows: list[dict[str, object]],
) -> tuple[set[str], set[str]]:
    safe: set[str] = set()
    active: set[str] = set()
    for row in rows:
        quality = str(row.get("identity_quality") or "").strip().lower()
        ticker = _clean_symbol(row.get("ticker"))
        if quality not in _SAFE_IDENTITY_QUALITIES or ticker is None:
            continue
        safe.add(ticker)
        if bool(row.get("active", True)):
            active.add(ticker)
    return safe, active


def _regular_alias_with_when_issued_variant(aliases: set[str]) -> str | None:
    """Return the regular alias for the exact ``BASE`` + ``BASEw`` pattern.

    NYSE/CTA symbol convention uses a lowercase trailing ``w`` as the compact
    representation of the ``WI`` (When Issued) suffix. The rule is deliberately
    narrow and case-sensitive: only an exact two-alias set ``{BASE, BASEw}`` is
    resolved here. Any other simultaneous-alias shape remains ambiguous.
    """

    if len(aliases) != 2:
        return None
    for candidate in aliases:
        if f"{candidate}w" in aliases:
            return candidate
    return None


def _unique_authoritative_composite_figi(
    rows: list[dict[str, object]],
    *,
    endpoint_session: date,
    instrument_id: str,
) -> str | None:
    """Return one Composite FIGI only when PIT evidence is internally consistent."""

    figis: set[str] = set()
    for row in rows:
        quality = str(row.get("identity_quality") or "").strip().lower()
        if quality not in _SAFE_IDENTITY_QUALITIES:
            continue
        value = str(row.get("composite_figi") or "").strip().upper()
        if value:
            figis.add(value)
    if len(figis) > 1:
        raise RuntimeError(
            "multiple Composite FIGIs appear for one stable LIT-01 development "
            f"instrument: {endpoint_session} {instrument_id} figis={sorted(figis)}"
        )
    return next(iter(figis)) if figis else None


def _unique_authoritative_cik(
    rows: list[dict[str, object]],
    *,
    endpoint_session: date,
    instrument_id: str,
) -> str | None:
    """Return one zero-padded SEC CIK only from internally consistent safe PIT rows."""

    ciks: set[str] = set()
    for row in rows:
        quality = str(row.get("identity_quality") or "").strip().lower()
        if quality not in _SAFE_IDENTITY_QUALITIES:
            continue
        raw = str(row.get("cik") or "").strip()
        if not raw:
            continue
        if not raw.isdigit():
            raise RuntimeError(
                "non-numeric SEC CIK appears on safe LIT-01 PIT identity row: "
                f"{endpoint_session} {instrument_id} cik={raw!r}"
            )
        ciks.add(str(int(raw)).zfill(10))
    if len(ciks) > 1:
        raise RuntimeError(
            "multiple SEC CIKs appear for one stable LIT-01 development instrument: "
            f"{endpoint_session} {instrument_id} ciks={sorted(ciks)}"
        )
    return next(iter(ciks)) if ciks else None


def authoritative_ticker_from_massive_events(
    raw_events: list[dict[str, object]],
    *,
    endpoint_session: date,
    instrument_id: str,
) -> str | None:
    """Resolve the ticker valid at ``endpoint_session`` from Massive ticker events."""

    by_date: dict[date, set[str]] = {}
    for raw in raw_events:
        if str(raw.get("type") or "").strip().lower() != "ticker_change":
            continue
        raw_date = raw.get("date")
        change = raw.get("ticker_change")
        if not raw_date or not isinstance(change, dict):
            continue
        ticker = _clean_symbol(change.get("ticker"))
        if ticker is None:
            continue
        try:
            event_date = date.fromisoformat(str(raw_date))
        except ValueError:
            continue
        by_date.setdefault(event_date, set()).add(ticker)

    for event_date, tickers in sorted(by_date.items()):
        if len(tickers) > 1:
            raise RuntimeError(
                "Massive Composite-FIGI ticker events report multiple tickers on one "
                "event date for LIT-01 development continuity: "
                f"{instrument_id} {event_date} aliases={sorted(tickers)}"
            )

    eligible = [event_date for event_date in by_date if event_date <= endpoint_session]
    if not eligible:
        return None
    latest = max(eligible)
    return next(iter(by_date[latest]))


def _plain_sec_submission_text(text: str) -> str:
    value = html.unescape(text)
    value = re.sub(r"(?is)<script\b.*?</script>", " ", value)
    value = re.sub(r"(?is)<style\b.*?</style>", " ", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _ticker_token(ticker: str) -> str:
    return rf"(?<![A-Za-z0-9])[\"'“”]?{re.escape(ticker)}[\"'“”]?(?![A-Za-z0-9])"


def _effective_dates_in_context(context: str) -> set[date]:
    values: set[date] = set()
    for match in _EFFECTIVE_DATE_RE.finditer(context):
        month = _MONTH_NAMES[match.group("month").lower()]
        try:
            values.add(date(int(match.group("year")), month, int(match.group("day"))))
        except ValueError:
            continue
    for match in _EFFECTIVE_ISO_DATE_RE.finditer(context):
        try:
            values.add(date.fromisoformat(match.group("iso")))
        except ValueError:
            continue
    return values


def authoritative_ticker_from_sec_filing_text(
    text: str,
    *,
    aliases: set[str],
    endpoint_session: date,
    instrument_id: str,
) -> dict[str, object] | None:
    """Resolve an explicit SEC-disclosed ticker-symbol transition without prices.

    The parser accepts only a narrow issuer statement that a trading/ticker symbol
    changed (or will change) from one provided PIT alias to another and an explicit
    effective/commencing/beginning date in the nearby filing text. Mere co-mention of
    two aliases is never enough.
    """

    clean_aliases = sorted({ticker for ticker in aliases if _clean_symbol(ticker) == ticker})
    if len(clean_aliases) < 2:
        return None
    plain = _plain_sec_submission_text(text)
    transitions: dict[tuple[str, str, date], str] = {}
    for old_ticker in clean_aliases:
        for new_ticker in clean_aliases:
            if old_ticker == new_ticker:
                continue
            pattern = re.compile(
                rf"(?is:(?i:(?:trading|ticker)\s+symbol).{{0,700}}?"
                rf"(?i:(?:(?:will\s+)?chang(?:e|ed|es|ing)\s+)?from)\s+"
                rf"{_ticker_token(old_ticker)}\s+(?i:to)\s+{_ticker_token(new_ticker)})"
            )
            for match in pattern.finditer(plain):
                start = max(0, match.start() - 400)
                end = min(len(plain), match.end() + 400)
                context = plain[start:end]
                effective_dates = _effective_dates_in_context(context)
                for effective_date in effective_dates:
                    transitions[(old_ticker, new_ticker, effective_date)] = context[:1600]

    if not transitions:
        return None
    if len(transitions) > 1:
        values = [
            f"{old}->{new}@{effective.isoformat()}"
            for old, new, effective in sorted(transitions)
        ]
        raise RuntimeError(
            "SEC filing text contains multiple explicit ticker-change interpretations for "
            f"LIT-01 development continuity: {instrument_id} transitions={values}"
        )

    (old_ticker, new_ticker, effective_date), excerpt = next(iter(transitions.items()))
    resolved = new_ticker if endpoint_session >= effective_date else old_ticker
    return {
        "old_ticker": old_ticker,
        "new_ticker": new_ticker,
        "effective_date": effective_date.isoformat(),
        "resolved_ticker": resolved,
        "matched_excerpt": excerpt,
        "resolution_rule": "EXPLICIT_SEC_TICKER_CHANGE_EFFECTIVE_DATE",
    }


def _columnar_sec_rows(block: object) -> list[dict[str, object]]:
    if not isinstance(block, dict):
        return []
    accessions = block.get("accessionNumber")
    if not isinstance(accessions, list):
        return []
    fields = ("accessionNumber", "filingDate", "form", "items", "primaryDocument")
    rows: list[dict[str, object]] = []
    for index in range(len(accessions)):
        row: dict[str, object] = {}
        for field in fields:
            values = block.get(field)
            row[field] = values[index] if isinstance(values, list) and index < len(values) else ""
        rows.append(row)
    return rows


def _sec_rows_from_payload(payload: dict[str, object]) -> list[dict[str, object]]:
    rows = _columnar_sec_rows(payload)
    filings = payload.get("filings")
    if isinstance(filings, dict):
        rows.extend(_columnar_sec_rows(filings.get("recent")))
    return rows


def _sec_declared_shards_for_window(
    payload: dict[str, object],
    *,
    start_date: date,
    end_date: date,
) -> list[str]:
    filings = payload.get("filings")
    files = filings.get("files") if isinstance(filings, dict) else None
    candidates: list[tuple[date, date, str]] = []
    if isinstance(files, list):
        for item in files:
            if not isinstance(item, dict):
                continue
            try:
                filing_from = date.fromisoformat(str(item.get("filingFrom") or ""))
                filing_to = date.fromisoformat(str(item.get("filingTo") or ""))
            except ValueError:
                continue
            if filing_from > filing_to or filing_to < start_date or filing_from > end_date:
                continue
            url = sec_submission_shard_url(item.get("name"))
            candidates.append((filing_from, filing_to, url))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    if len(candidates) > SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP:
        raise RuntimeError(
            "SEC submissions ticker-change lookup exceeded bounded declared-shard count: "
            f"{len(candidates)} > {SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP}"
        )
    return [item[2] for item in candidates]


def _filtered_sec_8k_rows(
    rows: list[dict[str, object]],
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, object]]:
    unique: dict[str, dict[str, object]] = {}
    for row in rows:
        accession = str(row.get("accessionNumber") or "").strip()
        filing_text = str(row.get("filingDate") or "").strip()
        form = str(row.get("form") or "").strip()
        if not accession or form != "8-K":
            continue
        try:
            filing_date = date.fromisoformat(filing_text)
        except ValueError:
            continue
        if not (start_date <= filing_date <= end_date):
            continue
        item_codes = {
            item.strip()
            for item in re.split(r"[,;]", str(row.get("items") or ""))
            if item.strip()
        }
        unique[accession] = {
            "accession_number": accession,
            "filing_date": filing_date.isoformat(),
            "form": form,
            "items": sorted(item_codes),
            "primary_document": str(row.get("primaryDocument") or "").strip() or None,
        }
    ordered = sorted(
        unique.values(),
        key=lambda item: (str(item["filing_date"]), str(item["accession_number"])),
        reverse=True,
    )
    if len(ordered) > LIT01_SEC_TICKER_CHANGE_MAX_FILINGS:
        raise RuntimeError(
            "SEC ticker-change source search exceeded the frozen bounded 8-K count: "
            f"{len(ordered)} > {LIT01_SEC_TICKER_CHANGE_MAX_FILINGS}"
        )
    return ordered


def resolve_target_ticker_from_pit_rows(
    rows: list[dict[str, object]],
    *,
    endpoint_session: date,
    instrument_id: str,
    authoritative_ticker: str | None,
) -> tuple[str | None, str]:
    """Resolve one endpoint alias without using price/outcome information."""

    safe, active = _safe_ticker_sets(rows)
    authoritative = _clean_symbol(authoritative_ticker)

    if len(active) == 1:
        return next(iter(active)), "UNIQUE_ACTIVE_PIT_ALIAS"

    if len(active) > 1:
        if authoritative is not None and authoritative in active:
            return authoritative, "AUTHORITATIVE_INTERVAL_ACTIVE_ALIAS"
        regular = _regular_alias_with_when_issued_variant(active)
        if regular is not None:
            return regular, "REGULAR_ALIAS_WITH_WHEN_ISSUED_VARIANT"
        raise RuntimeError(
            "ambiguous active PIT ticker for development target endpoint without "
            "unique authoritative continuity evidence or exact regular/When-Issued "
            "alias semantics: "
            f"{endpoint_session} {instrument_id} aliases={sorted(active)}"
        )

    if len(safe) == 1:
        return next(iter(safe)), "UNIQUE_SAFE_PIT_ALIAS"

    if len(safe) > 1:
        if authoritative is not None and authoritative in safe:
            return authoritative, "AUTHORITATIVE_INTERVAL_SAFE_ALIAS"
        raise RuntimeError(
            "ambiguous PIT ticker for development target endpoint without unique "
            "authoritative continuity evidence: "
            f"{endpoint_session} {instrument_id} aliases={sorted(safe)}"
        )

    return None, "NO_SAFE_PIT_ALIAS"


class MomSeasonDevelopmentResearchIdentitySafe(MomSeasonDevelopmentResearch):
    """LIT-01 development runner with source-grounded target alias resolution."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._allow_identity_source_acquisition = False
        self._identity_provider_calls_this_run = 0
        self._identity_cache_hits_this_run = 0
        self._identity_resolutions_this_run = 0
        self._sec_provider_calls_this_run = 0
        self._sec_cache_hits_this_run = 0
        self._sec_resolutions_this_run = 0
        self._sec_urls_requested_this_run: set[str] = set()
        self._sec_submissions_client: SECEDGARClient | None = None
        self._sec_archive_client: SECEDGARArchiveClient | None = None

    def identity_evidence_path(self, instrument_id: str) -> Path:
        return self.root / "identity_continuity" / f"instrument_id={instrument_id}.json"

    def sec_identity_evidence_path(self, instrument_id: str, endpoint_session: date) -> Path:
        return (
            self.root
            / "identity_continuity_sec"
            / f"instrument_id={instrument_id}"
            / f"endpoint={endpoint_session.isoformat()}.json"
        )

    def _authoritative_interval_ticker(
        self,
        *,
        endpoint_session: date,
        instrument_id: str,
    ) -> str | None:
        path = self.native.paths.authoritative_ticker_intervals_file()
        if not path.is_file():
            return None
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                """
                SELECT ticker
                FROM read_parquet(?)
                WHERE instrument_id = ?
                  AND continuity_authority = TRUE
                  AND valid_from_date <= ?
                  AND (valid_to_date_exclusive IS NULL OR ? < valid_to_date_exclusive)
                ORDER BY ticker
                """,
                [str(path), instrument_id, endpoint_session, endpoint_session],
            ).fetchall()
        finally:
            con.close()
        tickers = sorted(
            {ticker for row in rows if (ticker := _clean_symbol(row[0])) is not None}
        )
        if len(tickers) > 1:
            raise RuntimeError(
                "multiple authoritative ticker intervals cover one LIT-01 development "
                f"endpoint: {endpoint_session} {instrument_id} aliases={tickers}"
            )
        return tickers[0] if tickers else None

    def _load_or_acquire_identity_events(
        self,
        *,
        endpoint_session: date,
        instrument_id: str,
        rows: list[dict[str, object]],
    ) -> list[dict[str, object]] | None:
        composite_figi = _unique_authoritative_composite_figi(
            rows,
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
        )
        if composite_figi is None:
            return None

        path = self.identity_evidence_path(instrument_id)
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("contract_version") != LIT01_IDENTITY_EVIDENCE_CONTRACT:
                raise RuntimeError(f"LIT-01 identity evidence contract mismatch: {instrument_id}")
            if payload.get("instrument_id") != instrument_id:
                raise RuntimeError(f"LIT-01 identity evidence instrument mismatch: {instrument_id}")
            if payload.get("query_identifier_type") != "composite_figi":
                raise RuntimeError(
                    f"LIT-01 identity evidence is not Composite-FIGI authoritative: {instrument_id}"
                )
            if str(payload.get("query_identifier") or "").upper() != composite_figi:
                raise RuntimeError(
                    "LIT-01 identity evidence Composite FIGI differs from PIT source: "
                    f"{instrument_id}"
                )
            if not bool(payload.get("continuity_authority")):
                raise RuntimeError(f"LIT-01 identity evidence lacks continuity authority: {instrument_id}")
            raw = payload.get("raw_events")
            if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
                raise RuntimeError(
                    f"LIT-01 identity evidence raw event payload is invalid: {instrument_id}"
                )
            expected_fingerprint = hashlib.sha256(
                canonical_json(raw).encode("utf-8")
            ).hexdigest()
            if payload.get("provider_response_fingerprint") != expected_fingerprint:
                raise RuntimeError(f"LIT-01 identity evidence fingerprint mismatch: {instrument_id}")
            self._identity_cache_hits_this_run += 1
            return [dict(item) for item in raw]

        if not self._allow_identity_source_acquisition:
            return None

        raw_events = self.native.source.reference_provider.ticker_events(composite_figi)
        if not isinstance(raw_events, list) or not all(isinstance(item, dict) for item in raw_events):
            raise RuntimeError(f"Massive ticker-event response is invalid for {instrument_id}")
        self._identity_provider_calls_this_run += 1
        normalized_raw = [dict(item) for item in raw_events]
        payload = {
            "contract_version": LIT01_IDENTITY_EVIDENCE_CONTRACT,
            "identity_repair_version": LIT01_DEVELOPMENT_IDENTITY_REPAIR_VERSION,
            "instrument_id": instrument_id,
            "query_identifier": composite_figi,
            "query_identifier_type": "composite_figi",
            "continuity_authority": True,
            "provider": "Massive",
            "source_endpoint": "ticker_events",
            "source_only_pre_outcome": True,
            "raw_events": normalized_raw,
            "provider_response_fingerprint": hashlib.sha256(
                canonical_json(normalized_raw).encode("utf-8")
            ).hexdigest(),
            "development_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, canonical_json(payload) + "\n")
        return normalized_raw

    def _isolated_authoritative_ticker(
        self,
        *,
        endpoint_session: date,
        instrument_id: str,
        rows: list[dict[str, object]],
    ) -> str | None:
        raw_events = self._load_or_acquire_identity_events(
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
            rows=rows,
        )
        if raw_events is None:
            return None
        return authoritative_ticker_from_massive_events(
            raw_events,
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
        )

    def _ensure_sec_clients(self) -> tuple[SECEDGARClient, SECEDGARArchiveClient]:
        try:
            if self._sec_submissions_client is None:
                self._sec_submissions_client = SECEDGARClient()
            if self._sec_archive_client is None:
                self._sec_archive_client = SECEDGARArchiveClient()
        except ProviderError as exc:
            raise RuntimeError(
                "official SEC identity-continuity source could not initialize under the "
                "existing ATLAS fair-access configuration"
            ) from exc
        return self._sec_submissions_client, self._sec_archive_client

    def _sec_get_json(self, url: str) -> tuple[dict[str, object], str]:
        submissions, _archive = self._ensure_sec_clients()
        if url not in self._sec_urls_requested_this_run:
            self._sec_provider_calls_this_run += 1
            self._sec_urls_requested_this_run.add(url)
        try:
            payload, text = submissions.get_json(url)
        except ProviderError as exc:
            raise RuntimeError(f"official SEC submissions identity read failed: {url}") from exc
        return dict(payload), text

    def _sec_get_submission(self, filename: str):
        _submissions, archive = self._ensure_sec_clients()
        url = sec_archive_submission_url(filename)
        if url not in self._sec_urls_requested_this_run:
            self._sec_provider_calls_this_run += 1
            self._sec_urls_requested_this_run.add(url)
        try:
            return archive.complete_submission(filename=filename)
        except ProviderError as exc:
            raise RuntimeError(f"official SEC archive identity read failed: {url}") from exc

    def _candidate_sec_8k_filings(
        self,
        *,
        cik: str,
        endpoint_session: date,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        start_date = endpoint_session - timedelta(days=LIT01_SEC_TICKER_CHANGE_LOOKBACK_DAYS)
        root_url = sec_company_submissions_url(cik=cik)
        root, root_text = self._sec_get_json(root_url)
        source_records: list[dict[str, object]] = [
            {
                "source_url": root_url,
                "source_sha256": hashlib.sha256(root_text.encode("utf-8")).hexdigest(),
            }
        ]
        rows = _sec_rows_from_payload(root)
        for shard_url in _sec_declared_shards_for_window(
            root,
            start_date=start_date,
            end_date=endpoint_session,
        ):
            shard, shard_text = self._sec_get_json(shard_url)
            source_records.append(
                {
                    "source_url": shard_url,
                    "source_sha256": hashlib.sha256(shard_text.encode("utf-8")).hexdigest(),
                }
            )
            rows.extend(_sec_rows_from_payload(shard))
        return (
            _filtered_sec_8k_rows(rows, start_date=start_date, end_date=endpoint_session),
            source_records,
        )

    def _load_or_acquire_sec_identity_ticker(
        self,
        *,
        endpoint_session: date,
        instrument_id: str,
        rows: list[dict[str, object]],
    ) -> str | None:
        safe, active = _safe_ticker_sets(rows)
        aliases = active if len(active) > 1 else safe
        if len(aliases) < 2:
            return None
        cik = _unique_authoritative_cik(
            rows,
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
        )
        if cik is None:
            return None

        path = self.sec_identity_evidence_path(instrument_id, endpoint_session)
        expected_aliases = sorted(aliases)
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("contract_version") != LIT01_SEC_IDENTITY_EVIDENCE_CONTRACT:
                raise RuntimeError(f"LIT-01 SEC identity evidence contract mismatch: {instrument_id}")
            if payload.get("instrument_id") != instrument_id:
                raise RuntimeError(f"LIT-01 SEC identity evidence instrument mismatch: {instrument_id}")
            if payload.get("endpoint_session") != endpoint_session.isoformat():
                raise RuntimeError(f"LIT-01 SEC identity evidence endpoint mismatch: {instrument_id}")
            if payload.get("issuer_cik") != cik or payload.get("aliases") != expected_aliases:
                raise RuntimeError(
                    f"LIT-01 SEC identity evidence no longer matches PIT identity: {instrument_id}"
                )
            fingerprint = str(payload.get("evidence_fingerprint") or "")
            core = dict(payload)
            core.pop("evidence_fingerprint", None)
            expected = hashlib.sha256(canonical_json(core).encode("utf-8")).hexdigest()
            if fingerprint != expected:
                raise RuntimeError(f"LIT-01 SEC identity evidence fingerprint mismatch: {instrument_id}")
            self._sec_cache_hits_this_run += 1
            resolved = _clean_symbol(payload.get("resolved_ticker"))
            if resolved is not None:
                self._sec_resolutions_this_run += 1
            return resolved

        if not self._allow_identity_source_acquisition:
            return None

        filings, submission_sources = self._candidate_sec_8k_filings(
            cik=cik,
            endpoint_session=endpoint_session,
        )
        examined: list[dict[str, object]] = []
        transitions_seen: dict[tuple[str, str, str], dict[str, object]] = {}
        for filing in filings:
            accession = str(filing["accession_number"])
            filename = f"edgar/data/{int(cik)}/{accession}.txt"
            document = self._sec_get_submission(filename)
            transition = authoritative_ticker_from_sec_filing_text(
                document.text,
                aliases=set(aliases),
                endpoint_session=endpoint_session,
                instrument_id=instrument_id,
            )
            item: dict[str, object] = {
                **filing,
                "source_url": document.source_url,
                "source_sha256": document.source_sha256,
                "transition": transition,
            }
            examined.append(item)
            if transition is not None:
                key = (
                    str(transition["old_ticker"]),
                    str(transition["new_ticker"]),
                    str(transition["effective_date"]),
                )
                transitions_seen[key] = transition

        if len(transitions_seen) > 1:
            values = [
                f"{old}->{new}@{effective}"
                for old, new, effective in sorted(transitions_seen)
            ]
            raise RuntimeError(
                "official SEC filings establish conflicting ticker-change facts for one LIT-01 "
                f"development endpoint: {endpoint_session} {instrument_id} transitions={values}"
            )
        transition = next(iter(transitions_seen.values())) if transitions_seen else None
        resolved_ticker = str(transition["resolved_ticker"]) if transition is not None else None
        core_payload: dict[str, object] = {
            "contract_version": LIT01_SEC_IDENTITY_EVIDENCE_CONTRACT,
            "identity_repair_version": LIT01_DEVELOPMENT_IDENTITY_REPAIR_VERSION,
            "instrument_id": instrument_id,
            "endpoint_session": endpoint_session.isoformat(),
            "issuer_cik": cik,
            "aliases": expected_aliases,
            "lookback_days": LIT01_SEC_TICKER_CHANGE_LOOKBACK_DAYS,
            "max_8k_filings": LIT01_SEC_TICKER_CHANGE_MAX_FILINGS,
            "provider": "SEC EDGAR",
            "submissions_sources": submission_sources,
            "filings_examined": examined,
            "resolved_ticker": resolved_ticker,
            "source_only_pre_outcome": True,
            "existing_canonical_sec_data_mutated": False,
            "development_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
        }
        payload = {
            **core_payload,
            "evidence_fingerprint": hashlib.sha256(
                canonical_json(core_payload).encode("utf-8")
            ).hexdigest(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, canonical_json(payload) + "\n")
        if resolved_ticker is not None:
            self._sec_resolutions_this_run += 1
        return resolved_ticker

    def _historical_ticker_for_target(
        self,
        *,
        endpoint_session: date,
        instrument_id: str,
        formation_ticker: str,
        historical: Mapping[date, Mapping[str, list[dict[str, object]]]],
    ) -> str:
        authoritative = self._authoritative_interval_ticker(
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
        )

        if endpoint_session in historical:
            rows = list(historical[endpoint_session].get(instrument_id, []))
            try:
                resolved, _reason = resolve_target_ticker_from_pit_rows(
                    rows,
                    endpoint_session=endpoint_session,
                    instrument_id=instrument_id,
                    authoritative_ticker=authoritative,
                )
            except RuntimeError as initial_error:
                massive_ticker = self._isolated_authoritative_ticker(
                    endpoint_session=endpoint_session,
                    instrument_id=instrument_id,
                    rows=rows,
                )
                if massive_ticker is not None:
                    try:
                        resolved, _reason = resolve_target_ticker_from_pit_rows(
                            rows,
                            endpoint_session=endpoint_session,
                            instrument_id=instrument_id,
                            authoritative_ticker=massive_ticker,
                        )
                    except RuntimeError:
                        resolved = None
                    else:
                        self._identity_resolutions_this_run += 1
                        return resolved

                sec_ticker = self._load_or_acquire_sec_identity_ticker(
                    endpoint_session=endpoint_session,
                    instrument_id=instrument_id,
                    rows=rows,
                )
                if sec_ticker is not None:
                    resolved, _reason = resolve_target_ticker_from_pit_rows(
                        rows,
                        endpoint_session=endpoint_session,
                        instrument_id=instrument_id,
                        authoritative_ticker=sec_ticker,
                    )
                    if resolved is not None:
                        return resolved

                if not self._allow_identity_source_acquisition:
                    raise RuntimeError(
                        f"{initial_error}; rerun with --acquire to permit source-only "
                        "Composite-FIGI ticker-event and official SEC 8-K continuity acquisition"
                    ) from initial_error
                raise RuntimeError(
                    f"{initial_error}; neither Massive Composite-FIGI ticker events nor bounded "
                    "official SEC 8-K ticker-change evidence established a ticker valid at this endpoint"
                ) from initial_error
            if resolved is not None:
                return resolved

        if authoritative is not None:
            return authoritative

        ticker = _clean_symbol(formation_ticker)
        if ticker is None:
            raise RuntimeError(
                f"invalid formation ticker for development target endpoint: {instrument_id}"
            )
        return ticker

    def run(
        self,
        *,
        acquire: bool = False,
        force_plan: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        self._allow_identity_source_acquisition = bool(acquire)
        self._identity_provider_calls_this_run = 0
        self._identity_cache_hits_this_run = 0
        self._identity_resolutions_this_run = 0
        self._sec_provider_calls_this_run = 0
        self._sec_cache_hits_this_run = 0
        self._sec_resolutions_this_run = 0
        self._sec_urls_requested_this_run = set()
        try:
            result = super().run(
                acquire=acquire,
                force_plan=force_plan,
                force_acquire=force_acquire,
            )
        finally:
            self._allow_identity_source_acquisition = False

        total_identity_calls = self._identity_provider_calls_this_run + self._sec_provider_calls_this_run
        total_identity_cache_hits = self._identity_cache_hits_this_run + self._sec_cache_hits_this_run
        total_identity_resolutions = self._identity_resolutions_this_run + self._sec_resolutions_this_run
        identity_source = {
            "contract_version": LIT01_IDENTITY_EVIDENCE_CONTRACT,
            "sec_contract_version": LIT01_SEC_IDENTITY_EVIDENCE_CONTRACT,
            "provider_calls_performed_this_run": total_identity_calls,
            "cache_hits_this_run": total_identity_cache_hits,
            "authoritative_endpoint_resolutions_this_run": total_identity_resolutions,
            "massive_provider_calls_performed_this_run": self._identity_provider_calls_this_run,
            "massive_cache_hits_this_run": self._identity_cache_hits_this_run,
            "massive_authoritative_endpoint_resolutions_this_run": self._identity_resolutions_this_run,
            "sec_provider_calls_performed_this_run": self._sec_provider_calls_this_run,
            "sec_cache_hits_this_run": self._sec_cache_hits_this_run,
            "sec_authoritative_endpoint_resolutions_this_run": self._sec_resolutions_this_run,
            "canonical_ticker_event_store_mutated": False,
            "canonical_sec_store_mutated": False,
            "development_outcome_rows_used_for_identity": 0,
            "protected_return_rows_read": 0,
        }
        result["identity_continuity_source"] = identity_source
        result["provider_reads_performed_this_run"] = int(
            result.get("provider_reads_performed_this_run") or 0
        ) + total_identity_calls
        atomic_write_text(self.report_path(), canonical_json(result) + "\n")
        return result
