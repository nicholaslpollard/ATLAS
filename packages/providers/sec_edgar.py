from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from packages.core.exceptions import ProviderError


SEC_EDGAR_ALLOWED_HOSTS = {"www.sec.gov"}
SEC_EDGAR_ARCHIVES_PREFIX = "/Archives/edgar/"
SEC_EDGAR_USER_AGENT_PREFIX = "ATLAS Research"
SEC_EDGAR_CONTACT_EMAIL_ENV = "SEC_EDGAR_CONTACT_EMAIL"
SEC_EDGAR_MAX_REQUESTS_PER_SECOND = 5
SEC_EDGAR_MIN_REQUEST_INTERVAL_SECONDS = 1.0 / SEC_EDGAR_MAX_REQUESTS_PER_SECOND
SEC_EDGAR_REQUEST_TIMEOUT_SECONDS = 30.0
SEC_EDGAR_MAX_ATTEMPTS = 4
SEC_EDGAR_HEADER_MAX_BYTES = 512_000

_ACCEPTANCE_RE = re.compile(r"(?im)^\s*<ACCEPTANCE-DATETIME>\s*(\d{14})\s*$")
_ITEM_RE = re.compile(r"(?im)^\s*ITEM INFORMATION:\s*(.+?)\s*$")
_ACCESSION_RE = re.compile(r"(?im)^\s*ACCESSION NUMBER:\s*([^\s]+)\s*$")
_CIK_RE = re.compile(r"(?im)^\s*CENTRAL INDEX KEY:\s*([^\s]+)\s*$")
_HEADER_RE = re.compile(r"(?is)<SEC-HEADER>(.*?)</SEC-HEADER>")
_ACCESSION_FORMAT_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_CONTACT_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True, slots=True)
class SECFilingHeader:
    accession_number: str
    first_cik: str | None
    acceptance_datetime: str
    item_information: tuple[str, ...]
    raw_header: str
    raw_header_sha256: str
    source_url: str


def _normalize_cik(value: object) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise ProviderError(f"SEC CIK is not numeric: {value!r}")
    return str(int(text))


def _validate_accession(accession_number: str) -> str:
    text = accession_number.strip()
    if not _ACCESSION_FORMAT_RE.fullmatch(text):
        raise ProviderError(f"SEC accession_number has unexpected format: {accession_number!r}")
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
    return f"{SEC_EDGAR_USER_AGENT_PREFIX} {contact} github.com/nicholaslpollard/ATLAS"


def sec_submission_url(*, cik: object, accession_number: str) -> str:
    accession = _validate_accession(accession_number)
    cik_path = _normalize_cik(cik)
    accession_path = accession.replace("-", "")
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik_path}/{accession_path}/{accession}.txt"
    )


def _extract_header(raw: str) -> str:
    match = _HEADER_RE.search(raw)
    if match is None:
        raise ProviderError("SEC submission is missing <SEC-HEADER> block")
    return match.group(1).strip() + "\n"


def parse_sec_filing_header(raw_submission: str, *, source_url: str) -> SECFilingHeader:
    header = _extract_header(raw_submission)
    acceptance_match = _ACCEPTANCE_RE.search(header)
    if acceptance_match is None:
        raise ProviderError("SEC submission header is missing ACCEPTANCE-DATETIME")
    raw_acceptance = acceptance_match.group(1)
    try:
        local_dt = datetime.strptime(raw_acceptance, "%Y%m%d%H%M%S").replace(
            tzinfo=ZoneInfo("America/New_York")
        )
    except ValueError as exc:
        raise ProviderError("SEC ACCEPTANCE-DATETIME is invalid") from exc

    accession_match = _ACCESSION_RE.search(header)
    if accession_match is None:
        raise ProviderError("SEC submission header is missing ACCESSION NUMBER")
    accession = _validate_accession(accession_match.group(1))
    cik_match = _CIK_RE.search(header)
    first_cik = None if cik_match is None else cik_match.group(1).strip()
    items = tuple(dict.fromkeys(item.strip() for item in _ITEM_RE.findall(header) if item.strip()))
    return SECFilingHeader(
        accession_number=accession,
        first_cik=first_cik,
        acceptance_datetime=local_dt.isoformat(),
        item_information=items,
        raw_header=header,
        raw_header_sha256=hashlib.sha256(header.encode("utf-8")).hexdigest(),
        source_url=source_url,
    )


class SECEDGARClient:
    """Bounded read-only SEC EDGAR submission-header client.

    The client is intentionally limited to official SEC Archives submission text,
    declares an ATLAS fair-access identity with a locally supplied contact email,
    and throttles below the SEC's public maximum. It exposes no market outcomes
    or mutation authority.
    """

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

    @staticmethod
    def _validate_url(url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme.lower() != "https":
            raise ProviderError("SEC EDGAR request must use https")
        if parts.netloc.lower() not in SEC_EDGAR_ALLOWED_HOSTS:
            raise ProviderError("SEC EDGAR request changed host")
        if not parts.path.startswith(SEC_EDGAR_ARCHIVES_PREFIX):
            raise ProviderError("SEC EDGAR request must stay under /Archives/edgar/")
        if parts.query or parts.fragment:
            raise ProviderError("SEC EDGAR archive request must not contain query/fragment")

    @property
    def declared_user_agent(self) -> str:
        return self._user_agent

    def get_text(self, url: str) -> str:
        self._validate_url(url)
        delay = SEC_EDGAR_MIN_REQUEST_INTERVAL_SECONDS
        last_error: Exception | None = None
        for attempt in range(1, SEC_EDGAR_MAX_ATTEMPTS + 1):
            self._sleep(SEC_EDGAR_MIN_REQUEST_INTERVAL_SECONDS)
            request = Request(
                url,
                method="GET",
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "text/plain,text/html;q=0.9,*/*;q=0.1",
                    "Host": "www.sec.gov",
                },
            )
            try:
                with self._opener(request, timeout=SEC_EDGAR_REQUEST_TIMEOUT_SECONDS) as response:
                    raw = response.read(SEC_EDGAR_HEADER_MAX_BYTES + 1)
                if len(raw) > SEC_EDGAR_HEADER_MAX_BYTES:
                    raw = raw[:SEC_EDGAR_HEADER_MAX_BYTES]
                return raw.decode("utf-8", errors="replace")
            except HTTPError as exc:
                last_error = exc
                if exc.code == 403:
                    raise ProviderError(
                        "SEC EDGAR request denied with HTTP 403 under fair-access controls; "
                        "ATLAS did not retry the denial. Verify SEC_EDGAR_CONTACT_EMAIL and "
                        "the current public-IP access state before rerunning."
                    ) from exc
                if exc.code not in self.RETRYABLE_HTTP or attempt >= SEC_EDGAR_MAX_ATTEMPTS:
                    raise ProviderError(f"SEC EDGAR request failed with HTTP {exc.code}") from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt >= SEC_EDGAR_MAX_ATTEMPTS:
                    raise ProviderError(
                        f"SEC EDGAR request failed: {type(exc).__name__}"
                    ) from exc
            self._sleep(delay)
            delay = min(2.0, delay * 2.0)
        raise ProviderError(
            f"SEC EDGAR request failed after retries: {type(last_error).__name__}"
        )

    def filing_header(self, *, cik: object, accession_number: str) -> SECFilingHeader:
        url = sec_submission_url(cik=cik, accession_number=accession_number)
        return parse_sec_filing_header(self.get_text(url), source_url=url)
