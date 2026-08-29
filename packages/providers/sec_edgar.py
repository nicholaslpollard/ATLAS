from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import time
import zlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from packages.core.exceptions import ProviderError


SEC_EDGAR_ALLOWED_HOSTS = {"data.sec.gov"}
SEC_EDGAR_SUBMISSIONS_PREFIX = "/submissions/"
SEC_EDGAR_USER_AGENT_PREFIX = "ATLAS Research"
SEC_EDGAR_CONTACT_EMAIL_ENV = "SEC_EDGAR_CONTACT_EMAIL"
SEC_EDGAR_MAX_REQUESTS_PER_SECOND = 1
SEC_EDGAR_MIN_REQUEST_INTERVAL_SECONDS = 1.0 / SEC_EDGAR_MAX_REQUESTS_PER_SECOND
SEC_EDGAR_REQUEST_TIMEOUT_SECONDS = 30.0
SEC_EDGAR_MAX_ATTEMPTS = 4
SEC_EDGAR_MAX_RESPONSE_BYTES = 8_000_000
SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP = 2
SEC_EDGAR_DECLARED_SHARD_BOUNDARY_TOLERANCE_DAYS = 1

_ACCESSION_FORMAT_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_CONTACT_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True, slots=True)
class SECSubmissionRecord:
    accession_number: str
    issuer_cik: str
    filing_date: str
    acceptance_datetime: str
    form: str
    item_codes: tuple[str, ...]
    primary_document: str | None
    source_url: str
    source_record_json: str
    source_record_sha256: str


def _normalize_cik(value: object) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise ProviderError(f"SEC CIK is not numeric: {value!r}")
    return str(int(text)).zfill(10)


def _validate_accession(accession_number: str) -> str:
    text = accession_number.strip()
    if not _ACCESSION_FORMAT_RE.fullmatch(text):
        raise ProviderError(f"SEC accession_number has unexpected format: {accession_number!r}")
    return text


def _validate_filing_date(value: object, *, field: str = "filingDate") -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ProviderError(f"SEC submissions {field} is invalid: {text!r}")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ProviderError(f"SEC submissions {field} is invalid: {text!r}") from exc
    if parsed.isoformat() != text:
        raise ProviderError(f"SEC submissions {field} is invalid: {text!r}")
    return text


def _resolve_contact_email(contact_email: str | None) -> str:
    value = (contact_email or os.getenv(SEC_EDGAR_CONTACT_EMAIL_ENV) or "").strip()
    if not value:
        raise ProviderError(
            "SEC EDGAR fair-access identity is missing; set SEC_EDGAR_CONTACT_EMAIL "
            "in the local environment or .env before running Phase32 feasibility"
        )
    if not _CONTACT_EMAIL_RE.fullmatch(value):
        raise ProviderError("SEC_EDGAR_CONTACT_EMAIL is not a valid contact email address")
    return value


def sec_declared_user_agent(contact_email: str) -> str:
    contact = _resolve_contact_email(contact_email)
    return f"{SEC_EDGAR_USER_AGENT_PREFIX} {contact}"


def sec_company_submissions_url(*, cik: object) -> str:
    padded = _normalize_cik(cik)
    return f"https://data.sec.gov/submissions/CIK{padded}.json"


def _validate_shard_name(name: object) -> str:
    text = str(name or "").strip()
    expected = re.compile(r"^CIK\d{10}-submissions-\d{3}\.json$")
    if not expected.fullmatch(text):
        raise ProviderError(f"SEC submissions archive shard has unexpected name: {name!r}")
    return text


def sec_submission_shard_url(name: object) -> str:
    shard = _validate_shard_name(name)
    return f"https://data.sec.gov/submissions/{shard}"


