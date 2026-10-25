from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from packages.data import hybrid_options_frozen_research_demand_v1 as v9
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_plan_v1 import _provider_query
from scripts import plan_hybrid_options_frozen_research_demand_v1 as cli


class FakeSettings:
    def __init__(self, root: Path):
        self.root = root
        (root / "data/options/manifests").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, binding):
        assert binding == "options"

    def resolved_path(self, relative):
        return self.root / relative


def candidate_item(symbol, day, *, case):
    source = {
        "request_type": "OPTION_CALL_CANDIDATE_SURFACE_AT_DECISION_CLOCK",
        "symbol": symbol,
        "date_et": day,
        "time_of_day_et": "09:35:00.000",
        "right": "call",
        "max_dte_calendar_days": 75,
        "expiration_policy": "ALL_EXPIRATIONS_WITHIN_PROVIDER_MAX_DTE",
        "strike_policy": "CANDIDATE_SURFACE_NOT_PRESELECTED_STRIKE",
    }
    source["query_fingerprint"] = _fingerprint(source)
    source["member_case_ids"] = [case]
    source["member_case_count"] = 1
    return _provider_query(source)


@pytest.fixture
def candidate(monkeypatch):
    first = candidate_item("AAPL", "2021-01-04", case="c1")
    second = candidate_item("MSFT", "2023-03-06", case="c2")
    plan = {
        "plan_fingerprint": "a" * 64,
        "qualification": {
            "anchor_query_count": 1,
            "anchors": [{
                "decision_spot_query_fingerprint":
                    first["source_query_fingerprint"]
            }],
        },
        "_synthetic_provider_queries": [first, second],
    }
    # Isolate V9's stricter PER-REQUEST validation from the frozen
    # 9,455-row parent envelope, which is validated by the original checker.
    monkeypatch.setattr(
        v9, "_validate_source_plan",
        lambda p: p["_synthetic_provider_queries"],
    )
    monkeypatch.setattr(v9, "EXPECTED_UNIQUE_SURFACES", 2)
    return plan


def test_pilot_only_reads_actual_frozen_weekly_demand():
    report = v9.build_frozen_research_demand()
    assert report["status"] == "PARTIAL_PILOT_ONLY_CANDIDATE_PLAN_NOT_READ"
    assert report["frozen_candidate_quote_queries"] == 0
    assert report["frozen_pilot_quote_queries"] > 390
    assert report["source_request_count"] == report["frozen_pilot_quote_queries"]
    assert report["request_ids_unique"] is True
    assert set(report["year_counts"]) == set(str(y) for y in range(2018, 2026))
    assert report["at_time_provider_adapter_ready"] is False
    assert report["paid_provider_authority"] is False
    assert report["simulator_ready"] is False
    assert report["provider_requests"] == 0
    assert all(x["decision_clock_et"] == "10:00:00.000"
               and x["right"] == "both"
               and x["params"]["strike_range"] == 2
               and x["exact_adapter"] ==
               "AT_TIME_ADAPTER_NOT_IMPLEMENTED_NO_PROVIDER_AUTHORITY"
               for x in report["requests"])
    assert report["manifest_fingerprint"] == _fingerprint({
        k: v for k, v in report.items() if k != "manifest_fingerprint"
    })


def test_both_branches_preserve_native_shapes_and_priority(candidate):
    report = v9.build_frozen_research_demand(candidate)
    assert report["status"] == "BOTH_FROZEN_SOURCE_BRANCHES_PRESERVED_EXACTLY"
    assert report["frozen_candidate_quote_queries"] == 2
    assert report["frozen_candidate_qualification_anchors"] == 1
    assert report["source_request_count"] == report["frozen_pilot_quote_queries"] + 2
    assert len({r["query_id"] for r in report["requests"]}) == report[
        "source_request_count"
    ]
    rows = [r for r in report["requests"] if "CALL_CANDIDATES" in r["origin"]]
    assert len(rows) == 2
    aapl = next(r for r in rows if r["symbol"] == "AAPL")
    assert aapl["qualification_anchor"] is True
    assert aapl["decision_clock_et"] == "09:35:00.000"
    assert aapl["right"] == "call"
    assert aapl["params"]["strike_range"] is None
    assert aapl["params"]["max_dte"] == 75
    assert aapl["params"]["expiration"] == "*"
    assert aapl["params"]["strike"] == "*"
    assert aapl["origin_query_fingerprint"] == candidate[
        "_synthetic_provider_queries"
    ][0]["source_query_fingerprint"]
    assert any(r["origin"] == "FROZEN_SPY_WEEKLY_OPTIONS_NATIVE"
               for r in report["requests"])
    assert [r["priority"] for r in report["requests"]] == list(
        range(1, report["source_request_count"] + 1)
    )
    anchors = [r for r in report["requests"] if r["qualification_anchor"]]
    assert anchors
    assert all(r["qualification_anchor"] for r in report["requests"][:len(anchors)])
    assert report == v9.build_frozen_research_demand(candidate)


def test_candidate_outside_0935_clock_is_blocked(candidate):
    other = deepcopy(candidate)
    other["_synthetic_provider_queries"][0]["params"]["time_of_day"] = "10:00:00.000"
    with pytest.raises(ValueError):
        v9.build_frozen_research_demand(other)


