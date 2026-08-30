from __future__ import annotations

import csv
import hashlib
import io
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from packages.core.exceptions import ProviderError


FINRA_SHORT_INTEREST_HOST = "cdn.finra.org"
FINRA_SHORT_INTEREST_PATH_PREFIX = "/equity/otcmarket/biweekly/"
FINRA_SHORT_INTEREST_MAX_RESPONSE_BYTES = 16_000_000
FINRA_SHORT_INTEREST_REQUEST_TIMEOUT_SECONDS = 30.0
FINRA_SHORT_INTEREST_MAX_ATTEMPTS = 3
FINRA_SHORT_INTEREST_MIN_REQUEST_INTERVAL_SECONDS = 0.25
FINRA_SHORT_INTEREST_USER_AGENT = "ATLAS Research/1.0"
FINRA_EXCHANGE_LISTED_CODES = frozenset({"A", "B", "E", "H", "R"})

_PATH_RE = re.compile(r"^/equity/otcmarket/biweekly/shrt(\d{8})\.csv$")

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "settlement_date": ("settlementDate", "settlement_date", "settlement"),
    "symbol": ("symbolCode", "issueSymbolIdentifier", "symbol", "issueSymbol"),
    "issue_name": ("issueName", "issue_name"),
    "current_short_position": (
        "currentShortPositionQuantity",
        "currentShortShareNumber",
        "currentShort",
    ),
    "previous_short_position": (
        "previousShortPositionQuantity",
        "previousShortShareNumber",
        "previousShort",
    ),
    "average_daily_volume": (
        "averageDailyVolumeQuantity",
        "averageShortShareNumber",
        "averageDailyVolume",
    ),
    "days_to_cover": ("daysToCoverQuantity", "daysToCoverNumber", "daysToCover"),
    "exchange_code": (
        "issuerServicesGroupExchangeCode",
        "exchangeCode",
        "primaryExchangeCode",
    ),
    "market_code": (
        "marketClassCode",
        "marketCategoryCode",
        "market",
        "marketCode",
    ),
    "revision_flag": ("revisionFlag", "revision"),
    "stock_split_flag": ("stockSplitFlag", "stockSplit"),
    "change_previous_number": (
        "changePreviousNumber",
        "changePreviousShort",
    ),
    "change_percent": (
        "changePercent",
        "percentageChangefromPreviousShort",
        "percentageChangeFromPreviousShort",
    ),
}

_REQUIRED_SEMANTICS = (
    "settlement_date",
    "symbol",
    "current_short_position",
)


@dataclass(frozen=True, slots=True)
class FINRAShortInterestFile:
    settlement_date: str
    source_url: str
    source_sha256: str
    delimiter: str
    resolved_columns: dict[str, str | None]
    rows: tuple[dict[str, Any], ...]


def _normalize_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def _parse_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ProviderError("FINRA short-interest row is missing settlement date")
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    raise ProviderError(f"FINRA short-interest settlement date is invalid: {text!r}")


def _parse_nonnegative_integer(value: object, *, field: str) -> int:
    text = str(value or "").strip().replace(",", "")
    if not text:
        raise ProviderError(f"FINRA short-interest row is missing {field}")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ProviderError(f"FINRA short-interest {field} is not numeric: {text!r}") from exc
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise ProviderError(
            f"FINRA short-interest {field} must be a finite nonnegative integer: {text!r}"
        )
    return int(number)


def _parse_optional_number(value: object, *, field: str) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ProviderError(f"FINRA short-interest {field} is not numeric: {text!r}") from exc
    if not number.is_finite():
        raise ProviderError(f"FINRA short-interest {field} is not finite: {text!r}")
    return float(number)


def _validate_settlement_date(value: object) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ProviderError(f"FINRA settlement date must be YYYY-MM-DD: {text!r}") from exc
    if parsed.isoformat() != text:
        raise ProviderError(f"FINRA settlement date must be canonical YYYY-MM-DD: {text!r}")
    return text


def finra_short_interest_url(*, settlement_date: object) -> str:
    settlement = _validate_settlement_date(settlement_date)
    compact = settlement.replace("-", "")
    return (
        f"https://{FINRA_SHORT_INTEREST_HOST}"
        f"{FINRA_SHORT_INTEREST_PATH_PREFIX}shrt{compact}.csv"
    )


