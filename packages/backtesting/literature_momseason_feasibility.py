from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string

from .literature_momseason_policy import (
    LITERATURE_MOMSEASON_BASE_MAIN_SHA,
    LITERATURE_MOMSEASON_FAMILY,
    LITERATURE_MOMSEASON_SOURCE_CONTRACT,
    MOMSEASON_HYPOTHESES,
    formation_months,
    literature_momseason_source_fingerprint,
    month_sessions,
    previous_month,
    required_lag_reference_dates,
    same_month_years_back,
    temporal_capacity,
)
from .literature_momseason_source import (
    MOMSEASON_SOURCE_ROOT_RELATIVE,
    MomSeasonSourceAcquirer,
    read_gzip_jsonl,
)


MOMSEASON_SOURCE_REPORT_NAME = "source_feasibility.json"


class MomSeasonSourceFeasibility:
    """Measure LIT-01 source capacity without reading a target-month return."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.acquirer = MomSeasonSourceAcquirer(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / MOMSEASON_SOURCE_ROOT_RELATIVE

    def report_path(self) -> Path:
        return self.root / MOMSEASON_SOURCE_REPORT_NAME

    def _daily_bar_inventory(self) -> dict[str, object]:
        root = (
            self.settings.resolved_path(self.settings.data.paths.canonical)
            / "stocks"
            / Timeframe.DAY_1.value
        )
        if not root.is_dir() or next(root.rglob("*.parquet"), None) is None:
            return {
                "available": False,
                "row_count": 0,
                "first_session": None,
                "last_session": None,
                "adjustment_state_counts": {},
            }
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        con = connect_utc(":memory:")
        try:
            row = con.execute(
                f"""
                SELECT count(*), min(CAST(session_date AS DATE)), max(CAST(session_date AS DATE))
                FROM read_parquet({sql_string(bar_glob)}, union_by_name=true, hive_partitioning=false)
                """
            ).fetchone()
            states = {
                str(key): int(value)
                for key, value in con.execute(
                    f"""
                    SELECT coalesce(CAST(is_adjusted AS VARCHAR), '<NULL>'), count(*)
                    FROM read_parquet({sql_string(bar_glob)}, union_by_name=true, hive_partitioning=false)
                    GROUP BY 1 ORDER BY 1
                    """
                ).fetchall()
            }
        finally:
            con.close()
        return {
            "available": True,
            "row_count": int(row[0]),
            "first_session": row[1].isoformat() if row[1] is not None else None,
            "last_session": row[2].isoformat() if row[2] is not None else None,
            "adjustment_state_counts": states,
        }

    def _formation_artifact_inventory(self) -> dict[str, object]:
        months = formation_months(self.calendar)
        missing_universe: list[str] = []
        missing_reference: list[str] = []
        complete = 0
        for item in months:
            universe = self.paths.universe_snapshot_file(item.first_session)
            reference = self.paths.reference_snapshot_file(item.first_session)
            if not universe.is_file():
                missing_universe.append(item.first_session.isoformat())
            if not reference.is_file():
                missing_reference.append(item.first_session.isoformat())
            if universe.is_file() and reference.is_file():
                complete += 1
        return {
            "formation_months": len(months),
            "complete_formation_artifact_months": complete,
            "missing_universe_sessions": missing_universe,
            "missing_reference_sessions": missing_reference,
        }

    def _research_reference_inventory(self) -> dict[str, object]:
        required = required_lag_reference_dates(self.calendar)
        missing = [
            item.isoformat()
            for item in required
            if not self.acquirer.reference_path(item).is_file()
        ]
        return {
            "required_reference_dates": len(required),
            "first_required_date": required[0].isoformat(),
            "last_required_date": required[-1].isoformat(),
            "materialized_reference_dates": len(required) - len(missing),
            "missing_reference_dates": missing,
        }

    def _action_inventory(self) -> dict[str, object]:
        result: dict[str, object] = {}
        all_available = True
        for name, date_field in (
            ("splits", "execution_date"),
            ("dividends", "ex_dividend_date"),
        ):
            path = self.acquirer.action_path(name)
            if not path.is_file():
                result[name] = {
                    "available": False,
                    "row_count": 0,
                    "missing_historical_adjustment_factor": None,
                }
                all_available = False
                continue
            rows = read_gzip_jsonl(path)
            relevant_rows = [
                row for row in rows if row.get("ticker") and row.get(date_field)
            ]
            missing_factor = sum(
                row.get("historical_adjustment_factor") in (None, "")
                for row in relevant_rows
            )
            result[name] = {
                "available": True,
                "row_count": len(rows),
                "dated_ticker_rows": len(relevant_rows),
                "missing_historical_adjustment_factor": int(missing_factor),
            }
        result["all_sources_available"] = all_available
        return result

    def _endpoint_bar_map(self, dates: tuple[date, ...]) -> dict[tuple[date, str], float]:
        date_sql = ", ".join(f"DATE '{item.isoformat()}'" for item in dates)
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT CAST(session_date AS DATE), symbol, CAST(close AS DOUBLE)
                FROM read_parquet(
                    {sql_string(self.paths.glob_for_timeframe(Timeframe.DAY_1))},
                    union_by_name=true,
                    hive_partitioning=false
                )
                WHERE CAST(session_date AS DATE) IN ({date_sql})
                  AND close IS NOT NULL
                  AND isfinite(CAST(close AS DOUBLE))
                  AND close > 0
                """
            ).fetchall()
        finally:
            con.close()
        result: dict[tuple[date, str], float] = {}
        duplicates: set[tuple[date, str]] = set()
        for session_date, symbol, close in rows:
            key = (session_date, str(symbol))
            if key in result:
                duplicates.add(key)
            result[key] = float(close)
        if duplicates:
            raise ValueError(
                "LIT-01 canonical daily endpoints contain duplicate date/symbol keys: "
                f"{len(duplicates)}"
            )
        return result

    def _reference_maps(
        self,
        dates: tuple[date, ...],
    ) -> dict[date, dict[str, tuple[str, str]]]:
        maps: dict[date, dict[str, tuple[str, str]]] = {}
        for item in dates:
            rows = read_gzip_jsonl(self.acquirer.reference_path(item))
            mapping: dict[str, tuple[str, str]] = {}
            ambiguous: set[str] = set()
            for row in rows:
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
            maps[item] = mapping
        return maps

    def _formation_members(self, session: date) -> list[tuple[str, str, str]]:
        path = self.paths.universe_snapshot_file(session)
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT instrument_id, ticker, CAST(identity_quality AS VARCHAR)
                FROM read_parquet({sql_string(path)})
                WHERE coalesce(discovery_eligible, FALSE)
                ORDER BY instrument_id
                """
            ).fetchall()
        finally:
            con.close()
        return [(str(row[0]), str(row[1]), str(row[2])) for row in rows]

    def _predictor_input_census(
        self,
        *,
        daily: dict[str, object],
        formation_inventory: dict[str, object],
        reference_inventory: dict[str, object],
    ) -> dict[str, object] | None:
        if (
            not bool(daily["available"])
            or bool(formation_inventory["missing_universe_sessions"])
            or bool(formation_inventory["missing_reference_sessions"])
            or bool(reference_inventory["missing_reference_dates"])
        ):
            return None

        required_dates = required_lag_reference_dates(self.calendar)
        bars = self._endpoint_bar_map(required_dates)
        refs = self._reference_maps(required_dates)
        counters: dict[str, Counter[str]] = {
            hypothesis.hypothesis_id: Counter()
            for hypothesis in MOMSEASON_HYPOTHESES
        }
        monthly_counts: dict[str, dict[str, int]] = {
            hypothesis.hypothesis_id: {}
            for hypothesis in MOMSEASON_HYPOTHESES
        }
        monthly_population: dict[str, int] = {}

        for formation in formation_months(self.calendar):
            month_key = formation.month_start.strftime("%Y-%m")
            members = self._formation_members(formation.first_session)
            monthly_population[month_key] = len(members)
            for hypothesis in MOMSEASON_HYPOTHESES:
                counter = counters[hypothesis.hypothesis_id]
                counter["formation_rows"] += len(members)
                usable = 0
                for instrument_id, _formation_ticker, formation_quality in members:
                    failure: str | None = None
                    if formation_quality.lower() == "fallback":
                        failure = "formation_fallback_identity"
                    for years_back in hypothesis.lag_years:
                        if failure is not None:
                            break
                        lag_month = same_month_years_back(
                            formation.month_start, years_back
                        )
                        prior_end = month_sessions(
                            self.calendar, previous_month(lag_month)
                        )[-1]
                        current_end = month_sessions(self.calendar, lag_month)[-1]
                        prior_ref = refs[prior_end].get(instrument_id)
                        current_ref = refs[current_end].get(instrument_id)
                        if prior_ref is None or current_ref is None:
                            failure = "historical_identity_unavailable"
                            break
                        if prior_ref[0] != current_ref[0]:
                            failure = "ticker_changed_inside_lag_month"
                            break
                        ticker = prior_ref[0]
                        if (prior_end, ticker) not in bars or (current_end, ticker) not in bars:
                            failure = "month_end_price_unavailable"
                            break
                    if failure is None:
                        usable += 1
                        counter["identity_price_reconstructable_rows"] += 1
                    else:
                        counter[failure] += 1
                monthly_counts[hypothesis.hypothesis_id][month_key] = usable

        return {
            "formation_cross_section_rows": monthly_population,
            "hypotheses": {
                hypothesis.hypothesis_id: {
                    **dict(counters[hypothesis.hypothesis_id]),
                    "monthly_reconstructable_rows": monthly_counts[
                        hypothesis.hypothesis_id
                    ],
                }
                for hypothesis in MOMSEASON_HYPOTHESES
            },
            "target_return_rows_read": 0,
            "protected_return_rows_read": 0,
            "note": (
                "This census proves only stable-identity and raw month-end price input "
                "availability for lagged predictor months. Corporate-action adjustment "
                "semantics are audited separately. No target-month price endpoint is read."
            ),
        }

    def run(
        self,
        *,
        acquire: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        acquisition = None
        if acquire:
            acquisition = self.acquirer.acquire(force=force_acquire)

        temporal = temporal_capacity(self.calendar)
        daily = self._daily_bar_inventory()
        formation_inventory = self._formation_artifact_inventory()
        reference_inventory = self._research_reference_inventory()
        actions = self._action_inventory()
        predictor_census = self._predictor_input_census(
            daily=daily,
            formation_inventory=formation_inventory,
            reference_inventory=reference_inventory,
        )

        base_sources_ready = (
            bool(daily["available"])
            and not bool(formation_inventory["missing_universe_sessions"])
            and not bool(formation_inventory["missing_reference_sessions"])
            and not bool(reference_inventory["missing_reference_dates"])
        )
        action_sources_ready = bool(actions["all_sources_available"])

        if not base_sources_ready:
            status = "SOURCE_ACQUISITION_REQUIRED"
        elif predictor_census is None:
            status = "SOURCE_CENSUS_BLOCKED"
        elif not action_sources_ready:
            status = "CORPORATE_ACTION_SOURCE_REQUIRED"
        elif not bool(temporal["current_protected_temporal_capacity_sufficient"]):
            status = "SOURCE_CAPACITY_PASS_NEW_PROTECTED_WINDOW_REQUIRED"
        else:
            status = "SOURCE_CAPACITY_PASS"

        report: dict[str, object] = {
            "contract_version": LITERATURE_MOMSEASON_SOURCE_CONTRACT,
            "source_fingerprint": literature_momseason_source_fingerprint(),
            "base_main_sha": LITERATURE_MOMSEASON_BASE_MAIN_SHA,
            "family": LITERATURE_MOMSEASON_FAMILY,
            "status": status,
            "alpha_hypotheses_frozen": False,
            "performance_evaluated": False,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "hypotheses": [
                {
                    "hypothesis_id": item.hypothesis_id,
                    "external_signal": item.external_signal,
                    "lag_years": list(item.lag_years),
                    "direction": item.direction,
                    "portfolio_period_months": item.portfolio_period_months,
                    "evidence_class": item.evidence_class,
                }
                for item in MOMSEASON_HYPOTHESES
            ],
            "temporal_capacity": temporal,
            "daily_bar_inventory": daily,
            "formation_artifact_inventory": formation_inventory,
            "research_reference_inventory": reference_inventory,
            "corporate_action_inventory": actions,
            "predictor_input_census": predictor_census,
            "acquisition": acquisition,
            "scientific_boundaries": {
                "native_broad_cross_section_first": True,
                "warm_hot_filter_applied": False,
                "strategy_router_applied": False,
                "regime_filter_applied": False,
                "target_month_return_read": False,
                "current_master_holdout_may_grant_support": bool(
                    temporal["current_protected_temporal_capacity_sufficient"]
                ),
            },
            "next_scientific_action": (
                "Audit total-return adjustment fidelity on the acquired split/dividend "
                "sources. If the source census is adequate, calibrate and prospectively "
                "freeze the two-hypothesis development/internal-validation experiment "
                "before reading target-month returns. The current master protected window "
                "cannot grant final support unless it contains the preregistered minimum "
                "number of independent complete calendar months."
            ),
        }
        self.report_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.report_path(),
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        report["report_path"] = str(self.report_path())
        return report
