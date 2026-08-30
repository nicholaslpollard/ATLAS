from __future__ import annotations

import gzip
import hashlib
import time
import zlib
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar import (
    SEC_EDGAR_MAX_ATTEMPTS,
    SEC_EDGAR_REQUEST_TIMEOUT_SECONDS,
    sec_declared_user_agent,
)


SEC_ARCHIVE_ALLOWED_HOST = "www.sec.gov"
SEC_ARCHIVE_PREFIX = "/Archives/edgar/"
SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES = 64_000_000
SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES = 20_000_000
SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES = 256_000_000
SEC_ARCHIVE_RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}
# SEC's published fair-access ceiling is 10 calls/second. ATLAS deliberately
# uses half that rate on the archive path to retain headroom while avoiding the
# prior 1 call/second artificial bottleneck. This changes transport cadence
# only; source selection, content, chronology, identity, and scientific policy
# are unchanged.
SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND = 5
SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS = 1.0 / SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND


@dataclass(frozen=True, slots=True)
class SECArchiveTextDocument:
    source_url: str
    text: str
    source_sha256: str


def sec_quarter_master_index_url(*, year: int, quarter: int) -> str:
    if year < 1994 or year > 2100:
        raise ProviderError(f"SEC EDGAR full-index year is outside bounded range: {year}")
    if quarter not in {1, 2, 3, 4}:
        raise ProviderError(f"SEC EDGAR quarter is invalid: {quarter}")
    return f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"


def _validate_archive_submission_filename(filename: object) -> str:
    text = str(filename or "").strip().lstrip("/")
    parts = text.split("/")
    if len(parts) != 4 or parts[0:2] != ["edgar", "data"]:
        raise ProviderError(f"SEC EDGAR archive filename is outside edgar/data: {filename!r}")
    cik, basename = parts[2], parts[3]
    if not cik.isdigit():
        raise ProviderError(f"SEC EDGAR archive filename CIK directory is invalid: {filename!r}")
    import re

    if not re.fullmatch(r"\d{10}-\d{2}-\d{6}\.txt", basename):
        raise ProviderError(f"SEC EDGAR archive submission filename is invalid: {filename!r}")
    return text


def sec_archive_submission_url(filename: object) -> str:
    safe = _validate_archive_submission_filename(filename)
    return f"https://www.sec.gov/Archives/{safe}"


def _decode_archive_content(raw: bytes, content_encoding: str | None) -> bytes:
    encoding = (content_encoding or "").strip().lower()
    if not encoding or encoding == "identity":
        return raw
    if encoding == "gzip":
        try:
            return gzip.decompress(raw)
        except OSError as exc:
            raise ProviderError("SEC EDGAR archive gzip response could not be decoded") from exc
    if encoding == "deflate":
        try:
            return zlib.decompress(raw)
        except zlib.error:
            try:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
            except zlib.error as exc:
                raise ProviderError("SEC EDGAR archive deflate response could not be decoded") from exc
    raise ProviderError(f"SEC EDGAR archive returned unsupported Content-Encoding {content_encoding!r}")


