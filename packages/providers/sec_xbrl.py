from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar import SECEDGARClient


SEC_XBRL_COMPANYFACTS_PREFIX = "/api/xbrl/companyfacts/"
_COMPANYFACTS_PATH_RE = re.compile(r"^/api/xbrl/companyfacts/CIK\d{10}\.json$")


@dataclass(frozen=True, slots=True)
class SECCompanyFactsDocument:
    issuer_cik: str
    entity_name: str
    facts: dict[str, Any]
    source_url: str
    source_sha256: str


def _normalize_cik(value: object) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise ProviderError(f"SEC XBRL CIK is not numeric: {value!r}")
    return str(int(text)).zfill(10)


def sec_companyfacts_url(*, cik: object) -> str:
    padded = _normalize_cik(cik)
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json"


class SECXBRLCompanyFactsClient(SECEDGARClient):
    """Read-only SEC XBRL Company Facts client using the accepted EDGAR HTTP seam.

    The retry, fair-access identity, cache, compression decoding, HTTPS-only host
    restriction, and request pacing are inherited from ``SECEDGARClient``.  Only
    the allowed path is changed, so this is not a second SEC network authority.
    """

    @staticmethod
    def _validate_url(url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme.lower() != "https":
            raise ProviderError("SEC XBRL request must use https")
        if parts.netloc.lower() != "data.sec.gov":
            raise ProviderError("SEC XBRL request changed host")
        if not _COMPANYFACTS_PATH_RE.fullmatch(parts.path):
            raise ProviderError("SEC XBRL request must target one companyfacts CIK JSON document")
        if parts.query or parts.fragment:
            raise ProviderError("SEC XBRL companyfacts request must not contain query/fragment")

    def company_facts(self, *, cik: object) -> SECCompanyFactsDocument:
        expected_cik = _normalize_cik(cik)
        source_url = sec_companyfacts_url(cik=expected_cik)
        payload, raw_text = self.get_json(source_url)

        source_cik = _normalize_cik(payload.get("cik"))
        if source_cik != expected_cik:
            raise ProviderError(
                f"SEC XBRL companyfacts CIK mismatch: expected={expected_cik} actual={source_cik}"
            )
        entity_name = str(payload.get("entityName") or "").strip()
        if not entity_name:
            raise ProviderError("SEC XBRL companyfacts response is missing entityName")
        facts = payload.get("facts")
        if not isinstance(facts, dict):
            raise ProviderError("SEC XBRL companyfacts response is missing facts object")

        return SECCompanyFactsDocument(
            issuer_cik=expected_cik,
            entity_name=entity_name,
            facts=facts,
            source_url=source_url,
            source_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        )
