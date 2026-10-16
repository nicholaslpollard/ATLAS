from __future__ import annotations

"""One-pass cached SPY minute-clock coverage for all frozen 2018-2025 native cases.

This is physical source coverage, NOT 411 accepted causal features. Recorded
bar-end and ex-dates cannot prove historical provider availability. The project
master holdout and all stock/option outcomes are physically outside this scan.
"""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from packages.backtesting.b35_development_source import (
    _binding_from_plan, _validate_native_plan_record,
)
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_acquisition import ACQUISITION_CONTRACT
from packages.data.alpaca_v2_postbuild import NATIVE_ACCEPTANCE_CONTRACT
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.duckdb_connection import connect_utc
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_plan_v1 import build_options_native_pilot_plan
from packages.data.options_native_spy_prior_variance_sensitivity_v1 import (
    PinnedReview, _read_report,
)
from packages.data.options_native_stock_input_review_v1 import (
    DEFAULT_BINDING, MAX_COMPRESSED, MAX_EXPANDED, MAX_INVENTORY, MAX_LINE,
    MAX_METADATA, MAX_MINUTE_UNIT, _file, _json, verify_retained_pilot_packet,
)
from packages.strategies.options_native_pair_v1 import decimal
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-options-native-spy-development-minute-clock-coverage-v1"
MAX_MONTHLY_UNITS = 125
MAX_UNIQUE_CLOCKS = 4000
MAX_REQUESTS = 500


class PilotClockCoverageError(ValueError):
    pass


def _require(test: bool, msg: str) -> None:
    if not test:
        raise PilotClockCoverageError(msg)


def _key(value: datetime) -> str:
    _require(value.tzinfo is not None and value.utcoffset() is not None, "UTC aware clock required")
    return value.astimezone(UTC).isoformat()


def frozen_clock_demand() -> tuple[dict[str, Any], dict[tuple[int, int], dict[str, datetime]]]:
    """Build one globally deduplicated requested-clock map for 411 weekly cases."""
    plan = build_options_native_pilot_plan()
    rows = [r for r in plan["rows"] if r["status"] == "PLANNED_DECISION_INPUT_SURFACE"]
    _require(len(rows) == plan["entry_quote_surface_count"] == 411
             and plan["specification_fingerprint"] == SPECIFICATION_FINGERPRINT,
             "frozen options-native SPY decision plan drifted")
    calendar = get_market_calendar("XNYS")
    by_month: dict[tuple[int, int], dict[str, datetime]] = defaultdict(dict)
    cases: list[dict[str, Any]] = []
    for row in rows:
        decision = datetime.fromisoformat(row["feature_cutoff_utc"]).astimezone(UTC)
        days = calendar.sessions_in_range((decision - timedelta(days=75)).date(), decision.date())
        closes = [(day, calendar.regular_open_close(day)[1]) for day in days
                  if calendar.regular_open_close(day)[1] < decision][-21:]
        _require(len(closes) == 21 and all(day < decision.date() for day, _ in closes),
                 "frozen decision missing 21 prior sessions")
        requested = []
        for day, end in closes:
            start = end - timedelta(minutes=1)
            key = _key(start)
            by_month[(day.year, day.month)][key] = start
            requested.append({"session": day.isoformat(), "clock": key})
        spot_at = decision - timedelta(minutes=1)
        by_month[(decision.year, decision.month)][_key(spot_at)] = spot_at
        cases.append({
            "decision_date": decision.date().isoformat(),
            "decision_utc": decision.isoformat(),
            "order_eligible_utc": row["order_eligible_utc"],
            "quote_query_fingerprint": row["quote_query_fingerprint"],
            "prior": requested,
            "spot": _key(spot_at),
        })
    _require(len(cases) == 411 and len({r["decision_date"] for r in cases}) == 411,
             "duplicate or omitted frozen weekly entry")
    all_clocks = [key for batch in by_month.values() for key in batch]
    _require(1 <= len(by_month) <= MAX_MONTHLY_UNITS
             and len(all_clocks) == len(set(all_clocks)) and len(all_clocks) <= MAX_UNIQUE_CLOCKS,
             "requested source scope exceeds bounded development design")
    return {"plan_fingerprint": plan["plan_fingerprint"], "cases": cases,
            "months": [f"{y:04d}-{m:02d}" for y, m in sorted(by_month)],
            "unique_clocks": len(all_clocks)}, by_month