def _validate_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise ProviderError("FINRA short-interest request must use https")
    if parts.netloc.lower() != FINRA_SHORT_INTEREST_HOST:
        raise ProviderError("FINRA short-interest request changed host")
    match = _PATH_RE.fullmatch(parts.path)
    if match is None:
        raise ProviderError("FINRA short-interest request changed historical-file path")
    if parts.query or parts.fragment:
        raise ProviderError("FINRA short-interest request must not contain query/fragment")
    compact = match.group(1)
    try:
        return datetime.strptime(compact, "%Y%m%d").date().isoformat()
    except ValueError as exc:
        raise ProviderError("FINRA short-interest path contains invalid settlement date") from exc


def _resolve_columns(fieldnames: list[str] | None) -> dict[str, str | None]:
    if not fieldnames:
        raise ProviderError("FINRA short-interest file is missing a CSV header")
    normalized: dict[str, list[str]] = {}
    for name in fieldnames:
        normalized.setdefault(_normalize_header(name), []).append(name)

    out: dict[str, str | None] = {}
    for semantic, aliases in _FIELD_ALIASES.items():
        matches: list[str] = []
        for alias in aliases:
            matches.extend(normalized.get(_normalize_header(alias), []))
        unique = list(dict.fromkeys(matches))
        if len(unique) > 1:
            raise ProviderError(
                f"FINRA short-interest schema is ambiguous for {semantic}: {unique}"
            )
        out[semantic] = unique[0] if unique else None

    missing = [semantic for semantic in _REQUIRED_SEMANTICS if out[semantic] is None]
    if missing:
        raise ProviderError(
            "FINRA short-interest schema is missing required semantics: "
            + ", ".join(missing)
        )
    if out["exchange_code"] is None and out["market_code"] is None:
        raise ProviderError(
            "FINRA short-interest schema must expose exchange_code or market_code"
        )
    return out


def _sniff_delimiter(text: str) -> str:
    sample = text[:8192]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",|\t").delimiter
    except csv.Error:
        delimiter = ","
    if delimiter not in {",", "|", "\t"}:
        raise ProviderError(f"FINRA short-interest delimiter is unsupported: {delimiter!r}")
    return delimiter


def _optional_text(row: dict[str, str], column: str | None) -> str | None:
    if column is None:
        return None
    text = str(row.get(column) or "").strip()
    return text or None


def parse_finra_short_interest_csv(
    text: str, *, expected_settlement_date: str, source_url: str
) -> FINRAShortInterestFile:
    settlement = _validate_settlement_date(expected_settlement_date)
    if not text.strip():
        raise ProviderError("FINRA short-interest response is empty")
    delimiter = _sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    resolved = _resolve_columns(reader.fieldnames)

    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(reader, start=2):
        if raw is None:
            continue
        if not any(str(value or "").strip() for value in raw.values()):
            continue
        row_date = _parse_date(raw.get(resolved["settlement_date"] or ""))
        if row_date != settlement:
            raise ProviderError(
                f"FINRA short-interest row settlement mismatch at line {line_number}: "
                f"{row_date} != {settlement}"
            )
        symbol = str(raw.get(resolved["symbol"] or "") or "").strip()
        if not symbol:
            raise ProviderError(
                f"FINRA short-interest row is missing symbol at line {line_number}"
            )
        current = _parse_nonnegative_integer(
            raw.get(resolved["current_short_position"] or ""),
            field="current_short_position",
        )
        exchange_code = _optional_text(raw, resolved["exchange_code"])
        market_code = _optional_text(raw, resolved["market_code"])
        if not exchange_code and not market_code:
            raise ProviderError(
                f"FINRA short-interest row lacks exchange/market identity at line {line_number}"
            )

        previous = (
            _parse_nonnegative_integer(
                raw.get(resolved["previous_short_position"] or ""),
                field="previous_short_position",
            )
            if resolved["previous_short_position"]
            and str(raw.get(resolved["previous_short_position"] or "") or "").strip()
            else None
        )
        rows.append(
            {
                "settlement_date": row_date,
                "symbol": symbol,
                "issue_name": _optional_text(raw, resolved["issue_name"]),
                "current_short_position": current,
                "previous_short_position": previous,
                "average_daily_volume": _parse_optional_number(
                    raw.get(resolved["average_daily_volume"] or ""),
                    field="average_daily_volume",
                )
                if resolved["average_daily_volume"]
                else None,
                "days_to_cover": _parse_optional_number(
                    raw.get(resolved["days_to_cover"] or ""),
                    field="days_to_cover",
                )
                if resolved["days_to_cover"]
                else None,
                "exchange_code": exchange_code,
                "market_code": market_code,
                "revision_flag": _optional_text(raw, resolved["revision_flag"]),
                "stock_split_flag": _optional_text(raw, resolved["stock_split_flag"]),
                "change_previous_number": _parse_optional_number(
                    raw.get(resolved["change_previous_number"] or ""),
                    field="change_previous_number",
                )
                if resolved["change_previous_number"]
                else None,
                "change_percent": _parse_optional_number(
                    raw.get(resolved["change_percent"] or ""),
                    field="change_percent",
                )
                if resolved["change_percent"]
                else None,
            }
        )

    if not rows:
        raise ProviderError("FINRA short-interest file contains no data rows")
    return FINRAShortInterestFile(
        settlement_date=settlement,
        source_url=source_url,
        source_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        delimiter=delimiter,
        resolved_columns=resolved,
        rows=tuple(rows),
    )


