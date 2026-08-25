from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import InstrumentIdentityQuality
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.universe.eligibility import ACTIVE_UNIVERSE_ELIGIBILITY_POLICY

from .phase25_gate1 import PHASE25_GATE1_REPORT_CONTRACT_VERSION, Phase25Gate1ScopeInventory
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_GATE2_CONTRACT_VERSION,
    PHASE25_GATE2_DISCOVERY_OVERRIDES_ALLOWED,
    PHASE25_GATE2_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED,
    PHASE25_GATE2_REQUIRES_MATERIALIZED_UNIVERSE_EQUIVALENCE,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_PROVIDER_READS,
    PHASE25_PROVIDER_WRITES,
    PHASE25_ROUTE_REPLAY_ORIGIN,
    phase25_gate1_policy_fingerprint,
    phase25_gate2_policy_fingerprint,
)


PHASE25_GATE2_REPORT_CONTRACT_VERSION = (
    "phase25-gate2-report-v1-active-only-reference-discovery-equivalence"
)


class Phase25Gate2Error(RuntimeError):
    pass


@dataclass(frozen=True, slots=True, order=True)
class DiscoveryMemberKey:
    instrument_id: str
    ticker: str
    identity_quality: str
    name: str | None
    market: str | None
    locale: str | None
    primary_exchange: str | None
    security_type: str | None
    reference_active: bool
    delisted_utc: str | None


