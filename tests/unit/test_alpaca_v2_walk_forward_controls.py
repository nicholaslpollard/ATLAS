from __future__ import annotations

import pytest
import json
from datetime import date
from types import SimpleNamespace

from scripts.run_a33_b33_reference_development import main as reference_main
from scripts.run_alpaca_v2_postbuild import main as postbuild_main
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.holdout_receipts import read_holdout_receipt


def _coordinator_harness(tmp_path, monkeypatch, *, development_exit=0, forward_exit=0,
                         materialization_error=None, materialized_end="2026-09-03",
                         expect_prior_consumption=False):
    import scripts.run_alpaca_v2_postbuild as script

    settings = SimpleNamespace(project_root=tmp_path)
    layout = V2Layout.beneath((tmp_path / "data").resolve())
    receipt_path = layout.manifests / "master_holdout_consumption.json"
    events = []
    result = lambda **report: SimpleNamespace(report=report)
    native = result(total_units=1, canonical_rows=200, excluded_symbol_count=0,
                    acceptance_fingerprint="1" * 64)
    daily = result(daily_rows=200, daily_symbols=1, symbols_with_internal_gaps=0)
    identity = result(identity_clear_common_stock_symbols=1, excluded_symbols=0)
    split = result(status="COMPLETE", clean_candidate=True, completed_units=1,
                   total_units=1, excluded_symbol_count=0, excluded_symbols=[],
                   source_fingerprint="2" * 64)
    research = result(research_rows=100, eligible_symbols=1, source_cutoff_session="2026-09-03",
                      cutoff_session="2026-05-11", source_fingerprint="3" * 64,
                      return_economics="SPLIT_ADJUSTED_PRICE_RETURN_WITHOUT_CASH_DISTRIBUTION_CREDIT")

    class Coordinator:
        def __init__(self, _settings):
            self.native_report_path = layout.manifests / "native.json"
            self.daily_report_path = layout.manifests / "daily.json"
            self.identity_report_path = layout.manifests / "identity.json"

        def validate_native(self, **kwargs):
            return native

        def validate_daily(self, source):
            return daily

        def build_identity_lifecycle(self, *args):
            return identity

        def build_research_daily(self, *args):
            return research

        def build_walk_forward_daily(self, *args, **kwargs):
            receipt = read_holdout_receipt(receipt_path)
            assert receipt["status"] == "CONSUMED_MATERIALIZATION_STARTED"
            assert "development" in events
            events.append("materialization")
            if materialization_error is not None:
                raise materialization_error
            return result(cutoff_session=materialized_end, protected_return_rows_materialized=123,
                          source_fingerprint="4" * 64)

    def run(command, **kwargs):
        if "--evaluation-stage" in command:
            receipt = read_holdout_receipt(receipt_path)
            assert receipt["status"] == "CONSUMED_REPLAY_STARTED"
            assert receipt["protected_return_rows_read"] == 123
            events.append("walk-forward")
            return SimpleNamespace(returncode=forward_exit)
        events.append("development")
        assert receipt_path.exists() is expect_prior_consumption
        return SimpleNamespace(returncode=development_exit)

    monkeypatch.setattr(script, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(script, "load_settings", lambda root: settings)
    monkeypatch.setattr(script, "AlpacaV2PostBuildCoordinator", Coordinator)
    monkeypatch.setattr(script, "AlpacaV2SplitDailyAcquirer", lambda settings: SimpleNamespace(run=lambda *a, **k: split))
    monkeypatch.setattr(script.subprocess, "run", run)
    return script, layout, events


def test_postbuild_development_failure_does_not_consume_holdout(tmp_path, monkeypatch):
    script, layout, events = _coordinator_harness(tmp_path, monkeypatch, development_exit=7)
    assert script.main(["--through-walk-forward-replay", "--authorize-master-holdout-consumption"]) == 7
    assert events == ["development"]
    assert not (layout.manifests / "master_holdout_consumption.json").exists()
    assert (layout.manifests / "master_holdout_authorization.json").is_file()


@pytest.mark.parametrize("error", [RuntimeError("synthetic materialization failure"), KeyboardInterrupt()])
def test_postbuild_materialization_failure_is_recorded_before_reraising(tmp_path, monkeypatch, error):
    script, layout, events = _coordinator_harness(tmp_path, monkeypatch, materialization_error=error)
    with pytest.raises(type(error)):
        script.main(["--through-walk-forward-replay", "--authorize-master-holdout-consumption"])
    receipt = read_holdout_receipt(layout.manifests / "master_holdout_consumption.json")
    assert receipt["status"] == "CONSUMED_MATERIALIZATION_FAILED"
    assert receipt["protected_return_rows_read"] is None
    assert len(receipt["receipt_history"]) == 1
    assert events == ["development", "materialization"]


@pytest.mark.parametrize("exit_code,status", [(0, "CONSUMED_WALK_FORWARD_COMPLETE"), (7, "CONSUMED_REPLAY_FAILED")])
def test_postbuild_orders_consumption_materialization_and_replay(tmp_path, monkeypatch, exit_code, status):
    script, layout, events = _coordinator_harness(tmp_path, monkeypatch, forward_exit=exit_code)
    assert script.main(["--through-walk-forward-replay", "--authorize-master-holdout-consumption"]) == exit_code
    receipt = read_holdout_receipt(layout.manifests / "master_holdout_consumption.json")
    assert receipt["status"] == status
    assert receipt["protected_return_rows_read"] == 123
    assert len(receipt["receipt_history"]) == 2
    assert events == ["development", "materialization", "walk-forward"]
    summary = json.loads((layout.manifests / "postbuild.json").read_text())
    assert summary["master_holdout_consumed"] is True
    assert summary["protected_return_rows_read"] == 123


def test_postbuild_source_only_rerun_preserves_prior_consumption(tmp_path, monkeypatch):
    script, layout, events = _coordinator_harness(tmp_path, monkeypatch, forward_exit=7)
    assert script.main(["--through-walk-forward-replay", "--authorize-master-holdout-consumption"]) == 7
    before = (layout.manifests / "master_holdout_consumption.json").read_bytes()
    assert script.main([]) == 0
    summary = json.loads((layout.manifests / "postbuild.json").read_text())
    assert summary["master_holdout_consumed"] is True
    assert summary["protected_return_rows_read"] == 123
    assert summary["prior_holdout_status"] == "CONSUMED_REPLAY_FAILED"
    assert (layout.manifests / "master_holdout_consumption.json").read_bytes() == before
    assert events == ["development", "materialization", "walk-forward"]


def test_postbuild_scope_failure_retains_observed_protected_count(tmp_path, monkeypatch):
    script, layout, events = _coordinator_harness(
        tmp_path, monkeypatch, materialized_end="2026-09-02"
    )
    with pytest.raises(RuntimeError, match="differs from the authorized source cutoff"):
        script.main(["--through-walk-forward-replay", "--authorize-master-holdout-consumption"])
    receipt = read_holdout_receipt(layout.manifests / "master_holdout_consumption.json")
    assert receipt["status"] == "CONSUMED_MATERIALIZATION_SCOPE_MISMATCH"
    assert receipt["protected_return_rows_read"] == 123
    assert receipt["protected_rows_accounting_pending"] is True
    summary = json.loads((layout.manifests / "postbuild.json").read_text())
    assert summary["protected_return_rows_read"] == 123
    assert summary["protected_return_rows_materialized"] == 123
    assert events == ["development", "materialization"]


@pytest.mark.parametrize("failure", ["scope", "replay"])
def test_postbuild_retry_preserves_failure_count_and_completes(tmp_path, monkeypatch, failure):
    script, layout, _ = _coordinator_harness(
        tmp_path, monkeypatch, forward_exit=7,
        materialized_end="2026-09-02" if failure == "scope" else "2026-09-03",
    )
    arguments = ["--through-walk-forward-replay", "--authorize-master-holdout-consumption"]
    if failure == "scope":
        with pytest.raises(RuntimeError, match="differs from the authorized source cutoff"):
            script.main(arguments)
    else:
        assert script.main(arguments) == 7
    path = layout.manifests / "master_holdout_consumption.json"
    failed = read_holdout_receipt(path)
    script, _, events = _coordinator_harness(
        tmp_path, monkeypatch, expect_prior_consumption=True
    )
    assert script.main(arguments) == 0
    complete = read_holdout_receipt(path)
    assert complete["status"] == "CONSUMED_WALK_FORWARD_COMPLETE"
    assert complete["attempt_number"] == 2
    assert complete["protected_return_rows_read"] == failed["protected_return_rows_read"] == 123
    assert complete["first_consumption_started_at_utc"] == failed["first_consumption_started_at_utc"]
    archived = path.with_name("master_holdout_consumption_history") / f"{failed['receipt_sha256']}.json"
    assert json.loads(archived.read_text()) == failed
    assert events == ["development", "materialization", "walk-forward"]


@pytest.mark.parametrize("verified", [True, False])
def test_postbuild_completed_rerun_requires_verified_results(tmp_path, monkeypatch, verified):
    import packages.performance.reference_replay_read_model as read_model

    script, layout, events = _coordinator_harness(tmp_path, monkeypatch)
    arguments = ["--through-walk-forward-replay", "--authorize-master-holdout-consumption"]
    assert script.main(arguments) == 0
    path = layout.manifests / "master_holdout_consumption.json"
    before = path.read_bytes()
    receipt = read_holdout_receipt(path)
    monkeypatch.setattr(read_model, "reference_replay_read_model", lambda settings: {
        "status": "AVAILABLE" if verified else "INVALID",
        "evaluation_stage": "walk-forward",
        "summary": {"master_holdout_authorization_id": receipt["authorization_id"]},
    })
    if verified:
        assert script.main(arguments) == 0
        summary = json.loads((layout.manifests / "postbuild.json").read_text())
        assert summary["completed_walk_forward_reused"] is True
    else:
        with pytest.raises(RuntimeError, match="completed walk-forward evidence failed"):
            script.main(arguments)
    assert path.read_bytes() == before
    assert events == ["development", "materialization", "walk-forward"]


def test_postbuild_walk_forward_requires_explicit_consumption_authorization() -> None:
    with pytest.raises(ValueError, match="requires --authorize-master-holdout"):
        postbuild_main(["--through-walk-forward-replay"])

    with pytest.raises(ValueError, match="valid only with --through-walk-forward"):
        postbuild_main(["--authorize-master-holdout-consumption"])


def test_postbuild_walk_forward_requires_exact_development_boundary() -> None:
    with pytest.raises(ValueError, match="exactly 2026-05-11"):
        postbuild_main(
            [
                "--through-walk-forward-replay",
                "--authorize-master-holdout-consumption",
                "--reference-end",
                "2026-05-08",
            ]
        )


def test_reference_walk_forward_cannot_be_selected_implicitly() -> None:
    with pytest.raises(ValueError, match="requires --authorize-master-holdout"):
        reference_main(["--evaluation-stage", "walk-forward"])

    with pytest.raises(ValueError, match="valid only with --evaluation-stage"):
        reference_main(["--authorize-master-holdout-consumption"])


def test_reference_walk_forward_cannot_stop_after_loading_protected_source() -> None:
    with pytest.raises(ValueError, match="--source-only is forbidden"):
        reference_main(
            [
                "--evaluation-stage",
                "walk-forward",
                "--authorize-master-holdout-consumption",
                "--source-only",
            ]
        )
