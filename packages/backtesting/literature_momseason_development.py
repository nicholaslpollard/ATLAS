from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping

import duckdb
import numpy as np

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_storage import AlpacaRawPayloadStore
from packages.providers.alpaca import AlpacaInvalidSymbolError, AlpacaMarketDataClient

from .literature_momseason_adjusted_predictor_source import (
    MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
    MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
    MOMSEASON_ADJUSTED_PREDICTOR_FEED,
    MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
    _chunks,
    _clean_symbol,
    _rows_fingerprint,
    _write_parquet_rows,
    extract_single_session_adjusted_closes,
)
from .literature_momseason_native_population import (
    MOMSEASON_NATIVE_POPULATION_CONTRACT,
    MOMSEASON_NATIVE_POPULATION_ROOT,
    MOMSEASON_NATIVE_REPORT,
    MomSeasonNativePopulationSource,
    _formula_defined,
)
from .literature_momseason_policy import (
    LITERATURE_MOMSEASON_PROTECTED_START,
    MOMSEASON_HYPOTHESES,
    formation_months,
    month_sessions,
    previous_month,
)
from .literature_momseason_research_freeze import (
    MOMSEASON_BOOTSTRAP_BLOCK_MONTHS,
    MOMSEASON_BOOTSTRAP_CONFIDENCE,
    MOMSEASON_BOOTSTRAP_REPLICATES,
    MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED,
    MOMSEASON_FAMILY_ALPHA,
    MOMSEASON_LONG_SHORT_QUANTILE,
    MOMSEASON_PRIMARY_COST_PER_LEG_BPS,
    MOMSEASON_RESEARCH_FREEZE_CONTRACT,
    MOMSEASON_RESEARCH_FREEZE_REPORT,
    MOMSEASON_RESEARCH_FREEZE_ROOT,
    MOMSEASON_RESEARCH_FREEZE_STATUS,
    MOMSEASON_ROBUSTNESS_FOLDS,
    MOMSEASON_STRESS_COST_PER_LEG_BPS,
    _circular_block_bootstrap_positive,
    _fold_means,
)
from .literature_momseason_source import (
    MOMSEASON_SOURCE_ROOT_RELATIVE,
    canonical_json,
    read_gzip_jsonl,
    write_gzip_jsonl,
)
from .literature_momseason_total_return_source import ALPACA_RESEARCH_NAMESPACE, _finite_float
from .phase26_research import holm_bonferroni


MOMSEASON_DEVELOPMENT_CONTRACT = (
    "literature-momseason-development-v1-frozen-native-ew-decile-turnover-holm-no-protected"
)
MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT = (
    "745ff247ecf9404f19aaf67450fdaf08fcec525e3a62c781f30a91662a901cfb"
)
MOMSEASON_DEVELOPMENT_ROOT = "development"
MOMSEASON_HOLDINGS_PLAN = "development_holdings.jsonl.gz"
MOMSEASON_TARGET_PLAN = "development_target_endpoint_plan.jsonl.gz"
MOMSEASON_PLAN_REPORT = "development_plan_report.json"
MOMSEASON_TARGET_ENDPOINTS = "development_target_endpoints.parquet"
MOMSEASON_DEVELOPMENT_REPORT = "development_research_report.json"
MOMSEASON_TARGET_UNIT_STATUS = "COMPLETE"

MOMSEASON_DEVELOPMENT_PLAN_READY = "LIT01_DEVELOPMENT_HOLDINGS_AND_TARGET_PLAN_READY"
MOMSEASON_DEVELOPMENT_TARGETS_REQUIRED = "LIT01_DEVELOPMENT_TARGET_ENDPOINTS_REQUIRED"
MOMSEASON_DEVELOPMENT_SOURCE_INCOMPLETE = "LIT01_DEVELOPMENT_TARGET_SOURCE_INCOMPLETE"
MOMSEASON_DEVELOPMENT_EVALUATED = "LIT01_DEVELOPMENT_EVALUATED"


@dataclass(frozen=True, slots=True)
class TargetAcquisitionUnit:
    endpoint_session: date
    batch_index: int
    symbols: tuple[str, ...]
    plan_fingerprint: str
    unit_id: str


