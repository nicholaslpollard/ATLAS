from __future__ import annotations

"""Bounded cached facts for the pilot's fixed prior window, without acceptance.

The retained daily packet is reused. Only two exact minute units, accepted
inventory/plan metadata and the original corporate-action snapshot are read.
Calendar endpoints and recorded action dates are never publication clocks.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from packages.backtesting.b35_development_source import (
    _assert_native_path, _binding_from_plan, _validate_native_plan_record,
)
from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_acquisition import ACQUISITION_CONTRACT, SOURCE_SNAPSHOT_CONTRACT
from packages.data.alpaca_v2_postbuild import NATIVE_ACCEPTANCE_CONTRACT
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.duckdb_connection import connect_utc
from packages.data.intraday_semantics_audit import _action_symbols
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_input_packet_v1 import (
    CONTRACT as PACKET_CONTRACT, FEATURE_CUTOFF, requested_prior_sessions,
)
from packages.strategies.options_native_pair_v1 import decimal
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-options-native-cached-stock-input-review-v1"
MAX_METADATA = 4 * 1024 * 1024
MAX_PACKET = 256 * 1024
MAX_COMPRESSED = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_ACTION_COMPRESSED = 128 * 1024 * 1024
MAX_ACTION_EXPANDED = 512 * 1024 * 1024
MAX_LINE = 1024 * 1024
MAX_MINUTE_UNIT = 256 * 1024 * 1024
MAX_INVENTORY = 128 * 1024 * 1024
SHA = re.compile(r"^[0-9a-f]{64}$")
MONTHS = {(2019, 12), (2020, 1)}


class StockInputReviewError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RetainedPilotPacketBindingV1:
    relative_path: str
    raw_sha256: str
    report_fingerprint: str


DEFAULT_BINDING = RetainedPilotPacketBindingV1(
    "data/research/options_native_pilot_input_packet_v1/92c4d71997ec3225.json",
    "e02946c3390626bf8f1b1aee13081febfbc00ae100c8f1a8bf272e868a444459",
    "92c4d71997ec3225d5040f00375fc4ad66d654be6ce4a6cb81136a87d75374dc",
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file(layout: V2Layout, path: Path, maximum: int, expected_sha: str | None = None) -> dict:
    _assert_native_path(path, expected=path, root=layout.root, label="pilot cached input")
    if not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise StockInputReviewError(f"cached input missing or exceeds {maximum} bytes: {path}")
    actual = _sha(path)
    if expected_sha is not None and (not SHA.fullmatch(str(expected_sha)) or actual != expected_sha):
        raise StockInputReviewError(f"cached input hash drifted: {path.name}")
    return {"bytes": path.stat().st_size, "sha256": actual}


def _json(layout, path, expected_sha=None):
    record = _file(layout, path, MAX_METADATA, expected_sha)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StockInputReviewError(f"metadata must be an object: {path.name}")
    return value, record


def verify_retained_pilot_packet(raw: bytes, binding=DEFAULT_BINDING) -> dict[str, Any]:
    if len(raw) > MAX_PACKET or hashlib.sha256(raw).hexdigest() != binding.raw_sha256:
        raise StockInputReviewError("retained pilot packet bytes differ from the inspected upload")
    packet = json.loads(raw)
    if (not isinstance(packet, dict) or packet.get("report_fingerprint") != binding.report_fingerprint
            or _fingerprint({k: v for k, v in packet.items() if k != "report_fingerprint"}) != binding.report_fingerprint):
        raise StockInputReviewError("retained pilot packet signature drifted")
    required = {
        "contract": PACKET_CONTRACT, "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "feature_cutoff_utc": FEATURE_CUTOFF.isoformat(), "requested_closes": 21, "present_closes": 21,
        "missing_sessions": [], "pilot_input_acceptance": False, "historical_availability_qualified": False,
        "economic_log_returns": None, "forecast_total_variance": None,
    }
    if any(packet.get(k) != v for k, v in required.items()):
        raise StockInputReviewError("retained packet scope or authority drifted")
    if packet.get("authority") != dict(AUTHORITY) | {"raw_source_scans": 2}:
        raise StockInputReviewError("retained packet authority changed")
    rows = packet.get("prior_close_rows")
    if not isinstance(rows, list) or [r.get("session_date") for r in rows] != [d.isoformat() for d in requested_prior_sessions()]:
        raise StockInputReviewError("retained prior window is not the exact 21 sessions")
    calendar = get_market_calendar("XNYS")
    units = packet["lineage"]["unit_bindings"]
    if (len(units) != 2 or {r["year"] for r in units} != {2019, 2020}
            or canonical_sha256(units) != packet["lineage"]["unit_bindings_fingerprint"]
            or packet["lineage"]["protected_or_future_daily_partition_opened"] is not False):
        raise StockInputReviewError("retained unit lineage drifted")
    for row, day in zip(rows, requested_prior_sessions()):
        unit = next(u for u in units if u["year"] == day.year)
        if (row.get("symbol") != "SPY" or row.get("state") != "RAW_DAILY_CLOSE_PRESENT"
                or row.get("economic_return_qualified") is not False
                or row.get("calendar_boundary_is_publication_proof") is not False
                or row.get("historical_available_at_utc") is not None or row.get("observed_at_utc") is not None
                or row.get("calendar_regular_close_utc") != calendar.regular_open_close(day)[1].isoformat()
                or row.get("native_unit_id") != unit["unit_id"] or row.get("canonical_sha256") != unit["canonical_sha256"]):
            raise StockInputReviewError("retained row clock or source binding drifted")
        decimal(row["raw_close_float64_text"])
    return packet


def _gzip_records(path):
    expanded, count = 0, 0
    with gzip.open(path, "rb") as handle:
        while line := handle.readline(MAX_LINE + 1):
            expanded += len(line)
            if expanded > MAX_ACTION_EXPANDED or len(line) > MAX_LINE:
                raise StockInputReviewError(f"expanded cached ledger exceeds bound: {path.name}")
            if line.strip():
                count += 1
                if count > 2000000:
                    raise StockInputReviewError("cached record count exceeds bound")
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise StockInputReviewError("cached ledger record must be an object")
                yield record


def _minute_records(layout, packet):
    path = layout.manifests / "native_acquisition_plan.json"
    expected = next(r["sha256"] for r in packet["metadata_file_bindings"] if r["locator"].endswith("/native_acquisition_plan.json"))
    manifest, _ = _json(layout, path, expected)
    if any(manifest.get(k) != v for k, v in {
        "contract": ACQUISITION_CONTRACT, "status": "FROZEN", "v1_ancestry": "FORBIDDEN",
        "plan_sha256": packet["lineage"]["native_plan_sha256"],
        "plan_file_sha256": packet["lineage"]["native_plan_file_sha256"],
    }.items()):
        raise StockInputReviewError("native frozen plan lineage drifted")
    plan = layout.manifests / "native_acquisition_plan.jsonl.gz"
    _file(layout, plan, MAX_COMPRESSED, manifest["plan_file_sha256"])
    records, digest = [], hashlib.sha256()
    # Hash the complete expanded plan, selecting identities before opening data.
    expanded = 0
    with gzip.open(plan, "rb") as handle:
        for line_number in range(1, 1000002):
            line = handle.readline(MAX_LINE + 1)
            if not line:
                break
            expanded += len(line)
            if expanded > MAX_EXPANDED or len(line) > MAX_LINE or line_number > 1000000:
                raise StockInputReviewError("native plan exceeds expanded/line/count bound")
            digest.update(line)
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise StockInputReviewError("native plan record is not an object")
            if (row.get("canonical_timeframe") == "1m" and (row.get("year"), row.get("month")) in MONTHS
                    and "SPY" in (row.get("symbols") or [])):
                _validate_native_plan_record(row, line_number)
                start = date(row["year"], row["month"], 1)
                end = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
                if (row["provider_timeframe"] != "1Min" or row["window_start"] != start.isoformat()
                        or row["window_end_exclusive"] != end.isoformat() or row["batch_index"] < 0):
                    raise StockInputReviewError("minute provider timeframe drifted")
                records.append(row)
    if digest.hexdigest() != manifest["plan_sha256"] or sorted((r["year"], r["month"]) for r in records) != sorted(MONTHS):
        raise StockInputReviewError("frozen minute selection/hash is not exactly the two permitted months")
    return sorted(records, key=lambda r: (r["year"], r["month"]))


def _minute_facts(settings, layout, records, native, packet, progress):
    inventory = native["unit_inventory"]
    inventory_path = layout.validation / "native_unit_inventory.parquet"
    if Path(str(inventory["path"])).absolute() != inventory_path.absolute():
        raise StockInputReviewError("accepted inventory path changed")
    _file(layout, inventory_path, MAX_INVENTORY, inventory["sha256"])
    if inventory["sha256"] != native["source_binding"]["unit_inventory_sha256"]:
        raise StockInputReviewError("native acceptance inventory bindings disagree")
    con = connect_utc(":memory:", config={"threads": 2, "memory_limit": "512MB"})
    try:
        ids = [r["unit_id"] for r in records]
        inventory_rows = con.execute(
            "SELECT unit_id, checkpoint_path, checkpoint_sha256, canonical_path, canonical_sha256, status "
            "FROM read_parquet(?, hive_partitioning=false) WHERE unit_id IN (?, ?)",
            [str(inventory_path), *ids],
        ).fetchall()
    finally:
        con.close()
    by_id = {r[0]: r for r in inventory_rows}
    if len(inventory_rows) != 2 or set(by_id) != set(ids):
        raise StockInputReviewError("minute units are not unique accepted-inventory members")
    calendar = get_market_calendar("XNYS")
    requested = [(day, calendar.regular_open_close(day)[1] - timedelta(minutes=1), "PRIOR_REGULAR_CLOSE")
                 for day in requested_prior_sessions()]
    requested.append((FEATURE_CUTOFF.date(), FEATURE_CUTOFF - timedelta(minutes=1), "DECISION_SPOT"))
    found, bindings = {}, []
    for number, row in enumerate(records, 1):
        if progress:
            progress(f"minute unit {number}/2: {row['year']}-{row['month']:02d}; exact SPY clock predicate")
        part = Path(f"year={row['year']:04d}") / f"month={row['month']:02d}" / f"batch={row['batch_index']:04d}"
        checkpoint = layout.checkpoints / "native_units" / "1m" / part / f"{row['unit_id'][:20]}.json"
        canonical = layout.canonical_minute / part / f"{row['unit_id'][:20]}.parquet"
        accepted = by_id[row["unit_id"]]
        if Path(str(accepted[1])).absolute() != checkpoint.absolute() or Path(str(accepted[3])).absolute() != canonical.absolute() or accepted[5] not in {"COMPLETE", "COMPLETE_WITH_QUARANTINE"}:
            raise StockInputReviewError("accepted minute path or status drifted")
        cp = _file(layout, checkpoint, MAX_METADATA, accepted[2])
        binding = _binding_from_plan(layout, row)
        if binding.canonical_sha256 != accepted[4]:
            raise StockInputReviewError("minute checkpoint and accepted inventory disagree")
        body = json.loads(checkpoint.read_text(encoding="utf-8"))
        if any(r.get("symbol") == "SPY" for r in body.get("provider_rejections", [])):
            raise StockInputReviewError("SPY rejected in selected minute checkpoint")
        unit = _file(layout, canonical, MAX_MINUTE_UNIT, accepted[4])
        clocks = [stamp for day, stamp, _ in requested if (day.year, day.month) == (row["year"], row["month"])]
        con = connect_utc(":memory:", config={"threads": 2, "memory_limit": "512MB"})
        try:
            placeholders = ",".join("?" for _ in clocks)
            physical = con.execute(
                "SELECT symbol,timestamp_utc,session_date,session_segment,close,timeframe,dataset,provider,source_id,is_adjusted "
                f"FROM read_parquet(?, hive_partitioning=false) WHERE symbol=? AND timestamp_utc IN ({placeholders})",
                [str(canonical), "SPY", *clocks],
            ).fetchall()
        finally:
            con.close()
        for symbol, stamp, day, segment, close, timeframe, dataset, provider, source_id, adjusted in physical:
            if (not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() is None
                    or stamp.astimezone(UTC) not in clocks or stamp in found
                    or str(day) != stamp.astimezone(UTC).date().isoformat()
                    or adjusted is not False
                    or (symbol, segment, timeframe, dataset, provider, source_id, adjusted) !=
                    ("SPY", "regular", "1m", "stock_minute_aggregates", "alpaca", "alpaca:sip:1Min:raw:asof=-:v2:unit=" + row["unit_id"], False)):
                raise StockInputReviewError("duplicate minute key, clock or raw provenance drifted")
            value = decimal(str(close))
            found[stamp] = {"raw_close": str(value), "unit_id": row["unit_id"], "canonical_sha256": unit["sha256"]}
        bindings.append({"year": row["year"], "month": row["month"], "unit_id": row["unit_id"],
                         "canonical_locator": canonical.relative_to(settings.project_root.resolve()).as_posix(),
                         "canonical_sha256": unit["sha256"], "canonical_bytes": unit["bytes"], "checkpoint_sha256": cp["sha256"]})
    daily = {r["session_date"]: r["raw_close_float64_text"] for r in packet["prior_close_rows"]}
    observations = []
    for day, stamp, role in requested:
        value = found.get(stamp)
        original = daily.get(day.isoformat())
        observations.append({"role": role, "session_date": day.isoformat(),
                             "interval_start_utc": stamp.isoformat(), "interval_end_utc": (stamp + timedelta(minutes=1)).isoformat(),
                             "state": "EXACT_CACHED_MINUTE_PRESENT" if value else "MISSING_EXACT_MINUTE_NO_FALLBACK",
                             "raw_close": value["raw_close"] if value else None,
                             "source_unit_id": value["unit_id"] if value else None,
                             "canonical_sha256": value["canonical_sha256"] if value else None,
                             "retained_daily_close": original,
                             "minute_minus_daily": str(decimal(value["raw_close"]) - decimal(original)) if value and original else None,
                             "historical_available_at_utc": None, "interval_end_is_publication_proof": False,
                             "economic_return_qualified": False, "pilot_eligible": False})
    return observations, bindings


def _corporate_action_facts(layout, native):
    snapshot_path = layout.manifests / "source_snapshot.json"
    snapshot, snapshot_file = _json(layout, snapshot_path, native["source_binding"]["source_snapshot_sha256"])
    if any(snapshot.get(k) != v for k, v in {"contract": SOURCE_SNAPSHOT_CONTRACT, "status": "COMPLETE", "v1_ancestry": "FORBIDDEN"}.items()):
        raise StockInputReviewError("accepted source snapshot identity drifted")
    manifest, manifest_file = _json(layout, layout.manifests / "corporate_actions.json")
    if (manifest.get("contract") != SOURCE_SNAPSHOT_CONTRACT or manifest.get("status") != "COMPLETE"
            or manifest.get("native_actions") != snapshot.get("corporate_actions_native")
            or manifest.get("raw_bundle") != snapshot.get("corporate_actions_raw_bundle")
            or manifest.get("page_count") != len(manifest.get("pages", []))
            or manifest.get("page_count") != snapshot.get("corporate_action_page_count")
            or manifest.get("action_record_count") != snapshot.get("corporate_action_record_count")):
        raise StockInputReviewError("corporate-action manifest differs from accepted source snapshot")
    if any(not isinstance(p, dict) or not SHA.fullmatch(str(p.get("sha256", ""))) for p in manifest["pages"]):
        raise StockInputReviewError("corporate-action page receipt identity malformed")
    ledger_path = layout.corporate_actions / "native_actions.jsonl.gz"
    raw_path = layout.source / "corporate_actions" / "complete_pages.concat.json.gz"
    for key, path in (("native_actions", ledger_path), ("raw_bundle", raw_path)):
        if Path(str(manifest[key]["path"])).absolute() != path.absolute():
            raise StockInputReviewError("corporate-action path changed")
    ledger_file = _file(layout, ledger_path, MAX_ACTION_COMPRESSED, manifest["native_actions"]["sha256"])
    raw_file = _file(layout, raw_path, MAX_ACTION_COMPRESSED, manifest["raw_bundle"]["sha256"])
    selected, seen, total = [], set(), 0
    first, last = requested_prior_sessions()[0], requested_prior_sessions()[-1]
    for record in _gzip_records(ledger_path):
        total += 1
        body, kind = record.get("payload"), record.get("action_type")
        page, index = record.get("source_page_index"), record.get("source_record_index")
        if (not isinstance(body, dict) or not isinstance(kind, str) or not kind
                or type(page) is not int or not 0 <= page < manifest["page_count"] or type(index) is not int or index < 0):
            raise StockInputReviewError("corporate-action row source identity malformed")
        key = (kind, page, index)
        if key in seen:
            raise StockInputReviewError("duplicate corporate-action source ordinal")
        seen.add(key)
        if "SPY" not in _action_symbols(body):
            continue
        candidates = [body[k] for k in ("ex_date", "effective_date", "execution_date") if body.get(k) is not None]
        dates = []
        for value in candidates:
            try:
                dates.append(date.fromisoformat(value))
            except (ValueError, TypeError):
                raise StockInputReviewError("SPY effective-date field malformed")
        if dates and not any(first <= day <= last for day in dates):
            continue
        selected.append({"action_type": kind, "source_page_index": page, "source_record_index": index,
                         "manifest_recorded_source_page_sha256": manifest["pages"][page]["sha256"], "payload": body,
                         "effective_date_state": "RECORDED_DATES_REQUIRE_TYPE_SPECIFIC_REVIEW" if dates else "UNKNOWN_EFFECTIVE_DATE",
                         "historical_available_at_utc": None, "point_in_time_qualified": False})
        if len(selected) > 1000 or len(json.dumps(selected)) > MAX_PACKET:
            raise StockInputReviewError("selected SPY action evidence exceeds output bound")
    if total != manifest["action_record_count"]:
        raise StockInputReviewError("corporate-action ledger population differs from accepted snapshot")
    return {"source_snapshot_sha256": snapshot_file["sha256"], "action_manifest_sha256": manifest_file["sha256"],
            "native_actions_sha256": ledger_file["sha256"], "raw_bundle_sha256": raw_file["sha256"],
            "snapshot_captured_at_utc": snapshot.get("captured_at_utc"), "process_date_scope": [manifest.get("start"), manifest.get("cutoff")],
            "cached_record_count": total, "selected_spy_records": selected,
            "effective_date_coverage_qualified": False, "historical_publication_qualified": False,
            "individual_raw_pages_reparsed": False,
            "empty_selection_proves_no_actions": False}


def review_options_native_stock_inputs(settings: AtlasSettings, *, binding=DEFAULT_BINDING,
                                       progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    packet_path = settings.resolved_path(binding.relative_path)
    if packet_path.is_symlink() or not packet_path.is_file() or packet_path.stat().st_size > MAX_PACKET:
        raise StockInputReviewError("named retained input packet missing, linked or oversized")
    packet = verify_retained_pilot_packet(packet_path.read_bytes(), binding)
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    expected_native = next(r["sha256"] for r in packet["metadata_file_bindings"] if r["locator"].endswith("/native_acceptance.json"))
    native, native_file = _json(layout, layout.validation / "native_acceptance.json", expected_native)
    if any(native.get(k) != v for k, v in {
        "contract": NATIVE_ACCEPTANCE_CONTRACT, "status": "PASS", "v1_ancestry": "FORBIDDEN",
        "protected_return_rows_read": 0, "production_promoted": False,
        "acceptance_fingerprint": packet["lineage"]["native_acceptance_fingerprint"],
    }.items()) or "SPY" in native.get("excluded_symbols", []):
        raise StockInputReviewError("native acceptance scope or SPY eligibility drifted")
    if progress:
        progress("retained packet verified; selecting two frozen SPY minute units without daily reread")
    records = _minute_records(layout, packet)
    observations, units = _minute_facts(settings, layout, records, native, packet, progress)
    if progress:
        progress("verifying accepted corporate-action snapshot; projecting SPY effective-date candidates")
    actions = _corporate_action_facts(layout, native)
    missing = [r["interval_start_utc"] for r in observations if r["raw_close"] is None]
    result = {
        "contract": CONTRACT, "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "status": "PARTIAL_CACHED_STOCK_INPUT_EVIDENCE_WITH_GAPS" if missing else "COMPLETE_CACHED_STOCK_INPUT_EVIDENCE_WITH_GAPS",
        "retained_packet_raw_sha256": binding.raw_sha256, "retained_packet_fingerprint": binding.report_fingerprint,
        "feature_cutoff_utc": FEATURE_CUTOFF.isoformat(), "native_acceptance_fingerprint": native["acceptance_fingerprint"],
        "native_acceptance_file_sha256": native_file["sha256"], "minute_unit_bindings": units,
        "requested_minute_observations": len(observations), "present_minute_observations": len(observations) - len(missing),
        "missing_minute_clocks": missing, "observations": observations, "corporate_actions": actions,
        "daily_minute_difference_establishes_error_or_replacement": False,
        "economic_log_returns": None, "forecast_total_variance": None, "pilot_input_acceptance": False,
        "qualification_gaps": ["REGULAR_CLOSE_PRICE_SEMANTICS_REVIEW_REQUIRED", "PIT_ECONOMIC_ACTION_TREATMENT_AND_COVERAGE_REQUIRED",
                               "HISTORICAL_AVAILABILITY_OR_QUALIFIED_BOUNDED_MODEL_REQUIRED", "EXACT_OPTION_PAIR_INPUTS_AND_BROKER_EXECUTION_OPEN"],
        "scan_scope": {"daily_units_reread": 0, "minute_units": 2, "corporate_action_ledgers": 1,
                       "raw_provider_bodies_parsed": 0, "option_histories": 0, "outcomes_computed": 0},
        "authority": dict(AUTHORITY) | {"raw_source_scans": 3},
    }
    result["report_fingerprint"] = _fingerprint(result)
    return result
