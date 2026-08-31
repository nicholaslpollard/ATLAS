from __future__ import annotations

import hashlib
import io
import os
import re
import time
import zipfile
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar import SEC_EDGAR_CONTACT_EMAIL_ENV, sec_declared_user_agent


SEC_13F_DATASET_HOST = "www.sec.gov"
SEC_13F_DATASET_PREFIX = "/files/structureddata/data/form-13f-data-sets/"
SEC_13F_DATASET_MAX_REQUESTS_PER_SECOND = 1
SEC_13F_DATASET_MIN_REQUEST_INTERVAL_SECONDS = 1.0
SEC_13F_DATASET_REQUEST_TIMEOUT_SECONDS = 60.0
SEC_13F_DATASET_MAX_ATTEMPTS = 4
SEC_13F_DATASET_MAX_RESPONSE_BYTES = 128_000_000
SEC_13F_DATASET_MAX_UNCOMPRESSED_BYTES = 1_500_000_000
SEC_13F_REQUIRED_TABLES = ("SUBMISSION.tsv", "COVERPAGE.tsv", "INFOTABLE.tsv")

_DATASET_FILENAME_RE = re.compile(
    r"^(?:\d{4}q[1-4]|"
    r"\d{2}[a-z]{3}\d{4}-\d{2}[a-z]{3}\d{4})_form13f\.zip$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SEC13FDatasetArchive:
    source_url: str
    source_sha256: str
    raw_bytes: bytes

    @property
    def compressed_bytes(self) -> int:
        return len(self.raw_bytes)


class SEC13FDatasetClient:
    """Read-only client for official SEC quarterly Form 13F flattened data sets."""

    RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        contact_email: str | None = None,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        contact = (contact_email or os.getenv(SEC_EDGAR_CONTACT_EMAIL_ENV) or "").strip()
        self._user_agent = sec_declared_user_agent(contact)
        self._opener = opener or urlopen
        self._sleep = sleeper
        self._cache: dict[str, SEC13FDatasetArchive] = {}

    @staticmethod
    def validate_url(url: str) -> str:
        parts = urlsplit(url)
        if parts.scheme.lower() != "https":
            raise ProviderError("SEC 13F data-set request must use https")
        if parts.netloc.lower() != SEC_13F_DATASET_HOST:
            raise ProviderError("SEC 13F data-set request changed host")
        if not parts.path.startswith(SEC_13F_DATASET_PREFIX):
            raise ProviderError("SEC 13F data-set request changed path")
        filename = parts.path.removeprefix(SEC_13F_DATASET_PREFIX)
        if "/" in filename or not _DATASET_FILENAME_RE.fullmatch(filename):
            raise ProviderError("SEC 13F data-set request must target one official Form 13F ZIP")
        if parts.query or parts.fragment:
            raise ProviderError("SEC 13F data-set request must not contain query/fragment")
        return filename

    @property
    def declared_user_agent(self) -> str:
        return self._user_agent

    def fetch(self, url: str) -> SEC13FDatasetArchive:
        self.validate_url(url)
        cached = self._cache.get(url)
        if cached is not None:
            return cached

        delay = SEC_13F_DATASET_MIN_REQUEST_INTERVAL_SECONDS
        last_error: Exception | None = None
        for attempt in range(1, SEC_13F_DATASET_MAX_ATTEMPTS + 1):
            self._sleep(SEC_13F_DATASET_MIN_REQUEST_INTERVAL_SECONDS)
            request = Request(
                url,
                method="GET",
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "application/zip, application/octet-stream",
                    "Accept-Encoding": "identity",
                    "Host": SEC_13F_DATASET_HOST,
                },
            )
            try:
                with self._opener(request, timeout=SEC_13F_DATASET_REQUEST_TIMEOUT_SECONDS) as response:
                    content_length = str(response.headers.get("Content-Length") or "").strip()
                    if content_length:
                        try:
                            announced = int(content_length)
                        except ValueError as exc:
                            raise ProviderError("SEC 13F data set returned invalid Content-Length") from exc
                        if announced > SEC_13F_DATASET_MAX_RESPONSE_BYTES:
                            raise ProviderError(
                                "SEC 13F data-set response exceeds frozen compressed-byte cap"
                            )

                    raw = response.read(SEC_13F_DATASET_MAX_RESPONSE_BYTES + 1)
                    if len(raw) > SEC_13F_DATASET_MAX_RESPONSE_BYTES:
                        raise ProviderError(
                            "SEC 13F data-set response exceeds frozen compressed-byte cap"
                        )
                    if not raw.startswith(b"PK"):
                        raise ProviderError("SEC 13F data-set response is not a ZIP archive")
                    archive = SEC13FDatasetArchive(
                        source_url=url,
                        source_sha256=hashlib.sha256(raw).hexdigest(),
                        raw_bytes=raw,
                    )
                    validate_13f_zip_structure(archive)
                    self._cache[url] = archive
                    return archive
            except HTTPError as exc:
                last_error = exc
                if exc.code not in self.RETRYABLE_HTTP or attempt >= SEC_13F_DATASET_MAX_ATTEMPTS:
                    break
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt >= SEC_13F_DATASET_MAX_ATTEMPTS:
                    break
            self._sleep(delay)
            delay = min(delay * 2.0, 8.0)

        raise ProviderError(f"SEC 13F data-set request failed for {url}: {last_error}") from last_error


def _safe_member_name(name: str) -> None:
    normalized = name.replace("\\", "/")
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or any(part == ".." for part in normalized.split("/"))
    ):
        raise ProviderError(f"SEC 13F ZIP contains unsafe member path: {name!r}")


def validate_13f_zip_structure(
    archive: SEC13FDatasetArchive,
) -> dict[str, object]:
    try:
        with zipfile.ZipFile(io.BytesIO(archive.raw_bytes)) as handle:
            infos = handle.infolist()
            if not infos:
                raise ProviderError("SEC 13F ZIP archive is empty")

            total_uncompressed = 0
            basenames: dict[str, str] = {}
            duplicate_members: set[str] = set()
            for info in infos:
                _safe_member_name(info.filename)
                if info.flag_bits & 0x1:
                    raise ProviderError("SEC 13F ZIP archive contains encrypted member")
                total_uncompressed += int(info.file_size)
                if total_uncompressed > SEC_13F_DATASET_MAX_UNCOMPRESSED_BYTES:
                    raise ProviderError(
                        "SEC 13F ZIP exceeds frozen uncompressed-byte cap"
                    )
                if info.is_dir():
                    continue
                basename = info.filename.replace("\\", "/").rsplit("/", 1)[-1]
                key = basename.upper()
                if key in basenames:
                    duplicate_members.add(key)
                basenames[key] = info.filename

            if duplicate_members:
                raise ProviderError(
                    "SEC 13F ZIP contains duplicate table basenames: "
                    + ",".join(sorted(duplicate_members))
                )
            missing = [
                table
                for table in SEC_13F_REQUIRED_TABLES
                if table.upper() not in basenames
            ]
            if missing:
                raise ProviderError(
                    "SEC 13F ZIP is missing required table(s): " + ",".join(missing)
                )
            return {
                "member_count": len(infos),
                "total_uncompressed_bytes": total_uncompressed,
                "table_members": {
                    table: basenames[table.upper()] for table in SEC_13F_REQUIRED_TABLES
                },
            }
    except zipfile.BadZipFile as exc:
        raise ProviderError("SEC 13F response could not be opened as ZIP") from exc