def _parse_acceptance(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ProviderError("SEC submissions metadata is missing acceptanceDateTime")
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ProviderError(f"SEC acceptanceDateTime is invalid: {text!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    eastern = dt.astimezone(ZoneInfo("America/New_York"))
    return eastern.isoformat()


def _split_items(value: object) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        return ()
    values = [part.strip() for part in re.split(r"[,;]", text) if part.strip()]
    return tuple(dict.fromkeys(values))


def _columnar_rows(block: object) -> tuple[dict[str, object], ...]:
    if not isinstance(block, dict):
        raise ProviderError("SEC submissions filing block is not an object")
    accessions = block.get("accessionNumber")
    if not isinstance(accessions, list):
        raise ProviderError("SEC submissions filing block is missing accessionNumber array")
    fields = (
        "accessionNumber",
        "filingDate",
        "acceptanceDateTime",
        "form",
        "items",
        "primaryDocument",
    )
    rows: list[dict[str, object]] = []
    for index in range(len(accessions)):
        row: dict[str, object] = {}
        for field in fields:
            values = block.get(field)
            if isinstance(values, list) and index < len(values):
                row[field] = values[index]
            else:
                row[field] = ""
        rows.append(row)
    return tuple(rows)


def _find_accession(block: object, accession_number: str) -> dict[str, object] | None:
    for row in _columnar_rows(block):
        if str(row["accessionNumber"]).strip() == accession_number:
            return row
    return None


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def _record_from_row(
    *,
    row: dict[str, object],
    issuer_cik: str,
    expected_accession: str,
    expected_filing_date: str,
    source_url: str,
) -> SECSubmissionRecord:
    accession = _validate_accession(str(row.get("accessionNumber") or ""))
    if accession != expected_accession:
        raise ProviderError("SEC submissions accession does not match requested accession")
    form = str(row.get("form") or "").strip()
    if form != "8-K":
        raise ProviderError(
            f"SEC submissions accession {accession} is not original 8-K metadata: form={form!r}"
        )
    filing_date = _validate_filing_date(row.get("filingDate"))
    if filing_date != expected_filing_date:
        raise ProviderError(
            f"SEC submissions accession {accession} filingDate does not match requested date: "
            f"{filing_date} != {expected_filing_date}"
        )
    acceptance_datetime = _parse_acceptance(row.get("acceptanceDateTime"))
    item_codes = _split_items(row.get("items"))
    primary_document = str(row.get("primaryDocument") or "").strip() or None
    source_record = {
        "accessionNumber": accession,
        "issuerCIK": issuer_cik,
        "filingDate": filing_date,
        "acceptanceDateTime": str(row.get("acceptanceDateTime") or "").strip(),
        "form": form,
        "items": str(row.get("items") or "").strip(),
        "primaryDocument": primary_document,
        "sourceUrl": source_url,
    }
    source_record_json = _canonical_json(source_record)
    return SECSubmissionRecord(
        accession_number=accession,
        issuer_cik=issuer_cik,
        filing_date=filing_date,
        acceptance_datetime=acceptance_datetime,
        form=form,
        item_codes=item_codes,
        primary_document=primary_document,
        source_url=source_url,
        source_record_json=source_record_json,
        source_record_sha256=hashlib.sha256(source_record_json.encode("utf-8")).hexdigest(),
    )


def _declared_shard_distance_days(item: dict[str, object], requested: date) -> int | None:
    start_text = str(item.get("filingFrom") or "").strip()
    end_text = str(item.get("filingTo") or "").strip()
    if not start_text or not end_text:
        return None
    try:
        start = date.fromisoformat(start_text)
        end = date.fromisoformat(end_text)
    except ValueError:
        return None
    if start > end:
        return None
    if start <= requested <= end:
        return 0
    if requested < start:
        return (start - requested).days
    return (requested - end).days


def _select_declared_shard_candidates(
    files: object, *, filing_date: str
) -> tuple[dict[str, object], ...]:
    """Select only SEC-declared shards under the bounded rollover rule.

    Exact date coverage remains authoritative. A one-calendar-day adjacent shard is
    eligible only when no declared shard covers the requested date. This narrow
    exception is evidence-backed by an observed SEC root/shard rollover mismatch;
    it never guesses a shard URL and exact accession/date/form validation still
    occurs after the shard is read.
    """

    expected_date = _validate_filing_date(filing_date, field="requested filing date")
    requested = date.fromisoformat(expected_date)
    declared = [dict(item) for item in files if isinstance(item, dict)] if isinstance(files, list) else []

    with_distance: list[tuple[int, str, dict[str, object]]] = []
    for item in declared:
        distance = _declared_shard_distance_days(item, requested)
        if distance is None:
            continue
        name = _validate_shard_name(item.get("name"))
        with_distance.append((distance, name, item))

    covering = [entry for entry in with_distance if entry[0] == 0]
    if covering:
        selected = covering
    else:
        selected = [
            entry
            for entry in with_distance
            if entry[0] == SEC_EDGAR_DECLARED_SHARD_BOUNDARY_TOLERANCE_DAYS
        ]

    if len(selected) > SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP:
        raise ProviderError("SEC submissions archive lookup exceeded bounded shard count")

    selected.sort(key=lambda entry: (entry[0], entry[1]))
    return tuple(entry[2] for entry in selected)


def _decode_content(raw: bytes, content_encoding: str | None) -> bytes:
    encoding = (content_encoding or "").strip().lower()
    if not encoding or encoding == "identity":
        return raw
    if encoding == "gzip":
        try:
            return gzip.decompress(raw)
        except OSError as exc:
            raise ProviderError("SEC EDGAR gzip response could not be decoded") from exc
    if encoding == "deflate":
        try:
            return zlib.decompress(raw)
        except zlib.error:
            try:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
            except zlib.error as exc:
                raise ProviderError("SEC EDGAR deflate response could not be decoded") from exc
    raise ProviderError(f"SEC EDGAR returned unsupported Content-Encoding {content_encoding!r}")


class SECEDGARClient:
    """Bounded read-only client for official SEC company submissions metadata."""

    RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        contact_email: str | None = None,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._contact_email = _resolve_contact_email(contact_email)
        self._user_agent = sec_declared_user_agent(self._contact_email)
        self._opener = opener or urlopen
        self._sleep = sleeper
        self._cache: dict[str, tuple[dict[str, Any], str]] = {}

    @staticmethod
    def _validate_url(url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme.lower() != "https":
            raise ProviderError("SEC EDGAR request must use https")
        if parts.netloc.lower() not in SEC_EDGAR_ALLOWED_HOSTS:
            raise ProviderError("SEC EDGAR request changed host")
        if not parts.path.startswith(SEC_EDGAR_SUBMISSIONS_PREFIX):
            raise ProviderError("SEC EDGAR request must stay under /submissions/")
        if not parts.path.endswith(".json"):
            raise ProviderError("SEC EDGAR submissions request must target JSON")
        if parts.query or parts.fragment:
            raise ProviderError("SEC EDGAR submissions request must not contain query/fragment")

    @property
    def declared_user_agent(self) -> str:
        return self._user_agent

    def get_json(self, url: str) -> tuple[dict[str, Any], str]:
        self._validate_url(url)
        cached = self._cache.get(url)
        if cached is not None:
            return cached
        delay = SEC_EDGAR_MIN_REQUEST_INTERVAL_SECONDS
        last_error: Exception | None = None
        for attempt in range(1, SEC_EDGAR_MAX_ATTEMPTS + 1):
            self._sleep(SEC_EDGAR_MIN_REQUEST_INTERVAL_SECONDS)
            request = Request(
                url,
                method="GET",
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                    "Host": "data.sec.gov",
                },
            )
            try:
                with self._opener(request, timeout=SEC_EDGAR_REQUEST_TIMEOUT_SECONDS) as response:
                    raw = response.read(SEC_EDGAR_MAX_RESPONSE_BYTES + 1)
                    content_encoding = response.headers.get("Content-Encoding")
                if len(raw) > SEC_EDGAR_MAX_RESPONSE_BYTES:
                    raise ProviderError("SEC EDGAR submissions response exceeded bounded size")
                decoded = _decode_content(raw, content_encoding)
                if len(decoded) > SEC_EDGAR_MAX_RESPONSE_BYTES:
                    raise ProviderError("SEC EDGAR decoded submissions response exceeded bounded size")
                text = decoded.decode("utf-8", errors="strict")
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ProviderError("SEC EDGAR submissions response is not valid JSON") from exc
                if not isinstance(payload, dict):
                    raise ProviderError("SEC EDGAR submissions response root is not an object")
                result = (payload, text)
                self._cache[url] = result
                return result
            except HTTPError as exc:
                last_error = exc
                if exc.code == 403:
                    raise ProviderError(
                        "SEC EDGAR submissions request denied with HTTP 403 under fair-access "
                        "controls; ATLAS did not retry the denial."
                    ) from exc
                if exc.code not in self.RETRYABLE_HTTP or attempt >= SEC_EDGAR_MAX_ATTEMPTS:
                    raise ProviderError(f"SEC EDGAR submissions request failed with HTTP {exc.code}") from exc
            except (URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
                last_error = exc
                if attempt >= SEC_EDGAR_MAX_ATTEMPTS:
                    raise ProviderError(
                        f"SEC EDGAR submissions request failed: {type(exc).__name__}"
                    ) from exc
            self._sleep(delay)
            delay = min(4.0, delay * 2.0)
        raise ProviderError(
            f"SEC EDGAR submissions request failed after retries: {type(last_error).__name__}"
        )

    def filing_metadata(
        self,
        *,
        cik: object,
        accession_number: str,
        filing_date: str,
    ) -> SECSubmissionRecord:
        issuer_cik = _normalize_cik(cik)
        expected_accession = _validate_accession(accession_number)
        expected_filing_date = _validate_filing_date(filing_date, field="requested filing date")
        root_url = sec_company_submissions_url(cik=issuer_cik)
        root, _ = self.get_json(root_url)
        filings = root.get("filings")
        if not isinstance(filings, dict):
            raise ProviderError("SEC company submissions response is missing filings object")
        recent = filings.get("recent")
        row = _find_accession(recent, expected_accession)
        if row is not None:
            return _record_from_row(
                row=row,
                issuer_cik=issuer_cik,
                expected_accession=expected_accession,
                expected_filing_date=expected_filing_date,
                source_url=root_url,
            )

        candidates = _select_declared_shard_candidates(
            filings.get("files"), filing_date=expected_filing_date
        )
        if not candidates:
            raise ProviderError(
                f"SEC submissions metadata does not cover requested accession/date within the "
                f"bounded declared-shard rollover rule: {expected_accession} / {expected_filing_date}"
            )
        for item in candidates:
            shard_url = sec_submission_shard_url(item.get("name"))
            shard, _ = self.get_json(shard_url)
            row = _find_accession(shard, expected_accession)
            if row is None and isinstance(shard.get("filings"), dict):
                row = _find_accession(shard["filings"].get("recent"), expected_accession)
            if row is not None:
                return _record_from_row(
                    row=row,
                    issuer_cik=issuer_cik,
                    expected_accession=expected_accession,
                    expected_filing_date=expected_filing_date,
                    source_url=shard_url,
                )
        raise ProviderError(
            f"SEC submissions metadata did not contain requested accession {expected_accession}"
        )