@dataclass(frozen=True, slots=True)
class DateEquivalence:
    as_of_date: str
    reference_manifest_include_inactive: bool
    full_reference_rows: int
    active_reference_rows: int
    inactive_reference_rows: int
    full_reference_instruments: int
    active_reference_instruments: int
    ambiguous_active_instruments: int
    mixed_active_inactive_instruments: int
    computed_full_discovery_members: int
    computed_active_only_discovery_members: int
    materialized_discovery_members: int
    computed_full_fingerprint: str
    computed_active_only_fingerprint: str
    materialized_fingerprint: str
    full_vs_active_only_mismatch_count: int
    active_only_vs_materialized_mismatch_count: int
    pass_equivalence: bool


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate2Error(f"missing required JSON evidence: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate2Error(f"invalid JSON evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase25Gate2Error(f"JSON evidence must be an object: {path}")
    return payload


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _datetime_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _member_fingerprint(members: Iterable[DiscoveryMemberKey]) -> str:
    payload = [asdict(item) for item in sorted(set(members))]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def discovery_members_from_reference_rows(
    rows: Iterable[dict[str, object]],
) -> tuple[set[DiscoveryMemberKey], dict[str, int]]:
    """Compute discovery-only Phase7 membership without overrides or side effects.

    This mirrors the discovery-relevant portion of UniverseManager.build. Inactive-only
    instruments cannot route to discovery. More than one active row for an instrument
    is ambiguous and fails closed. No watchlist/position/custom override is modeled.
    """

    by_instrument: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        instrument_id = str(row.get("instrument_id") or "").strip()
        if not instrument_id:
            raise Phase25Gate2Error("reference row has blank instrument_id")
        by_instrument[instrument_id].append(row)

    members: set[DiscoveryMemberKey] = set()
    ambiguous_active = 0
    mixed_active_inactive = 0

    for instrument_id, group in sorted(by_instrument.items()):
        qualities = {str(row.get("identity_quality") or "").strip() for row in group}
        if len(qualities) != 1 or "" in qualities:
            raise Phase25Gate2Error(
                f"instrument {instrument_id} has conflicting or blank identity quality"
            )
        identity_quality = InstrumentIdentityQuality(next(iter(qualities)))
        active_rows = [row for row in group if bool(row.get("active"))]
        inactive_rows = [row for row in group if not bool(row.get("active"))]
        mixed_active_inactive += int(bool(active_rows and inactive_rows))
        if len(active_rows) > 1:
            ambiguous_active += 1
            continue
        if len(active_rows) != 1:
            continue

        row = active_rows[0]
        eligible, _ = ACTIVE_UNIVERSE_ELIGIBILITY_POLICY.evaluate(
            reference_active=True,
            delisted_utc=row.get("delisted_utc") if isinstance(row.get("delisted_utc"), datetime) else None,
            market=_text(row.get("market")),
            locale=_text(row.get("locale")),
            primary_exchange=_text(row.get("primary_exchange")),
            security_type=_text(row.get("security_type")),
            identity_quality=identity_quality,
            data_available=True,
            data_quarantined=False,
            manual_exclude=False,
        )
        if not eligible:
            continue
        members.add(
            DiscoveryMemberKey(
                instrument_id=instrument_id,
                ticker=str(row.get("ticker") or "").strip(),
                identity_quality=identity_quality.value,
                name=_text(row.get("name")),
                market=_text(row.get("market")),
                locale=_text(row.get("locale")),
                primary_exchange=_text(row.get("primary_exchange")),
                security_type=_text(row.get("security_type")),
                reference_active=True,
                delisted_utc=_datetime_text(row.get("delisted_utc")),
            )
        )

    return members, {
        "instrument_count": len(by_instrument),
        "ambiguous_active_instruments": ambiguous_active,
        "mixed_active_inactive_instruments": mixed_active_inactive,
    }


class Phase25Gate2ActiveOnlyEquivalence:
    """Provider-free proof that inactive PIT rows are unnecessary for discovery replay."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate2"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "active_only_equivalence.json"

    def _gate1_evidence(self, through_date: date) -> tuple[Path, dict[str, object]]:
        path = Phase25Gate1ScopeInventory(self.settings).report_path(through_date)
        report = _read_json(path)
        if report.get("contract_version") != PHASE25_GATE1_REPORT_CONTRACT_VERSION:
            raise Phase25Gate2Error("Gate1 report contract mismatch")
        if report.get("through_date") != through_date.isoformat():
            raise Phase25Gate2Error("Gate1 report through-date mismatch")
        if report.get("phase25_gate1_policy_fingerprint") != phase25_gate1_policy_fingerprint():
            raise Phase25Gate2Error("Gate1 policy fingerprint mismatch")
        if report.get("pass") is not True:
            raise Phase25Gate2Error("Gate1 evidence is not passing")
        for key in (
            "provider_reads",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
            "phase11_support_writes",
            "protected_strategy_evidence_reads",
        ):
            if int(report.get(key, -1)) != 0:
                raise Phase25Gate2Error(f"Gate1 authority counter is nonzero: {key}")
        return path, report

    def _reference_rows(self, as_of_date: date) -> list[dict[str, object]]:
        path = self.paths.reference_snapshot_file(as_of_date)
        if not path.is_file():
            raise Phase25Gate2Error(f"reference snapshot missing: {path}")
        con = connect_utc(":memory:")
        try:
            cursor = con.execute(
                f"""
                SELECT instrument_id, identity_quality, ticker, name, market, locale,
                       primary_exchange, security_type, active, delisted_utc
                FROM read_parquet({sql_string(path)})
                ORDER BY instrument_id, ticker
                """
            )
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            con.close()

    def _materialized_members(self, as_of_date: date) -> set[DiscoveryMemberKey]:
        path = self.paths.universe_snapshot_file(as_of_date)
        if not path.is_file():
            raise Phase25Gate2Error(f"materialized universe snapshot missing: {path}")
        con = connect_utc(":memory:")
        try:
            cursor = con.execute(
                f"""
                SELECT instrument_id, ticker, identity_quality, name, market, locale,
                       primary_exchange, security_type, reference_active, delisted_utc
                FROM read_parquet({sql_string(path)})
                WHERE discovery_eligible = true
                ORDER BY instrument_id, ticker
                """
            )
            rows = cursor.fetchall()
        finally:
            con.close()
        return {
            DiscoveryMemberKey(
                instrument_id=str(row[0]),
                ticker=str(row[1]),
                identity_quality=str(row[2]),
                name=_text(row[3]),
                market=_text(row[4]),
                locale=_text(row[5]),
                primary_exchange=_text(row[6]),
                security_type=_text(row[7]),
                reference_active=bool(row[8]),
                delisted_utc=_datetime_text(row[9]),
            )
            for row in rows
        }

    def _validate_manifests(self, as_of_date: date) -> bool:
        reference_manifest_path = self.paths.reference_snapshot_manifest(as_of_date)
        universe_manifest_path = self.paths.universe_snapshot_manifest(as_of_date)
        reference_manifest = _read_json(reference_manifest_path)
        universe_manifest = _read_json(universe_manifest_path)
        include_inactive = reference_manifest.get("include_inactive") is True
        if not include_inactive:
            raise Phase25Gate2Error(
                f"Gate2 requires a full active+inactive reference snapshot for equivalence proof: {as_of_date}"
            )
        if universe_manifest.get("as_of_date") != as_of_date.isoformat():
            raise Phase25Gate2Error(f"universe manifest date mismatch: {as_of_date}")
        if universe_manifest.get("reference_snapshot_date") != as_of_date.isoformat():
            raise Phase25Gate2Error(f"universe reference date mismatch: {as_of_date}")
        reference_sha = sha256_file(self.paths.reference_snapshot_file(as_of_date))
        if universe_manifest.get("source_reference_sha256") != reference_sha:
            raise Phase25Gate2Error(
                f"materialized universe is not bound to the exact reference snapshot: {as_of_date}"
            )
        if universe_manifest.get("policy_fingerprint") != ACTIVE_UNIVERSE_ELIGIBILITY_POLICY.fingerprint:
            raise Phase25Gate2Error(f"universe eligibility policy mismatch: {as_of_date}")
        return include_inactive

    def run(self, *, through_date: date) -> dict[str, object]:
        if through_date < PHASE25_ROUTE_REPLAY_ORIGIN:
            raise Phase25Gate2Error("through_date predates the locked Phase25 replay origin")
        gate1_path, gate1 = self._gate1_evidence(through_date)
        raw_dates = gate1.get("local_reference_snapshot_dates")
        if not isinstance(raw_dates, list) or not raw_dates:
            raise Phase25Gate2Error("Gate1 has no local PIT reference snapshot dates")
        reference_dates = tuple(date.fromisoformat(str(item)) for item in raw_dates)

        results: list[DateEquivalence] = []
        mismatch_previews: dict[str, dict[str, list[dict[str, object]]]] = {}
        lineage: list[dict[str, str]] = []
        total_full_rows = 0
        total_active_rows = 0

        for as_of_date in reference_dates:
            include_inactive = self._validate_manifests(as_of_date)
            rows = self._reference_rows(as_of_date)
            if not rows:
                raise Phase25Gate2Error(f"reference snapshot is empty: {as_of_date}")
            active_rows = [row for row in rows if bool(row.get("active"))]
            inactive_rows = [row for row in rows if not bool(row.get("active"))]
            if not inactive_rows:
                raise Phase25Gate2Error(
                    f"equivalence proof requires at least one inactive row: {as_of_date}"
                )

            full_members, full_stats = discovery_members_from_reference_rows(rows)
            active_members, active_stats = discovery_members_from_reference_rows(active_rows)
            materialized_members = self._materialized_members(as_of_date)

            full_vs_active = full_members.symmetric_difference(active_members)
            active_vs_materialized = active_members.symmetric_difference(materialized_members)
            passed = not full_vs_active and not active_vs_materialized

            def preview(items: set[DiscoveryMemberKey]) -> list[dict[str, object]]:
                return [asdict(item) for item in sorted(items)[:20]]

            if not passed:
                mismatch_previews[as_of_date.isoformat()] = {
                    "full_vs_active_only": preview(full_vs_active),
                    "active_only_vs_materialized": preview(active_vs_materialized),
                }

            full_instruments = int(full_stats["instrument_count"])
            active_instruments = int(active_stats["instrument_count"])
            total_full_rows += len(rows)
            total_active_rows += len(active_rows)
            results.append(
                DateEquivalence(
                    as_of_date=as_of_date.isoformat(),
                    reference_manifest_include_inactive=include_inactive,
                    full_reference_rows=len(rows),
                    active_reference_rows=len(active_rows),
                    inactive_reference_rows=len(inactive_rows),
                    full_reference_instruments=full_instruments,
                    active_reference_instruments=active_instruments,
                    ambiguous_active_instruments=int(full_stats["ambiguous_active_instruments"]),
                    mixed_active_inactive_instruments=int(full_stats["mixed_active_inactive_instruments"]),
                    computed_full_discovery_members=len(full_members),
                    computed_active_only_discovery_members=len(active_members),
                    materialized_discovery_members=len(materialized_members),
                    computed_full_fingerprint=_member_fingerprint(full_members),
                    computed_active_only_fingerprint=_member_fingerprint(active_members),
                    materialized_fingerprint=_member_fingerprint(materialized_members),
                    full_vs_active_only_mismatch_count=len(full_vs_active),
                    active_only_vs_materialized_mismatch_count=len(active_vs_materialized),
                    pass_equivalence=passed,
                )
            )
            lineage.append(
                {
                    "date": as_of_date.isoformat(),
                    "reference_sha256": sha256_file(self.paths.reference_snapshot_file(as_of_date)),
                    "reference_manifest_sha256": sha256_file(self.paths.reference_snapshot_manifest(as_of_date)),
                    "universe_sha256": sha256_file(self.paths.universe_snapshot_file(as_of_date)),
                    "universe_manifest_sha256": sha256_file(self.paths.universe_snapshot_manifest(as_of_date)),
                }
            )

        all_pass = bool(results) and all(item.pass_equivalence for item in results)
        row_reduction_fraction = (
            1.0 - (total_active_rows / total_full_rows) if total_full_rows else 0.0
        )
        recommendation = (
            "GATE3_PREREGISTER_ACTIVE_ONLY_EXACT_PIT_ACQUISITION"
            if all_pass
            else "GATE3_ACTIVE_ONLY_EQUIVALENCE_NOT_PROVEN"
        )
        source_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "gate1_report_sha256": sha256_file(gate1_path),
                    "lineage": lineage,
                    "dates": [item.as_of_date for item in results],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        report_path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE2_REPORT_CONTRACT_VERSION,
            "gate2_policy_contract_version": PHASE25_GATE2_CONTRACT_VERSION,
            "phase25_gate2_policy_fingerprint": phase25_gate2_policy_fingerprint(),
            "phase25_gate1_policy_fingerprint": phase25_gate1_policy_fingerprint(),
            "gate1_report_contract_version": PHASE25_GATE1_REPORT_CONTRACT_VERSION,
            "gate1_report_path": str(gate1_path.resolve()),
            "gate1_report_sha256": sha256_file(gate1_path),
            "replay_origin": PHASE25_ROUTE_REPLAY_ORIGIN.isoformat(),
            "through_date": through_date.isoformat(),
            "tested_reference_dates": [item.as_of_date for item in results],
            "tested_reference_date_count": len(results),
            "total_full_reference_rows": total_full_rows,
            "total_active_reference_rows": total_active_rows,
            "total_inactive_reference_rows": total_full_rows - total_active_rows,
            "observed_row_reduction_fraction": row_reduction_fraction,
            "date_equivalence": [asdict(item) for item in results],
            "mismatch_previews": mismatch_previews,
            "source_lineage": lineage,
            "source_fingerprint": source_fingerprint,
            "all_dates_equivalent": all_pass,
            "discovery_overrides_modeled": False,
            "active_only_reference_acquisition_authority": False,
            "recommendation": recommendation,
            "protected_strategy_evidence_reads": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
            "provider_reads": PHASE25_PROVIDER_READS,
            "provider_writes": PHASE25_PROVIDER_WRITES,
            "broker_reads": PHASE25_BROKER_READS,
            "broker_writes": PHASE25_BROKER_WRITES,
            "order_writes": PHASE25_ORDER_WRITES,
            "paper_submits": PHASE25_PAPER_SUBMITS,
            "live_writes": PHASE25_LIVE_WRITES,
            "phase11_support_writes": PHASE25_PHASE11_SUPPORT_WRITES,
            "checks": {
                "provider_acquisition_authority_forbidden": PHASE25_GATE2_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED is False,
                "discovery_overrides_forbidden": PHASE25_GATE2_DISCOVERY_OVERRIDES_ALLOWED is False,
                "materialized_universe_equivalence_required": PHASE25_GATE2_REQUIRES_MATERIALIZED_UNIVERSE_EQUIVALENCE is True,
                "all_dates_equivalent": all_pass,
                "provider_reads_zero": PHASE25_PROVIDER_READS == 0,
                "provider_writes_zero": PHASE25_PROVIDER_WRITES == 0,
                "broker_reads_writes_zero": PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0,
                "order_paper_live_writes_zero": PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0,
                "support_writes_zero": PHASE25_PHASE11_SUPPORT_WRITES == 0,
                "protected_strategy_evidence_reads_zero": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0,
            },
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": all_pass,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
