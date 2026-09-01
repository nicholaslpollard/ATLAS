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

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_storage import AlpacaRawPayloadStore
from packages.data.paths import MarketDataPaths
from packages.providers.alpaca import (
    AlpacaInvalidSymbolError,
    AlpacaMarketDataClient,
)

from .literature_momseason_policy import (
    LITERATURE_MOMSEASON_PROTECTED_START,
    MOMSEASON_HYPOTHESES,
    formation_months,
    literature_momseason_source_fingerprint,
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
from .literature_momseason_total_return_source import (
    ALPACA_RESEARCH_NAMESPACE,
    _finite_float,
    _parse_date,
)
from .research_population_coverage import (
    PopulationCoverageStage,
    PopulationScope,
    assess_population_coverage,
)


MOMSEASON_ADJUSTED_PREDICTOR_SOURCE_CONTRACT = (
    "literature-momseason-adjusted-predictor-source-v1-single-session-all-adjusted-pit-lag-only"
)
MOMSEASON_ADJUSTED_PREDICTOR_ROLE = "LAG_PREDICTOR_ENDPOINT"
MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT = "all"
MOMSEASON_ADJUSTED_PREDICTOR_FEED = "sip"
MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME = "1Day"
MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY = "USD"
MOMSEASON_ADJUSTED_PREDICTOR_UNIT_STATUS = "COMPLETE"
MOMSEASON_ADJUSTED_PREDICTOR_ROOT_NAME = "adjusted_predictor_source"
MOMSEASON_ADJUSTED_PREDICTOR_PLAN = "endpoint_plan.jsonl.gz"
MOMSEASON_ADJUSTED_PREDICTOR_PLAN_REPORT = "endpoint_plan_report.json"
MOMSEASON_ADJUSTED_PREDICTOR_ENDPOINTS = "adjusted_predictor_endpoints.parquet"
MOMSEASON_ADJUSTED_PREDICTOR_REPORT = "adjusted_predictor_source_report.json"


@dataclass(frozen=True, slots=True)
class PredictorAcquisitionUnit:
    endpoint_session: date
    batch_index: int
    symbols: tuple[str, ...]
    plan_fingerprint: str
    unit_id: str


def _chunks(values: list[str], size: int) -> Iterable[tuple[str, ...]]:
    for index in range(0, len(values), size):
        yield tuple(values[index : index + size])


def _clean_symbol(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip()
    if not symbol or "," in symbol or any(char.isspace() for char in symbol):
        return None
    return symbol


def _rows_fingerprint(rows: Iterable[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(canonical_json(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _unit_id(
    *,
    endpoint_session: date,
    batch_index: int,
    symbols: tuple[str, ...],
    plan_fingerprint: str,
) -> str:
    payload = {
        "contract": MOMSEASON_ADJUSTED_PREDICTOR_SOURCE_CONTRACT,
        "plan_fingerprint": plan_fingerprint,
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


def extract_single_session_adjusted_closes(
    payload: object,
    *,
    requested_symbols: set[str],
    endpoint_session: date,
) -> tuple[dict[str, float], list[dict[str, object]]]:
    """Extract exact-literal daily closes and quarantine response anomalies."""

    observed: dict[str, float] = {}
    anomalies: list[dict[str, object]] = []
    if not isinstance(payload, dict):
        return observed, anomalies
    bars = payload.get("bars")
    if not isinstance(bars, dict):
        return observed, anomalies

    for raw_symbol, raw_values in bars.items():
        symbol = _clean_symbol(raw_symbol)
        if symbol is None:
            anomalies.append(
                {
                    "type": "INVALID_RESPONSE_SYMBOL",
                    "response_symbol": raw_symbol,
                }
            )
            continue
        if symbol not in requested_symbols:
            anomalies.append(
                {
                    "type": "UNSUBMITTED_RESPONSE_SYMBOL",
                    "response_symbol": symbol,
                }
            )
            continue
        if not isinstance(raw_values, list):
            anomalies.append(
                {
                    "type": "NON_LIST_BAR_COLLECTION",
                    "response_symbol": symbol,
                }
            )
            continue

        for item in raw_values:
            if not isinstance(item, dict):
                anomalies.append(
                    {
                        "type": "NON_OBJECT_BAR_ROW",
                        "response_symbol": symbol,
                    }
                )
                continue
            session = _parse_date(item.get("t"))
            if session != endpoint_session:
                anomalies.append(
                    {
                        "type": "OUTSIDE_ENDPOINT_SESSION",
                        "response_symbol": symbol,
                        "bar_session": session.isoformat() if session else None,
                    }
                )
                continue
            close = _finite_float(item.get("c"))
            if close is None or close <= 0:
                anomalies.append(
                    {
                        "type": "INVALID_CLOSE",
                        "response_symbol": symbol,
                        "bar_session": endpoint_session.isoformat(),
                    }
                )
                continue
            existing = observed.get(symbol)
            if existing is not None and not math.isclose(
                existing, close, rel_tol=0.0, abs_tol=0.0
            ):
                raise ValueError(
                    "conflicting Alpaca adjusted closes for "
                    f"{symbol} on {endpoint_session}: {existing} vs {close}"
                )
            observed[symbol] = close
    return observed, anomalies


def _write_parquet_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(path)
    frame = pd.DataFrame(rows)
    con = duckdb.connect(":memory:")
    try:
        con.register("endpoint_rows", frame)
        target = str(temp).replace("'", "''")
        con.execute(
            "COPY endpoint_rows TO '"
            + target
            + "' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        con.close()
    try:
        replace_with_retry(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


class MomSeasonAdjustedPredictorSource:
    """Materialize only PIT lag-predictor endpoints after total-return source acceptance.

    The acquisition date whitelist comes exclusively from ``required_lag_reference_dates``.
    Every Alpaca request is a one-session request with ``adjustment=all`` and the same
    historical session supplied as ``asof``. No formation-month target return is computed,
    no protected endpoint is requested, and no production/canonical/broker state is changed.
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
        self.raw_store = AlpacaRawPayloadStore(
            settings, namespace=ALPACA_RESEARCH_NAMESPACE
        )
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = (
            derived
            / MOMSEASON_SOURCE_ROOT_RELATIVE
            / "total_return_source"
            / MOMSEASON_ADJUSTED_PREDICTOR_ROOT_NAME
        )
        self.allowed_endpoint_sessions = frozenset(required_lag_reference_dates(self.calendar))
        if not self.allowed_endpoint_sessions:
            raise RuntimeError("LIT-01 required lag endpoint whitelist is empty")
        if max(self.allowed_endpoint_sessions) >= LITERATURE_MOMSEASON_PROTECTED_START:
            raise RuntimeError(
                "LIT-01 lag endpoint whitelist unexpectedly reaches protected window"
            )

    def plan_path(self) -> Path:
        return self.root / MOMSEASON_ADJUSTED_PREDICTOR_PLAN

    def plan_report_path(self) -> Path:
        return self.root / MOMSEASON_ADJUSTED_PREDICTOR_PLAN_REPORT

    def endpoint_parquet_path(self) -> Path:
        return self.root / MOMSEASON_ADJUSTED_PREDICTOR_ENDPOINTS

    def report_path(self) -> Path:
        return self.root / MOMSEASON_ADJUSTED_PREDICTOR_REPORT

    def unit_manifest_path(self, unit: PredictorAcquisitionUnit) -> Path:
        return (
            self.root
            / "units"
            / f"date={unit.endpoint_session.isoformat()}"
            / f"batch_{unit.batch_index:04d}.json"
        )

    def _formation_members(self, session: date) -> list[tuple[str, str, str]]:
        path = self.paths.universe_snapshot_file(session)
        if not path.is_file():
            raise RuntimeError(f"missing LIT-01 formation universe snapshot: {path}")
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                "SELECT instrument_id, ticker, CAST(identity_quality AS VARCHAR) "
                "FROM read_parquet(?) "
                "WHERE coalesce(discovery_eligible, FALSE) "
                "ORDER BY instrument_id",
                [str(path)],
            ).fetchall()
        finally:
            con.close()
        return [(str(row[0]), str(row[1]), str(row[2])) for row in rows]

    def _reference_maps(
        self,
    ) -> dict[date, dict[str, tuple[str, str]]]:
        maps: dict[date, dict[str, tuple[str, str]]] = {}
        for session in sorted(self.allowed_endpoint_sessions):
            path = self.source.reference_path(session)
            if not path.is_file():
                raise RuntimeError(
                    f"missing LIT-01 PIT historical reference snapshot: {path}"
                )
            mapping: dict[str, tuple[str, str]] = {}
            ambiguous: set[str] = set()
            for row in read_gzip_jsonl(path):
                instrument_id = str(row.get("instrument_id") or "")
                ticker = str(row.get("ticker") or "")
                quality = str(row.get("identity_quality") or "")
                if not instrument_id or not ticker:
                    continue
                value = (ticker, quality)
                if instrument_id in mapping and mapping[instrument_id] != value:
                    ambiguous.add(instrument_id)
                else:
                    mapping[instrument_id] = value
            for instrument_id in ambiguous:
                mapping.pop(instrument_id, None)
            maps[session] = mapping
        return maps

    def _row_endpoint_requirements(
        self,
        *,
        formation_month_start: date,
        instrument_id: str,
        hypothesis_lag_years: tuple[int, ...],
        refs: dict[date, dict[str, tuple[str, str]]],
    ) -> tuple[list[tuple[date, str, str]], str | None]:
        endpoints: list[tuple[date, str, str]] = []
        for years_back in hypothesis_lag_years:
            lag_month = same_month_years_back(formation_month_start, years_back)
            prior_end = month_sessions(self.calendar, previous_month(lag_month))[-1]
            current_end = month_sessions(self.calendar, lag_month)[-1]
            if prior_end not in self.allowed_endpoint_sessions or current_end not in self.allowed_endpoint_sessions:
                raise RuntimeError("LIT-01 predictor planner attempted a non-whitelisted session")
            prior_ref = refs[prior_end].get(instrument_id)
            current_ref = refs[current_end].get(instrument_id)
            if prior_ref is None or current_ref is None:
                return [], "historical_identity_unavailable"
            if prior_ref[0] != current_ref[0]:
                return [], "ticker_changed_inside_lag_month"
            ticker = prior_ref[0]
            endpoints.extend(
                (
                    (prior_end, instrument_id, ticker),
                    (current_end, instrument_id, ticker),
                )
            )
        return endpoints, None

    def build_plan(self, *, force: bool = False) -> dict[str, object]:
        if self.plan_path().is_file() and self.plan_report_path().is_file() and not force:
            rows = read_gzip_jsonl(self.plan_path())
            report = json.loads(self.plan_report_path().read_text(encoding="utf-8"))
            report["plan_rows"] = len(rows)
            report["skipped"] = True
            return report

        refs = self._reference_maps()
        plan: dict[tuple[date, str], dict[str, object]] = {}
        counters: dict[str, Counter[str]] = {
            hypothesis.hypothesis_id: Counter() for hypothesis in MOMSEASON_HYPOTHESES
        }
        monthly_eligible: dict[str, dict[str, int]] = {
            hypothesis.hypothesis_id: {} for hypothesis in MOMSEASON_HYPOTHESES
        }
        monthly_identity: dict[str, dict[str, int]] = {
            hypothesis.hypothesis_id: {} for hypothesis in MOMSEASON_HYPOTHESES
        }
        formation_instruments: set[str] = set()

        months = formation_months(self.calendar)
        for formation in months:
            month_key = formation.month_start.strftime("%Y-%m")
            members = self._formation_members(formation.first_session)
            for instrument_id, _formation_ticker, _quality in members:
                formation_instruments.add(instrument_id)

            for hypothesis in MOMSEASON_HYPOTHESES:
                counter = counters[hypothesis.hypothesis_id]
                counter["eligible_predictor_rows"] += len(members)
                monthly_eligible[hypothesis.hypothesis_id][month_key] = len(members)
                identity_count = 0
                for instrument_id, _formation_ticker, formation_quality in members:
                    if formation_quality.lower() == "fallback":
                        counter["formation_fallback_identity"] += 1
                        continue
                    endpoints, failure = self._row_endpoint_requirements(
                        formation_month_start=formation.month_start,
                        instrument_id=instrument_id,
                        hypothesis_lag_years=hypothesis.lag_years,
                        refs=refs,
                    )
                    if failure is not None:
                        counter[failure] += 1
                        continue
                    identity_count += 1
                    counter["identity_reconstructable_predictor_rows"] += 1
                    for endpoint_session, endpoint_instrument, ticker in endpoints:
                        key = (endpoint_session, endpoint_instrument)
                        existing = plan.get(key)
                        if existing is not None and existing["historical_ticker"] != ticker:
                            raise RuntimeError(
                                "conflicting historical ticker for one LIT-01 endpoint/instrument: "
                                f"{endpoint_session} {endpoint_instrument}"
                            )
                        plan[key] = {
                            "role": MOMSEASON_ADJUSTED_PREDICTOR_ROLE,
                            "endpoint_session": endpoint_session.isoformat(),
                            "instrument_id": endpoint_instrument,
                            "historical_ticker": ticker,
                        }
                monthly_identity[hypothesis.hypothesis_id][month_key] = identity_count

        rows = sorted(
            plan.values(),
            key=lambda row: (
                str(row["endpoint_session"]),
                str(row["instrument_id"]),
                str(row["historical_ticker"]),
            ),
        )
        for row in rows:
            endpoint = date.fromisoformat(str(row["endpoint_session"]))
            if endpoint not in self.allowed_endpoint_sessions:
                raise RuntimeError("persisted LIT-01 plan contains non-whitelisted endpoint")
        fingerprint = _rows_fingerprint(rows)
        session_counts = Counter(str(row["endpoint_session"]) for row in rows)
        report: dict[str, object] = {
            "contract_version": MOMSEASON_ADJUSTED_PREDICTOR_SOURCE_CONTRACT,
            "source_policy_fingerprint": literature_momseason_source_fingerprint(),
            "plan_fingerprint": fingerprint,
            "role": MOMSEASON_ADJUSTED_PREDICTOR_ROLE,
            "allowed_endpoint_sessions": len(self.allowed_endpoint_sessions),
            "first_endpoint_session": min(self.allowed_endpoint_sessions).isoformat(),
            "last_endpoint_session": max(self.allowed_endpoint_sessions).isoformat(),
            "plan_rows": len(rows),
            "formation_months": len(months),
            "formation_instruments": len(formation_instruments),
            "endpoint_rows_by_session": dict(sorted(session_counts.items())),
            "hypotheses": {
                hypothesis.hypothesis_id: {
                    **dict(counters[hypothesis.hypothesis_id]),
                    "monthly_eligible_predictor_rows": monthly_eligible[hypothesis.hypothesis_id],
                    "monthly_identity_reconstructable_predictor_rows": monthly_identity[
                        hypothesis.hypothesis_id
                    ],
                }
                for hypothesis in MOMSEASON_HYPOTHESES
            },
            "adjustment": MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
            "feed": MOMSEASON_ADJUSTED_PREDICTOR_FEED,
            "timeframe": MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
            "currency": MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
            "asof_rule": "endpoint_session",
            "single_session_request_only": True,
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
            raise RuntimeError("LIT-01 adjusted predictor endpoint plan is required")
        rows = read_gzip_jsonl(self.plan_path())
        report = json.loads(self.plan_report_path().read_text(encoding="utf-8"))
        fingerprint = _rows_fingerprint(rows)
        if fingerprint != report.get("plan_fingerprint"):
            raise RuntimeError("LIT-01 adjusted predictor endpoint plan fingerprint mismatch")
        return rows, report

    def build_units(self) -> list[PredictorAcquisitionUnit]:
        rows, report = self._load_plan()
        plan_fingerprint = str(report["plan_fingerprint"])
        by_session: dict[date, dict[str, str]] = defaultdict(dict)
        for row in rows:
            endpoint = date.fromisoformat(str(row["endpoint_session"]))
            if endpoint not in self.allowed_endpoint_sessions:
                raise RuntimeError("LIT-01 acquisition plan escaped endpoint whitelist")
            ticker = str(row["historical_ticker"])
            instrument_id = str(row["instrument_id"])
            existing = by_session[endpoint].get(ticker)
            if existing is not None and existing != instrument_id:
                raise RuntimeError(
                    "one historical ticker maps to multiple instruments on the same endpoint session: "
                    f"{endpoint} {ticker}"
                )
            by_session[endpoint][ticker] = instrument_id

        units: list[PredictorAcquisitionUnit] = []
        batch_size = int(self.alpaca.cfg.symbol_batch_size)
        for endpoint in sorted(by_session):
            symbols = sorted(by_session[endpoint])
            for batch_index, batch in enumerate(_chunks(symbols, batch_size)):
                units.append(
                    PredictorAcquisitionUnit(
                        endpoint_session=endpoint,
                        batch_index=batch_index,
                        symbols=batch,
                        plan_fingerprint=plan_fingerprint,
                        unit_id=_unit_id(
                            endpoint_session=endpoint,
                            batch_index=batch_index,
                            symbols=batch,
                            plan_fingerprint=plan_fingerprint,
                        ),
                    )
                )
        return units

    def _load_completed_manifest(
        self, unit: PredictorAcquisitionUnit
    ) -> dict[str, object] | None:
        path = self.unit_manifest_path(unit)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        compatible = (
            payload.get("contract_version") == MOMSEASON_ADJUSTED_PREDICTOR_SOURCE_CONTRACT
            and payload.get("unit_id") == unit.unit_id
            and payload.get("plan_fingerprint") == unit.plan_fingerprint
            and payload.get("status") == MOMSEASON_ADJUSTED_PREDICTOR_UNIT_STATUS
            and payload.get("endpoint_session") == unit.endpoint_session.isoformat()
            and payload.get("symbols") == list(unit.symbols)
            and payload.get("adjustment") == MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT
            and payload.get("feed") == MOMSEASON_ADJUSTED_PREDICTOR_FEED
            and payload.get("timeframe") == MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME
            and payload.get("currency") == MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY
            and payload.get("asof") == unit.endpoint_session.isoformat()
        )
        if not compatible:
            raise RuntimeError(f"stale or incompatible LIT-01 acquisition manifest: {path}")
        for record in payload.get("raw_pages") or []:
            if not isinstance(record, dict):
                raise RuntimeError(f"invalid raw-page evidence in LIT-01 manifest: {path}")
            payload_path = Path(str(record.get("payload_path") or ""))
            metadata_path = Path(str(record.get("metadata_path") or ""))
            if not payload_path.is_file() or not metadata_path.is_file():
                raise RuntimeError(f"missing raw provider evidence in LIT-01 manifest: {path}")
        for record in payload.get("provider_rejections") or []:
            if not isinstance(record, dict):
                raise RuntimeError(f"invalid rejection evidence in LIT-01 manifest: {path}")
            payload_path = Path(str(record.get("payload_path") or ""))
            metadata_path = Path(str(record.get("metadata_path") or ""))
            if not payload_path.is_file() or not metadata_path.is_file():
                raise RuntimeError(f"missing provider-rejection evidence in LIT-01 manifest: {path}")
        return payload

    def _acquire_unit(self, unit: PredictorAcquisitionUnit) -> dict[str, object]:
        requested = list(unit.symbols)
        remaining = list(requested)
        observed: dict[str, float] = {}
        source_hashes: dict[str, set[str]] = defaultdict(set)
        raw_pages: list[dict[str, object]] = []
        provider_rejections: dict[str, dict[str, object]] = {}
        response_anomalies: list[dict[str, object]] = []
        provider_calls = 0

        while remaining:
            pages_started = len(raw_pages)
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
                        category="predictor_endpoint_all",
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
                            "page_token_used": raw_record.page_token_used,
                            "next_page_token": raw_record.next_page_token,
                        }
                    )
                    page_observed, anomalies = extract_single_session_adjusted_closes(
                        page.payload,
                        requested_symbols=set(remaining),
                        endpoint_session=unit.endpoint_session,
                    )
                    for symbol, close in page_observed.items():
                        existing = observed.get(symbol)
                        if existing is not None and not math.isclose(
                            existing, close, rel_tol=0.0, abs_tol=0.0
                        ):
                            raise ValueError(
                                "conflicting paginated Alpaca endpoint close for "
                                f"{symbol} on {unit.endpoint_session}"
                            )
                        observed[symbol] = close
                        source_hashes[symbol].add(raw_record.sha256)
                    response_anomalies.extend(anomalies)
                break
            except AlpacaInvalidSymbolError as exc:
                provider_calls += 1
                if len(raw_pages) != pages_started:
                    raise RuntimeError(
                        "Alpaca rejected a LIT-01 symbol after successful pages had already "
                        "been returned; refusing partial-pagination retry"
                    ) from exc
                invalid = exc.symbol
                if invalid not in remaining:
                    raise RuntimeError(
                        f"Alpaca rejected symbol outside LIT-01 submitted batch: {invalid}"
                    ) from exc
                raw_record = self.raw_store.persist(
                    exc.page,
                    category="predictor_endpoint_rejections",
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
                remaining = [symbol for symbol in remaining if symbol != invalid]

        symbol_results: list[dict[str, object]] = []
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
            symbol_results.append(
                {
                    "symbol": symbol,
                    "availability_status": status,
                    "adjusted_close": close,
                    "source_page_sha256": sorted(source_hashes.get(symbol, set())),
                }
            )

        manifest: dict[str, object] = {
            "contract_version": MOMSEASON_ADJUSTED_PREDICTOR_SOURCE_CONTRACT,
            "unit_id": unit.unit_id,
            "plan_fingerprint": unit.plan_fingerprint,
            "status": MOMSEASON_ADJUSTED_PREDICTOR_UNIT_STATUS,
            "role": MOMSEASON_ADJUSTED_PREDICTOR_ROLE,
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
            "provider_rejections": [
                provider_rejections[symbol] for symbol in sorted(provider_rejections)
            ],
            "response_symbol_anomalies": response_anomalies,
            "symbol_results": symbol_results,
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
        atomic_write_text(path, canonical_json(manifest) + "\n")
        return manifest

    @staticmethod
    def _manifest_counts(payload: dict[str, object]) -> Counter[str]:
        counts: Counter[str] = Counter()
        for row in payload.get("symbol_results") or []:
            if isinstance(row, dict):
                counts[str(row.get("availability_status") or "UNKNOWN")] += 1
        return counts

    def acquire(self, *, force: bool = False) -> dict[str, object]:
        units = self.build_units()
        by_session: dict[date, list[PredictorAcquisitionUnit]] = defaultdict(list)
        for unit in units:
            by_session[unit.endpoint_session].append(unit)

        total_calls = 0
        executed_units = 0
        skipped_units = 0
        all_counts: Counter[str] = Counter()
        ordered_sessions = sorted(by_session)
        for session_index, endpoint in enumerate(ordered_sessions, start=1):
            date_counts: Counter[str] = Counter()
            date_executed = 0
            date_skipped = 0
            for unit in sorted(by_session[endpoint], key=lambda item: item.batch_index):
                existing = None if force else self._load_completed_manifest(unit)
                if existing is not None:
                    payload = existing
                    skipped_units += 1
                    date_skipped += 1
                else:
                    payload = self._acquire_unit(unit)
                    executed_units += 1
                    date_executed += 1
                    total_calls += int(payload.get("provider_calls_performed") or 0)
                counts = self._manifest_counts(payload)
                date_counts.update(counts)
                all_counts.update(counts)
            print(
                "LIT-01 adjusted endpoint acquisition: "
                f"{session_index}/{len(ordered_sessions)} date={endpoint.isoformat()} "
                f"symbols={sum(date_counts.values())} units={len(by_session[endpoint])} "
                f"executed={date_executed} skipped={date_skipped} "
                f"available={date_counts['AVAILABLE']} "
                f"rejected={date_counts['PROVIDER_REJECTED']} "
                f"zero_bar={date_counts['ZERO_BAR']}"
            )

        return {
            "contract_version": MOMSEASON_ADJUSTED_PREDICTOR_SOURCE_CONTRACT,
            "planned_units": len(units),
            "executed_units_this_run": executed_units,
            "skipped_units_this_run": skipped_units,
            "provider_calls_performed": total_calls,
            "availability_counts": dict(sorted(all_counts.items())),
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
        }

    def _all_manifests(
        self,
    ) -> tuple[list[PredictorAcquisitionUnit], list[dict[str, object]], int]:
        units = self.build_units()
        manifests: list[dict[str, object]] = []
        missing = 0
        for unit in units:
            payload = self._load_completed_manifest(unit)
            if payload is None:
                missing += 1
            else:
                manifests.append(payload)
        return units, manifests, missing

    def _materialize_endpoint_rows(
        self,
        plan_rows: list[dict[str, object]],
        manifests: list[dict[str, object]],
    ) -> tuple[list[dict[str, object]], Counter[str]]:
        result_by_key: dict[tuple[str, str], dict[str, object]] = {}
        for manifest in manifests:
            endpoint = str(manifest["endpoint_session"])
            for row in manifest.get("symbol_results") or []:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol") or "")
                key = (endpoint, symbol)
                if key in result_by_key and result_by_key[key] != row:
                    raise RuntimeError(
                        f"conflicting LIT-01 symbol result across manifests: {key}"
                    )
                result_by_key[key] = row

        rows: list[dict[str, object]] = []
        status_counts: Counter[str] = Counter()
        for plan in plan_rows:
            endpoint = str(plan["endpoint_session"])
            ticker = str(plan["historical_ticker"])
            source = result_by_key.get((endpoint, ticker))
            if source is None:
                status = "UNIT_NOT_MATERIALIZED"
                close = None
                source_hashes: list[str] = []
            else:
                status = str(source.get("availability_status") or "UNKNOWN")
                close = _finite_float(source.get("adjusted_close"))
                source_hashes = [
                    str(value)
                    for value in source.get("source_page_sha256") or []
                    if str(value)
                ]
            status_counts[status] += 1
            rows.append(
                {
                    "contract_version": MOMSEASON_ADJUSTED_PREDICTOR_SOURCE_CONTRACT,
                    "role": MOMSEASON_ADJUSTED_PREDICTOR_ROLE,
                    "endpoint_session": endpoint,
                    "instrument_id": str(plan["instrument_id"]),
                    "historical_ticker": ticker,
                    "availability_status": status,
                    "adjusted_close": close,
                    "price_currency": MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
                    "source_provider": "alpaca",
                    "source_adjustment": MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
                    "source_feed": MOMSEASON_ADJUSTED_PREDICTOR_FEED,
                    "source_timeframe": MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
                    "source_asof": endpoint,
                    "source_page_sha256_json": canonical_json(source_hashes),
                }
            )
        rows.sort(
            key=lambda row: (
                str(row["endpoint_session"]),
                str(row["instrument_id"]),
                str(row["historical_ticker"]),
            )
        )
        return rows, status_counts

    def _predictor_coverage(
        self,
        available_endpoint_keys: set[tuple[date, str]],
    ) -> dict[str, object]:
        refs = self._reference_maps()
        combined_eligible = 0
        combined_identity = 0
        combined_adjusted = 0
        eligible_instruments: set[str] = set()
        identity_instruments: set[str] = set()
        adjusted_instruments: set[str] = set()
        result: dict[str, object] = {}

        for hypothesis in MOMSEASON_HYPOTHESES:
            eligible = 0
            identity = 0
            adjusted = 0
            failure_counts: Counter[str] = Counter()
            monthly_eligible: dict[str, int] = {}
            monthly_identity: dict[str, int] = {}
            monthly_adjusted: dict[str, int] = {}
            for formation in formation_months(self.calendar):
                month_key = formation.month_start.strftime("%Y-%m")
                members = self._formation_members(formation.first_session)
                eligible += len(members)
                combined_eligible += len(members)
                monthly_eligible[month_key] = len(members)
                identity_month = 0
                adjusted_month = 0
                for instrument_id, _ticker, formation_quality in members:
                    eligible_instruments.add(instrument_id)
                    if formation_quality.lower() == "fallback":
                        failure_counts["formation_fallback_identity"] += 1
                        continue
                    endpoints, failure = self._row_endpoint_requirements(
                        formation_month_start=formation.month_start,
                        instrument_id=instrument_id,
                        hypothesis_lag_years=hypothesis.lag_years,
                        refs=refs,
                    )
                    if failure is not None:
                        failure_counts[failure] += 1
                        continue
                    identity += 1
                    combined_identity += 1
                    identity_month += 1
                    identity_instruments.add(instrument_id)
                    if all(
                        (endpoint_session, endpoint_instrument) in available_endpoint_keys
                        for endpoint_session, endpoint_instrument, _ticker in endpoints
                    ):
                        adjusted += 1
                        combined_adjusted += 1
                        adjusted_month += 1
                        adjusted_instruments.add(instrument_id)
                    else:
                        failure_counts["adjusted_endpoint_unavailable"] += 1
                monthly_identity[month_key] = identity_month
                monthly_adjusted[month_key] = adjusted_month
            result[hypothesis.hypothesis_id] = {
                "eligible_predictor_rows": eligible,
                "identity_reconstructable_predictor_rows": identity,
                "adjusted_endpoint_reconstructable_predictor_rows": adjusted,
                "identity_reconstructable_ratio": identity / eligible if eligible else None,
                "adjusted_reconstructable_ratio_of_eligible": (
                    adjusted / eligible if eligible else None
                ),
                "adjusted_reconstructable_ratio_of_identity": (
                    adjusted / identity if identity else None
                ),
                "failure_counts": dict(sorted(failure_counts.items())),
                "monthly_eligible_predictor_rows": monthly_eligible,
                "monthly_identity_reconstructable_predictor_rows": monthly_identity,
                "monthly_adjusted_endpoint_reconstructable_predictor_rows": monthly_adjusted,
            }

        population = assess_population_coverage(
            (
                PopulationCoverageStage(
                    name="eligible_literature_predictor_population",
                    rows=combined_eligible,
                    instruments=len(eligible_instruments),
                    scope=PopulationScope.FULL_ELIGIBLE_UNIVERSE,
                    complete_scope=True,
                    grain="formation_month_hypothesis_instrument",
                    source="PIT formation universe snapshots",
                ),
                PopulationCoverageStage(
                    name="stable_identity_predictor_population",
                    rows=combined_identity,
                    instruments=len(identity_instruments),
                    scope=PopulationScope.FILTERED_POPULATION,
                    complete_scope=True,
                    grain="formation_month_hypothesis_instrument",
                    source="Massive PIT historical references + ATLAS identity resolver",
                ),
                PopulationCoverageStage(
                    name="alpaca_adjusted_endpoint_population",
                    rows=combined_adjusted,
                    instruments=len(adjusted_instruments),
                    scope=PopulationScope.FILTERED_POPULATION,
                    complete_scope=True,
                    grain="formation_month_hypothesis_instrument",
                    source="Alpaca single-session adjustment=all daily endpoints",
                ),
            )
        )
        return {
            "hypotheses": result,
            "population_coverage": population.to_dict(),
        }

    def run(
        self,
        *,
        acquire: bool = False,
        force_plan: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        plan_report = self.build_plan(force=force_plan)
        acquisition = self.acquire(force=force_acquire) if acquire else None
        plan_rows, stored_plan_report = self._load_plan()
        units, manifests, missing_units = self._all_manifests()

        if missing_units:
            status = "ADJUSTED_PREDICTOR_SOURCE_ACQUISITION_REQUIRED"
            endpoint_rows: list[dict[str, object]] = []
            endpoint_status_counts: Counter[str] = Counter()
            coverage: dict[str, object] | None = None
        else:
            endpoint_rows, endpoint_status_counts = self._materialize_endpoint_rows(
                plan_rows, manifests
            )
            _write_parquet_rows(self.endpoint_parquet_path(), endpoint_rows)
            available_keys = {
                (date.fromisoformat(str(row["endpoint_session"])), str(row["instrument_id"]))
                for row in endpoint_rows
                if row.get("availability_status") == "AVAILABLE"
                and _finite_float(row.get("adjusted_close")) is not None
            }
            coverage = self._predictor_coverage(available_keys)
            population = coverage["population_coverage"]
            if not isinstance(population, dict) or not bool(population.get("valid_contract")):
                status = "ADJUSTED_PREDICTOR_SOURCE_POPULATION_CONTRACT_FAILURE"
            elif not bool(population.get("source_scope_proven")):
                status = "ADJUSTED_PREDICTOR_SOURCE_SCOPE_UNPROVEN"
            else:
                # The first complete target-machine acquisition is a source-capacity
                # census, not a post-hoc coverage PASS. Review its missingness pattern
                # before freezing any minimum coverage requirement.
                status = "ADJUSTED_PREDICTOR_SOURCE_CAPACITY_READY_FOR_REVIEW"

        total_provider_calls = (
            int(acquisition.get("provider_calls_performed") or 0)
            if isinstance(acquisition, dict)
            else 0
        )
        report: dict[str, object] = {
            "status": status,
            "contract_version": MOMSEASON_ADJUSTED_PREDICTOR_SOURCE_CONTRACT,
            "source_policy_fingerprint": literature_momseason_source_fingerprint(),
            "plan_fingerprint": stored_plan_report.get("plan_fingerprint"),
            "role": MOMSEASON_ADJUSTED_PREDICTOR_ROLE,
            "plan_rows": len(plan_rows),
            "planned_endpoint_sessions": len(self.allowed_endpoint_sessions),
            "planned_units": len(units),
            "completed_units": len(manifests),
            "missing_units": missing_units,
            "endpoint_status_counts": dict(sorted(endpoint_status_counts.items())),
            "endpoint_parquet_path": (
                str(self.endpoint_parquet_path()) if self.endpoint_parquet_path().is_file() else None
            ),
            "coverage": coverage,
            "plan_report": plan_report,
            "acquisition": acquisition,
            "request_semantics": {
                "start_equals_end_endpoint_session": True,
                "adjustment": MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
                "feed": MOMSEASON_ADJUSTED_PREDICTOR_FEED,
                "timeframe": MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
                "currency": MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
                "asof_rule": "endpoint_session",
                "date_whitelist_source": "required_lag_reference_dates",
            },
            "provider_calls_performed": total_provider_calls,
            "provider_writes_performed": 0,
            "existing_canonical_market_data_mutated": False,
            "global_alpaca_adjustment_config_mutated": False,
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
        return report


assert max(required_lag_reference_dates()) < LITERATURE_MOMSEASON_PROTECTED_START
