from dataclasses import replace
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from packages.backtesting import successor_spy_benchmark_source as source
from packages.core.settings import load_settings
from packages.data import options_native_pilot_input_packet_v1 as packet
from packages.data.alpaca_v2_acquisition import ACQUISITION_CONTRACT, UNIT_CONTRACT
from packages.data.alpaca_v2_postbuild import NATIVE_ACCEPTANCE_CONTRACT, RESEARCH_DAILY_CONTRACT
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts import inspect_options_native_pilot_inputs_v1 as cli

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def write_parquet(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        con.register("fixture", pd.DataFrame(rows))
        con.execute("COPY fixture TO '" + path.as_posix().replace("'", "''") + "' (FORMAT PARQUET)")
    finally:
        con.close()


@pytest.fixture
def native(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_EXTERNAL_DATA_ROOT", raising=False)
    project = tmp_path / "atlas"
    project.mkdir()
    settings = load_settings(ROOT, "development").model_copy(update={"project_root": project})
    layout = V2Layout.beneath((project / "data").resolve())
    requested = packet.requested_prior_sessions()
    records, canonicals, checkpoints = [], [], []
    for year in (2019, 2020):
        base = {
            "provider_timeframe": "1Day", "canonical_timeframe": "1d",
            "window_start": f"{year}-01-01", "window_end_exclusive": f"{year + 1}-01-01",
            "year": year, "month": None, "batch_index": 0, "symbols": ["AAA", "SPY"],
            "policy_sha256": "a" * 64, "universe_sha256": "b" * 64,
        }
        unit = hashlib.sha256(json.dumps(
            {"contract": UNIT_CONTRACT, **{k: v for k, v in base.items()
             if k not in {"canonical_timeframe", "year", "month"}}},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        record = {"unit_id": unit, **base}
        records.append(record)
        partition = Path(f"year={year}") / "batch=0000"
        canonical = layout.canonical_daily / partition / f"{unit[:20]}.parquet"
        checkpoint = layout.checkpoints / "native_units" / "1d" / partition / f"{unit[:20]}.json"
        rows = [{"symbol": "SPY", "session_date": day, "close": 300.0 + n,
                 "provider": "alpaca", "dataset": "stock_daily_aggregates", "timeframe": "1d",
                 "session_segment": "regular", "is_adjusted": False,
                 "source_id": f"alpaca:sip:1Day:raw:asof=-:v2:unit={unit}"}
                for n, day in enumerate(requested) if day.year == year]
        # Validated bytes can contain later rows. The bounded SQL projection
        # must never expose them as this decision's inputs or inspect their price.
        rows += [{**rows[0], "session_date": date(2019, 1, 2) if year == 2019 else date(2020, 12, 31), "close": -999.0}]
        write_parquet(canonical, rows)
        write_json(checkpoint, {
            "contract": UNIT_CONTRACT, "status": "COMPLETE", "unit_id": unit, "unit": record,
            "policy_sha256": base["policy_sha256"], "universe_sha256": base["universe_sha256"],
            "canonical": {"path": str(canonical), "sha256": sha(canonical)}, "provider_rejections": [],
        })
        canonicals.append(canonical)
        checkpoints.append(checkpoint)
    raw = ("\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in records) + "\n").encode()
    layout.manifests.mkdir(parents=True, exist_ok=True)
    plan = layout.manifests / "native_acquisition_plan.jsonl.gz"
    plan.write_bytes(gzip.compress(raw, mtime=0))
    write_json(layout.manifests / "native_acquisition_plan.json", {
        "contract": ACQUISITION_CONTRACT, "status": "FROZEN", "v1_ancestry": "FORBIDDEN",
        "plan_sha256": hashlib.sha256(raw).hexdigest(), "plan_file_sha256": sha(plan),
    })
    inventory = layout.validation / "native_unit_inventory.parquet"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_bytes(b"hash-only fixture inventory; never scanned")
    write_json(layout.validation / "native_acceptance.json", {
        "contract": NATIVE_ACCEPTANCE_CONTRACT, "status": "PASS", "v1_ancestry": "FORBIDDEN",
        "protected_return_rows_read": 0, "production_promoted": False,
        "acceptance_fingerprint": "c" * 64, "excluded_symbols": [],
        "unit_inventory": {"path": str(inventory), "sha256": sha(inventory)},
    })
    write_json(layout.manifests / "research_daily.json", {
        "contract": RESEARCH_DAILY_CONTRACT, "status": "PASS", "v1_ancestry": "FORBIDDEN",
        "v1_rows_read": 0, "historical_performance_opened": False, "production_promoted": False,
        "paper_authority": False, "live_authority": False, "cash_dividend_credits_materialized": False,
        "development_only": True, "protected_return_rows_materialized": 0,
        "master_protected_return_rows_read": 0, "master_protected_holdout_consumed": False,
        "source_fingerprint": "d" * 64, "native_acceptance_fingerprint": "c" * 64,
    })
    # The reader cannot fall back to this protected partition, even when a
    # requested prior close is missing from an otherwise valid unit.
    trap = layout.canonical_daily / "year=2026" / "do-not-open.parquet"
    trap.parent.mkdir(parents=True)
    trap.write_bytes(b"protected partition trap")
    return settings, layout, canonicals, checkpoints


def test_real_native_reader_produces_only_fixed_prior_raw_rows_and_explicit_gaps(native):
    settings, _, _, _ = native
    report = packet.build_options_native_pilot_input_packet(settings)
    assert report["present_closes"] == report["requested_closes"] == 21
    assert report["prior_close_rows"][0]["session_date"] == "2019-12-04"
    assert report["prior_close_rows"][-1]["session_date"] == "2020-01-03"
    early_close = next(r for r in report["prior_close_rows"] if r["session_date"] == "2019-12-24")
    assert early_close["calendar_regular_close_utc"] == "2019-12-24T18:00:00+00:00"
    assert early_close["historical_available_at_utc"] is None
    assert report["economic_log_returns"] is report["forecast_total_variance"] is None
    assert report["pilot_input_acceptance"] is False
    assert report["historical_availability_qualified"] is False
    assert report["authority"]["raw_source_scans"] == 2
    assert not any(v for k, v in report["authority"].items() if k != "raw_source_scans")
    assert len(report["metadata_file_bindings"]) == 3
    assert report["report_fingerprint"] == _fingerprint({k: v for k, v in report.items() if k != "report_fingerprint"})


def test_opt_in_bounded_reader_and_legacy_reader_have_identical_selected_rows_and_lineage(native):
    settings, _, _, _ = native
    sessions = packet.requested_prior_sessions()
    a, al = source._daily_fallback_rows(settings, requested_sessions=sessions)
    b, bl = source._daily_fallback_rows(settings, requested_sessions=sessions, read_limits=packet.READ_LIMITS)
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))
    assert al == bl


def test_missing_prior_close_is_retained_without_cross_session_fill_or_alternate_source(native):
    settings, _, canonicals, checkpoints = native
    con = duckdb.connect(":memory:")
    frame = con.execute("SELECT * FROM read_parquet(?)", [str(canonicals[1])]).fetchdf()
    con.close()
    frame = frame.iloc[1:]
    write_parquet(canonicals[1], frame.to_dict("records"))
    checkpoint = json.loads(checkpoints[1].read_text())
    checkpoint["canonical"]["sha256"] = sha(canonicals[1])
    write_json(checkpoints[1], checkpoint)
    report = packet.build_options_native_pilot_input_packet(settings)
    assert report["present_closes"] == 20
    assert report["missing_sessions"] == ["2020-01-02"]
    assert report["prior_close_rows"][-2]["raw_close_float64_text"] is None
    assert report["status"] == "PARTIAL_RAW_INPUT_PACKET_WITH_GAPS"


@pytest.mark.parametrize("component", ["canonical", "inventory", "plan", "checkpoint", "acceptance"])
def test_source_hash_or_identity_drift_blocks_before_a_packet_is_accepted(native, component):
    settings, layout, canonicals, checkpoints = native
    if component == "canonical":
        canonicals[0].write_bytes(canonicals[0].read_bytes() + b"drift")
    elif component == "inventory":
        (layout.validation / "native_unit_inventory.parquet").write_bytes(b"drift")
    elif component == "plan":
        (layout.manifests / "native_acquisition_plan.jsonl.gz").write_bytes(b"drift")
    elif component == "checkpoint":
        body = json.loads(checkpoints[0].read_text())
        body["unit"]["symbols"] = ["SPY"]
        write_json(checkpoints[0], body)
    else:
        path = layout.validation / "native_acceptance.json"
        body = json.loads(path.read_text())
        body["acceptance_fingerprint"] = "e" * 64
        write_json(path, body)
    with pytest.raises(RuntimeError):
        packet.build_options_native_pilot_input_packet(settings)


@pytest.mark.parametrize("limit", [
    "metadata_bytes", "compressed_plan_bytes", "expanded_plan_bytes", "plan_line_bytes",
    "inventory_bytes", "canonical_unit_bytes",
])
def test_all_resource_bounds_fail_without_fallback(native, monkeypatch, limit):
    settings, _, _, _ = native
    monkeypatch.setattr(packet, "READ_LIMITS", replace(packet.READ_LIMITS, **{limit: 1}))
    with pytest.raises(RuntimeError, match="bound|exceeds"):
        packet.build_options_native_pilot_input_packet(settings)


def test_symlinked_native_unit_is_rejected(native, tmp_path):
    settings, _, canonicals, _ = native
    moved = tmp_path / "redirected.parquet"
    moved.write_bytes(canonicals[0].read_bytes())
    canonicals[0].unlink()
    try:
        canonicals[0].symlink_to(moved)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(RuntimeError, match="symlink"):
        packet.build_options_native_pilot_input_packet(settings)


def test_cli_saves_one_small_deterministic_packet_without_changing_sources(native, monkeypatch, capsys):
    settings, layout, _, _ = native
    before = {p: sha(p) for p in layout.root.rglob("*") if p.is_file()}
    monkeypatch.setattr(cli, "ROOT", settings.project_root)
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    assert cli.main(["--save-report"]) == 0
    assert cli.main(["--save-report"]) == 0
    files = list((settings.project_root / "data/research/options_native_pilot_input_packet_v1").glob("*.json"))
    assert len(files) == 1
    assert files[0].stat().st_size < 32 * 1024
    report = json.loads(files[0].read_text())
    assert report["present_closes"] == 21
    assert "UNQUALIFIED" in capsys.readouterr().out
    assert {p: sha(p) for p in before} == before
    files[0].write_text("conflicting evidence")
    assert cli.main(["--save-report"]) == 3
    assert files[0].read_text() == "conflicting evidence"


def test_cli_blocked_source_does_not_save_an_acceptance_packet(native, monkeypatch, capsys):
    settings, _, canonicals, _ = native
    canonicals[0].unlink()
    monkeypatch.setattr(cli, "ROOT", settings.project_root)
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    assert cli.main(["--save-report"]) == 3
    assert "BLOCKED" in capsys.readouterr().out
    assert not (settings.project_root / "data/research/options_native_pilot_input_packet_v1").exists()
