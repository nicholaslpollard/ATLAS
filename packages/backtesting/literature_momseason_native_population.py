from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_storage import AlpacaRawPayloadStore
from packages.data.paths import MarketDataPaths
from packages.providers.alpaca import AlpacaInvalidSymbolError, AlpacaMarketDataClient

from .literature_momseason_adjusted_predictor_source import (
    MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
    MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
    MOMSEASON_ADJUSTED_PREDICTOR_ENDPOINTS,
    MOMSEASON_ADJUSTED_PREDICTOR_FEED,
    MOMSEASON_ADJUSTED_PREDICTOR_ROOT_NAME,
    MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
    _chunks,
    _clean_symbol,
    _rows_fingerprint,
    _write_parquet_rows,
    extract_single_session_adjusted_closes,
)
from .literature_momseason_policy import (
    LITERATURE_MOMSEASON_PROTECTED_START,
    MOMSEASON_HYPOTHESES,
    formation_months,
    month_sessions,
    previous_month,
    required_lag_reference_dates,
    same_month_years_back,
)
from .literature_momseason_source import (
    MOMSEASON_SOURCE_ROOT_RELATIVE,
    MomSeasonSourceAcquirer,
    canonical_json,
    read_gzip_jsonl,
    write_gzip_jsonl,
)
from .literature_momseason_total_return_source import ALPACA_RESEARCH_NAMESPACE, _finite_float
from .research_population_coverage import (
    PopulationCoverageStage,
    PopulationScope,
    assess_population_coverage,
)


MOMSEASON_NATIVE_POPULATION_CONTRACT = (
    "literature-momseason-native-population-v1-open-source-ap-nyse-amex-common-stock-available-lags-pre-outcome"
)
MOMSEASON_NATIVE_POPULATION_ROOT = "native_population"
MOMSEASON_NATIVE_PLAN = "native_endpoint_plan.jsonl.gz"
MOMSEASON_NATIVE_PLAN_REPORT = "native_endpoint_plan_report.json"
MOMSEASON_NATIVE_SUPPLEMENTAL_PLAN = "supplemental_endpoint_plan.jsonl.gz"
MOMSEASON_NATIVE_ENDPOINTS = "native_adjusted_predictor_endpoints.parquet"
MOMSEASON_NATIVE_REPORT = "native_population_source_report.json"
MOMSEASON_NATIVE_UNIT_STATUS = "COMPLETE"

# OpenSourceAP builds its signal master table from CRSP share codes 10/11/12 on
# NYSE/AMEX/NASDAQ, then SignalDoc applies exchcd in (1,2) to MomSeason and
# MomSeasonShort at portfolio formation. Massive type CS is its provider-native
# common-stock analogue. Historical lag rows may therefore be on NYSE/AMEX/NASDAQ,
# while the formation cross-section is restricted to NYSE/AMEX.
MOMSEASON_NATIVE_FORMATION_EXCHANGES = frozenset({"XNYS", "XASE"})
MOMSEASON_NATIVE_HISTORY_EXCHANGES = frozenset({"XNYS", "XASE", "XNAS"})
MOMSEASON_NATIVE_SECURITY_TYPE = "CS"
MOMSEASON_NATIVE_MARKET = "stocks"
MOMSEASON_NATIVE_LOCALE = "us"
MOMSEASON_NATIVE_IDENTITY_QUALITIES = frozenset({"strong", "medium"})
MOMSEASON_NATIVE_MIN_AVAILABLE_LAGS = {
    "momseason_short_year1": 1,
    "momseason_years2_5": 1,
}


@dataclass(frozen=True, slots=True)
class NativeEndpointUnit:
    endpoint_session: date
    batch_index: int
    symbols: tuple[str, ...]
    supplemental_plan_fingerprint: str
    unit_id: str


