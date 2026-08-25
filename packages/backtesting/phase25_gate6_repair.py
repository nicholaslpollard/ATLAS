from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.discovery.scanner import DiscoveryFoundationScanner
from packages.discovery.scoring import (
    DISCOVERY_SCORE_MANIFEST_VERSION,
    DiscoverySetupScanner,
)
from packages.features.partition_store import sha256_file
from packages.schemas.universe import UNIVERSE_CONTRACT_VERSION
from packages.universe.eligibility import UNIVERSE_ELIGIBILITY_POLICY_VERSION
from packages.universe.manager import (
    UNIVERSE_MANIFEST_VERSION,
    UniverseManager,
    _routing_input_fingerprint,
)

from .phase25_gate6 import (
    Phase25Gate6DiscoveryReconstruction,
    Phase25Gate6Error,
    _pair_state,
)


PHASE25_GATE6_REPAIR_CONTRACT_VERSION = (
    "phase25-gate6-repair-v1-preflight-before-build-semantic-score-reconciliation"
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate6Error(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate6Error(f"JSON evidence must be an object: {path}")
    return value


class Phase25Gate6SafeDiscoveryReconstruction(Phase25Gate6DiscoveryReconstruction):
    """Gate6 repair: validate existing artifacts before any production builder can write.

    The first target attempt exposed that the original Gate6 guard checked `skipped`
    only after invoking a builder. Production builders are intentionally allowed to
    refresh stale artifacts, so that ordering could mutate an existing artifact before
    Gate6 raised. This subclass moves all existing-artifact checks ahead of builders.

    If an existing discovery score is stale only because the foundation's physical
    snapshot hash changed, the score may be preserved only when the exact scoring
    interface rows remain semantically identical. Otherwise Gate6 still fails closed.
    """

    def __init__(self, settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(settings)
        self.reconciliation_events: list[dict[str, object]] = []

    def _existing_universe(self, session: date):  # type: ignore[no-untyped-def]
        manager = UniverseManager(self.settings)
        snapshot = self.paths.universe_snapshot_file(session)
        exclusion = self.paths.universe_exclusion_file(session)
        manifest_path = self.paths.universe_snapshot_manifest(session)
        manifest = _read_json(manifest_path)
        reference = self.paths.reference_snapshot_file(session)
        expected_routing = _routing_input_fingerprint(
            override_routes={},
            override_tickers={},
            unavailable_ids=set(),
            quarantined_ids=set(),
            manual_exclude_ids=set(),
        )
        checks = {
            "manifest_version": manifest.get("manifest_version") == UNIVERSE_MANIFEST_VERSION,
            "contract_version": manifest.get("universe_contract_version") == UNIVERSE_CONTRACT_VERSION,
            "policy_version": manifest.get("policy_version") == UNIVERSE_ELIGIBILITY_POLICY_VERSION,
            "policy_fingerprint": manifest.get("policy_fingerprint") == manager.policy.fingerprint,
            "as_of_date": manifest.get("as_of_date") == session.isoformat(),
            "reference_date": manifest.get("reference_snapshot_date") == session.isoformat(),
            "reference_sha": manifest.get("source_reference_sha256") == sha256_file(reference),
            "routing_input": manifest.get("routing_input_fingerprint") == expected_routing,
            "snapshot_sha": manifest.get("snapshot_sha256") == sha256_file(snapshot),
            "exclusion_sha": manifest.get("exclusion_sha256") == sha256_file(exclusion),
        }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase25Gate6Error(
                f"existing Phase7 universe is stale for {session}; Gate6 preflight refuses overwrite: "
                + ", ".join(failed)
            )
        return manager._result_from_manifest(
            manifest=manifest,
            snapshot_path=snapshot,
            exclusion_path=exclusion,
            manifest_path=manifest_path,
            skipped=True,
        )

    def _existing_foundation(self, session: date):  # type: ignore[no-untyped-def]
        scanner = DiscoveryFoundationScanner(self.settings)
        lineage, _ = scanner._upstream_lineage(session)
        dependency = scanner._dependency_fingerprint(session, lineage)
        snapshot = self.paths.discovery_snapshot_file(session)
        manifest_path = self.paths.discovery_snapshot_manifest(session)
        manifest = scanner._existing_current(
            as_of_date=session,
            dependency_fingerprint=dependency,
            snapshot_path=snapshot,
            manifest_path=manifest_path,
        )
        if manifest is None:
            raise Phase25Gate6Error(
                f"existing discovery foundation is stale for {session}; "
                "Gate6 preflight refuses overwrite"
            )
        return scanner._result_from_manifest(
            manifest=manifest,
            snapshot_path=snapshot,
            manifest_path=manifest_path,
            wall_seconds=0.0,
            skipped=True,
        )

    def _score_interface_mismatch_count(self, session: date) -> int:
        foundation = self.paths.discovery_snapshot_file(session)
        score = self.paths.discovery_score_file(session)
        con = connect_utc(":memory:")
        try:
            row = con.execute(
                f"""
                WITH f AS (
                    SELECT
                        instrument_id,
                        ticker,
                        coalesce(security_type, '') AS security_type,
                        CAST(routes AS VARCHAR) AS routes,
                        CAST(activity_tier AS VARCHAR) AS activity_tier,
                        broad_discovery_ready,
                        mandatory_route
                    FROM read_parquet({sql_string(foundation)})
                    WHERE consideration_required = TRUE
                ),
                s AS (
                    SELECT
                        instrument_id,
                        ticker,
                        coalesce(security_type, '') AS security_type,
                        CAST(routes AS VARCHAR) AS routes,
                        CAST(activity_tier AS VARCHAR) AS activity_tier,
                        broad_discovery_ready,
                        mandatory_route
                    FROM read_parquet({sql_string(score)})
                ),
                delta AS (
                    (SELECT * FROM f EXCEPT SELECT * FROM s)
                    UNION ALL
                    (SELECT * FROM s EXCEPT SELECT * FROM f)
                )
                SELECT count(*) FROM delta
                """
            ).fetchone()
        finally:
            con.close()
        return int(row[0])

    def _existing_score(self, session: date):  # type: ignore[no-untyped-def]
        scanner = DiscoverySetupScanner(self.settings)
        lineage, _ = scanner._upstream(session)
        dependency = scanner._dependency(session, lineage)
        snapshot = self.paths.discovery_score_file(session)
        manifest_path = self.paths.discovery_score_manifest(session)
        current = scanner._existing(
            dependency=dependency,
            snapshot_path=snapshot,
            manifest_path=manifest_path,
        )
        if current is not None:
            return scanner._result(
                manifest=current,
                snapshot_path=snapshot,
                manifest_path=manifest_path,
                wall_seconds=0.0,
                skipped=True,
            )

        # Preserve a stale accepted score only when the exact fields consumed by the
        # scoring stage are unchanged under the current foundation. This is a
        # reconciliation, not a dependency-fingerprint rewrite.
        manifest = _read_json(manifest_path)
        if manifest.get("manifest_version") != DISCOVERY_SCORE_MANIFEST_VERSION:
            raise Phase25Gate6Error(
                f"existing discovery score manifest contract is stale for {session}"
            )
        if manifest.get("as_of_date") != session.isoformat():
            raise Phase25Gate6Error(f"existing discovery score date mismatch for {session}")
        if manifest.get("snapshot_sha256") != sha256_file(snapshot):
            raise Phase25Gate6Error(f"existing discovery score snapshot hash mismatch for {session}")
        mismatch_count = self._score_interface_mismatch_count(session)
        if mismatch_count != 0:
            raise Phase25Gate6Error(
                f"existing discovery score is stale and its scoring interface differs for {session}; "
                f"semantic mismatches={mismatch_count}; Gate6 refuses overwrite"
            )
        self.reconciliation_events.append(
            {
                "session": session.isoformat(),
                "artifact": "discovery_score",
                "mode": "PRESERVE_STALE_HASH_IF_SCORING_INTERFACE_EXACT",
                "semantic_interface_mismatch_count": 0,
                "current_foundation_sha256": sha256_file(
                    self.paths.discovery_snapshot_file(session)
                ),
                "preserved_score_sha256": sha256_file(snapshot),
                "preserved_score_dependency_fingerprint": str(
                    manifest.get("dependency_fingerprint") or ""
                ),
            }
        )
        return scanner._result(
            manifest=manifest,
            snapshot_path=snapshot,
            manifest_path=manifest_path,
            wall_seconds=0.0,
            skipped=True,
        )

    def _materialize_stateless_session(self, session: date) -> dict[str, object]:
        self._assert_reference_pair(session)

        universe_paths = (
            self.paths.universe_snapshot_file(session),
            self.paths.universe_exclusion_file(session),
            self.paths.universe_snapshot_manifest(session),
        )
        universe_existing = _pair_state(
            universe_paths, label="Phase7 universe", session=session
        )
        if universe_existing:
            universe = self._existing_universe(session)
        else:
            universe = UniverseManager(self.settings).build(session, force=False)
            if universe.skipped:
                raise Phase25Gate6Error(
                    f"new Phase7 universe unexpectedly reported skipped for {session}"
                )

        foundation_paths = (
            self.paths.discovery_snapshot_file(session),
            self.paths.discovery_snapshot_manifest(session),
        )
        foundation_existing = _pair_state(
            foundation_paths, label="discovery foundation", session=session
        )
        if foundation_existing:
            foundation = self._existing_foundation(session)
        else:
            foundation = DiscoveryFoundationScanner(self.settings).build(session)
            if foundation.skipped:
                raise Phase25Gate6Error(
                    f"new discovery foundation unexpectedly reported skipped for {session}"
                )

        score_paths = (
            self.paths.discovery_score_file(session),
            self.paths.discovery_score_manifest(session),
        )
        score_existing = _pair_state(score_paths, label="discovery score", session=session)
        if score_existing:
            score = self._existing_score(session)
        else:
            score = DiscoverySetupScanner(self.settings).build(session)
            if score.skipped:
                raise Phase25Gate6Error(
                    f"new discovery score unexpectedly reported skipped for {session}"
                )

        return {
            "universe_existing": universe_existing,
            "foundation_existing": foundation_existing,
            "score_existing": score_existing,
            "universe_routed": universe.routed_instrument_count,
            "universe_discovery": universe.discovery_count,
            "foundation_broad_ready": foundation.broad_discovery_ready_count,
            "foundation_consideration": foundation.consideration_required_count,
            "scored": score.scored_count,
            "universe_sha256": sha256_file(self.paths.universe_snapshot_file(session)),
            "foundation_sha256": sha256_file(self.paths.discovery_snapshot_file(session)),
            "score_sha256": sha256_file(self.paths.discovery_score_file(session)),
        }

    def run(self, *, through_date: date, progress_callback=None) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self.reconciliation_events = []
        report = super().run(
            through_date=through_date,
            progress_callback=progress_callback,
        )
        report["gate6_repair_contract_version"] = PHASE25_GATE6_REPAIR_CONTRACT_VERSION
        report["preflight_existing_artifacts_before_builder"] = True
        report["reconciliation_event_count"] = len(self.reconciliation_events)
        report["reconciliation_events"] = list(self.reconciliation_events)
        path = self.report_path(through_date)
        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