def test_candidate_mutated_source_query_lineage_is_blocked(candidate):
    mutated = deepcopy(candidate)
    mutated["_synthetic_provider_queries"][0]["member_case_count"] = 3
    with pytest.raises(ValueError):
        v9.build_frozen_research_demand(mutated)


def test_candidate_same_provider_request_collision_blocks(candidate):
    mutated = deepcopy(candidate)
    mutated["_synthetic_provider_queries"][1] = deepcopy(
        mutated["_synthetic_provider_queries"][0]
    )
    with pytest.raises(v9.HybridFrozenDemandError, match="DRIFT"):
        v9.build_frozen_research_demand(mutated)


def test_missing_qualification_anchor_is_blocked(candidate):
    mutated = deepcopy(candidate)
    mutated["qualification"]["anchors"][0][
        "decision_spot_query_fingerprint"
    ] = "0" * 64
    with pytest.raises(v9.HybridFrozenDemandError, match="ANCHOR"):
        v9.build_frozen_research_demand(mutated)


def test_frozen_manifest_only_writes_with_both_branches(candidate, tmp_path, monkeypatch):
    settings = FakeSettings(tmp_path)
    monkeypatch.setattr(
        shutil, "disk_usage",
        lambda _: SimpleNamespace(free=160 * 1024**3),
    )
    pilot = v9.build_frozen_research_demand()
    with pytest.raises(v9.HybridFrozenDemandError, match="FULL_SOURCE_DEMAND"):
        v9.write_frozen_demand_manifest(settings, pilot)
    report = v9.build_frozen_research_demand(candidate)
    expected = settings.resolved_path("data/options/manifests")
    assert not list(expected.glob("hybrid_exact*"))
    path, inserted = v9.write_frozen_demand_manifest(settings, report)
    assert inserted is True
    assert path.is_file()
    assert json.loads(path.read_text()) == report
    same_path, inserted = v9.write_frozen_demand_manifest(settings, report)
    assert inserted is False
    assert same_path == path


def test_immutable_conflict_never_overwrites(candidate, tmp_path, monkeypatch):
    settings = FakeSettings(tmp_path)
    monkeypatch.setattr(
        shutil, "disk_usage",
        lambda _: SimpleNamespace(free=160 * 1024**3),
    )
    report = v9.build_frozen_research_demand(candidate)
    path, _ = v9.write_frozen_demand_manifest(settings, report)
    path.write_text("tampered")
    with pytest.raises(v9.HybridFrozenDemandError, match="CONFLICT"):
        v9.write_frozen_demand_manifest(settings, report)
    assert path.read_text() == "tampered"


def test_low_storage_blocks_before_write(candidate, tmp_path, monkeypatch):
    settings = FakeSettings(tmp_path)
    monkeypatch.setattr(
        shutil, "disk_usage",
        lambda _: SimpleNamespace(free=39 * 1024**3),
    )
    report = v9.build_frozen_research_demand(candidate)
    with pytest.raises(v9.HybridFrozenDemandError, match="STORAGE_WARNING"):
        v9.write_frozen_demand_manifest(settings, report)


def test_explicit_source_path_and_filename_binding(candidate, tmp_path):
    settings = FakeSettings(tmp_path)
    origin = settings.resolved_path(
        "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
        + "a" * 16 + ".json"
    )
    origin.write_text(json.dumps(candidate))
    loaded = v9.load_candidate_source_plan(settings, Path(
        "data/options/manifests/" + origin.name
    ))
    assert loaded == candidate
    with pytest.raises(v9.HybridFrozenDemandError, match="FINGERPRINT"):
        v9.load_candidate_source_plan(settings, settings.resolved_path(
            "data/options/manifests/thetadata_candidate_surface_source_plan_v1_bad.json"
        ))


def test_source_path_outside_options_binding_blocked(candidate, tmp_path):
    settings = FakeSettings(tmp_path)
    outside = tmp_path / "wrong.json"
    outside.write_text(json.dumps(candidate))
    with pytest.raises(v9.HybridFrozenDemandError, match="NOT_AVAILABLE"):
        v9.load_candidate_source_plan(settings, outside)


def test_cli_pilot_readonly(candidate, tmp_path, monkeypatch, capsys):
    settings = FakeSettings(tmp_path)
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    assert cli.main([]) == 0
    output = capsys.readouterr().out
    assert "PARTIAL_PILOT_ONLY_CANDIDATE_PLAN_NOT_READ" in output
    assert "READ_ONLY no manifest written" in output
    assert "provider_requests=0" in output
    with pytest.raises(SystemExit):
        cli.main(["--write-manifest"])
    assert not list(settings.resolved_path(
        "data/options/manifests"
    ).glob("hybrid_exact*"))


def test_cli_both_branches_preview(candidate, tmp_path, monkeypatch, capsys):
    settings = FakeSettings(tmp_path)
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    plan = settings.resolved_path(
        "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
        + "a" * 16 + ".json"
    )
    plan.write_text(json.dumps(candidate))
    assert cli.main(["--candidate-plan", str(plan)]) == 0
    output = capsys.readouterr().out
    assert "BOTH_FROZEN_SOURCE_BRANCHES_PRESERVED_EXACTLY" in output
    assert "candidate_0935_requests=2" in output
    assert "reservations=0" in output
    assert not list(plan.parent.glob("hybrid_exact*"))