def _unit_id(
    *,
    endpoint_session: date,
    batch_index: int,
    symbols: tuple[str, ...],
    supplemental_plan_fingerprint: str,
) -> str:
    payload = {
        "contract": MOMSEASON_NATIVE_POPULATION_CONTRACT,
        "supplemental_plan_fingerprint": supplemental_plan_fingerprint,
        "endpoint_session": endpoint_session.isoformat(),
        "batch_index": batch_index,
        "symbols": list(symbols),
        "adjustment": MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
        "feed": MOMSEASON_ADJUSTED_PREDICTOR_FEED,
        "timeframe": MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
        "currency": MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
        "asof": endpoint_session.isoformat(),
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_upper(value: object) -> str:
    return _normalize_text(value).upper()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _formation_row_status(rows: list[dict[str, object]]) -> tuple[dict[str, object] | None, str]:
    active_rows = [
        row
        for row in rows
        if bool(row.get("active")) and row.get("delisted_utc") is None
    ]
    qualifying = [
        row
        for row in active_rows
        if _normalize_lower(row.get("market")) == MOMSEASON_NATIVE_MARKET
        and _normalize_lower(row.get("locale")) == MOMSEASON_NATIVE_LOCALE
        and _normalize_upper(row.get("primary_exchange")) in MOMSEASON_NATIVE_FORMATION_EXCHANGES
        and _normalize_upper(row.get("security_type")) == MOMSEASON_NATIVE_SECURITY_TYPE
    ]
    if not qualifying:
        return None, "NOT_NATIVE_FORMATION_STOCK"
    if len(active_rows) != 1 or len(qualifying) != 1:
        return None, "FORMATION_AMBIGUOUS_ACTIVE_LISTING"
    row = qualifying[0]
    if _normalize_lower(row.get("identity_quality")) not in MOMSEASON_NATIVE_IDENTITY_QUALITIES:
        return row, "FORMATION_IDENTITY_UNSAFE"
    if not _clean_symbol(row.get("ticker")):
        return row, "FORMATION_TICKER_UNAVAILABLE"
    return row, "OK"


def _historical_row_status(
    rows: list[dict[str, object]],
    *,
    require_signal_master_membership: bool,
) -> tuple[dict[str, object] | None, str]:
    if not rows:
        return None, "HISTORICAL_REFERENCE_ABSENT"
    active_rows = [
        row
        for row in rows
        if bool(row.get("active", True)) and _clean_symbol(row.get("ticker")) is not None
    ]
    qualifying = [
        row
        for row in active_rows
        if (
            not require_signal_master_membership
            or (
                _normalize_upper(row.get("primary_exchange"))
                in MOMSEASON_NATIVE_HISTORY_EXCHANGES
                and _normalize_upper(row.get("security_type"))
                == MOMSEASON_NATIVE_SECURITY_TYPE
            )
        )
    ]
    if not qualifying:
        reason = (
            "HISTORICAL_NOT_COMMON_MAJOR_EXCHANGE"
            if require_signal_master_membership
            else "HISTORICAL_ENDPOINT_METADATA_UNAVAILABLE"
        )
        return None, reason
    if len(active_rows) != 1 or len(qualifying) != 1:
        return None, "HISTORICAL_AMBIGUOUS_LISTING"
    row = qualifying[0]
    if _normalize_lower(row.get("identity_quality")) not in MOMSEASON_NATIVE_IDENTITY_QUALITIES:
        return row, "HISTORICAL_IDENTITY_UNSAFE"
    return row, "OK"


def _lag_dates(calendar: Any, formation_month_start: date, years_back: int) -> tuple[date, date]:
    lag_month = same_month_years_back(formation_month_start, years_back)
    prior_end = month_sessions(calendar, previous_month(lag_month))[-1]
    current_end = month_sessions(calendar, lag_month)[-1]
    return prior_end, current_end


def _formula_defined(hypothesis_id: str, valid_lag_count: int) -> bool:
    required = MOMSEASON_NATIVE_MIN_AVAILABLE_LAGS[hypothesis_id]
    return int(valid_lag_count) >= int(required)


def _supplemental_rows(
    native_plan_rows: Iterable[dict[str, object]],
    prior_endpoints: dict[tuple[str, str], dict[str, object]],
) -> tuple[list[dict[str, object]], int]:
    missing: list[dict[str, object]] = []
    reused = 0
    for row in native_plan_rows:
        key = (str(row["endpoint_session"]), str(row["instrument_id"]))
        existing = prior_endpoints.get(key)
        if existing is None:
            missing.append(dict(row))
            continue
        if str(existing.get("historical_ticker") or "") != str(row["historical_ticker"]):
            raise RuntimeError(
                "native endpoint plan conflicts with previously materialized historical ticker: "
                f"{key}"
            )
        reused += 1
    missing.sort(
        key=lambda row: (
            str(row["endpoint_session"]),
            str(row["instrument_id"]),
            str(row["historical_ticker"]),
        )
    )
    return missing, reused


def _median_int(values: Iterable[int]) -> float | None:
    ordered = sorted(int(value) for value in values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


class MomSeasonNativePopulationSource:
    """Reconstruct the externally specified LIT-01 source population before outcomes.

    This stage removes ATLAS discovery-routing policy from the scientific population.
    Formation membership is read from the complete PIT reference snapshot and restricted
    to provider-native common stocks on NYSE/NYSE American. Historical lag rows may be on
    NYSE/NYSE American/NASDAQ, matching OpenSourceAP's common-stock master-table scope.

    ``momseason_years2_5`` uses the externally replicated available-history convention:
    each of years 2, 3, 4 and 5 is assessed independently and the later signal may average
    the available annual lag returns. At least one valid annual lag is required. This
    source stage records lag availability only; it never computes a return or signal.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        alpaca_client: AlpacaMarketDataClient | None = None,
    ) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.source = MomSeasonSourceAcquirer(settings)
        self.alpaca = alpaca_client or AlpacaMarketDataClient(settings)
        self.raw_store = AlpacaRawPayloadStore(settings, namespace=ALPACA_RESEARCH_NAMESPACE)
        derived = settings.resolved_path(settings.data.paths.derived)
        total_return_root = derived / MOMSEASON_SOURCE_ROOT_RELATIVE / "total_return_source"
        self.prior_endpoint_path = (
            total_return_root
            / MOMSEASON_ADJUSTED_PREDICTOR_ROOT_NAME
            / MOMSEASON_ADJUSTED_PREDICTOR_ENDPOINTS
        )
        self.root = total_return_root / MOMSEASON_NATIVE_POPULATION_ROOT
        self.allowed_endpoint_sessions = frozenset(required_lag_reference_dates(self.calendar))
        if not self.allowed_endpoint_sessions:
            raise RuntimeError("LIT-01 native source endpoint whitelist is empty")
        if max(self.allowed_endpoint_sessions) >= LITERATURE_MOMSEASON_PROTECTED_START:
            raise RuntimeError("LIT-01 native source endpoint whitelist reaches protected window")

    def plan_path(self) -> Path:
        return self.root / MOMSEASON_NATIVE_PLAN

    def plan_report_path(self) -> Path:
        return self.root / MOMSEASON_NATIVE_PLAN_REPORT

    def supplemental_plan_path(self) -> Path:
        return self.root / MOMSEASON_NATIVE_SUPPLEMENTAL_PLAN

    def endpoint_path(self) -> Path:
        return self.root / MOMSEASON_NATIVE_ENDPOINTS

    def report_path(self) -> Path:
        return self.root / MOMSEASON_NATIVE_REPORT

    def unit_manifest_path(self, unit: NativeEndpointUnit) -> Path:
        return (
            self.root
            / "supplemental_units"
            / f"date={unit.endpoint_session.isoformat()}"
            / f"batch_{unit.batch_index:04d}.json"
        )

    def _formation_groups(self, session: date) -> dict[str, list[dict[str, object]]]:
        path = self.paths.reference_snapshot_file(session)
        if not path.is_file():
            raise RuntimeError(f"missing PIT formation reference snapshot: {path}")
        con = duckdb.connect(":memory:")
        try:
            cursor = con.execute(
                """
                SELECT instrument_id, CAST(identity_quality AS VARCHAR) AS identity_quality,
                       ticker, market, locale, primary_exchange, security_type,
                       active, delisted_utc
                FROM read_parquet(?)
                ORDER BY instrument_id, ticker
                """,
                [str(path)],
            )
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            con.close()
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            instrument_id = _normalize_text(row.get("instrument_id"))
            if instrument_id:
                grouped[instrument_id].append(row)
        return dict(grouped)

    def _historical_groups(self) -> dict[date, dict[str, list[dict[str, object]]]]:
        result: dict[date, dict[str, list[dict[str, object]]]] = {}
        for session in sorted(self.allowed_endpoint_sessions):
            path = self.source.reference_path(session)
            if not path.is_file():
                raise RuntimeError(f"missing LIT-01 historical reference snapshot: {path}")
            grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
            for row in read_gzip_jsonl(path):
                instrument_id = _normalize_text(row.get("instrument_id"))
                if instrument_id:
                    grouped[instrument_id].append(row)
            result[session] = dict(grouped)
        return result

    def _native_formation_members(self, session: date) -> tuple[list[dict[str, object]], Counter[str]]:
        members: list[dict[str, object]] = []
        counts: Counter[str] = Counter()
        for instrument_id, rows in sorted(self._formation_groups(session).items()):
            row, status = _formation_row_status(rows)
            if status == "NOT_NATIVE_FORMATION_STOCK":
                continue
            counts[status] += 1
            members.append(
                {
                    "instrument_id": instrument_id,
                    "formation_ticker": _clean_symbol(row.get("ticker")) if row else None,
                    "formation_identity_quality": _normalize_lower(row.get("identity_quality")) if row else None,
                    "formation_status": status,
                    "primary_exchange": _normalize_upper(row.get("primary_exchange")) if row else None,
                    "security_type": _normalize_upper(row.get("security_type")) if row else None,
                }
            )
        members.sort(key=lambda row: str(row["instrument_id"]))
        return members, counts

    def _valid_lag(
        self,
        *,
        formation_month_start: date,
        instrument_id: str,
        years_back: int,
        historical: dict[date, dict[str, list[dict[str, object]]]],
    ) -> tuple[dict[str, object] | None, str]:
        prior_end, current_end = _lag_dates(self.calendar, formation_month_start, years_back)
        if prior_end not in self.allowed_endpoint_sessions or current_end not in self.allowed_endpoint_sessions:
            raise RuntimeError("native LIT-01 lag escaped endpoint whitelist")
        # The lag-month row itself must belong to OpenSourceAP's common-stock/major-
        # exchange master table. The prior endpoint is only a price anchor for that
        # monthly return and therefore requires identity-safe continuity, not a second
        # portfolio-universe membership test.
        prior_row, prior_status = _historical_row_status(
            historical.get(prior_end, {}).get(instrument_id, []),
            require_signal_master_membership=False,
        )
        current_row, current_status = _historical_row_status(
            historical.get(current_end, {}).get(instrument_id, []),
            require_signal_master_membership=True,
        )
        if prior_status != "OK" or current_status != "OK":
            reason = prior_status if prior_status != "OK" else current_status
            return None, reason
        assert prior_row is not None and current_row is not None
        prior_ticker = _clean_symbol(prior_row.get("ticker"))
        current_ticker = _clean_symbol(current_row.get("ticker"))
        if prior_ticker is None or current_ticker is None:
            return None, "HISTORICAL_TICKER_UNAVAILABLE"
        return {
            "years_back": years_back,
            "prior_end": prior_end,
            "prior_ticker": prior_ticker,
            "current_end": current_end,
            "current_ticker": current_ticker,
            "ticker_changed_inside_lag_month": prior_ticker != current_ticker,
        }, "OK"

    def build_plan(self, *, force: bool = False) -> dict[str, object]:
        if self.plan_path().is_file() and self.plan_report_path().is_file() and not force:
            rows = read_gzip_jsonl(self.plan_path())
            report = json.loads(self.plan_report_path().read_text(encoding="utf-8"))
            if _rows_fingerprint(rows) != report.get("plan_fingerprint"):
                raise RuntimeError("native LIT-01 plan fingerprint mismatch")
            report["skipped"] = True
            return report

        historical = self._historical_groups()
        plan: dict[tuple[date, str], dict[str, object]] = {}
        hypothesis_counts: dict[str, Counter[str]] = {
            item.hypothesis_id: Counter() for item in MOMSEASON_HYPOTHESES
        }
        monthly_native: dict[str, dict[str, int]] = {
            item.hypothesis_id: {} for item in MOMSEASON_HYPOTHESES
        }
        monthly_identity_defined: dict[str, dict[str, int]] = {
            item.hypothesis_id: {} for item in MOMSEASON_HYPOTHESES
        }
        formation_status_counts: Counter[str] = Counter()
        lag_failure_counts: dict[str, Counter[str]] = {
            item.hypothesis_id: Counter() for item in MOMSEASON_HYPOTHESES
        }
        identity_lag_distribution: dict[str, Counter[int]] = {
            item.hypothesis_id: Counter() for item in MOMSEASON_HYPOTHESES
        }
        formation_instruments: set[str] = set()
        months = formation_months(self.calendar)

        for formation in months:
            month_key = formation.month_start.strftime("%Y-%m")
            members, formation_counts = self._native_formation_members(formation.first_session)
            formation_status_counts.update(formation_counts)
            formation_instruments.update(str(row["instrument_id"]) for row in members)

            for hypothesis in MOMSEASON_HYPOTHESES:
                counter = hypothesis_counts[hypothesis.hypothesis_id]
                counter["native_eligible_rows"] += len(members)
                monthly_native[hypothesis.hypothesis_id][month_key] = len(members)
                identity_defined_month = 0
                for member in members:
                    instrument_id = str(member["instrument_id"])
                    if member["formation_status"] != "OK":
                        counter[str(member["formation_status"]).lower()] += 1
                        continue
                    valid_lags: list[dict[str, object]] = []
                    for years_back in hypothesis.lag_years:
                        lag, status = self._valid_lag(
                            formation_month_start=formation.month_start,
                            instrument_id=instrument_id,
                            years_back=years_back,
                            historical=historical,
                        )
                        if lag is None:
                            lag_failure_counts[hypothesis.hypothesis_id][status] += 1
                            continue
                        valid_lags.append(lag)
                        if bool(lag["ticker_changed_inside_lag_month"]):
                            counter["ticker_change_lags_allowed"] += 1
                        for endpoint, ticker in (
                            (lag["prior_end"], lag["prior_ticker"]),
                            (lag["current_end"], lag["current_ticker"]),
                        ):
                            assert isinstance(endpoint, date)
                            key = (endpoint, instrument_id)
                            existing = plan.get(key)
                            if existing is not None and existing["historical_ticker"] != ticker:
                                raise RuntimeError(
                                    "conflicting native historical ticker for endpoint/instrument: "
                                    f"{endpoint} {instrument_id}"
                                )
                            plan[key] = {
                                "role": "LITERATURE_NATIVE_LAG_ENDPOINT",
                                "endpoint_session": endpoint.isoformat(),
                                "instrument_id": instrument_id,
                                "historical_ticker": str(ticker),
                            }
                    lag_count = len(valid_lags)
                    identity_lag_distribution[hypothesis.hypothesis_id][lag_count] += 1
                    if _formula_defined(hypothesis.hypothesis_id, lag_count):
                        counter["identity_formula_defined_rows"] += 1
                        identity_defined_month += 1
                    else:
                        counter["identity_formula_undefined_rows"] += 1
                monthly_identity_defined[hypothesis.hypothesis_id][month_key] = identity_defined_month

        rows = sorted(
            plan.values(),
            key=lambda row: (
                str(row["endpoint_session"]),
                str(row["instrument_id"]),
                str(row["historical_ticker"]),
            ),
        )
        fingerprint = _rows_fingerprint(rows)
        report = {
            "contract_version": MOMSEASON_NATIVE_POPULATION_CONTRACT,
            "plan_fingerprint": fingerprint,
            "formation_rule": {
                "market": MOMSEASON_NATIVE_MARKET,
                "locale": MOMSEASON_NATIVE_LOCALE,
                "primary_exchange": sorted(MOMSEASON_NATIVE_FORMATION_EXCHANGES),
                "security_type": MOMSEASON_NATIVE_SECURITY_TYPE,
                "active": True,
                "source": "PIT formation reference snapshot; no ATLAS discovery-route filter",
            },
            "historical_lag_rule": {
                "primary_exchange": sorted(MOMSEASON_NATIVE_HISTORY_EXCHANGES),
                "security_type": MOMSEASON_NATIVE_SECURITY_TYPE,
                "identity_quality": sorted(MOMSEASON_NATIVE_IDENTITY_QUALITIES),
                "ticker_change_inside_lag_month": "ALLOWED_WHEN_STABLE_INSTRUMENT_ID_CONTINUES",
            },
            "history_availability_rule": {
                "momseason_short_year1": "exact year-1 lag required",
                "momseason_years2_5": "average available valid annual lags among years 2,3,4,5; at least one required",
            },
            "formation_months": len(months),
            "formation_instruments": len(formation_instruments),
            "endpoint_plan_rows": len(rows),
            "formation_status_counts": dict(sorted(formation_status_counts.items())),
            "hypotheses": {
                hypothesis.hypothesis_id: {
                    **dict(hypothesis_counts[hypothesis.hypothesis_id]),
                    "identity_valid_lag_count_distribution": {
                        str(key): value
                        for key, value in sorted(identity_lag_distribution[hypothesis.hypothesis_id].items())
                    },
                    "lag_failure_counts": dict(sorted(lag_failure_counts[hypothesis.hypothesis_id].items())),
                    "monthly_native_eligible_rows": monthly_native[hypothesis.hypothesis_id],
                    "monthly_identity_formula_defined_rows": monthly_identity_defined[hypothesis.hypothesis_id],
                }
                for hypothesis in MOMSEASON_HYPOTHESES
            },
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "skipped": False,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        write_gzip_jsonl(self.plan_path(), rows)
        atomic_write_text(self.plan_report_path(), canonical_json(report) + "\n")
        return report

    def _load_plan(self) -> tuple[list[dict[str, object]], dict[str, object]]:
        if not self.plan_path().is_file() or not self.plan_report_path().is_file():
            raise RuntimeError("native LIT-01 plan is required")
        rows = read_gzip_jsonl(self.plan_path())
        report = json.loads(self.plan_report_path().read_text(encoding="utf-8"))
        if _rows_fingerprint(rows) != report.get("plan_fingerprint"):
            raise RuntimeError("native LIT-01 plan fingerprint mismatch")
        return rows, report

    def _load_prior_endpoints(self) -> dict[tuple[str, str], dict[str, object]]:
        if not self.prior_endpoint_path.is_file():
            raise RuntimeError(
                "accepted adjusted predictor endpoint parquet is required before native census"
            )
        con = duckdb.connect(":memory:")
        try:
            cursor = con.execute(
                """
                SELECT CAST(endpoint_session AS VARCHAR) AS endpoint_session,
                       instrument_id, historical_ticker, availability_status,
                       adjusted_close, price_currency, source_provider, source_adjustment,
                       source_feed, source_timeframe, source_asof, source_page_sha256_json
                FROM read_parquet(?)
                ORDER BY endpoint_session, instrument_id
                """,
                [str(self.prior_endpoint_path)],
            )
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            con.close()
        result: dict[tuple[str, str], dict[str, object]] = {}
        for row in rows:
            key = (str(row["endpoint_session"]), str(row["instrument_id"]))
            if key in result:
                raise RuntimeError(f"duplicate prior adjusted endpoint key: {key}")
            result[key] = row
        return result

    def build_supplemental_plan(self) -> dict[str, object]:
        plan_rows, report = self._load_plan()
        prior = self._load_prior_endpoints()
        missing, reused = _supplemental_rows(plan_rows, prior)
        write_gzip_jsonl(self.supplemental_plan_path(), missing)
        return {
            "native_plan_fingerprint": report["plan_fingerprint"],
            "native_endpoint_rows": len(plan_rows),
            "reused_prior_endpoint_rows": reused,
            "supplemental_endpoint_rows": len(missing),
            "supplemental_plan_fingerprint": _rows_fingerprint(missing),
        }

    def _supplemental_units(self) -> list[NativeEndpointUnit]:
        if not self.supplemental_plan_path().is_file():
            self.build_supplemental_plan()
        rows = read_gzip_jsonl(self.supplemental_plan_path())
        fingerprint = _rows_fingerprint(rows)
        by_session: dict[date, dict[str, str]] = defaultdict(dict)
        for row in rows:
            endpoint = date.fromisoformat(str(row["endpoint_session"]))
            if endpoint not in self.allowed_endpoint_sessions:
                raise RuntimeError("supplemental native endpoint escaped whitelist")
            ticker = str(row["historical_ticker"])
            instrument_id = str(row["instrument_id"])
            existing = by_session[endpoint].get(ticker)
            if existing is not None and existing != instrument_id:
                raise RuntimeError(
                    "one supplemental historical ticker maps to multiple instruments on one date: "
                    f"{endpoint} {ticker}"
                )
            by_session[endpoint][ticker] = instrument_id
        units: list[NativeEndpointUnit] = []
        batch_size = int(self.alpaca.cfg.symbol_batch_size)
        for endpoint in sorted(by_session):
            symbols = sorted(by_session[endpoint])
            for batch_index, batch in enumerate(_chunks(symbols, batch_size)):
                units.append(
                    NativeEndpointUnit(
                        endpoint_session=endpoint,
                        batch_index=batch_index,
                        symbols=batch,
                        supplemental_plan_fingerprint=fingerprint,
                        unit_id=_unit_id(
                            endpoint_session=endpoint,
                            batch_index=batch_index,
                            symbols=batch,
                            supplemental_plan_fingerprint=fingerprint,
                        ),
                    )
                )
        return units

    def _load_unit_manifest(self, unit: NativeEndpointUnit) -> dict[str, object] | None:
        path = self.unit_manifest_path(unit)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        compatible = (
            payload.get("contract_version") == MOMSEASON_NATIVE_POPULATION_CONTRACT
            and payload.get("unit_id") == unit.unit_id
            and payload.get("supplemental_plan_fingerprint") == unit.supplemental_plan_fingerprint
            and payload.get("status") == MOMSEASON_NATIVE_UNIT_STATUS
            and payload.get("endpoint_session") == unit.endpoint_session.isoformat()
            and payload.get("symbols") == list(unit.symbols)
            and payload.get("adjustment") == MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT
            and payload.get("feed") == MOMSEASON_ADJUSTED_PREDICTOR_FEED
            and payload.get("timeframe") == MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME
            and payload.get("asof") == unit.endpoint_session.isoformat()
        )
        if not compatible:
            raise RuntimeError(f"stale native supplemental unit manifest: {path}")
        for record in payload.get("raw_pages") or []:
            if not isinstance(record, dict):
                raise RuntimeError(f"invalid native raw-page evidence: {path}")
            if not Path(str(record.get("payload_path") or "")).is_file():
                raise RuntimeError(f"missing native raw payload evidence: {path}")
            if not Path(str(record.get("metadata_path") or "")).is_file():
                raise RuntimeError(f"missing native raw metadata evidence: {path}")
        return payload

    def _acquire_unit(self, unit: NativeEndpointUnit) -> dict[str, object]:
        requested = list(unit.symbols)
        remaining = list(requested)
        observed: dict[str, float] = {}
        source_hashes: dict[str, set[str]] = defaultdict(set)
        raw_pages: list[dict[str, object]] = []
        provider_rejections: dict[str, dict[str, object]] = {}
        anomalies: list[dict[str, object]] = []
        provider_calls = 0

        while remaining:
            page_count_before = len(raw_pages)
            try:
                for page_index, page in enumerate(
                    self.alpaca.historical_bar_pages(
                        symbols=remaining,
                        start=unit.endpoint_session.isoformat(),
                        end=unit.endpoint_session.isoformat(),
                        adjustment=MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
                        asof=unit.endpoint_session.isoformat(),
                        feed=MOMSEASON_ADJUSTED_PREDICTOR_FEED,
                        timeframe=MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
                    )
                ):
                    provider_calls += 1
                    raw_record = self.raw_store.persist(
                        page,
                        category="native_predictor_endpoint_all",
                        partition=(
                            f"{unit.endpoint_session.isoformat()}_batch_{unit.batch_index:04d}_"
                            f"page_{page_index:04d}"
                        ),
                    )
                    raw_pages.append(
                        {
                            "sha256": raw_record.sha256,
                            "payload_path": raw_record.payload_path,
                            "metadata_path": raw_record.metadata_path,
                        }
                    )
                    page_values, page_anomalies = extract_single_session_adjusted_closes(
                        page.payload,
                        requested_symbols=set(remaining),
                        endpoint_session=unit.endpoint_session,
                    )
                    for symbol, close in page_values.items():
                        previous = observed.get(symbol)
                        if previous is not None and not math.isclose(previous, close, rel_tol=0.0, abs_tol=0.0):
                            raise RuntimeError(
                                f"conflicting native adjusted close for {symbol} on {unit.endpoint_session}"
                            )
                        observed[symbol] = close
                        source_hashes[symbol].add(raw_record.sha256)
                    anomalies.extend(page_anomalies)
                break
            except AlpacaInvalidSymbolError as exc:
                provider_calls += 1
                if len(raw_pages) != page_count_before:
                    raise RuntimeError(
                        "Alpaca rejected native supplemental symbol after pagination began"
                    ) from exc
                invalid = exc.symbol
                if invalid not in remaining:
                    raise RuntimeError(
                        f"Alpaca rejected unsubmitted native supplemental symbol: {invalid}"
                    ) from exc
                raw_record = self.raw_store.persist(
                    exc.page,
                    category="native_predictor_endpoint_rejections",
                    partition=(
                        f"{unit.endpoint_session.isoformat()}_batch_{unit.batch_index:04d}_"
                        f"reject_{len(provider_rejections):04d}"
                    ),
                )
                provider_rejections[invalid] = {
                    "symbol": invalid,
                    "http_status": exc.page.http_status,
                    "provider_message": exc.provider_message,
                    "sha256": raw_record.sha256,
                    "payload_path": raw_record.payload_path,
                    "metadata_path": raw_record.metadata_path,
                }
                remaining = [item for item in remaining if item != invalid]

        results: list[dict[str, object]] = []
        for symbol in sorted(requested):
            if symbol in observed:
                status = "AVAILABLE"
                close: float | None = observed[symbol]
            elif symbol in provider_rejections:
                status = "PROVIDER_REJECTED"
                close = None
            else:
                status = "ZERO_BAR"
                close = None
            results.append(
                {
                    "symbol": symbol,
                    "availability_status": status,
                    "adjusted_close": close,
                    "source_page_sha256": sorted(source_hashes.get(symbol, set())),
                }
            )

        payload: dict[str, object] = {
            "contract_version": MOMSEASON_NATIVE_POPULATION_CONTRACT,
            "unit_id": unit.unit_id,
            "supplemental_plan_fingerprint": unit.supplemental_plan_fingerprint,
            "status": MOMSEASON_NATIVE_UNIT_STATUS,
            "endpoint_session": unit.endpoint_session.isoformat(),
            "batch_index": unit.batch_index,
            "symbols": list(unit.symbols),
            "adjustment": MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
            "feed": MOMSEASON_ADJUSTED_PREDICTOR_FEED,
            "timeframe": MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
            "currency": MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
            "asof": unit.endpoint_session.isoformat(),
            "single_session_request": True,
            "raw_pages": raw_pages,
            "provider_rejections": [provider_rejections[key] for key in sorted(provider_rejections)],
            "response_symbol_anomalies": anomalies,
            "symbol_results": results,
            "provider_calls_performed": provider_calls,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
        }
        path = self.unit_manifest_path(unit)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, canonical_json(payload) + "\n")
        return payload

    def acquire_supplemental(self, *, force: bool = False) -> dict[str, object]:
        self.build_supplemental_plan()
        units = self._supplemental_units()
        by_session: dict[date, list[NativeEndpointUnit]] = defaultdict(list)
        for unit in units:
            by_session[unit.endpoint_session].append(unit)
        executed = 0
        skipped = 0
        calls = 0
        availability: Counter[str] = Counter()
        for session_index, endpoint in enumerate(sorted(by_session), start=1):
            day_counts: Counter[str] = Counter()
            day_executed = 0
            day_skipped = 0
            for unit in sorted(by_session[endpoint], key=lambda item: item.batch_index):
                payload = None if force else self._load_unit_manifest(unit)
                if payload is None:
                    payload = self._acquire_unit(unit)
                    executed += 1
                    day_executed += 1
                    calls += int(payload.get("provider_calls_performed") or 0)
                else:
                    skipped += 1
                    day_skipped += 1
                for row in payload.get("symbol_results") or []:
                    if isinstance(row, dict):
                        day_counts[str(row.get("availability_status") or "UNKNOWN")] += 1
            availability.update(day_counts)
            print(
                "LIT-01 native supplemental acquisition: "
                f"{session_index}/{len(by_session)} date={endpoint.isoformat()} "
                f"symbols={sum(day_counts.values())} units={len(by_session[endpoint])} "
                f"executed={day_executed} skipped={day_skipped} "
                f"available={day_counts['AVAILABLE']} rejected={day_counts['PROVIDER_REJECTED']} "
                f"zero_bar={day_counts['ZERO_BAR']}"
            )
        return {
            "planned_units": len(units),
            "executed_units_this_run": executed,
            "skipped_units_this_run": skipped,
            "provider_calls_performed": calls,
            "availability_counts": dict(sorted(availability.items())),
        }

    def _supplemental_results(self) -> tuple[dict[tuple[str, str], dict[str, object]], int, int]:
        units = self._supplemental_units()
        result: dict[tuple[str, str], dict[str, object]] = {}
        missing_units = 0
        provider_calls = 0
        for unit in units:
            payload = self._load_unit_manifest(unit)
            if payload is None:
                missing_units += 1
                continue
            provider_calls += int(payload.get("provider_calls_performed") or 0)
            for row in payload.get("symbol_results") or []:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol") or "")
                result[(unit.endpoint_session.isoformat(), symbol)] = row
        return result, missing_units, provider_calls

    def _materialize_native_endpoints(self) -> tuple[dict[tuple[date, str], dict[str, object]], Counter[str], int]:
        plan_rows, _ = self._load_plan()
        prior = self._load_prior_endpoints()
        supplemental, missing_units, _calls = self._supplemental_results()
        rows: list[dict[str, object]] = []
        endpoint_map: dict[tuple[date, str], dict[str, object]] = {}
        counts: Counter[str] = Counter()
        for plan in plan_rows:
            endpoint_text = str(plan["endpoint_session"])
            instrument_id = str(plan["instrument_id"])
            ticker = str(plan["historical_ticker"])
            prior_row = prior.get((endpoint_text, instrument_id))
            if prior_row is not None:
                status = str(prior_row.get("availability_status") or "UNKNOWN")
                close = _finite_float(prior_row.get("adjusted_close"))
                source_hashes_json = str(prior_row.get("source_page_sha256_json") or "[]")
                provenance = "REUSED_ACCEPTED_ADJUSTED_ENDPOINT"
            else:
                source = supplemental.get((endpoint_text, ticker))
                if source is None:
                    status = "SUPPLEMENTAL_UNIT_NOT_MATERIALIZED"
                    close = None
                    hashes: list[str] = []
                else:
                    status = str(source.get("availability_status") or "UNKNOWN")
                    close = _finite_float(source.get("adjusted_close"))
                    hashes = [str(value) for value in source.get("source_page_sha256") or []]
                source_hashes_json = canonical_json(hashes)
                provenance = "NATIVE_SUPPLEMENTAL_ENDPOINT"
            counts[status] += 1
            row = {
                "contract_version": MOMSEASON_NATIVE_POPULATION_CONTRACT,
                "role": "LITERATURE_NATIVE_LAG_ENDPOINT",
                "endpoint_session": endpoint_text,
                "instrument_id": instrument_id,
                "historical_ticker": ticker,
                "availability_status": status,
                "adjusted_close": close,
                "price_currency": MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
                "source_provider": "alpaca",
                "source_adjustment": MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
                "source_feed": MOMSEASON_ADJUSTED_PREDICTOR_FEED,
                "source_timeframe": MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
                "source_asof": endpoint_text,
                "source_lineage": provenance,
                "source_page_sha256_json": source_hashes_json,
            }
            rows.append(row)
            endpoint_map[(date.fromisoformat(endpoint_text), instrument_id)] = row
        rows.sort(key=lambda row: (str(row["endpoint_session"]), str(row["instrument_id"])))
        if missing_units == 0:
            _write_parquet_rows(self.endpoint_path(), rows)
        return endpoint_map, counts, missing_units

    def _coverage(self, endpoint_map: dict[tuple[date, str], dict[str, object]]) -> dict[str, object]:
        historical = self._historical_groups()
        combined_native = 0
        combined_identity = 0
        combined_adjusted = 0
        native_instruments: set[str] = set()
        identity_instruments: set[str] = set()
        adjusted_instruments: set[str] = set()
        result: dict[str, object] = {}

        for hypothesis in MOMSEASON_HYPOTHESES:
            native_rows = 0
            identity_rows = 0
            adjusted_rows = 0
            formation_failure: Counter[str] = Counter()
            lag_identity_failures: Counter[str] = Counter()
            identity_lag_distribution: Counter[int] = Counter()
            adjusted_lag_distribution: Counter[int] = Counter()
            ticker_change_lags = 0
            monthly_native: dict[str, int] = {}
            monthly_identity: dict[str, int] = {}
            monthly_adjusted: dict[str, int] = {}

            for formation in formation_months(self.calendar):
                month_key = formation.month_start.strftime("%Y-%m")
                members, _counts = self._native_formation_members(formation.first_session)
                native_rows += len(members)
                combined_native += len(members)
                monthly_native[month_key] = len(members)
                identity_month = 0
                adjusted_month = 0
                for member in members:
                    instrument_id = str(member["instrument_id"])
                    native_instruments.add(instrument_id)
                    if member["formation_status"] != "OK":
                        formation_failure[str(member["formation_status"])] += 1
                        identity_lag_distribution[0] += 1
                        adjusted_lag_distribution[0] += 1
                        continue
                    valid_lags: list[dict[str, object]] = []
                    adjusted_lags = 0
                    for years_back in hypothesis.lag_years:
                        lag, status = self._valid_lag(
                            formation_month_start=formation.month_start,
                            instrument_id=instrument_id,
                            years_back=years_back,
                            historical=historical,
                        )
                        if lag is None:
                            lag_identity_failures[status] += 1
                            continue
                        valid_lags.append(lag)
                        if bool(lag["ticker_changed_inside_lag_month"]):
                            ticker_change_lags += 1
                        prior_key = (lag["prior_end"], instrument_id)
                        current_key = (lag["current_end"], instrument_id)
                        prior = endpoint_map.get(prior_key)
                        current = endpoint_map.get(current_key)
                        if (
                            prior is not None
                            and current is not None
                            and prior.get("availability_status") == "AVAILABLE"
                            and current.get("availability_status") == "AVAILABLE"
                        ):
                            adjusted_lags += 1
                    identity_lag_distribution[len(valid_lags)] += 1
                    adjusted_lag_distribution[adjusted_lags] += 1
                    if _formula_defined(hypothesis.hypothesis_id, len(valid_lags)):
                        identity_rows += 1
                        combined_identity += 1
                        identity_month += 1
                        identity_instruments.add(instrument_id)
                    if _formula_defined(hypothesis.hypothesis_id, adjusted_lags):
                        adjusted_rows += 1
                        combined_adjusted += 1
                        adjusted_month += 1
                        adjusted_instruments.add(instrument_id)
                monthly_identity[month_key] = identity_month
                monthly_adjusted[month_key] = adjusted_month

            result[hypothesis.hypothesis_id] = {
                "native_eligible_rows": native_rows,
                "identity_formula_defined_rows": identity_rows,
                "adjusted_formula_defined_rows": adjusted_rows,
                "identity_ratio_of_native": identity_rows / native_rows if native_rows else None,
                "adjusted_ratio_of_native": adjusted_rows / native_rows if native_rows else None,
                "adjusted_ratio_of_identity": adjusted_rows / identity_rows if identity_rows else None,
                "formation_failure_counts": dict(sorted(formation_failure.items())),
                "lag_identity_failure_counts": dict(sorted(lag_identity_failures.items())),
                "identity_valid_lag_count_distribution": {
                    str(key): value for key, value in sorted(identity_lag_distribution.items())
                },
                "adjusted_valid_lag_count_distribution": {
                    str(key): value for key, value in sorted(adjusted_lag_distribution.items())
                },
                "ticker_change_lags_allowed": ticker_change_lags,
                "monthly_native_eligible_rows": monthly_native,
                "monthly_identity_formula_defined_rows": monthly_identity,
                "monthly_adjusted_formula_defined_rows": monthly_adjusted,
                "monthly_adjusted_min": min(monthly_adjusted.values()) if monthly_adjusted else None,
                "monthly_adjusted_median": _median_int(monthly_adjusted.values()),
                "monthly_adjusted_max": max(monthly_adjusted.values()) if monthly_adjusted else None,
            }

        population = assess_population_coverage(
            (
                PopulationCoverageStage(
                    name="literature_native_formation_population",
                    rows=combined_native,
                    instruments=len(native_instruments),
                    scope=PopulationScope.FULL_ELIGIBLE_UNIVERSE,
                    complete_scope=True,
                    grain="formation_month_hypothesis_instrument",
                    source="complete PIT reference snapshots; NYSE/AMEX Massive common-stock analogue",
                ),
                PopulationCoverageStage(
                    name="identity_formula_defined_population",
                    rows=combined_identity,
                    instruments=len(identity_instruments),
                    scope=PopulationScope.FILTERED_POPULATION,
                    complete_scope=True,
                    grain="formation_month_hypothesis_instrument",
                    source="Massive PIT historical references + ATLAS stable identity; available annual lags",
                ),
                PopulationCoverageStage(
                    name="adjusted_formula_defined_population",
                    rows=combined_adjusted,
                    instruments=len(adjusted_instruments),
                    scope=PopulationScope.FILTERED_POPULATION,
                    complete_scope=True,
                    grain="formation_month_hypothesis_instrument",
                    source="accepted Alpaca adjustment=all endpoints plus native supplemental endpoints",
                ),
            )
        )
        return {"hypotheses": result, "population_coverage": population.to_dict()}

    def run(
        self,
        *,
        acquire: bool = False,
        force_plan: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        plan_report = self.build_plan(force=force_plan)
        supplemental_plan = self.build_supplemental_plan()
        acquisition = self.acquire_supplemental(force=force_acquire) if acquire else None
        endpoint_map, endpoint_counts, missing_units = self._materialize_native_endpoints()
        coverage = self._coverage(endpoint_map)

        if missing_units:
            status = "NATIVE_POPULATION_SOURCE_ACQUISITION_INCOMPLETE"
        elif int(supplemental_plan["supplemental_endpoint_rows"]) > 0 and not acquire and not self.endpoint_path().is_file():
            status = "NATIVE_POPULATION_SUPPLEMENTAL_ENDPOINTS_REQUIRED"
        else:
            status = "NATIVE_POPULATION_SOURCE_CAPACITY_READY_FOR_REVIEW"

        report: dict[str, object] = {
            "status": status,
            "contract_version": MOMSEASON_NATIVE_POPULATION_CONTRACT,
            "native_plan": plan_report,
            "supplemental_plan": supplemental_plan,
            "acquisition": acquisition,
            "endpoint_availability_counts": dict(sorted(endpoint_counts.items())),
            "coverage": coverage,
            "source_request_boundary": {
                "single_session_requests_only": True,
                "adjustment": MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
                "feed": MOMSEASON_ADJUSTED_PREDICTOR_FEED,
                "timeframe": MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
                "currency": MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
                "asof_rule": "endpoint_session",
                "date_whitelist": "required_lag_reference_dates",
            },
            "provider_calls_performed_this_run": int(
                (acquisition or {}).get("provider_calls_performed") or 0
            ),
            "existing_canonical_market_data_mutated": False,
            "global_alpaca_adjustment_mutated": False,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        report["report_path"] = str(self.report_path())
        report["native_endpoint_path"] = str(self.endpoint_path()) if self.endpoint_path().is_file() else None
        return report
