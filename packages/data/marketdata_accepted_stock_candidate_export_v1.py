from __future__ import annotations

import gzip
import hashlib
import json
import math
import time
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd

from packages.backtesting.recurrent_successor_outcome_replay import (
    SelectedReplayOpportunity,
    load_selected_replay_opportunities,
)
from packages.backtesting.successor_selected_daily_path_analysis import _validated_daily_source
from packages.backtesting.b35_development_source import _assert_native_path, _validate_native_plan_record
from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.backtesting.reference_v2_lake_adapter import ReferenceV2DailyLakeAdapter
from packages.data.alpaca_v2_acquisition import ACQUISITION_CONTRACT, UNIT_CONTRACT
from packages.data.alpaca_v2_postbuild import NATIVE_ACCEPTANCE_CONTRACT
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings, load_settings
from packages.data.marketdata_candidate_batch_plan_v1 import (
    TICKER_PATTERN,
    plan_candidate_chain_batches,
)


CONTRACT = "atlas-marketdata-accepted-stock-candidate-export-v1"
EASTERN = ZoneInfo("America/New_York")
MIN_YEAR = 2022
MAX_YEAR = 2025
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
        raise CandidateStockExportError("year must remain in the 2022..2025 native-raw-safe DEVELOPMENT cohort")
    if not 1 <= per_month <= MAX_PER_MONTH:
        raise CandidateStockExportError("per_month must be 1..3")
    grouped: dict[int, list[SelectedReplayOpportunity]] = defaultdict(list)
    for item in opportunities:
        if (
            item.signal_session.year == year
            and item.native_timeframe == "1d"
            and item.direction == "LONG"
            and item.entry_utc.astimezone(EASTERN).year == year
            and isinstance(item.ticker, str)
            and TICKER_PATTERN.fullmatch(item.ticker)
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


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise CandidateStockExportError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CandidateStockExportError(f"invalid {label}") from exc
    if not isinstance(payload, dict):
        raise CandidateStockExportError(f"{label} must be an object")
    return payload


def _accepted_native_plan(
    settings: AtlasSettings,
    research_report: dict[str, object],
    requested: set[tuple[str, date]],
) -> tuple[list[dict[str, Any]], dict[str, Any], V2Layout]:
    """Verify accepted native source, not merely the split-adjusted research view."""
    if any(session.year > 2025 for _, session in requested):
        raise CandidateStockExportError("2026 native daily partitions are forbidden")
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    adapter = ReferenceV2DailyLakeAdapter(settings)
    _, research_manifest = adapter._manifest(None)
    expected = research_manifest.get("native_acceptance_fingerprint")
    if not isinstance(expected, str) or len(expected) != 64:
        raise CandidateStockExportError("research source lacks native-acceptance fingerprint")
    native = _read_json(layout.validation / "native_acceptance.json", "native acceptance")
    if any((
        native.get("contract") != NATIVE_ACCEPTANCE_CONTRACT,
        native.get("status") != "PASS",
        native.get("v1_ancestry") != "FORBIDDEN",
        native.get("protected_return_rows_read") != 0,
        native.get("production_promoted") is not False,
        native.get("acceptance_fingerprint") != expected,
    )):
        raise CandidateStockExportError("native source does not match accepted research lineage")
    excluded = set(str(s) for s in native.get("excluded_symbols") or [])
    if excluded.intersection(ticker for ticker, _ in requested):
        raise CandidateStockExportError("candidate ticker is excluded from accepted native source")

    manifest = _read_json(layout.manifests / "native_acquisition_plan.json", "native plan manifest")
    if any((
        manifest.get("contract") != ACQUISITION_CONTRACT,
        manifest.get("status") != "FROZEN",
        manifest.get("v1_ancestry") != "FORBIDDEN",
    )):
        raise CandidateStockExportError("native acquisition plan identity drifted")
    plan_path = layout.manifests / "native_acquisition_plan.jsonl.gz"
    if not plan_path.is_file() or _file_sha(plan_path) != manifest.get("plan_file_sha256"):
        raise CandidateStockExportError("native plan compressed SHA mismatch")
    try:
        plan_bytes = gzip.decompress(plan_path.read_bytes())
    except (OSError, EOFError) as exc:
        raise CandidateStockExportError("native plan gzip failed") from exc
    if hashlib.sha256(plan_bytes).hexdigest() != manifest.get("plan_sha256"):
        raise CandidateStockExportError("native plan content SHA mismatch")

    selected: dict[tuple[str, int], dict[str, Any]] = {}
    sought = {(ticker, session.year) for ticker, session in requested}
    for line_number, line in enumerate(plan_bytes.splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict) or record.get("canonical_timeframe") != "1d":
            continue
        year = int(record.get("year", -1))
        if year not in {y for _, y in sought}:
            continue
        _validate_native_plan_record(record, line_number)
        if record.get("provider_timeframe") != "1Day" or record.get("month") is not None:
            raise CandidateStockExportError("native daily plan identity drifted")
        for ticker in record.get("symbols") or []:
            key = (str(ticker), year)
            if key not in sought:
                continue
            if key in selected:
                raise CandidateStockExportError("ticker/year native-unit ambiguity")
            selected[key] = record
    if set(selected) != sought:
        raise CandidateStockExportError("native plan lacks exact source unit for selected ticker/year")
    return list({str(v["unit_id"]): v for v in selected.values()}.values()), {
        "native_acceptance_fingerprint": expected,
        "native_plan_sha256": manifest["plan_sha256"],
        "native_plan_file_sha256": manifest["plan_file_sha256"],
        "research_daily_source_fingerprint": research_report["source_fingerprint"],
    }, layout


def _read_entry_opens(
    project_root: Path,
    cohort: Sequence[SelectedReplayOpportunity],
    *,
    progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> tuple[dict[str, float], dict[str, object]]:
    calendar = get_market_calendar()
    requests: list[dict[str, object]] = []
    for item in cohort:
        entry_session = item.entry_utc.astimezone(EASTERN).date()
        expected_open, _ = calendar.regular_open_close(entry_session)
        if item.entry_utc.astimezone(UTC) != expected_open:
            raise CandidateStockExportError("selected daily entry timestamp drifted from XNYS open")
        if entry_session <= item.signal_session or entry_session.year > 2025:
            raise CandidateStockExportError("entry must remain in pre-2026 DEVELOPMENT native raw source")
        requests.append({
            "opportunity_id": item.opportunity_id,
            "instrument_id": item.instrument_id,
            "ticker": item.ticker,
            "entry_session": entry_session,
        })
    # The research view provides accepted identity and an exact raw CLOSE check,
    # but its OPEN is split-adjusted and must NEVER be used to construct strikes.
    conn = duckdb.connect()
    try:
        conn.execute("PRAGMA threads=4")
        conn.execute("PRAGMA preserve_insertion_order=false")
        conn.register("candidate_entry_requests", pd.DataFrame(requests))
        source_sql, source_report = _validated_daily_source(conn, project_root)
        observations = conn.execute(
            f"""
            SELECT r.opportunity_id, r.ticker, r.entry_session,
                   b.unadjusted_close, b.price_adjustment_mode
            FROM candidate_entry_requests r
            JOIN {source_sql} b
              ON b.instrument_id=r.instrument_id
             AND b.session_date=r.entry_session
             AND b.ticker=r.ticker
            ORDER BY r.opportunity_id
            """
        ).fetchall()
    finally:
        conn.close()
    if len(observations) != len(cohort):
        raise CandidateStockExportError("accepted stock identity/raw-close source join incomplete")
    if int(source_report.get("protected_master_return_rows_read", -1)) != 0:
        raise CandidateStockExportError("protected master source boundary changed")
    reference: dict[tuple[str, date], float] = {}
    wanted: dict[str, tuple[str, date]] = {}
    for identifier, ticker, session, close, mode in observations:
        if mode != "SPLIT_ADJUSTED":
            raise CandidateStockExportError("research view's price basis changed")
        session = session if isinstance(session, date) else pd.Timestamp(session).date()
        raw_close = float(close)
        if not math.isfinite(raw_close) or raw_close <= 0:
            raise CandidateStockExportError("research view lacks valid as-traded close")
        key = (str(ticker), session)
        if key in reference and reference[key] != raw_close:
            raise CandidateStockExportError("accepted raw-close ambiguity")
        reference[key] = raw_close
        wanted[str(identifier)] = key

    settings = load_settings(project_root, "development")
    records, native_source, layout = _accepted_native_plan(settings, source_report, set(reference))
    result_by_key: dict[tuple[str, date], float] = {}
    unit_bindings: list[dict[str, object]] = []
    for unit_number, record in enumerate(sorted(records, key=lambda r: str(r["unit_id"])), start=1):
        year, batch, unit_id = int(record["year"]), int(record["batch_index"]), str(record["unit_id"])
        if year > 2025:
            raise CandidateStockExportError("protected/2026 native unit forbidden")
        part = Path(f"year={year:04d}") / f"batch={batch:04d}"
        prefix = unit_id[:20]
        checkpoint_path = layout.checkpoints / "native_units" / "1d" / part / f"{prefix}.json"
        canonical_path = layout.canonical_daily / part / f"{prefix}.parquet"
        _assert_native_path(
            checkpoint_path, expected=checkpoint_path, root=layout.root,
            label="candidate native daily checkpoint",
        )
        _assert_native_path(
            canonical_path, expected=canonical_path, root=layout.root,
            label="candidate native daily raw canonical",
        )
        checkpoint = _read_json(checkpoint_path, "exact native daily unit checkpoint")
        if checkpoint.get("contract") != UNIT_CONTRACT or checkpoint.get("status") not in {
            "COMPLETE", "COMPLETE_WITH_QUARANTINE",
        }:
            raise CandidateStockExportError("native daily unit is not checkpoint-complete")
        if any((
            checkpoint.get("unit_id") != unit_id,
            checkpoint.get("policy_sha256") != record.get("policy_sha256"),
            checkpoint.get("universe_sha256") != record.get("universe_sha256"),
            canonical_sha256(checkpoint.get("unit")) != canonical_sha256(record),
        )):
            raise CandidateStockExportError("native checkpoint plan binding drifted")
        canonical = checkpoint.get("canonical")
        if not isinstance(canonical, dict) or not canonical_path.is_file():
            raise CandidateStockExportError("native canonical file binding missing")
        if Path(str(canonical.get("path") or "")).absolute() != canonical_path.absolute():
            raise CandidateStockExportError("native canonical path drifted")
        expected_sha = str(canonical.get("sha256") or "")
        if len(expected_sha) != 64 or _file_sha(canonical_path) != expected_sha:
            raise CandidateStockExportError("native daily raw unit SHA mismatch")
        ticker_set = {
            ticker for ticker, session in reference
            if session.year == year and ticker in (record.get("symbols") or [])
        }
        rejected = {
            str(value.get("symbol") or "")
            for value in checkpoint.get("provider_rejections") or []
            if isinstance(value, dict)
        }
        if ticker_set.intersection(rejected):
            raise CandidateStockExportError("native daily provider rejection for selected ticker")
        read_conn = duckdb.connect()
        try:
            read_conn.execute("PRAGMA threads=2")
            read_conn.register("needed_native_pairs", pd.DataFrame([
                {"symbol": ticker, "session_date": session}
                for ticker, session in reference
                if ticker in ticker_set and session.year == year
            ]))
            raw_rows = read_conn.execute(
                """
                SELECT p.symbol, p.session_date, p.open, p.close, p.provider,
                       p.dataset, p.timeframe, p.session_segment,
                       p.is_adjusted, p.source_id
                FROM read_parquet(?, hive_partitioning=false) p
                JOIN needed_native_pairs r
                  ON p.symbol=r.symbol AND p.session_date=r.session_date
                """,
                [str(canonical_path)],
            ).fetchall()
        finally:
            read_conn.close()
        for ticker, session, opening, closing, provider, dataset, timeframe, segment, adjusted, source_id in raw_rows:
            key = (str(ticker), session if isinstance(session, date) else pd.Timestamp(session).date())
            if key not in reference or key in result_by_key:
                raise CandidateStockExportError("native raw pair is unexpected/duplicate")
            if (provider, dataset, timeframe, segment, adjusted, source_id) != (
                "alpaca", "stock_daily_aggregates", "1d", "regular", False,
                f"alpaca:sip:1Day:raw:asof=-:v2:unit={unit_id}",
            ):
                raise CandidateStockExportError("native raw provenance mismatch")
            raw_open, raw_close = float(opening), float(closing)
            if not all(math.isfinite(p) and p > 0 for p in (raw_open, raw_close)):
                raise CandidateStockExportError("native raw OHLC invalid")
            if abs(raw_close - reference[key]) > 1e-8:
                raise CandidateStockExportError("native raw close disagrees with accepted research raw close")
            result_by_key[key] = raw_open
        unit_bindings.append({"unit_id": unit_id, "year": year, "canonical_sha256": expected_sha})
        if progress is not None:
            progress("NATIVE_RAW_UNIT_VERIFIED", {
                "verified_units": unit_number,
                "total_units": len(records),
                "unit_id": unit_id,
                "year": year,
                "canonical_sha256": expected_sha,
            })
    if set(result_by_key) != set(reference):
        raise CandidateStockExportError("native raw opening-price coverage incomplete")
    native_source["verified_native_raw_unit_bindings"] = unit_bindings
    native_source["verified_native_raw_unit_count"] = len(unit_bindings)
    return {ident: result_by_key[key] for ident, key in wanted.items()}, {
        **source_report, "native_raw_source": native_source,
    }


def _preserve_exact(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file() or path.read_bytes() != payload:
            raise CandidateStockExportError(
                f"existing source/plan differs; refuse to overwrite: {path}"
            )
        return
    atomic_write_text(path, payload.decode("utf-8"))


def _export_candidate_stock_manifest_impl(
    settings: AtlasSettings,
    *,
    year: int = 2025,
    per_month: int = 1,
    duckdb_threads: int = 4,
    progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not MIN_YEAR <= year <= MAX_YEAR or not 1 <= per_month <= MAX_PER_MONTH:
        raise CandidateStockExportError("invalid bounded candidate cohort selection")
    if not 1 <= duckdb_threads <= 8:
        raise CandidateStockExportError("duckdb_threads must be 1..8")
    period_start = date(year, 1, 1)
    period_end = date(year, 12, 31)

    if progress is not None:
        progress("ACCEPTED_SOURCE_LOADING", {"year": year, "duckdb_threads": duckdb_threads})

    opportunities, source = load_selected_replay_opportunities(
        settings.project_root,
        start_session=period_start,
        end_session=period_end,
        duckdb_threads=duckdb_threads,
    )
    if progress is not None:
        progress("ACCEPTED_SOURCE_LOADED", {
            "accepted_selected_opportunities": len(opportunities),
            "source_integrity_fingerprint": source.get("source_integrity_fingerprint"),
        })
    cohort = select_monthly_cohort(opportunities, year=year, per_month=per_month)
    if not cohort:
        raise CandidateStockExportError("accepted cohort has no daily LONG opportunities")
    print(
        f"  sample: {len(cohort)} daily LONG cases from "
        f"{len({item.signal_session.month for item in cohort})} months; "
        "selection uses identifiers, not outcomes", flush=True,
    )

    if progress is not None:
        progress("COHORT_SELECTED", {
            "selected_opportunities": len(cohort),
            "months_represented": len({item.signal_session.month for item in cohort}),
        })
        progress("NATIVE_RAW_SOURCE_VERIFYING", {"selected_opportunities": len(cohort)})
    raw_opens, daily_source = _read_entry_opens(
        settings.project_root, cohort, progress=progress,
    )
    if progress is not None:
        progress("NATIVE_RAW_SOURCE_VERIFIED", {
            "verified_native_raw_units": daily_source["native_raw_source"]["verified_native_raw_unit_count"],
            "accepted_research_daily_source_fingerprint": daily_source["source_fingerprint"],
        })
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
            "price_origin": "ACCEPTED_NATIVE_RAW_1DAY_ENTRY_OPEN",
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
        "accepted_research_daily_source_fingerprint": daily_source["source_fingerprint"],
        "accepted_native_raw_source": daily_source["native_raw_source"],
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

    if progress is not None:
        progress("CHAIN_PLAN_READY", {
            "selected_opportunities": len(cohort),
            "shared_chain_requests": plan["shared_chain_requests"],
            "saved_duplicate_requests": len(cohort) - plan["shared_chain_requests"],
            "plan_fingerprint": plan["plan_fingerprint"],
        })

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
    if progress is not None:
        progress("ARTIFACTS_WRITTEN", {
            "source_file": str(source_path),
            "stock_source_sha256": bundle_sha,
            "plan_file": str(plan_path),
            "plan_fingerprint": plan["plan_fingerprint"],
        })
    return {
        "status": "EXPORTED_SOURCE_ONLY",
        "verified_native_raw_units": daily_source["native_raw_source"]["verified_native_raw_unit_count"],
        "contract": CONTRACT,
        "cohort_identity": cohort_identity,
        "selected_opportunities": len(cohort),
        "shared_chain_requests": plan["shared_chain_requests"],
        "sample": [
            {
                "ticker": row["ticker"],
                "signal_session": row["signal_session"],
                "entry_price": row["raw_underlying_price"],
                "candidate_expiration": row["expiration"],
                "opportunity_id": row["opportunity_id"],
            }
            for row in bundle_rows
        ],
        "stock_source_sha256": bundle_sha,
        "plan_fingerprint": plan["plan_fingerprint"],
        "stock_source_file": str(source_path),
        "opportunities_file": str(opportunities_path),
        "plan_file": str(plan_path),
        "protected_master_rows_read": 0,
        "provider_reads": 0,
        "no_option_price_or_pnl_authority": True,
    }



def export_candidate_stock_manifest(
    settings: AtlasSettings,
    *,
    year: int = 2025,
    per_month: int = 1,
    duckdb_threads: int = 4,
) -> dict[str, Any]:
    """Durable source-only progress separate from deterministic frozen artifacts."""
    # Keep scientific/cohort validation in the actual exporter; this wrapper
    # records state without injecting timestamps or paths into bundle identity.
    started = time.monotonic()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    # Operational stage reports must remain Windows-short; all scientific
    # lineage and immutable output hashes stay in the report and bundle.
    path = settings.resolved_path(
        f"{PLAN_SUBDIR}/md_stock_runs/{run_id}.json"
    )
    report: dict[str, Any] = {
        "contract": CONTRACT,
        "run_id": run_id,
        "run_report_path": str(path),
        "status": "RUNNING",
        "started_at_utc": datetime.now(UTC).isoformat(),
        "year": year,
        "per_month": per_month,
        "duckdb_threads": duckdb_threads,
        "stages": [],
        "provider_reads": 0,
        "broker_reads_writes": 0,
        "protected_master_return_rows_read": 0,
        "no_option_price_or_pnl_authority": True,
    }

    def checkpoint(stage: str, details: dict[str, Any]) -> None:
        report["stage"] = stage
        report["last_updated_at_utc"] = datetime.now(UTC).isoformat()
        elapsed = round(max(0.0, time.monotonic() - started), 3)
        report["elapsed_seconds"] = elapsed
        report["stages"].append({
            "stage": stage, "elapsed_seconds": elapsed, **details,
        })
        report.pop("report_fingerprint", None)
        report["report_fingerprint"] = _hash(report)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, _encoded(report).decode("utf-8"))
        print(f"  export stage={stage} elapsed={elapsed:.1f}s", flush=True)

    checkpoint("STARTED", {})
    try:
        result = _export_candidate_stock_manifest_impl(
            settings, year=year, per_month=per_month,
            duckdb_threads=duckdb_threads, progress=checkpoint,
        )
    except BaseException as exc:
        report["status"] = (
            "INTERRUPTED" if isinstance(exc, KeyboardInterrupt)
            else "FAILED_REVIEW_REQUIRED"
        )
        report["exception_type"] = type(exc).__name__
        checkpoint(report["status"], {})
        raise

    report["status"] = "SOURCE_ONLY_COMPLETE"
    report["summary"] = {
        "selected_opportunities": result["selected_opportunities"],
        "shared_chain_requests": result["shared_chain_requests"],
        "verified_native_raw_units": result["verified_native_raw_units"],
        "source_sha256": result["stock_source_sha256"],
        "plan_fingerprint": result["plan_fingerprint"],
        "stock_source_file": result["stock_source_file"],
        "plan_file": result["plan_file"],
    }
    checkpoint("COMPLETE", {})
    result["run_report_path"] = str(path)
    result["elapsed_seconds"] = report["elapsed_seconds"]
    result["source_only_run_id"] = run_id
    result["stages_completed"] = len(report["stages"])
    return result
