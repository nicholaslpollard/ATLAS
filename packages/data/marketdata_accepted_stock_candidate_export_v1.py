from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd

from packages.backtesting.recurrent_successor_outcome_replay import (
    SelectedReplayOpportunity,
    load_selected_replay_opportunities,
)
from packages.backtesting.successor_selected_daily_path_analysis import _validated_daily_source
from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_batch_plan_v1 import plan_candidate_chain_batches


CONTRACT = "atlas-marketdata-accepted-stock-candidate-export-v1"
EASTERN = ZoneInfo("America/New_York")
MIN_YEAR = 2022
MAX_YEAR = 2026
MAX_PER_MONTH = 3
SAMPLE_SALT = "ATLAS_OPTION_CHAIN_CANDIDATE_SOURCE_V1"
BUNDLE_SUBDIR = "data/research/evidence/marketdata_candidate_stock_v1"
PLAN_SUBDIR = "data/options/manifests"


class CandidateStockExportError(RuntimeError):
    pass


def _encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _monthly_expiration(snapshot: date) -> date:
    """First exchange-session-adjusted monthly expiry 28..60 calendar days out."""
    calendar = get_market_calendar()
    for offset in range(1, 4):
        month_index = snapshot.year * 12 + snapshot.month - 1 + offset
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
        first = date(year, month, 1)
        first_friday = 1 + (4 - first.weekday()) % 7
        expiry = date(year, month, first_friday + 14)
        while not calendar.is_session(expiry):
            expiry -= timedelta(days=1)
        if 28 <= (expiry - snapshot).days <= 60:
            return expiry
    raise CandidateStockExportError("no bounded exchange monthly expiry is available")


def select_monthly_cohort(
    opportunities: Sequence[SelectedReplayOpportunity],
    *,
    year: int,
    per_month: int,
) -> tuple[SelectedReplayOpportunity, ...]:
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise CandidateStockExportError("year must remain in the 2022..2026 DEVELOPMENT cohort")
    if not 1 <= per_month <= MAX_PER_MONTH:
        raise CandidateStockExportError("per_month must be 1..3")
    grouped: dict[int, list[SelectedReplayOpportunity]] = defaultdict(list)
    for item in opportunities:
        if (
            item.signal_session.year == year
            and item.native_timeframe == "1d"
            and item.direction == "LONG"
        ):
            grouped[item.signal_session.month].append(item)
    result: list[SelectedReplayOpportunity] = []
    for month in sorted(grouped):
        rows = grouped[month]
        rows.sort(key=lambda row: (
            _hash({"salt": SAMPLE_SALT, "id": row.opportunity_id}),
            row.opportunity_id,
        ))
        result.extend(rows[:per_month])
    return tuple(sorted(result, key=lambda row: (
        row.signal_session, row.ticker, row.opportunity_id,
    )))


def _read_entry_opens(
    project_root: Path,
    cohort: Sequence[SelectedReplayOpportunity],
) -> tuple[dict[str, float], dict[str, object]]:
    calendar = get_market_calendar()
    requests: list[dict[str, object]] = []
    for item in cohort:
        entry_session = item.entry_utc.astimezone(EASTERN).date()
        expected_open, _ = calendar.regular_open_close(entry_session)
        if item.entry_utc.astimezone(UTC) != expected_open:
            raise CandidateStockExportError("selected daily entry timestamp drifted from XNYS open")
        if entry_session <= item.signal_session:
            raise CandidateStockExportError("entry must occur after EOD signal session")
        requests.append({
            "opportunity_id": item.opportunity_id,
            "instrument_id": item.instrument_id,
            "entry_session": entry_session,
        })
    conn = duckdb.connect()
    try:
        conn.execute("PRAGMA threads=4")
        conn.execute("PRAGMA preserve_insertion_order=false")
        conn.register("candidate_entry_requests", pd.DataFrame(requests))
        source_sql, source_report = _validated_daily_source(conn, project_root)
        observations = conn.execute(
            f"""
            SELECT r.opportunity_id, b.open AS raw_entry_open
            FROM candidate_entry_requests r
            JOIN {source_sql} b
              ON b.instrument_id=r.instrument_id
             AND b.session_date=r.entry_session
            ORDER BY r.opportunity_id
            """
        ).fetchall()
    finally:
        conn.close()
    if len(observations) != len(cohort):
        raise CandidateStockExportError(
            f"accepted raw-stock entry price join incomplete: {len(observations)} != {len(cohort)}"
        )
    result: dict[str, float] = {}
    for identifier, value in observations:
        if identifier in result:
            raise CandidateStockExportError("ambiguous duplicate stock open for opportunity")
        price = float(value)
        if not math.isfinite(price) or price <= 0.0:
            raise CandidateStockExportError("invalid raw as-traded stock entry open")
        result[str(identifier)] = price
    if int(source_report.get("protected_master_return_rows_read", -1)) != 0:
        raise CandidateStockExportError("protected master source boundary changed")
    return result, source_report


