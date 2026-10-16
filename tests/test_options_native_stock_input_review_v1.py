from datetime import UTC, date, datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from test_options_native_pilot_input_packet_v1 import native, sha, write_json, write_parquet
from packages.core.market_calendar import get_market_calendar
from packages.data import options_native_pilot_input_packet_v1 as packet
from packages.data import options_native_stock_input_review_v1 as review
from packages.data.alpaca_v2_acquisition import SOURCE_SNAPSHOT_CONTRACT, UNIT_CONTRACT
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts import review_options_native_stock_inputs_v1 as cli


def reseal(ctx):
    """Publish internally consistent invented source bytes, never workstation acceptance."""
    layout = ctx["layout"]
    inventory = []
    for record, canonical, checkpoint in ctx["units"]:
        write_json(checkpoint, {
            "contract": UNIT_CONTRACT, "status": "COMPLETE", "unit_id": record["unit_id"], "unit": record,
            "policy_sha256": record["policy_sha256"], "universe_sha256": record["universe_sha256"],
            "canonical": {"path": str(canonical), "sha256": sha(canonical)}, "provider_rejections": [],
        })
        inventory.append({"unit_id": record["unit_id"], "checkpoint_path": str(checkpoint),
                          "checkpoint_sha256": sha(checkpoint), "canonical_path": str(canonical),
                          "canonical_sha256": sha(canonical), "status": "COMPLETE"})
    inv = layout.validation / "native_unit_inventory.parquet"
    write_parquet(inv, inventory)
    plan_path = layout.manifests / "native_acquisition_plan.jsonl.gz"
    raw = ("\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in ctx["records"]) + "\n").encode()
    plan_path.write_bytes(gzip.compress(raw, mtime=0))
    pm = layout.manifests / "native_acquisition_plan.json"
    manifest = json.loads(pm.read_text())
    manifest.update(plan_file_sha256=sha(plan_path), plan_sha256=hashlib.sha256(raw).hexdigest())
    write_json(pm, manifest)
    actions_path = layout.corporate_actions / "native_actions.jsonl.gz"
    actions_path.parent.mkdir(parents=True, exist_ok=True)
    actions_path.write_bytes(gzip.compress(("\n".join(json.dumps(r) for r in ctx["actions"]) + "\n").encode(), mtime=0))
    raw_path = layout.source / "corporate_actions" / "complete_pages.concat.json.gz"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_page = json.dumps({"corporate_actions": {"fixture": [r["payload"] for r in ctx["actions"]]}}).encode()
    raw_path.write_bytes(gzip.compress(raw_page, mtime=0))
    action_manifest = {
        "contract": SOURCE_SNAPSHOT_CONTRACT, "status": "COMPLETE", "start": "2016-01-01", "cutoff": "2026-09-01",
        "page_count": 1, "action_record_count": len(ctx["actions"]), "data_quality": "complete",
        "pages": [{"sha256": hashlib.sha256(raw_page).hexdigest(), "captured_at_utc": "2026-09-01T12:00:00+00:00"}],
        "native_actions": {"path": str(actions_path), "sha256": sha(actions_path)},
        "raw_bundle": {"path": str(raw_path), "sha256": sha(raw_path)},
    }
    write_json(layout.manifests / "corporate_actions.json", action_manifest)
    snap = layout.manifests / "source_snapshot.json"
    write_json(snap, {"contract": SOURCE_SNAPSHOT_CONTRACT, "status": "COMPLETE", "v1_ancestry": "FORBIDDEN",
                     "corporate_action_page_count": 1, "corporate_action_record_count": len(ctx["actions"]),
                     "corporate_actions_native": action_manifest["native_actions"],
                     "corporate_actions_raw_bundle": action_manifest["raw_bundle"],
                     "captured_at_utc": "2026-09-01T12:00:00+00:00"})
    na = layout.validation / "native_acceptance.json"
    body = json.loads(na.read_text())
    body["unit_inventory"] = {"path": str(inv), "sha256": sha(inv)}
    body["source_binding"] = {"source_snapshot_sha256": sha(snap), "unit_inventory_sha256": sha(inv), "plan_manifest_sha256": sha(pm)}
    write_json(na, body)
    artifact = packet.build_options_native_pilot_input_packet(ctx["settings"])
    target = ctx["settings"].project_root / "data/research/options_native_pilot_input_packet_v1/fixture.json"
    write_json(target, artifact)
    ctx["packet_path"] = target
    ctx["binding"] = review.RetainedPilotPacketBindingV1(
        target.relative_to(ctx["settings"].project_root).as_posix(), sha(target), artifact["report_fingerprint"],
    )


@pytest.fixture
def source(native):
    settings, layout, daily, checkpoints = native
    records = [json.loads(line) for line in gzip.decompress((layout.manifests / "native_acquisition_plan.jsonl.gz").read_bytes()).splitlines()]
    units = list(zip(records, daily, checkpoints))
    calendar = get_market_calendar("XNYS")
    requested = [(d, calendar.regular_open_close(d)[1] - timedelta(minutes=1), 300.0 + n)
                 for n, d in enumerate(packet.requested_prior_sessions())]
    requested.append((date(2020, 1, 6), packet.FEATURE_CUTOFF - timedelta(minutes=1), 345.25))
    for year, month in sorted(review.MONTHS):
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        base = {"provider_timeframe": "1Min", "canonical_timeframe": "1m", "window_start": start.isoformat(),
                "window_end_exclusive": end.isoformat(), "year": year, "month": month, "batch_index": 0,
                "symbols": ["AAA", "SPY"], "policy_sha256": "a" * 64, "universe_sha256": "b" * 64}
        uid = hashlib.sha256(json.dumps({"contract": UNIT_CONTRACT, **{k: v for k, v in base.items()
                                      if k not in {"canonical_timeframe", "year", "month"}}},
                                      sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        record = {"unit_id": uid, **base}
        records.append(record)
        part = Path(f"year={year}") / f"month={month:02d}" / "batch=0000"
        canonical = layout.canonical_minute / part / f"{uid[:20]}.parquet"
        checkpoint = layout.checkpoints / "native_units/1m" / part / f"{uid[:20]}.json"
        rows = [{"symbol": "SPY", "timestamp_utc": stamp, "session_date": day, "session_segment": "regular",
                 "close": value + (0.05 if day == date(2019, 12, 20) else 0), "timeframe": "1m",
                 "dataset": "stock_minute_aggregates", "provider": "alpaca",
                 "source_id": "alpaca:sip:1Min:raw:asof=-:v2:unit=" + uid, "is_adjusted": False}
                for day, stamp, value in requested if (day.year, day.month) == (year, month)]
        if year == 2020:
            # The 10:00-starting bar ends after cutoff and must not be selected.
            rows.append({**rows[-1], "timestamp_utc": packet.FEATURE_CUTOFF, "close": -999.0})
        write_parquet(canonical, rows)
        units.append((record, canonical, checkpoint))
    actions = [{"action_type": kind, "source_page_index": 0, "source_record_index": i, "payload": body}
               for i, (kind, body) in enumerate((
                   ("cash_dividends", {"symbol": "SPY", "ex_date": "2019-12-20", "rate": "1.25", "declaration_date": "2019-12-19"}),
                   ("cash_dividends", {"symbol": "AAA", "ex_date": "2019-12-20", "rate": "2.0"}),
                   ("forward_splits", {"symbol": "SPY", "ex_date": "2020-02-03", "new_rate": "2", "old_rate": "1"}),
                   ("reorganizations", {"old_symbol": "SPY", "new_symbol": "SPY"}),
               ))]
    ctx = {"settings": settings, "layout": layout, "records": records, "units": units, "actions": actions, "daily": daily}
    reseal(ctx)
    return ctx


def inspect(ctx):
    return review.review_options_native_stock_inputs(ctx["settings"], binding=ctx["binding"])


def rewrite_unit(ctx, number, transform):
    path = ctx["units"][number][1]
    con = duckdb.connect(":memory:")
    try:
        frame = con.execute("SELECT * FROM read_parquet(?, hive_partitioning=false)", [str(path)]).fetchdf()
    finally:
        con.close()
    rows = transform(frame.to_dict("records"))
    for row in rows:
        if isinstance(row["session_date"], datetime):
            row["session_date"] = row["session_date"].date()
    write_parquet(path, rows)
    reseal(ctx)


def test_two_exact_accepted_minute_units_and_action_snapshot_without_repeating_daily_scan(source):
    source["daily"][0].unlink()
    source["daily"][1].unlink()
    report = inspect(source)
    assert report["requested_minute_observations"] == report["present_minute_observations"] == 22
    assert report["scan_scope"]["daily_units_reread"] == 0
    assert report["observations"][-1]["raw_close"] == "345.25"
    assert report["observations"][-1]["interval_start_utc"] == "2020-01-06T14:59:00+00:00"
    early = next(r for r in report["observations"] if r["session_date"] == "2019-12-24")
    assert early["interval_end_utc"] == "2019-12-24T18:00:00+00:00"
    assert sum(r["minute_minus_daily"] not in (None, "0.0", "0.00") for r in report["observations"][:-1]) == 1
    assert report["economic_log_returns"] is report["forecast_total_variance"] is None
    assert report["daily_minute_difference_establishes_error_or_replacement"] is False
    assert report["pilot_input_acceptance"] is False
    assert all(not r["pilot_eligible"] and r["historical_available_at_utc"] is None for r in report["observations"])
    assert report["report_fingerprint"] == _fingerprint({k: v for k, v in report.items() if k != "report_fingerprint"})
    assert not any(v for k, v in report["authority"].items() if k != "raw_source_scans")


def test_action_candidates_keep_unknowns_and_revisions_without_imputing_publication_or_zero(source):
    report = inspect(source)
    facts = report["corporate_actions"]
    assert len(facts["selected_spy_records"]) == 2
    assert facts["selected_spy_records"][0]["payload"]["rate"] == "1.25"
    assert facts["selected_spy_records"][1]["effective_date_state"] == "UNKNOWN_EFFECTIVE_DATE"
    assert not facts["empty_selection_proves_no_actions"]
    assert not facts["effective_date_coverage_qualified"]
    assert not facts["historical_publication_qualified"]
    assert facts["snapshot_captured_at_utc"].startswith("2026-")


def test_missing_exact_bar_remains_a_gap_without_daily_or_other_minute_fallback(source):
    rewrite_unit(source, -1, lambda rows: [r for r in rows if r["timestamp_utc"] != packet.FEATURE_CUTOFF - timedelta(minutes=1)])
    report = inspect(source)
    assert report["present_minute_observations"] == 21
    assert report["observations"][-1]["raw_close"] is None
    assert report["status"].startswith("PARTIAL_")


@pytest.mark.parametrize("component", ["minute", "checkpoint", "inventory", "plan", "native", "snapshot", "actions", "raw_bundle", "packet"])
def test_pinned_byte_or_source_binding_drift_blocks_without_rebuild(source, component):
    layout = source["layout"]
    paths = {"minute": source["units"][-1][1], "checkpoint": source["units"][-1][2],
             "inventory": layout.validation / "native_unit_inventory.parquet",
             "plan": layout.manifests / "native_acquisition_plan.jsonl.gz", "native": layout.validation / "native_acceptance.json",
             "snapshot": layout.manifests / "source_snapshot.json", "actions": layout.corporate_actions / "native_actions.jsonl.gz",
             "raw_bundle": layout.source / "corporate_actions/complete_pages.concat.json.gz", "packet": source["packet_path"]}
    target = paths[component]
    target.write_bytes(target.read_bytes() + b"drift")
    with pytest.raises((ValueError, RuntimeError)):
        inspect(source)


@pytest.mark.parametrize("change", ["duplicate", "adjusted", "wrong_source", "zero_price"])
def test_selected_minute_provenance_or_identity_error_blocks_even_with_new_fixture_hashes(source, change):
    def alter(rows):
        if change == "duplicate":
            return [*rows, rows[0]]
        key, value = {"adjusted": ("is_adjusted", True), "wrong_source": ("source_id", "unqualified"), "zero_price": ("close", 0)}[change]
        rows[0][key] = value
        return rows
    rewrite_unit(source, -1, alter)
    with pytest.raises((ValueError, RuntimeError)):
        inspect(source)


@pytest.mark.parametrize("limit", ["MAX_METADATA", "MAX_COMPRESSED", "MAX_EXPANDED", "MAX_LINE", "MAX_MINUTE_UNIT", "MAX_INVENTORY", "MAX_ACTION_COMPRESSED", "MAX_ACTION_EXPANDED"])
def test_all_resource_limits_block_before_unbounded_read(source, monkeypatch, limit):
    monkeypatch.setattr(review, limit, 1)
    with pytest.raises((ValueError, RuntimeError), match="bound|exceeds"):
        inspect(source)


def test_empty_action_selection_does_not_become_qualified_no_action_coverage(source):
    source["actions"] = [source["actions"][1]]
    reseal(source)
    result = inspect(source)["corporate_actions"]
    assert result["selected_spy_records"] == []
    assert result["effective_date_coverage_qualified"] is False
    assert result["empty_selection_proves_no_actions"] is False


def test_accepted_checkpoint_hash_blocks_later_self_signed_replacement(source):
    path = source["units"][-1][2]
    body = json.loads(path.read_text())
    body["new_unaccepted_note"] = "later generation"
    write_json(path, body)
    with pytest.raises(ValueError, match="hash drifted"):
        inspect(source)


def test_multiple_revision_candidates_are_not_deduplicated_into_a_convenient_history(source):
    revision = dict(source["actions"][0])
    revision["source_record_index"] = 999
    revision["payload"] = {**revision["payload"], "rate": "1.3", "updated_at": "2026-09-01T12:00:00Z"}
    source["actions"].append(revision)
    reseal(source)
    selected = inspect(source)["corporate_actions"]["selected_spy_records"]
    assert len(selected) == 3
    assert [r["payload"]["rate"] for r in selected if r["action_type"] == "cash_dividends"] == ["1.25", "1.3"]
    assert all(r["point_in_time_qualified"] is False for r in selected)


def test_symlinked_canonical_minute_is_rejected(source, tmp_path):
    path = source["units"][-1][1]
    moved = tmp_path / "redirected.parquet"
    moved.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(moved)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(RuntimeError, match="symlink"):
        inspect(source)


def test_duplicate_native_action_source_ordinal_is_not_silently_deduplicated(source):
    source["actions"].append(dict(source["actions"][0]))
    reseal(source)
    with pytest.raises(ValueError, match="duplicate corporate-action source ordinal"):
        inspect(source)


def test_cli_saves_small_reproducible_report_and_preserves_source_files(source, monkeypatch, capsys):
    before = {p: sha(p) for p in source["layout"].root.rglob("*") if p.is_file()}
    monkeypatch.setattr(cli, "ROOT", source["settings"].project_root)
    monkeypatch.setattr(cli, "load_settings", lambda *_: source["settings"])
    monkeypatch.setattr(cli, "DEFAULT_BINDING", source["binding"])
    monkeypatch.setattr(cli, "review_options_native_stock_inputs", lambda settings, **kwargs: review.review_options_native_stock_inputs(settings, binding=source["binding"], **kwargs))
    assert cli.main(["--save-report"]) == 0
    assert cli.main(["--save-report"]) == 0
    files = list((source["settings"].project_root / "data/research/options_native_stock_input_review_v1").glob("*.json"))
    assert len(files) == 1 and files[0].stat().st_size < 32 * 1024
    assert {p: sha(p) for p in before} == before
    assert "UNQUALIFIED" in capsys.readouterr().out
    files[0].write_text("original retained conflict")
    assert cli.main(["--save-report"]) == 3
    assert files[0].read_text() == "original retained conflict"


def test_uploaded_packet_semantics_cannot_gain_authority_by_resigning(source):
    body = json.loads(source["packet_path"].read_text())
    body["pilot_input_acceptance"] = True
    body["report_fingerprint"] = _fingerprint({k: v for k, v in body.items() if k != "report_fingerprint"})
    raw = json.dumps(body).encode()
    binding = review.RetainedPilotPacketBindingV1("fixture", hashlib.sha256(raw).hexdigest(), body["report_fingerprint"])
    with pytest.raises(ValueError, match="scope or authority"):
        review.verify_retained_pilot_packet(raw, binding)
