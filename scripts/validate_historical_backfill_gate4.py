from __future__ import annotations

import json
from pathlib import Path

import duckdb

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_identity_asset_risk import (
    ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION,
    ASSET_ID_HISTORICAL_EFFECT,
    ASSET_ID_MULTIPLICITY_REFERENCE,
    ASSET_ID_REFERENCE_POLICY,
)
from packages.data.alpaca_backfill_identity_policy import (
    ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
    MAX_SAFE_RENAME_HANDOFF_CALENDAR_DAYS,
)
from packages.data.alpaca_backfill_identity_segments_policy import (
    ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
    CUSIP_AMBIGUITY_REASON,
)


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise SystemExit(f"Historical Backfill Gate 4: FAIL; missing {label}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _scalar(con: duckdb.DuckDBPyConnection, sql: str, path: Path) -> int:
    row = con.execute(sql, [str(path)]).fetchone()
    return int(row[0]) if row is not None else -1


def main() -> None:
    settings = load_settings()
    root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
    identity_root = root / "identity"

    identity_report_path = identity_root / "identity_report.json"
    segment_report_path = identity_root / "identity_segment_report.json"
    asset_risk_report_path = identity_root / "identity_asset_risk_report.json"

    identity = _read_json(identity_report_path, "Gate 4-B identity report")
    segment = _read_json(segment_report_path, "Gate 4-C segment report")
    asset_risk = _read_json(asset_risk_report_path, "Gate 4-D asset-risk report")

    event_path = Path(str(identity.get("event_ledger_path") or ""))
    relationship_path = Path(str(identity.get("relationship_path") or ""))
    rename_path = Path(str(identity.get("rename_candidate_path") or ""))
    safe_edge_path = Path(str(segment.get("safe_edge_path") or ""))
    quarantined_edge_path = Path(str(segment.get("quarantined_safe_edge_path") or ""))
    cusip_ambiguous_path = Path(str(segment.get("ambiguous_symbol_path") or ""))
    chain_path = Path(str(segment.get("chain_path") or ""))
    segment_path = Path(str(segment.get("segment_path") or ""))
    reference_path = Path(str(asset_risk.get("reference_artifact_path") or ""))

    required_paths = {
        "event_ledger": event_path,
        "relationships": relationship_path,
        "rename_candidates": rename_path,
        "safe_edges": safe_edge_path,
        "quarantined_edges": quarantined_edge_path,
        "cusip_ambiguous_symbols": cusip_ambiguous_path,
        "identity_chains": chain_path,
        "identity_segments": segment_path,
        "asset_id_reference": reference_path,
    }
    missing_artifacts = [name for name, path in required_paths.items() if not path.is_file()]

    con = duckdb.connect(":memory:")
    try:
        event_count = _scalar(con, "SELECT count(*) FROM read_parquet(?)", event_path)
        relationship_count = _scalar(con, "SELECT count(*) FROM read_parquet(?)", relationship_path)
        rename_count = _scalar(con, "SELECT count(*) FROM read_parquet(?)", rename_path)
        rename_safe = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE status='SAFE_STITCH_CANDIDATE' AND safe_to_stitch=TRUE",
            rename_path,
        )
        rename_evidence = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE status='CONTINUITY_EVIDENCE_ONLY' AND safe_to_stitch=FALSE",
            rename_path,
        )
        rename_review = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE status='REVIEW_REQUIRED' AND safe_to_stitch=FALSE",
            rename_path,
        )
        invalid_safe_gap = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE status='SAFE_STITCH_CANDIDATE' AND "
            "(handoff_gap_calendar_days IS NULL OR handoff_gap_calendar_days < 1 OR "
            f"handoff_gap_calendar_days > {MAX_SAFE_RENAME_HANDOFF_CALENDAR_DAYS})",
            rename_path,
        )
        safe_edges = _scalar(con, "SELECT count(*) FROM read_parquet(?)", safe_edge_path)
        quarantined_edges = _scalar(con, "SELECT count(*) FROM read_parquet(?)", quarantined_edge_path)
        cusip_ambiguous = _scalar(con, "SELECT count(*) FROM read_parquet(?)", cusip_ambiguous_path)
        invalid_cusip_ambiguity = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE identity_ambiguity_reason <> ? "
            "OR automatic_continuity_forbidden <> TRUE",
            cusip_ambiguous_path,
        ) if cusip_ambiguous_path.is_file() else -1
        chain_count = _scalar(con, "SELECT count(*) FROM read_parquet(?)", chain_path)
        segment_count = _scalar(con, "SELECT count(*) FROM read_parquet(?)", segment_path)
        segment_ambiguous = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE identity_ambiguous=TRUE",
            segment_path,
        )
        reference_count = _scalar(con, "SELECT count(*) FROM read_parquet(?)", reference_path)
        invalid_reference = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE risk_classification <> ? "
            "OR asset_state_role <> ? OR historical_identity_effect <> ? "
            "OR automatic_continuity_forbidden <> FALSE "
            "OR historical_identity_ambiguous_from_uuid_alone <> FALSE",
            reference_path,
        ) if reference_path.is_file() else -1
        segment_reference_count = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE asset_id_multiplicity_reference=TRUE",
            segment_path,
        )
        chain_reference_count = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE asset_id_multiplicity_reference=TRUE",
            chain_path,
        )
        reference_not_singleton = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE asset_id_multiplicity_reference=TRUE "
            "AND chain_length <> 1",
            segment_path,
        )
        reference_historical_ambiguous = _scalar(
            con,
            "SELECT count(*) FROM read_parquet(?) WHERE asset_id_multiplicity_reference=TRUE "
            "AND identity_ambiguous=TRUE",
            segment_path,
        )
        reference_symbol_mismatch = int(
            con.execute(
                "SELECT count(*) FROM ("
                "SELECT symbol FROM read_parquet(?) "
                "EXCEPT SELECT symbol FROM read_parquet(?) WHERE asset_id_multiplicity_reference=TRUE"
                ")",
                [str(reference_path), str(segment_path)],
            ).fetchone()[0]
        ) + int(
            con.execute(
                "SELECT count(*) FROM ("
                "SELECT symbol FROM read_parquet(?) WHERE asset_id_multiplicity_reference=TRUE "
                "EXCEPT SELECT symbol FROM read_parquet(?)"
                ")",
                [str(segment_path), str(reference_path)],
            ).fetchone()[0]
        )
    finally:
        con.close()

    identity_event_type_total = sum(int(value) for value in (identity.get("event_type_counts") or {}).values())
    triage_total = (
        int(identity.get("safe_stitch_candidates", -1))
        + int(identity.get("continuity_evidence_only", -1))
        + int(identity.get("rename_review_required", -1))
    )

    checks = {
        "identity_policy_contract": identity.get("contract_version") == ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
        "identity_canonical_untouched": identity.get("canonical_data_modified") is False,
        "retained_corporate_action_pages_complete": (
            int(identity.get("retained_corporate_action_pages", 0))
            == int(identity.get("expected_corporate_action_pages", -1))
            and int(identity.get("retained_corporate_action_pages", 0)) > 0
        ),
        "raw_corporate_action_hashes_clean": int(identity.get("raw_payload_hash_failures", -1)) == 0,
        "provider_event_ids_unique": int(identity.get("duplicate_provider_event_ids", -1)) == 0,
        "known_event_types_only": not (identity.get("unknown_event_types") or []),
        "event_ledger_accounting": event_count == int(identity.get("corporate_action_events", -1)) == identity_event_type_total,
        "relationship_accounting": relationship_count == int(identity.get("identity_relationship_rows", -1)),
        "rename_triage_accounting": (
            rename_count == int(identity.get("rename_continuity_candidates", -1)) == triage_total
            and rename_safe == int(identity.get("safe_stitch_candidates", -1))
            and rename_evidence == int(identity.get("continuity_evidence_only", -1))
            and rename_review == int(identity.get("rename_review_required", -1))
        ),
        "safe_handoff_policy": invalid_safe_gap == 0,
        "gate3_casefold_not_auto_stitched": int(identity.get("gate3_casefold_sensitive_candidates", -1)) == 0,
        "segment_policy_contract": segment.get("contract_version") == ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
        "segment_canonical_untouched": segment.get("canonical_data_modified") is False,
        "segment_safe_input_matches_gate4b": int(segment.get("safe_candidate_rows", -1)) == rename_safe,
        "segment_duplicate_accounting": (
            int(segment.get("input_unique_safe_edges", -1))
            + int(segment.get("duplicate_safe_candidate_rows", -1))
            == int(segment.get("safe_candidate_rows", -1))
        ),
        "eligible_edge_artifact_matches_report": safe_edges == int(segment.get("identity_eligible_safe_edges", -1)),
        "quarantine_artifact_matches_report": quarantined_edges == int(segment.get("quarantined_unique_safe_edges", -1)),
        "cusip_ambiguity_artifact_matches_report": cusip_ambiguous == int(segment.get("cusip_ambiguous_symbols", -1)),
        "cusip_ambiguity_policy": invalid_cusip_ambiguity == 0 and segment_ambiguous == cusip_ambiguous,
        "segment_chain_accounting": (
            chain_count == int(segment.get("identity_chains", -1))
            and segment_count == int(segment.get("identity_segments", -1))
            and int(segment.get("expected_chain_count", -1)) == chain_count
            and segment.get("edge_component_accounting") is True
            and segment.get("chain_coverage_exact") is True
            and segment.get("eligible_safe_edges_consumed_exact") is True
            and segment.get("quarantine_accounting_exact") is True
        ),
        "asset_risk_contract": asset_risk.get("contract_version") == ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION,
        "asset_risk_parent_contract": asset_risk.get("parent_segment_policy_contract_version") == ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
        "asset_risk_canonical_untouched": asset_risk.get("canonical_data_modified") is False,
        "asset_state_reference_only": (
            asset_risk.get("asset_state_role") == ASSET_ID_REFERENCE_POLICY
            and asset_risk.get("historical_identity_effect") == ASSET_ID_HISTORICAL_EFFECT
            and asset_risk.get("reference_policy_is_non_segmenting") is True
        ),
        "asset_uuid_risk_does_not_touch_continuity": (
            int(asset_risk.get("reuse_touching_eligible_edge", -1)) == 0
            and int(asset_risk.get("reuse_touching_quarantined_edge", -1)) == 0
            and int(asset_risk.get("reuse_in_multi_symbol_chain", -1)) == 0
        ),
        "asset_reference_artifact_matches_report": (
            reference_count == int(asset_risk.get("reference_rows", -1))
            == int(asset_risk.get("observed_symbols_with_multiple_asset_ids", -1))
            and invalid_reference == 0
        ),
        "asset_reference_annotations_exact": (
            segment_reference_count == int(asset_risk.get("segment_reference_annotations", -1))
            and chain_reference_count == int(asset_risk.get("chain_reference_annotations", -1))
            and segment_reference_count == reference_count
            and chain_reference_count == reference_count
            and reference_symbol_mismatch == 0
        ),
        "asset_reference_remains_singleton_nonhistorical": (
            reference_not_singleton == 0 and reference_historical_ambiguous == 0
        ),
        "historical_chain_structure_preserved_by_gate4d": (
            asset_risk.get("historical_chain_structure_unchanged") is True
            and int(asset_risk.get("parent_identity_chains", -1)) == chain_count
            and int(asset_risk.get("parent_identity_segments", -1)) == segment_count
            and int(asset_risk.get("resulting_identity_chains", -1)) == chain_count
            and int(asset_risk.get("resulting_identity_segments", -1)) == segment_count
        ),
        "required_artifacts_present": not missing_artifacts,
    }

    print("ATLAS Historical Backfill Gate 4 Validation")
    print("  Historical Backfill Gates 1-3: ACCEPTED")
    print(f"  identity policy:                 {identity.get('contract_version')}")
    print(f"  segment policy:                  {segment.get('contract_version')}")
    print(f"  asset-risk policy:               {asset_risk.get('contract_version')}")
    print(f"  retained corporate-action pages: {int(identity.get('retained_corporate_action_pages', 0)):,}")
    print(f"  corporate-action events:         {event_count:,}")
    print(f"  relationship rows:               {relationship_count:,}")
    print(f"  rename candidates:               {rename_count:,}")
    print(f"    safe Gate 4-B rows:             {rename_safe:,}")
    print(f"    evidence-only rows:             {rename_evidence:,}")
    print(f"    review-required rows:           {rename_review:,}")
    print(f"  identity-eligible unique edges:   {safe_edges:,}")
    print(f"  quarantined unique edges:         {quarantined_edges:,}")
    print(f"  CUSIP-ambiguous literals:         {cusip_ambiguous:,}")
    print(f"  identity chains:                  {chain_count:,}")
    print(f"  identity segments:                {segment_count:,}")
    print(f"  asset-ID multiplicity references: {reference_count:,}")
    print(f"    touching eligible continuity:   {int(asset_risk.get('reuse_touching_eligible_edge', -1)):,}")
    print(f"    touching quarantine:            {int(asset_risk.get('reuse_touching_quarantined_edge', -1)):,}")
    print(f"    inside multi-symbol chain:      {int(asset_risk.get('reuse_in_multi_symbol_chain', -1)):,}")
    print("  checks:")
    for name, passed in checks.items():
        print(f"    {name}: {passed}")

    if not all(checks.values()):
        raise SystemExit("Historical Backfill Gate 4: FAIL")

    print("  Historical Backfill Gate 4 corporate action / identity segmentation: PASS")
    print("  Historical Backfill Gate 5 provider completeness / quality: CURRENT")


if __name__ == "__main__":
    main()