class SECEDGARArchiveClient:
    """Narrow read-only client for SEC quarterly indexes and complete submissions."""

    def __init__(
        self,
        *,
        contact_email: str | None = None,
        submission_max_response_bytes: int = SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        bounded_submission_limit = int(submission_max_response_bytes)
        if (
            bounded_submission_limit <= 0
            or bounded_submission_limit > SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES
        ):
            raise ProviderError(
                "SEC EDGAR archive submission response bound is outside allowed range "
                f"(1..{SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES}): "
                f"{submission_max_response_bytes!r}"
            )
        self._user_agent = sec_declared_user_agent(contact_email)
        self._submission_max_response_bytes = bounded_submission_limit
        self._opener = opener or urlopen
        self._sleep = sleeper
        self._cache: dict[str, SECArchiveTextDocument] = {}

    @staticmethod
    def _validate_url(url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme.lower() != "https":
            raise ProviderError("SEC EDGAR archive request must use https")
        if parts.netloc.lower() != SEC_ARCHIVE_ALLOWED_HOST:
            raise ProviderError("SEC EDGAR archive request changed host")
        if not parts.path.startswith(SEC_ARCHIVE_PREFIX):
            raise ProviderError("SEC EDGAR archive request left /Archives/edgar/")
        if parts.query or parts.fragment:
            raise ProviderError("SEC EDGAR archive request must not contain query/fragment")

        index_ok = parts.path.endswith("/master.idx") and "/full-index/" in parts.path
        submission_ok = parts.path.endswith(".txt") and "/data/" in parts.path
        if not (index_ok or submission_ok):
            raise ProviderError("SEC EDGAR archive request is outside approved index/submission paths")

    @staticmethod
    def _response_limit(url: str) -> int:
        """Return the historical/default archive response limit for a URL."""
        path = urlsplit(url).path
        if path.endswith("/master.idx") and "/full-index/" in path:
            return SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES
        return SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES

    def _configured_response_limit(self, url: str) -> int:
        """Apply an explicit per-client submission override without changing index policy."""
        path = urlsplit(url).path
        if path.endswith("/master.idx") and "/full-index/" in path:
            return self._response_limit(url)
        return self._submission_max_response_bytes

    @property
    def declared_user_agent(self) -> str:
        return self._user_agent

    @property
    def submission_max_response_bytes(self) -> int:
        return self._submission_max_response_bytes

    def get_text(self, url: str) -> SECArchiveTextDocument:
        self._validate_url(url)
        cached = self._cache.get(url)
        if cached is not None:
            return cached

        response_limit = self._configured_response_limit(url)
        delay = SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS
        last_error: Exception | None = None
        for attempt in range(1, SEC_EDGAR_MAX_ATTEMPTS + 1):
            self._sleep(SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS)
            request = Request(
                url,
                method="GET",
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "text/plain,*/*;q=0.1",
                    "Accept-Encoding": "gzip, deflate",
                    "Host": SEC_ARCHIVE_ALLOWED_HOST,
                },
            )
            try:
                with self._opener(request, timeout=SEC_EDGAR_REQUEST_TIMEOUT_SECONDS) as response:
                    raw = response.read(response_limit + 1)
                    content_encoding = response.headers.get("Content-Encoding")
                if len(raw) > response_limit:
                    raise ProviderError(
                        "SEC EDGAR archive response exceeded bounded size: "
                        f"url={url} limit_bytes={response_limit}"
                    )
                decoded = _decode_archive_content(raw, content_encoding)
                if len(decoded) > response_limit:
                    raise ProviderError(
                        "SEC EDGAR decoded archive response exceeded bounded size: "
                        f"url={url} limit_bytes={response_limit}"
                    )
                text = decoded.decode("utf-8", errors="replace")
                document = SECArchiveTextDocument(
                    source_url=url,
                    text=text,
                    source_sha256=hashlib.sha256(decoded).hexdigest(),
                )
                self._cache[url] = document
                return document
            except HTTPError as exc:
                last_error = exc
                if exc.code == 403:
                    raise ProviderError(
                        "SEC EDGAR archive request denied with HTTP 403 under fair-access controls; "
                        "ATLAS did not retry the denial."
                    ) from exc
                if exc.code not in SEC_ARCHIVE_RETRYABLE_HTTP or attempt >= SEC_EDGAR_MAX_ATTEMPTS:
                    raise ProviderError(f"SEC EDGAR archive request failed with HTTP {exc.code}") from exc
            except (URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
                last_error = exc
                if attempt >= SEC_EDGAR_MAX_ATTEMPTS:
                    raise ProviderError(
                        f"SEC EDGAR archive request failed: {type(exc).__name__}"
                    ) from exc
            self._sleep(delay)
            delay = min(4.0, delay * 2.0)
        raise ProviderError(
            f"SEC EDGAR archive request failed after retries: {type(last_error).__name__}"
        )

    def quarter_master_index(self, *, year: int, quarter: int) -> SECArchiveTextDocument:
        return self.get_text(sec_quarter_master_index_url(year=year, quarter=quarter))

    def complete_submission(self, *, filename: object) -> SECArchiveTextDocument:
        return self.get_text(sec_archive_submission_url(filename))
