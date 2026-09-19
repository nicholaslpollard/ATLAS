from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.core.settings import load_settings
from packages.execution.trade_expression import SelectionKind
from packages.simulation.recurrent_workstation_acceptance import (
    RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_FINGERPRINT,
    RecurrentWorkstationAcceptanceError,
    build_workstation_acceptance_receipt_v1,
    build_workstation_reference_decision_v1,
    isolated_acceptance_settings,
    read_workstation_acceptance_receipt_v1,
    write_workstation_acceptance_receipt_v1,
)


def test_workstation_acceptance_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_FINGERPRINT
        == "5d450f115c03cfef389845ba594402f34a62ed7491f263dc7e33f8b5bb38af50"
    )


def test_isolated_acceptance_settings_refuses_normal_live_root(
    tmp_path,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    settings = load_settings(project_root)
    normal_live = settings.resolved_path(
        settings.data.paths.live
    )
    with pytest.raises(
        RecurrentWorkstationAcceptanceError,
        match="refuses the configured normal live root",
    ):
        isolated_acceptance_settings(
            project_root=project_root,
            live_root=normal_live,
        )

    isolated = isolated_acceptance_settings(
        project_root=project_root,
        live_root=tmp_path / "isolated-live",
    )
    assert isolated.resolved_path(
        isolated.data.paths.live
    ) == (tmp_path / "isolated-live").resolve()


def test_reference_fixture_produces_stock_decision_without_strategy_claim() -> None:
    cutoff = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    record = build_workstation_reference_decision_v1(
        ticker="SPY",
        reference_price=500.0,
        decision_created_utc=cutoff + timedelta(seconds=1),
        evidence_cutoff_utc=cutoff,
        position_notional_dollars=10_000.0,
    )
    assert (
        record.trade_expression_decision.selection_kind
        == SelectionKind.STOCK
    )
    assert record.forecast.horizon_value == 1
    assert record.forecast.thresholds[0].threshold_fraction == pytest.approx(
        0.20
    )
    assert "NOT_STRATEGY_EVIDENCE" in record.forecast.reason_codes


def test_acceptance_receipt_self_hash_roundtrips(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    settings = isolated_acceptance_settings(
        project_root=project_root,
        live_root=tmp_path / "acceptance-live",
    )
    sha = "a" * 64
    receipt = build_workstation_acceptance_receipt_v1(
        run_id="fixture-run",
        ticker="SPY",
        isolated_live_root=str(
            settings.resolved_path(settings.data.paths.live)
        ),
        initial_equity=100_000.0,
        entry_fee_dollars=0.0,
        exit_fee_dollars=0.0,
        entry_cycle_id="entry-cycle",
        close_cycle_id="close-cycle",
        entry_quote_bundle_fingerprint=sha,
        mark_quote_bundle_fingerprint="b" * 64,
        close_quote_bundle_fingerprint="c" * 64,
        decision_record_fingerprint="d" * 64,
        exit_plan_book_fingerprint="e" * 64,
        clock_book_fingerprint="f" * 64,
        time_disposition_bundle_fingerprint="1" * 64,
        time_aware_close_bundle_fingerprint="2" * 64,
        final_disposition="TIME",
        final_checkpoint_sha256="3" * 64,
        final_snapshot_fingerprint="4" * 64,
        final_revision=7,
        closed_trade_count=1,
        dashboard_status_after_mark="AVAILABLE",
        dashboard_account_state_fingerprint="5" * 64,
        cycle_health_status_after_retry="OPEN_CYCLE",
        accepted_at_utc="2026-09-18T15:02:00+00:00",
        provider_read_calls=3,
    )
    path = write_workstation_acceptance_receipt_v1(
        settings,
        receipt,
    )
    restored = read_workstation_acceptance_receipt_v1(
        settings,
        path=path,
    )
    assert restored == receipt
    assert restored.paper_authority is False
    assert restored.live_authority is False