def _preserve_exact(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file() or path.read_bytes() != payload:
            raise CandidateStockExportError(
                f"existing source/plan differs; refuse to overwrite: {path}"
            )
        return
    atomic_write_text(path, payload.decode("utf-8"))


def export_candidate_stock_manifest(
    settings: AtlasSettings,
    *,
    year: int = 2025,
    per_month: int = 1,
    duckdb_threads: int = 4,
) -> dict[str, Any]:
    if not MIN_YEAR <= year <= MAX_YEAR or not 1 <= per_month <= MAX_PER_MONTH:
        raise CandidateStockExportError("invalid bounded candidate cohort selection")
    if not 1 <= duckdb_threads <= 8:
        raise CandidateStockExportError("duckdb_threads must be 1..8")
    period_start = date(year, 1, 1)
    period_end = min(date(year, 12, 31), date(2026, 4, 30))

    opportunities, source = load_selected_replay_opportunities(
        settings.project_root,
        start_session=period_start,
        end_session=period_end,
        duckdb_threads=duckdb_threads,
    )
    cohort = select_monthly_cohort(opportunities, year=year, per_month=per_month)
    if not cohort:
        raise CandidateStockExportError("accepted cohort has no daily LONG opportunities")
    print(
        f"  sample: {len(cohort)} daily LONG cases from "
        f"{len({item.signal_session.month for item in cohort})} months; "
        "selection uses identifiers, not outcomes", flush=True,
    )

    raw_opens, daily_source = _read_entry_opens(settings.project_root, cohort)
    if not source.get("source_integrity_fingerprint"):
        raise CandidateStockExportError("accepted selected-opportunity source fingerprint missing")
    bundle_rows: list[dict[str, str]] = []
    for item in cohort:
        snapshot = item.signal_session
        decision = item.entry_utc.astimezone(UTC) + timedelta(minutes=5)
        expiry = _monthly_expiration(snapshot)
        bundle_rows.append({
            "opportunity_id": item.opportunity_id,
            "ticker": item.ticker,
            "instrument_id": item.instrument_id,
            "policy_id": item.policy_id,
            "signal_session": snapshot.isoformat(),
            "snapshot_date": snapshot.isoformat(),
            "decision_at_utc": decision.isoformat(),
            "raw_underlying_price": str(raw_opens[item.opportunity_id]),
            "price_origin": "ACCEPTED_V2_RAW_ENTRY_OPEN",
            "expiration": expiry.isoformat(),
            "side": "call",
            "underlying_price_basis": "RAW_AS_TRADED",
        })

    bundle: dict[str, Any] = {
        "contract": CONTRACT,
        "scope": "DEVELOPMENT_SOURCE_ONLY",
        "sample_salt": SAMPLE_SALT,
        "year": year,
        "per_month": per_month,
        "selection": "MIN_SHA256_OF_ID_PER_MONTH_NO_OPTION_NEWS_OR_OUTCOME_FILTER",
        "source_selected_opportunity_integrity_fingerprint": source["source_integrity_fingerprint"],
        "source_conditioning_analysis_fingerprint": source.get("conditioning_analysis_fingerprint"),
        "accepted_raw_daily_source_fingerprint": daily_source["source_fingerprint"],
        "accepted_raw_daily_manifest_sha256": daily_source["manifest_sha256"],
        "protected_master_return_rows_read": 0,
        "rows": bundle_rows,
        "authority": {
            "provider_reads": False, "broker_reads_writes": False,
            "option_price_or_pnl": False, "paper": False, "live": False,
        },
    }
    bundle_bytes = _encoded(bundle)
    bundle_sha = hashlib.sha256(bundle_bytes).hexdigest()

    planning_rows = [{
        "opportunity_id": row["opportunity_id"],
        "ticker": row["ticker"],
        "snapshot_date": row["snapshot_date"],
        "decision_at_utc": row["decision_at_utc"],
        "raw_underlying_price": row["raw_underlying_price"],
        "underlying_price_basis": row["underlying_price_basis"],
        "expiration": row["expiration"],
        "side": row["side"],
        "stock_source_sha256": bundle_sha,
    } for row in bundle_rows]
    payload = {
        "purpose": "SOURCE_ACQUISITION_ONLY",
        "opportunities": planning_rows,
    }
    plan = plan_candidate_chain_batches(payload)

    cohort_identity = _hash({
        "contract": CONTRACT,
        "year": year,
        "per_month": per_month,
        "bundle_sha256": bundle_sha,
        "plan_fingerprint": plan["plan_fingerprint"],
    })[:16]
    source_path = settings.resolved_path(
        f"{BUNDLE_SUBDIR}/{cohort_identity}.json"
    )
    opportunities_path = settings.resolved_path(
        f"{PLAN_SUBDIR}/marketdata_stock_opportunities_v1_{cohort_identity}.json"
    )
    plan_path = settings.resolved_path(
        f"{PLAN_SUBDIR}/marketdata_candidate_batch_plan_v1_{cohort_identity}.json"
    )
    _preserve_exact(source_path, bundle_bytes)
    _preserve_exact(opportunities_path, _encoded(payload))
    _preserve_exact(plan_path, _encoded(plan))
    return {
        "status": "EXPORTED_SOURCE_ONLY",
        "contract": CONTRACT,
        "cohort_identity": cohort_identity,
        "selected_opportunities": len(cohort),
        "shared_chain_requests": plan["shared_chain_requests"],
        "stock_source_sha256": bundle_sha,
        "plan_fingerprint": plan["plan_fingerprint"],
        "stock_source_file": str(source_path),
        "opportunities_file": str(opportunities_path),
        "plan_file": str(plan_path),
        "protected_master_rows_read": 0,
        "provider_reads": 0,
        "no_option_price_or_pnl_authority": True,
    }