def select_native_units(layout: V2Layout, packet: dict, months: set[tuple[int, int]]) -> dict[tuple[int, int], dict]:
    """Read frozen compressed metadata once, verifying the original global plan hash."""
    plan_manifest = layout.manifests / "native_acquisition_plan.json"
    manifest_sha = next((item["sha256"] for item in packet["metadata_file_bindings"]
                         if item["locator"].endswith("/native_acquisition_plan.json")), None)
    _require(isinstance(manifest_sha, str), "retained pilot packet lacks frozen plan manifest binding")
    manifest, _ = _json(layout, plan_manifest, manifest_sha)
    _require(manifest.get("contract") == ACQUISITION_CONTRACT
             and manifest.get("status") == "FROZEN"
             and manifest.get("v1_ancestry") == "FORBIDDEN"
             and manifest.get("plan_sha256") == packet["lineage"]["native_plan_sha256"]
             and manifest.get("plan_file_sha256") == packet["lineage"]["native_plan_file_sha256"],
             "global native plan identity changed")
    src = layout.manifests / "native_acquisition_plan.jsonl.gz"
    _file(layout, src, MAX_COMPRESSED, manifest["plan_file_sha256"])
    digest = hashlib.sha256()
    seen: dict[tuple[int, int], dict] = {}
    expanded = 0
    with gzip.open(src, "rb") as handle:
        for line_number in range(1, 1000002):
            line = handle.readline(MAX_LINE + 1)
            if not line:
                break
            expanded += len(line)
            _require(expanded <= MAX_EXPANDED and len(line) <= MAX_LINE and line_number <= 1000000,
                     "global native plan exceeds bounded expanded scope")
            digest.update(line)
            if not line.strip():
                continue
            row = json.loads(line)
            _require(isinstance(row, dict), "malformed native plan record")
            month = (row.get("year"), row.get("month"))
            if (row.get("canonical_timeframe") != "1m" or month not in months
                    or "SPY" not in (row.get("symbols") or [])):
                continue
            _validate_native_plan_record(row, line_number)
            start = date(row["year"], row["month"], 1)
            end = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
            _require(month not in seen and row["provider_timeframe"] == "1Min"
                     and row["window_start"] == start.isoformat()
                     and row["window_end_exclusive"] == end.isoformat()
                     and row["batch_index"] >= 0, "duplicate or changed SPY monthly plan identity")
            seen[month] = row
    _require(digest.hexdigest() == manifest["plan_sha256"],
             "globally frozen native plan expanded SHA-256 differs")
    return seen


def verify_physical_rows(
    physical: list[tuple], clocks: set[datetime], unit_id: str,
) -> dict[str, str]:
    """Reject duplicate/source-drift rows, with missing clocks left explicit."""
    found: dict[str, str] = {}
    for symbol, stamp, day, segment, close, timeframe, dataset, provider, source_id, adjusted in physical:
        _require(isinstance(stamp, datetime) and stamp.tzinfo is not None,
                 "minute bar missing timezone")
        key = _key(stamp)
        _require(stamp.astimezone(UTC) in clocks and key not in found,
                 "minute bar duplicates requested identity or clock")
        _require(str(day) == stamp.astimezone(UTC).date().isoformat()
                 and (symbol, segment, timeframe, dataset, provider, source_id, adjusted) ==
                 ("SPY", "regular", "1m", "stock_minute_aggregates", "alpaca",
                  "alpaca:sip:1Min:raw:asof=-:v2:unit=" + unit_id, False),
                 "minute bar provenance or regular-session semantics changed")
        found[key] = str(decimal(str(close)))
    return found


def project_case_coverage(demand: dict, observed: dict[str, dict[str, Any]]) -> dict:
    """Separate physical completeness from all historical feature qualification."""
    cases = []
    full = 0
    for case in demand["cases"]:
        prior = case["prior"]
        missing = [p["clock"] for p in prior if p["clock"] not in observed
                   or observed[p["clock"]].get("raw_close") is None]
        spot = observed.get(case["spot"])
        if spot is None or spot.get("raw_close") is None:
            missing.append(case["spot"])
        full += not missing
        cases.append({
            "decision_date": case["decision_date"],
            "decision_utc": case["decision_utc"],
            "quote_query_fingerprint": case["quote_query_fingerprint"],
            "prior_close_keys": [p["clock"] for p in prior],
            "spot_key": case["spot"],
            "exact_minutes_present": 22 - len(missing),
            "missing_clocks": missing,
            "status": "RAW_CLOCKS_PRESENT_PIT_UNQUALIFIED" if not missing else "RAW_CLOCKS_MISSING",
            "historical_input_accepted": False, "forecast_total_variance": None,
        })
    return {"cases": cases, "raw_complete": full, "raw_with_gaps": len(cases) - full}