def is_exchange_listed_short_interest_row(row: dict[str, Any]) -> bool:
    exchange = str(row.get("exchange_code") or "").strip().upper()
    market = str(row.get("market_code") or "").strip().upper()
    return exchange in FINRA_EXCHANGE_LISTED_CODES or market in FINRA_EXCHANGE_LISTED_CODES


class FINRAShortInterestClient:
    """Bounded read-only client for FINRA historical consolidated short-interest files."""

    RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._opener = opener or urlopen
        self._sleep = sleeper
        self._cache: dict[str, FINRAShortInterestFile] = {}

    def historical_file(self, *, settlement_date: object) -> FINRAShortInterestFile:
        settlement = _validate_settlement_date(settlement_date)
        url = finra_short_interest_url(settlement_date=settlement)
        path_date = _validate_url(url)
        if path_date != settlement:
            raise ProviderError("FINRA short-interest URL settlement date drifted")
        cached = self._cache.get(url)
        if cached is not None:
            return cached

        last_error: Exception | None = None
        for attempt in range(1, FINRA_SHORT_INTEREST_MAX_ATTEMPTS + 1):
            self._sleep(FINRA_SHORT_INTEREST_MIN_REQUEST_INTERVAL_SECONDS)
            request = Request(
                url,
                method="GET",
                headers={
                    "User-Agent": FINRA_SHORT_INTEREST_USER_AGENT,
                    "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.1",
                    "Host": FINRA_SHORT_INTEREST_HOST,
                },
            )
            try:
                with self._opener(
                    request, timeout=FINRA_SHORT_INTEREST_REQUEST_TIMEOUT_SECONDS
                ) as response:
                    raw = response.read(FINRA_SHORT_INTEREST_MAX_RESPONSE_BYTES + 1)
                if len(raw) > FINRA_SHORT_INTEREST_MAX_RESPONSE_BYTES:
                    raise ProviderError(
                        "FINRA short-interest response exceeded bounded size"
                    )
                try:
                    text = raw.decode("utf-8-sig", errors="strict")
                except UnicodeDecodeError as exc:
                    raise ProviderError(
                        "FINRA short-interest response is not valid UTF-8"
                    ) from exc
                parsed = parse_finra_short_interest_csv(
                    text,
                    expected_settlement_date=settlement,
                    source_url=url,
                )
                self._cache[url] = parsed
                return parsed
            except HTTPError as exc:
                last_error = exc
                if exc.code not in self.RETRYABLE_HTTP or attempt >= FINRA_SHORT_INTEREST_MAX_ATTEMPTS:
                    raise ProviderError(
                        f"FINRA short-interest request failed with HTTP {exc.code}"
                    ) from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt >= FINRA_SHORT_INTEREST_MAX_ATTEMPTS:
                    raise ProviderError(
                        f"FINRA short-interest request failed: {type(exc).__name__}"
                    ) from exc
            self._sleep(min(2.0, 0.5 * (2 ** (attempt - 1))))
        raise ProviderError(
            "FINRA short-interest request failed after retries: "
            f"{type(last_error).__name__}"
        )