def _fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _target_unit_id(
    *,
    endpoint_session: date,
    batch_index: int,
    symbols: tuple[str, ...],
    plan_fingerprint: str,
) -> str:
    return _fingerprint(
        {
            "contract": MOMSEASON_DEVELOPMENT_CONTRACT,
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
    )


def select_equal_weight_deciles(
    rows: Iterable[Mapping[str, object]],
    *,
    quantile: float = MOMSEASON_LONG_SHORT_QUANTILE,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    ordered = sorted(
        (dict(row) for row in rows),
        key=lambda row: (float(row["predictor_value"]), str(row["instrument_id"])),
    )
    if not ordered:
        raise ValueError("cannot form LIT-01 deciles from an empty population")
    leg_size = int(math.floor(len(ordered) * quantile))
    if leg_size <= 0 or leg_size * 2 >= len(ordered):
        raise ValueError("LIT-01 decile leg size is invalid for the cross-section")
    short_leg = ordered[:leg_size]
    long_leg = ordered[-leg_size:]
    if {str(row["instrument_id"]) for row in short_leg} & {
        str(row["instrument_id"]) for row in long_leg
    }:
        raise ValueError("LIT-01 long and short deciles overlap")
    return long_leg, short_leg


def one_way_turnover(
    previous_weights: Mapping[str, float] | None,
    current_weights: Mapping[str, float],
) -> float:
    if not current_weights:
        raise ValueError("current portfolio weights cannot be empty")
    current_total = float(sum(current_weights.values()))
    if not math.isclose(current_total, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("current portfolio weights must sum to one")
    if previous_weights is None:
        return 1.0
    previous_total = float(sum(previous_weights.values()))
    if not math.isclose(previous_total, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("previous portfolio weights must sum to one")
    keys = set(previous_weights) | set(current_weights)
    return 0.5 * sum(
        abs(float(current_weights.get(key, 0.0)) - float(previous_weights.get(key, 0.0)))
        for key in keys
    )


class MomSeasonDevelopmentResearch:
    """Build and evaluate the frozen native LIT-01 development experiment."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        alpaca_client: AlpacaMarketDataClient | None = None,
    ) -> None:
        self.settings = settings
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.alpaca = alpaca_client or AlpacaMarketDataClient(settings)
        self.native = MomSeasonNativePopulationSource(settings, alpaca_client=self.alpaca)
        self.raw_store = AlpacaRawPayloadStore(settings, namespace=ALPACA_RESEARCH_NAMESPACE)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.native_root = (
            derived
            / MOMSEASON_SOURCE_ROOT_RELATIVE
            / "total_return_source"
            / MOMSEASON_NATIVE_POPULATION_ROOT
        )
        self.freeze_root = self.native_root / MOMSEASON_RESEARCH_FREEZE_ROOT
        self.root = self.freeze_root / MOMSEASON_DEVELOPMENT_ROOT
        self.development_formations = tuple(
            item for item in formation_months(self.calendar) if item.scope == "DEVELOPMENT"
        )
        if len(self.development_formations) != MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED:
            raise RuntimeError("LIT-01 development month count changed after freeze")
        allowed: set[date] = set()
        for formation in self.development_formations:
            allowed.add(month_sessions(self.calendar, previous_month(formation.month_start))[-1])
            allowed.add(formation.last_session)
        self.allowed_target_sessions = frozenset(allowed)
        if not self.allowed_target_sessions:
            raise RuntimeError("LIT-01 development target whitelist is empty")
        if max(self.allowed_target_sessions) >= LITERATURE_MOMSEASON_PROTECTED_START:
            raise RuntimeError("LIT-01 development target whitelist reaches protected dates")

    def freeze_report_path(self) -> Path:
        return self.freeze_root / MOMSEASON_RESEARCH_FREEZE_REPORT

    def native_report_path(self) -> Path:
        return self.native_root / MOMSEASON_NATIVE_REPORT

    def holdings_path(self) -> Path:
        return self.root / MOMSEASON_HOLDINGS_PLAN

    def target_plan_path(self) -> Path:
        return self.root / MOMSEASON_TARGET_PLAN

    def plan_report_path(self) -> Path:
        return self.root / MOMSEASON_PLAN_REPORT

    def target_endpoint_path(self) -> Path:
        return self.root / MOMSEASON_TARGET_ENDPOINTS

    def report_path(self) -> Path:
        return self.root / MOMSEASON_DEVELOPMENT_REPORT

    def unit_manifest_path(self, unit: TargetAcquisitionUnit) -> Path:
        return self.root / "target_units" / f"date={unit.endpoint_session.isoformat()}" / f"batch_{unit.batch_index:04d}.json"

    def _require_freeze(self) -> dict[str, object]:
        path = self.freeze_report_path()
        if not path.is_file():
            raise RuntimeError(f"LIT-01 research freeze is required: {path}")
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("status") != MOMSEASON_RESEARCH_FREEZE_STATUS:
            raise RuntimeError("LIT-01 research freeze status is not ready")
        if report.get("contract_version") != MOMSEASON_RESEARCH_FREEZE_CONTRACT:
            raise RuntimeError("LIT-01 research freeze contract mismatch")
        if report.get("freeze_fingerprint") != MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT:
            raise RuntimeError("LIT-01 research freeze fingerprint differs from the accepted target-machine freeze")
        zero_fields = (
            "development_outcome_rows_read",
            "target_outcome_rows_read",
            "protected_return_rows_read",
            "provider_reads_performed",
            "broker_reads_performed",
            "broker_writes_performed",
            "order_writes_performed",
            "paper_submits_performed",
            "live_writes_performed",
        )
        for field in zero_fields:
            if int(report.get(field) or 0) != 0:
                raise RuntimeError(f"LIT-01 freeze safety field is nonzero: {field}")
        if bool(report.get("protected_holdout_consumed")):
            raise RuntimeError("LIT-01 protected holdout was consumed before development")
        return report

    def _require_native_report(self) -> dict[str, object]:
        path = self.native_report_path()
        if not path.is_file():
            raise RuntimeError(f"LIT-01 native report is required: {path}")
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("status") != "NATIVE_POPULATION_SOURCE_CAPACITY_READY_FOR_REVIEW":
            raise RuntimeError("LIT-01 native source report is not capacity-ready")
        if report.get("contract_version") != MOMSEASON_NATIVE_POPULATION_CONTRACT:
            raise RuntimeError("LIT-01 native source report contract mismatch")
        if int(report.get("protected_return_rows_read") or 0) != 0:
            raise RuntimeError("LIT-01 native report has protected reads")
        if bool(report.get("protected_holdout_consumed")):
            raise RuntimeError("LIT-01 native report consumed the protected holdout")
        return report

    def _lag_endpoint_map(self) -> dict[tuple[date, str], dict[str, object]]:
        path = self.native.endpoint_path()
        if not path.is_file():
            raise RuntimeError(f"LIT-01 native adjusted endpoint file is required: {path}")
        con = duckdb.connect(":memory:")
        try:
            cursor = con.execute(
                "SELECT endpoint_session, instrument_id, historical_ticker, availability_status, adjusted_close "
                "FROM read_parquet(?) ORDER BY endpoint_session, instrument_id",
                [str(path)],
            )
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            con.close()
        result: dict[tuple[date, str], dict[str, object]] = {}
        for row in rows:
            endpoint = date.fromisoformat(str(row["endpoint_session"]))
            key = (endpoint, str(row["instrument_id"]))
            if key in result:
                raise RuntimeError(f"duplicate LIT-01 lag endpoint row: {key}")
            result[key] = row
        return result

    def _historical_ticker_for_target(
        self,
        *,
        endpoint_session: date,
        instrument_id: str,
        formation_ticker: str,
        historical: Mapping[date, Mapping[str, list[dict[str, object]]]],
    ) -> str:
        if endpoint_session in historical:
            rows = historical[endpoint_session].get(instrument_id, [])
            clean = sorted(
                {
                    str(row.get("ticker") or "").strip()
                    for row in rows
                    if str(row.get("ticker") or "").strip()
                    and str(row.get("identity_quality") or "").strip().lower() in {"strong", "medium"}
                }
            )
            if len(clean) == 1:
                return clean[0]
            if len(clean) > 1:
                raise RuntimeError(
                    "ambiguous PIT ticker for development target endpoint: "
                    f"{endpoint_session} {instrument_id}"
                )
        ticker = _clean_symbol(formation_ticker)
        if ticker is None:
            raise RuntimeError(f"invalid formation ticker for development target endpoint: {instrument_id}")
        return ticker

    def build_plan(self, *, force: bool = False) -> dict[str, object]:
        self._require_freeze()
        native_report = self._require_native_report()
        if self.holdings_path().is_file() and self.target_plan_path().is_file() and self.plan_report_path().is_file() and not force:
            holdings = read_gzip_jsonl(self.holdings_path())
            targets = read_gzip_jsonl(self.target_plan_path())
            report = json.loads(self.plan_report_path().read_text(encoding="utf-8"))
            if _rows_fingerprint(holdings) != report.get("holdings_fingerprint"):
                raise RuntimeError("LIT-01 development holdings fingerprint mismatch")
            if _rows_fingerprint(targets) != report.get("target_plan_fingerprint"):
                raise RuntimeError("LIT-01 development target plan fingerprint mismatch")
            report["skipped"] = True
            return report

        lag_endpoints = self._lag_endpoint_map()
        historical = self.native._historical_groups()
        holdings: list[dict[str, object]] = []
        target_plan: dict[tuple[date, str], dict[str, object]] = {}
        monthly_counts: dict[str, dict[str, dict[str, int]]] = {
            hypothesis.hypothesis_id: {} for hypothesis in MOMSEASON_HYPOTHESES
        }
        lag_count_distributions: dict[str, Counter[int]] = {
            hypothesis.hypothesis_id: Counter() for hypothesis in MOMSEASON_HYPOTHESES
        }

        for formation in self.development_formations:
            month_key = formation.month_start.strftime("%Y-%m")
            members, _formation_counts = self.native._native_formation_members(formation.first_session)
            member_map = {str(row["instrument_id"]): row for row in members}
            for hypothesis in MOMSEASON_HYPOTHESES:
                candidates: list[dict[str, object]] = []
                for instrument_id, member in member_map.items():
                    if member["formation_status"] != "OK":
                        continue
                    lag_returns: list[float] = []
                    for years_back in hypothesis.lag_years:
                        lag, status = self.native._valid_lag(
                            formation_month_start=formation.month_start,
                            instrument_id=instrument_id,
                            years_back=years_back,
                            historical=historical,
                        )
                        if lag is None or status != "OK":
                            continue
                        prior = lag_endpoints.get((lag["prior_end"], instrument_id))
                        current = lag_endpoints.get((lag["current_end"], instrument_id))
                        if prior is None or current is None:
                            continue
                        if prior.get("availability_status") != "AVAILABLE" or current.get("availability_status") != "AVAILABLE":
                            continue
                        prior_close = _finite_float(prior.get("adjusted_close"))
                        current_close = _finite_float(current.get("adjusted_close"))
                        if prior_close is None or current_close is None or prior_close <= 0.0 or current_close <= 0.0:
                            continue
                        lag_returns.append(current_close / prior_close - 1.0)
                    if not _formula_defined(hypothesis.hypothesis_id, len(lag_returns)):
                        continue
                    predictor = float(np.mean(np.asarray(lag_returns, dtype=np.float64)))
                    lag_count_distributions[hypothesis.hypothesis_id][len(lag_returns)] += 1
                    candidates.append(
                        {
                            "instrument_id": instrument_id,
                            "formation_ticker": str(member["formation_ticker"]),
                            "predictor_value": predictor,
                            "valid_lag_count": len(lag_returns),
                        }
                    )

                long_leg, short_leg = select_equal_weight_deciles(candidates)
                leg_size = len(long_leg)
                prior_target = month_sessions(self.calendar, previous_month(formation.month_start))[-1]
                current_target = formation.last_session
                if prior_target not in self.allowed_target_sessions or current_target not in self.allowed_target_sessions:
                    raise RuntimeError("LIT-01 target plan escaped development whitelist")

                for side, leg_rows in (("LONG", long_leg), ("SHORT", short_leg)):
                    for rank_index, row in enumerate(leg_rows, start=1):
                        instrument_id = str(row["instrument_id"])
                        formation_ticker = str(row["formation_ticker"])
                        holdings.append(
                            {
                                "contract_version": MOMSEASON_DEVELOPMENT_CONTRACT,
                                "freeze_fingerprint": MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT,
                                "target_month": month_key,
                                "hypothesis_id": hypothesis.hypothesis_id,
                                "side": side,
                                "instrument_id": instrument_id,
                                "formation_ticker": formation_ticker,
                                "predictor_value": float(row["predictor_value"]),
                                "valid_lag_count": int(row["valid_lag_count"]),
                                "leg_rank": rank_index,
                                "leg_size": leg_size,
                                "equal_weight": 1.0 / leg_size,
                                "prior_endpoint_session": prior_target.isoformat(),
                                "target_endpoint_session": current_target.isoformat(),
                            }
                        )
                        for endpoint_session in (prior_target, current_target):
                            ticker = self._historical_ticker_for_target(
                                endpoint_session=endpoint_session,
                                instrument_id=instrument_id,
                                formation_ticker=formation_ticker,
                                historical=historical,
                            )
                            key = (endpoint_session, instrument_id)
                            existing = target_plan.get(key)
                            if existing is not None and str(existing["historical_ticker"]) != ticker:
                                raise RuntimeError(
                                    "conflicting development target ticker for endpoint/instrument: "
                                    f"{endpoint_session} {instrument_id}"
                                )
                            target_plan[key] = {
                                "role": "LIT01_DEVELOPMENT_TARGET_ENDPOINT",
                                "endpoint_session": endpoint_session.isoformat(),
                                "instrument_id": instrument_id,
                                "historical_ticker": ticker,
                            }

                monthly_counts[hypothesis.hypothesis_id][month_key] = {
                    "predictor_defined": len(candidates),
                    "long_holdings": len(long_leg),
                    "short_holdings": len(short_leg),
                }

        holdings.sort(
            key=lambda row: (
                str(row["target_month"]),
                str(row["hypothesis_id"]),
                str(row["side"]),
                int(row["leg_rank"]),
                str(row["instrument_id"]),
            )
        )
        target_rows = sorted(
            target_plan.values(),
            key=lambda row: (str(row["endpoint_session"]), str(row["instrument_id"]), str(row["historical_ticker"])),
        )
        holdings_fingerprint = _rows_fingerprint(holdings)
        target_fingerprint = _rows_fingerprint(target_rows)
        native_plan = native_report.get("native_plan") or {}
        report = {
            "status": MOMSEASON_DEVELOPMENT_PLAN_READY,
            "contract_version": MOMSEASON_DEVELOPMENT_CONTRACT,
            "freeze_fingerprint": MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT,
            "native_plan_fingerprint": str(native_plan.get("plan_fingerprint") or ""),
            "development_month_count": len(self.development_formations),
            "development_month_start": self.development_formations[0].month_start.strftime("%Y-%m"),
            "development_month_end": self.development_formations[-1].month_start.strftime("%Y-%m"),
            "decile_implementation": {
                "sort": "predictor_value ascending, then stable instrument_id",
                "leg_size": "floor(eligible_predictor_rows * 0.10)",
                "tie_rule": "stable instrument_id breaks exact predictor ties",
                "weighting": "equal weight within each leg",
                "future_outcome_availability_used_for_selection": False,
            },
            "holdings_rows": len(holdings),
            "holdings_fingerprint": holdings_fingerprint,
            "target_plan_rows": len(target_rows),
            "target_plan_fingerprint": target_fingerprint,
            "allowed_target_sessions": len(self.allowed_target_sessions),
            "first_target_session": min(self.allowed_target_sessions).isoformat(),
            "last_target_session": max(self.allowed_target_sessions).isoformat(),
            "monthly_counts": monthly_counts,
            "valid_lag_count_distributions": {
                key: {str(k): v for k, v in sorted(value.items())}
                for key, value in sorted(lag_count_distributions.items())
            },
            "development_outcome_rows_read": 0,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "skipped": False,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        write_gzip_jsonl(self.holdings_path(), holdings)
        write_gzip_jsonl(self.target_plan_path(), target_rows)
        atomic_write_text(self.plan_report_path(), canonical_json(report) + "\n")
        return report

    def _load_target_plan(self) -> tuple[list[dict[str, object]], dict[str, object]]:
        if not self.target_plan_path().is_file() or not self.plan_report_path().is_file():
            raise RuntimeError("LIT-01 development target plan is required")
        rows = read_gzip_jsonl(self.target_plan_path())
        report = json.loads(self.plan_report_path().read_text(encoding="utf-8"))
        if _rows_fingerprint(rows) != report.get("target_plan_fingerprint"):
            raise RuntimeError("LIT-01 development target plan fingerprint mismatch")
        return rows, report

    def build_units(self) -> list[TargetAcquisitionUnit]:
        rows, report = self._load_target_plan()
        fingerprint = str(report["target_plan_fingerprint"])
        by_session: dict[date, dict[str, str]] = defaultdict(dict)
        for row in rows:
            endpoint = date.fromisoformat(str(row["endpoint_session"]))
            if endpoint not in self.allowed_target_sessions:
                raise RuntimeError("LIT-01 development acquisition escaped target whitelist")
            ticker = str(row["historical_ticker"])
            instrument_id = str(row["instrument_id"])
            existing = by_session[endpoint].get(ticker)
            if existing is not None and existing != instrument_id:
                raise RuntimeError(
                    "one target ticker maps to multiple instruments on one endpoint: "
                    f"{endpoint} {ticker}"
                )
            by_session[endpoint][ticker] = instrument_id

        units: list[TargetAcquisitionUnit] = []
        batch_size = int(self.alpaca.cfg.symbol_batch_size)
        for endpoint in sorted(by_session):
            symbols = sorted(by_session[endpoint])
            for batch_index, batch in enumerate(_chunks(symbols, batch_size)):
                units.append(
                    TargetAcquisitionUnit(
                        endpoint_session=endpoint,
                        batch_index=batch_index,
                        symbols=batch,
                        plan_fingerprint=fingerprint,
                        unit_id=_target_unit_id(
                            endpoint_session=endpoint,
                            batch_index=batch_index,
                            symbols=batch,
                            plan_fingerprint=fingerprint,
                        ),
                    )
                )
        return units

    def _load_completed_manifest(self, unit: TargetAcquisitionUnit) -> dict[str, object] | None:
        path = self.unit_manifest_path(unit)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        compatible = (
            payload.get("contract_version") == MOMSEASON_DEVELOPMENT_CONTRACT
            and payload.get("unit_id") == unit.unit_id
            and payload.get("plan_fingerprint") == unit.plan_fingerprint
            and payload.get("status") == MOMSEASON_TARGET_UNIT_STATUS
            and payload.get("endpoint_session") == unit.endpoint_session.isoformat()
            and payload.get("symbols") == list(unit.symbols)
            and payload.get("adjustment") == MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT
            and payload.get("feed") == MOMSEASON_ADJUSTED_PREDICTOR_FEED
            and payload.get("timeframe") == MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME
            and payload.get("currency") == MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY
            and payload.get("asof") == unit.endpoint_session.isoformat()
        )
        if not compatible:
            raise RuntimeError(f"stale LIT-01 development target manifest: {path}")
        return payload

    def _acquire_unit(self, unit: TargetAcquisitionUnit) -> dict[str, object]:
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
                        category="development_target_endpoint_all",
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
                    page_observed, anomalies = extract_single_session_adjusted_closes(
                        page.payload,
                        requested_symbols=set(remaining),
                        endpoint_session=unit.endpoint_session,
                    )
                    for symbol, close in page_observed.items():
                        existing = observed.get(symbol)
                        if existing is not None and not math.isclose(existing, close, rel_tol=0.0, abs_tol=0.0):
                            raise RuntimeError(
                                "conflicting paginated LIT-01 target close for "
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
                        "Alpaca rejected a LIT-01 target symbol after successful pages; "
                        "refusing partial-pagination retry"
                    ) from exc
                invalid = exc.symbol
                if invalid not in remaining:
                    raise RuntimeError(f"Alpaca rejected an unsubmitted LIT-01 target symbol: {invalid}") from exc
                raw_record = self.raw_store.persist(
                    exc.page,
                    category="development_target_endpoint_rejections",
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

        manifest = {
            "contract_version": MOMSEASON_DEVELOPMENT_CONTRACT,
            "unit_id": unit.unit_id,
            "plan_fingerprint": unit.plan_fingerprint,
            "status": MOMSEASON_TARGET_UNIT_STATUS,
            "role": "LIT01_DEVELOPMENT_TARGET_ENDPOINT",
            "endpoint_session": unit.endpoint_session.isoformat(),
            "batch_index": unit.batch_index,
            "symbols": list(unit.symbols),
            "adjustment": MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
            "feed": MOMSEASON_ADJUSTED_PREDICTOR_FEED,
            "timeframe": MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
            "currency": MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
            "asof": unit.endpoint_session.isoformat(),
            "raw_pages": raw_pages,
            "provider_rejections": [provider_rejections[key] for key in sorted(provider_rejections)],
            "response_anomalies": response_anomalies,
            "symbol_results": symbol_results,
            "provider_calls_performed": provider_calls,
        }
        path = self.unit_manifest_path(unit)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, canonical_json(manifest) + "\n")
        return manifest

    def acquire_targets(self, *, force: bool = False) -> dict[str, object]:
        self._require_freeze()
        units = self.build_units()
        availability: Counter[str] = Counter()
        executed = 0
        skipped = 0
        calls = 0
        for unit in units:
            manifest = None if force else self._load_completed_manifest(unit)
            if manifest is None:
                manifest = self._acquire_unit(unit)
                executed += 1
                calls += int(manifest.get("provider_calls_performed") or 0)
            else:
                skipped += 1
            for row in manifest.get("symbol_results") or []:
                if isinstance(row, Mapping):
                    availability[str(row.get("availability_status") or "UNKNOWN")] += 1
        return {
            "planned_units": len(units),
            "executed_units_this_run": executed,
            "skipped_units_this_run": skipped,
            "provider_calls_performed_this_run": calls,
            "availability_counts": dict(sorted(availability.items())),
        }

    def _materialize_target_endpoints(self) -> tuple[dict[tuple[date, str], dict[str, object]], Counter[str], int]:
        plan_rows, _ = self._load_target_plan()
        units = self.build_units()
        results: dict[tuple[date, str], dict[str, object]] = {}
        missing_units = 0
        for unit in units:
            manifest = self._load_completed_manifest(unit)
            if manifest is None:
                missing_units += 1
                continue
            for row in manifest.get("symbol_results") or []:
                if isinstance(row, Mapping):
                    results[(unit.endpoint_session, str(row["symbol"]))] = dict(row)

        rows: list[dict[str, object]] = []
        endpoint_map: dict[tuple[date, str], dict[str, object]] = {}
        counts: Counter[str] = Counter()
        for plan in plan_rows:
            endpoint = date.fromisoformat(str(plan["endpoint_session"]))
            instrument_id = str(plan["instrument_id"])
            ticker = str(plan["historical_ticker"])
            source = results.get((endpoint, ticker))
            if source is None:
                status = "TARGET_UNIT_NOT_MATERIALIZED"
                close = None
                hashes: list[str] = []
            else:
                status = str(source.get("availability_status") or "UNKNOWN")
                close = _finite_float(source.get("adjusted_close"))
                hashes = [str(value) for value in source.get("source_page_sha256") or []]
            counts[status] += 1
            materialized = {
                "contract_version": MOMSEASON_DEVELOPMENT_CONTRACT,
                "role": "LIT01_DEVELOPMENT_TARGET_ENDPOINT",
                "endpoint_session": endpoint.isoformat(),
                "instrument_id": instrument_id,
                "historical_ticker": ticker,
                "availability_status": status,
                "adjusted_close": close,
                "price_currency": MOMSEASON_ADJUSTED_PREDICTOR_CURRENCY,
                "source_provider": "alpaca",
                "source_adjustment": MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
                "source_feed": MOMSEASON_ADJUSTED_PREDICTOR_FEED,
                "source_timeframe": MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
                "source_asof": endpoint.isoformat(),
                "source_page_sha256_json": canonical_json(hashes),
            }
            rows.append(materialized)
            endpoint_map[(endpoint, instrument_id)] = materialized
        rows.sort(key=lambda row: (str(row["endpoint_session"]), str(row["instrument_id"])))
        if missing_units == 0:
            _write_parquet_rows(self.target_endpoint_path(), rows)
        return endpoint_map, counts, missing_units

    def _evaluate(self, endpoint_map: Mapping[tuple[date, str], Mapping[str, object]]) -> dict[str, object]:
        holdings = read_gzip_jsonl(self.holdings_path())
        by_hyp_month: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(lambda: defaultdict(list))
        complete_holding_returns = 0
        unavailable_holdings = 0
        for row in holdings:
            prior_date = date.fromisoformat(str(row["prior_endpoint_session"]))
            target_date = date.fromisoformat(str(row["target_endpoint_session"]))
            instrument_id = str(row["instrument_id"])
            prior = endpoint_map.get((prior_date, instrument_id))
            target = endpoint_map.get((target_date, instrument_id))
            outcome: float | None = None
            if prior is not None and target is not None and prior.get("availability_status") == "AVAILABLE" and target.get("availability_status") == "AVAILABLE":
                prior_close = _finite_float(prior.get("adjusted_close"))
                target_close = _finite_float(target.get("adjusted_close"))
                if prior_close is not None and target_close is not None and prior_close > 0.0 and target_close > 0.0:
                    outcome = target_close / prior_close - 1.0
            enriched = dict(row)
            enriched["target_return"] = outcome
            if outcome is None:
                unavailable_holdings += 1
            else:
                complete_holding_returns += 1
            by_hyp_month[str(row["hypothesis_id"])][str(row["target_month"])].append(enriched)

        monthly_by_hyp: dict[str, list[dict[str, object]]] = {}
        source_complete = True
        for hypothesis in MOMSEASON_HYPOTHESES:
            hypothesis_id = hypothesis.hypothesis_id
            previous_weights: dict[str, Mapping[str, float] | None] = {"LONG": None, "SHORT": None}
            monthly_rows: list[dict[str, object]] = []
            for formation in self.development_formations:
                month_key = formation.month_start.strftime("%Y-%m")
                rows = by_hyp_month[hypothesis_id].get(month_key, [])
                sides = {side: [row for row in rows if row["side"] == side] for side in ("LONG", "SHORT")}
                month_complete = bool(rows) and all(row.get("target_return") is not None for row in rows)
                if not month_complete:
                    source_complete = False
                    monthly_rows.append({"target_month": month_key, "complete": False, "holding_rows": len(rows)})
                    continue

                gross_leg: dict[str, float] = {}
                turnover: dict[str, float] = {}
                for side in ("LONG", "SHORT"):
                    leg = sides[side]
                    if not leg:
                        raise RuntimeError(f"LIT-01 {hypothesis_id} {month_key} has an empty {side} leg")
                    weights = {str(row["instrument_id"]): float(row["equal_weight"]) for row in leg}
                    gross_leg[side] = float(np.mean(np.asarray([float(row["target_return"]) for row in leg], dtype=np.float64)))
                    turnover[side] = one_way_turnover(previous_weights[side], weights)
                    previous_weights[side] = weights

                gross_spread = gross_leg["LONG"] - gross_leg["SHORT"]
                total_turnover = turnover["LONG"] + turnover["SHORT"]
                primary = gross_spread - (MOMSEASON_PRIMARY_COST_PER_LEG_BPS / 10_000.0) * total_turnover
                stress = gross_spread - (MOMSEASON_STRESS_COST_PER_LEG_BPS / 10_000.0) * total_turnover
                monthly_rows.append(
                    {
                        "target_month": month_key,
                        "complete": True,
                        "holding_rows": len(rows),
                        "gross_long_return": gross_leg["LONG"],
                        "gross_short_return": gross_leg["SHORT"],
                        "gross_long_short_return": gross_spread,
                        "long_one_way_turnover": turnover["LONG"],
                        "short_one_way_turnover": turnover["SHORT"],
                        "total_one_way_turnover": total_turnover,
                        "primary_after_cost_return": primary,
                        "stress_after_cost_return": stress,
                    }
                )
            monthly_by_hyp[hypothesis_id] = monthly_rows

        if not source_complete:
            return {
                "source_complete": False,
                "complete_holding_returns": complete_holding_returns,
                "unavailable_holding_returns": unavailable_holdings,
                "hypotheses": {key: {"monthly": value} for key, value in sorted(monthly_by_hyp.items())},
            }

        provisional: dict[str, dict[str, object]] = {}
        for hypothesis in MOMSEASON_HYPOTHESES:
            hypothesis_id = hypothesis.hypothesis_id
            monthly = monthly_by_hyp[hypothesis_id]
            if len(monthly) != MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED:
                raise RuntimeError("LIT-01 development monthly vector length changed")
            primary = np.asarray([float(row["primary_after_cost_return"]) for row in monthly], dtype=np.float64)
            stress = np.asarray([float(row["stress_after_cost_return"]) for row in monthly], dtype=np.float64)
            gross = np.asarray([float(row["gross_long_short_return"]) for row in monthly], dtype=np.float64)
            mean, lcb, p_value = _circular_block_bootstrap_positive(
                primary,
                label=f"development:{MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT}:{hypothesis_id}",
            )
            folds = _fold_means(primary)
            month_of_year: dict[str, float] = {}
            for month_number in range(1, 13):
                values = [
                    float(row["primary_after_cost_return"])
                    for row in monthly
                    if int(str(row["target_month"])[5:7]) == month_number
                ]
                if values:
                    month_of_year[f"{month_number:02d}"] = float(np.mean(values))
            provisional[hypothesis_id] = {
                "monthly": monthly,
                "gross_mean": float(gross.mean()),
                "primary_mean": mean,
                "primary_lcb": lcb,
                "primary_p_value": p_value,
                "stress_mean": float(stress.mean()),
                "fold_means": list(folds),
                "positive_folds": sum(value > 0.0 for value in folds),
                "month_of_year_primary_means": month_of_year,
            }

        holm = holm_bonferroni(
            {hypothesis_id: float(item["primary_p_value"]) for hypothesis_id, item in provisional.items()},
            alpha=MOMSEASON_FAMILY_ALPHA,
        )
        hypothesis_results: dict[str, object] = {}
        finalists: list[str] = []
        for hypothesis in MOMSEASON_HYPOTHESES:
            hypothesis_id = hypothesis.hypothesis_id
            item = provisional[hypothesis_id]
            correction = holm[hypothesis_id]
            checks = {
                "primary_mean_positive": float(item["primary_mean"]) > 0.0,
                "primary_lcb_positive": float(item["primary_lcb"]) > 0.0,
                "holm_rejected_null": bool(correction["rejected_null"]),
                "stress_mean_positive": float(item["stress_mean"]) > 0.0,
            }
            passed = all(checks.values())
            if passed:
                finalists.append(hypothesis_id)
            hypothesis_results[hypothesis_id] = {
                **item,
                "holm_threshold": float(correction["threshold"]),
                "holm_rejected_null": bool(correction["rejected_null"]),
                "checks": checks,
                "passed_all_primary_checks": passed,
            }

        return {
            "source_complete": True,
            "complete_holding_returns": complete_holding_returns,
            "unavailable_holding_returns": unavailable_holdings,
            "family_finalist": bool(finalists),
            "finalist_hypotheses": finalists,
            "hypotheses": hypothesis_results,
            "inference_contract": {
                "independent_unit": "target_calendar_month_long_short_portfolio_return",
                "months": MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED,
                "bootstrap_type": "circular_block_bootstrap",
                "bootstrap_block_months": MOMSEASON_BOOTSTRAP_BLOCK_MONTHS,
                "bootstrap_replicates": MOMSEASON_BOOTSTRAP_REPLICATES,
                "bootstrap_confidence": MOMSEASON_BOOTSTRAP_CONFIDENCE,
                "family_alpha": MOMSEASON_FAMILY_ALPHA,
                "multiple_testing": "HOLM_BONFERRONI_FIXED_TWO_HYPOTHESES",
                "robustness_folds": MOMSEASON_ROBUSTNESS_FOLDS,
            },
        }

    def run(
        self,
        *,
        acquire: bool = False,
        force_plan: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        plan_report = self.build_plan(force=force_plan)
        acquisition = self.acquire_targets(force=force_acquire) if acquire else None
        endpoint_map, endpoint_counts, missing_units = self._materialize_target_endpoints()

        if missing_units:
            status = MOMSEASON_DEVELOPMENT_TARGETS_REQUIRED
            evaluation = None
        else:
            evaluation = self._evaluate(endpoint_map)
            status = (
                MOMSEASON_DEVELOPMENT_EVALUATED
                if bool(evaluation["source_complete"])
                else MOMSEASON_DEVELOPMENT_SOURCE_INCOMPLETE
            )

        development_rows = 0 if evaluation is None else int(evaluation.get("complete_holding_returns") or 0)
        report = {
            "status": status,
            "contract_version": MOMSEASON_DEVELOPMENT_CONTRACT,
            "freeze_fingerprint": MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT,
            "plan": plan_report,
            "acquisition": acquisition,
            "target_endpoint_availability_counts": dict(sorted(endpoint_counts.items())),
            "missing_target_units": missing_units,
            "evaluation": evaluation,
            "source_request_boundary": {
                "development_only": True,
                "allowed_target_sessions": sorted(item.isoformat() for item in self.allowed_target_sessions),
                "last_allowed_target_session": max(self.allowed_target_sessions).isoformat(),
                "protected_start": LITERATURE_MOMSEASON_PROTECTED_START.isoformat(),
                "adjustment": MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
                "feed": MOMSEASON_ADJUSTED_PREDICTOR_FEED,
                "timeframe": MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
                "asof_rule": "endpoint_session",
            },
            "development_outcome_rows_read": development_rows,
            "target_outcome_rows_read": development_rows,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads_performed_this_run": int((acquisition or {}).get("provider_calls_performed_this_run") or 0),
            "existing_canonical_market_data_mutated": False,
            "global_alpaca_adjustment_mutated": False,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        report["report_path"] = str(self.report_path())
        report["holdings_path"] = str(self.holdings_path())
        report["target_endpoint_path"] = str(self.target_endpoint_path()) if self.target_endpoint_path().is_file() else None
        return report