def review_spy_development_minute_coverage(
    settings: AtlasSettings, *,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Open only accepted pre-2026 SPY 1m units required by frozen weekly input clocks."""
    old_report = _read_report(settings, PinnedReview())
    _require(old_report.get("contract") == "atlas-options-native-cached-stock-input-review-v1"
             and old_report.get("specification_fingerprint") == SPECIFICATION_FINGERPRINT
             and old_report.get("requested_minute_observations") == 22
             and old_report.get("present_minute_observations") == 22
             and old_report.get("pilot_input_acceptance") is False,
             "calibration stock report is not the accepted 22-clock diagnostic")
    source_packet_path = settings.resolved_path(DEFAULT_BINDING.relative_path)
    _require(not source_packet_path.is_symlink() and source_packet_path.is_file()
             and source_packet_path.stat().st_size <= 256 * 1024, "retained native packet unavailable")
    packet = verify_retained_pilot_packet(source_packet_path.read_bytes())
    demand, months = frozen_clock_demand()
    _require(max(months) <= (2025, 12), "request would touch 2026 or protected source units")
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    expected = old_report["native_acceptance_file_sha256"]
    native, native_info = _json(layout, layout.validation / "native_acceptance.json", expected)
    _require(native.get("contract") == NATIVE_ACCEPTANCE_CONTRACT
             and native.get("status") == "PASS"
             and native.get("v1_ancestry") == "FORBIDDEN"
             and native.get("protected_return_rows_read") == 0
             and native.get("production_promoted") is False
             and native.get("acceptance_fingerprint") == old_report["native_acceptance_fingerprint"],
             "accepted pre-protected V2 source authority drifted")
    if progress:
        progress(f"frozen {len(demand['cases'])} weekly cases -> {demand['unique_clocks']} unique SPY minute clocks, "
                 f"{len(months)} months; verifying original plan and accepted inventory")
    records = select_native_units(layout, packet, set(months))
    inventory = native["unit_inventory"]
    inventory_path = layout.validation / "native_unit_inventory.parquet"
    _require(Path(str(inventory["path"])).absolute() == inventory_path.absolute()
             and inventory["sha256"] == native["source_binding"]["unit_inventory_sha256"],
             "accepted inventory path or identity changed")
    _file(layout, inventory_path, MAX_INVENTORY, inventory["sha256"])
    ids = [r["unit_id"] for r in records.values()]
    _require(len(ids) <= MAX_MONTHLY_UNITS, "too many monthly units")
    con = connect_utc(":memory:", config={"threads": 2, "memory_limit": "512MB"})
    try:
        inventory_rows = con.execute(
            "SELECT unit_id,checkpoint_path,checkpoint_sha256,canonical_path,canonical_sha256,status "
            "FROM read_parquet(?, hive_partitioning=false) WHERE unit_id IN (SELECT UNNEST(?))",
            [str(inventory_path), ids],
        ).fetchall()
    finally:
        con.close()
    inv: dict[str, tuple] = {}
    for row in inventory_rows:
        _require(row[0] not in inv, "accepted inventory contains duplicate unit ID")
        inv[row[0]] = row

    observations: dict[str, dict[str, Any]] = {}
    unit_bindings: list[dict[str, Any]] = []
    for index, month in enumerate(sorted(months), 1):
        requested = months[month]
        row = records.get(month)
        accepted = inv.get(row["unit_id"]) if row else None
        if progress and (index == 1 or index % 5 == 0 or index == len(months)):
            progress(f"SPY month {index}/{len(months)} {month[0]}-{month[1]:02d}, accepted={bool(accepted)}")
        if row is None or accepted is None:
            for key in requested:
                observations[key] = {"raw_close": None, "status": "FROZEN_UNIT_ABSENT_OR_NOT_ACCEPTED",
                                     "source_unit_id": row["unit_id"] if row else None}
            unit_bindings.append({"month": f"{month[0]:04d}-{month[1]:02d}",
                                  "status": "SOURCE_UNIT_ABSENT_OR_UNACCEPTED"})
            continue
        part = Path(f"year={month[0]:04d}") / f"month={month[1]:02d}" / f"batch={row['batch_index']:04d}"
        cp = layout.checkpoints / "native_units" / "1m" / part / f"{row['unit_id'][:20]}.json"
        canonical = layout.canonical_minute / part / f"{row['unit_id'][:20]}.parquet"
        _require(Path(str(accepted[1])).absolute() == cp.absolute()
                 and Path(str(accepted[3])).absolute() == canonical.absolute()
                 and accepted[5] in {"COMPLETE", "COMPLETE_WITH_QUARANTINE"},
                 "accepted unit path, status or source eligibility differs")
        check = _file(layout, cp, MAX_METADATA, accepted[2])
        b = _binding_from_plan(layout, row)
        _require(b.canonical_sha256 == accepted[4], "native checkpoint/inventory canonical hash disagrees")
        cp_obj = json.loads(cp.read_text(encoding="utf-8"))
        _require(not any(r.get("symbol") == "SPY" for r in cp_obj.get("provider_rejections", [])),
                 "selected SPY month includes provider rejection")
        unit = _file(layout, canonical, MAX_MINUTE_UNIT, accepted[4])
        clock_set = set(requested.values())
        con = connect_utc(":memory:", config={"threads": 2, "memory_limit": "512MB"})
        try:
            placeholders = ",".join("?" for _ in clock_set)
            physical = con.execute(
                "SELECT symbol,timestamp_utc,session_date,session_segment,close,timeframe,dataset,provider,source_id,is_adjusted "
                f"FROM read_parquet(?, hive_partitioning=false) WHERE symbol=? AND timestamp_utc IN ({placeholders})",
                [str(canonical), "SPY", *sorted(clock_set)],
            ).fetchall()
        finally:
            con.close()
        found = verify_physical_rows(physical, clock_set, row["unit_id"])
        for key in requested:
            observations[key] = {
                "raw_close": found.get(key),
                "status": "RAW_MINUTE_PRESENT" if key in found else "EXACT_MINUTE_MISSING",
                "source_unit_id": row["unit_id"], "canonical_sha256": unit["sha256"],
                "historical_available_at_utc": None,
            }
        unit_bindings.append({"month": f"{month[0]:04d}-{month[1]:02d}", "status": "ACCEPTED_UNIT_CHECKED",
                              "unit_id": row["unit_id"], "canonical_sha256": unit["sha256"],
                              "checkpoint_sha256": check["sha256"]})

    _require(len(observations) == demand["unique_clocks"],
             "one or more frozen SPY minute clocks were silently omitted")
    # Exact January 2020 link to the already inspected raw 22-clock report.
    prior = [r for r in old_report["observations"] if r["role"] == "PRIOR_REGULAR_CLOSE"]
    spot = next(r for r in old_report["observations"] if r["role"] == "DECISION_SPOT")
    calibration_rows = [*prior, spot]
    for row in calibration_rows:
        observed = observations.get(row["interval_start_utc"])
        _require(observed is not None and observed.get("raw_close") == row["raw_close"]
                 and observed.get("canonical_sha256") == row["canonical_sha256"]
                 and observed.get("source_unit_id") == row["source_unit_id"],
                 "first SPY pilot raw minute/calibration identity disagrees")
    projection = project_case_coverage(demand, observations)
    result = {
        "contract": CONTRACT, "status": "PHYSICAL_COVERAGE_REVIEW_ONLY_NO_PIT_INPUT_ACCEPTANCE",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "frozen_plan_fingerprint": demand["plan_fingerprint"],
        "retained_2020_calibration_fingerprint": old_report["report_fingerprint"],
        "accepted_native_source_fingerprint": native["acceptance_fingerprint"],
        "accepted_native_source_sha256": native_info["sha256"],
        "scanned_monthly_units": sum(u["status"] == "ACCEPTED_UNIT_CHECKED" for u in unit_bindings),
        "unavailable_months": [u["month"] for u in unit_bindings if u["status"] != "ACCEPTED_UNIT_CHECKED"],
        "target_months": len(months), "unique_exact_clocks_requested": demand["unique_clocks"],
        "observed_exact_clocks": sum(v["raw_close"] is not None for v in observations.values()),
        "target_weekly_cases": 411,
        "raw_complete_weekly_cases": projection["raw_complete"],
        "raw_incomplete_weekly_cases": projection["raw_with_gaps"],
        "cases": projection["cases"], "observations": observations, "unit_bindings": unit_bindings,
        "raw_close_source_qualified_for_features": False,
        "historical_publication_and_adjustment_qualified": False,
        "economic_log_returns": None, "forecast_total_variance": None,
        "historical_option_premiums": None, "pilot_input_acceptance": False,
        "protected_return_rows_read": 0, "option_outcomes_read": 0,
        "scan_scope": {"daily_units": 0, "monthly_minute_units": sum(u["status"] == "ACCEPTED_UNIT_CHECKED" for u in unit_bindings),
                       "corporate_action_pages": 0, "options": 0, "outcomes": 0, "provider_requests": 0},
        "authority": dict(AUTHORITY),
    }
    result["report_fingerprint"] = _fingerprint(result)
    return result
