from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import InstrumentIdentityQuality
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION
from packages.instruments.registry import REFERENCE_CONTRACT_VERSION
from packages.schemas.universe import (
    UNIVERSE_CONTRACT_VERSION,
    UniverseExclusion,
    UniverseMember,
    UniverseReasonCode,
    UniverseRoute,
    UniverseSnapshot,
    universe_members_fingerprint,
)
from packages.universe.eligibility import (
    ACTIVE_UNIVERSE_ELIGIBILITY_POLICY,
    UNIVERSE_ELIGIBILITY_POLICY_VERSION,
    UniverseEligibilityPolicy,
)


UNIVERSE_MANIFEST_VERSION = "universe-manifest-v1-source-policy-routing-bound"


@dataclass(frozen=True, slots=True)
class UniverseBuildResult:
    as_of_date: date
    reference_snapshot_date: date
    source_row_count: int
    source_instrument_count: int
    routed_instrument_count: int
    discovery_count: int
    exclusion_count: int
    position_count: int
    watchlist_count: int
    custom_count: int
    fingerprint: str
    snapshot_path: Path
    exclusion_path: Path
    manifest_path: Path
    reason_counts: dict[str, int]
    discovery_security_type_counts: dict[str, int]
    skipped: bool


def _safe(path: Path | str) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ordered_text(rows: Iterable[dict[str, object]], field: str) -> tuple[str, ...]:
    return tuple(sorted({_optional_text(row.get(field)) for row in rows if _optional_text(row.get(field))}))


def _routing_input_fingerprint(
    *,
    override_routes: Mapping[str, Iterable[UniverseRoute]],
    override_tickers: Mapping[str, str],
    unavailable_ids: set[str],
    quarantined_ids: set[str],
    manual_exclude_ids: set[str],
) -> str:
    payload = {
        "override_routes": {
            instrument_id: sorted(route.value for route in routes)
            for instrument_id, routes in sorted(override_routes.items())
        },
        "override_tickers": dict(sorted((key, value) for key, value in override_tickers.items())),
        "unavailable_ids": sorted(unavailable_ids),
        "quarantined_ids": sorted(quarantined_ids),
        "manual_exclude_ids": sorted(manual_exclude_ids),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class UniverseManager:
    """Build and persist the deterministic point-in-time ATLAS routing universe."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        policy: UniverseEligibilityPolicy = ACTIVE_UNIVERSE_ELIGIBILITY_POLICY,
    ) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.policy = policy

    def _validate_reference_contract(self, as_of_date: date) -> dict[str, Any]:
        manifest_path = self.paths.reference_snapshot_manifest(as_of_date)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Reference manifest is not available: {manifest_path}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Reference manifest is invalid JSON: {manifest_path}") from exc
        if manifest.get("contract_version") != REFERENCE_CONTRACT_VERSION:
            raise ValueError(
                "Reference snapshot contract is stale: "
                f"expected {REFERENCE_CONTRACT_VERSION}, got {manifest.get('contract_version')}"
            )
        if manifest.get("identity_contract_version") != IDENTITY_CONTRACT_VERSION:
            raise ValueError(
                "Reference identity contract is stale: "
                f"expected {IDENTITY_CONTRACT_VERSION}, got {manifest.get('identity_contract_version')}"
            )
        return manifest

    def _load_reference_rows(self, as_of_date: date) -> list[dict[str, object]]:
        source = self.paths.reference_snapshot_file(as_of_date)
        if not source.exists():
            raise FileNotFoundError(f"Reference snapshot is not available: {source}")
        con = connect_utc(":memory:")
        try:
            cursor = con.execute(
                f"""
                SELECT
                    instrument_id,
                    identity_quality,
                    as_of_date,
                    ticker,
                    name,
                    market,
                    locale,
                    primary_exchange,
                    security_type,
                    active,
                    delisted_utc,
                    provider_last_updated_utc
                FROM read_parquet('{_safe(source)}')
                ORDER BY instrument_id, ticker
                """
            )
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            con.close()
        if not rows:
            raise ValueError(f"Reference snapshot contains no rows: {source}")
        return rows

    @staticmethod
    def _normalize_override_routes(
        override_routes: Mapping[str, Iterable[UniverseRoute]] | None,
    ) -> dict[str, tuple[UniverseRoute, ...]]:
        normalized: dict[str, tuple[UniverseRoute, ...]] = {}
        for instrument_id, routes in (override_routes or {}).items():
            key = str(instrument_id).strip()
            if not key:
                raise ValueError("override instrument_id cannot be blank")
            route_set = {UniverseRoute(route) for route in routes}
            if UniverseRoute.DISCOVERY in route_set:
                raise ValueError("DISCOVERY is policy-derived and cannot be supplied as an override")
            if not route_set:
                continue
            normalized[key] = tuple(sorted(route_set, key=lambda item: item.value))
        return normalized

    @staticmethod
    def _representative_row(rows: list[dict[str, object]]) -> dict[str, object]:
        def key(row: dict[str, object]) -> tuple[str, str]:
            updated = row.get("provider_last_updated_utc")
            updated_key = updated.isoformat() if isinstance(updated, datetime) else str(updated or "")
            return updated_key, str(row.get("ticker") or "")

        return max(rows, key=key)

    @staticmethod
    def _override_reasons(routes: Iterable[UniverseRoute]) -> set[UniverseReasonCode]:
        mapping = {
            UniverseRoute.POSITION: UniverseReasonCode.POSITION_OVERRIDE,
            UniverseRoute.WATCHLIST: UniverseReasonCode.WATCHLIST_OVERRIDE,
            UniverseRoute.CUSTOM: UniverseReasonCode.CUSTOM_OVERRIDE,
        }
        return {mapping[route] for route in routes if route in mapping}

    def _exclusion(
        self,
        *,
        instrument_id: str,
        as_of_date: date,
        rows: list[dict[str, object]],
        reasons: set[UniverseReasonCode],
    ) -> UniverseExclusion:
        qualities = {InstrumentIdentityQuality(str(row["identity_quality"])) for row in rows}
        if len(qualities) != 1:
            raise ValueError(f"Instrument {instrument_id} has conflicting identity quality in one snapshot")
        return UniverseExclusion(
            instrument_id=instrument_id,
            as_of_date=as_of_date,
            identity_quality=next(iter(qualities)),
            tickers=_ordered_text(rows, "ticker"),
            active_tickers=_ordered_text((row for row in rows if bool(row["active"])), "ticker"),
            markets=_ordered_text(rows, "market"),
            locales=_ordered_text(rows, "locale"),
            primary_exchanges=_ordered_text(rows, "primary_exchange"),
            security_types=_ordered_text(rows, "security_type"),
            reason_codes=tuple(sorted(reasons, key=lambda item: item.value)),
        )

    def _write_json_models_to_parquet(
        self,
        *,
        models: Iterable[UniverseMember | UniverseExclusion],
        target: Path,
        model_kind: str,
    ) -> int:
        items = list(models)
        target.parent.mkdir(parents=True, exist_ok=True)
        staging_json = target.with_name(f".{target.name}.{os.getpid()}.{model_kind}.jsonl")
        with staging_json.open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(item.model_dump_json() + "\n")

        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        con = connect_utc(":memory:")
        try:
            dest = _safe(temp)
            compression = self.settings.data.parquet.compression.upper()
            if items:
                source = _safe(staging_json)
                if model_kind == "member":
                    query = f"""
                        SELECT
                            instrument_id,
                            ticker,
                            CAST(as_of_date AS DATE) AS as_of_date,
                            identity_quality,
                            name,
                            market,
                            locale,
                            primary_exchange,
                            security_type,
                            reference_active,
                            CAST(delisted_utc AS TIMESTAMPTZ) AS delisted_utc,
                            discovery_eligible,
                            reason_codes,
                            routes
                        FROM read_json_auto('{source}', format='newline_delimited')
                        ORDER BY instrument_id
                    """
                else:
                    query = f"""
                        SELECT
                            instrument_id,
                            CAST(as_of_date AS DATE) AS as_of_date,
                            identity_quality,
                            tickers,
                            active_tickers,
                            markets,
                            locales,
                            primary_exchanges,
                            security_types,
                            reason_codes
                        FROM read_json_auto('{source}', format='newline_delimited')
                        ORDER BY instrument_id
                    """
            elif model_kind == "member":
                query = """
                    SELECT
                        CAST(NULL AS VARCHAR) AS instrument_id,
                        CAST(NULL AS VARCHAR) AS ticker,
                        CAST(NULL AS DATE) AS as_of_date,
                        CAST(NULL AS VARCHAR) AS identity_quality,
                        CAST(NULL AS VARCHAR) AS name,
                        CAST(NULL AS VARCHAR) AS market,
                        CAST(NULL AS VARCHAR) AS locale,
                        CAST(NULL AS VARCHAR) AS primary_exchange,
                        CAST(NULL AS VARCHAR) AS security_type,
                        CAST(NULL AS BOOLEAN) AS reference_active,
                        CAST(NULL AS TIMESTAMPTZ) AS delisted_utc,
                        CAST(NULL AS BOOLEAN) AS discovery_eligible,
                        CAST(NULL AS VARCHAR[]) AS reason_codes,
                        CAST(NULL AS VARCHAR[]) AS routes
                    WHERE FALSE
                """
            else:
                query = """
                    SELECT
                        CAST(NULL AS VARCHAR) AS instrument_id,
                        CAST(NULL AS DATE) AS as_of_date,
                        CAST(NULL AS VARCHAR) AS identity_quality,
                        CAST(NULL AS VARCHAR[]) AS tickers,
                        CAST(NULL AS VARCHAR[]) AS active_tickers,
                        CAST(NULL AS VARCHAR[]) AS markets,
                        CAST(NULL AS VARCHAR[]) AS locales,
                        CAST(NULL AS VARCHAR[]) AS primary_exchanges,
                        CAST(NULL AS VARCHAR[]) AS security_types,
                        CAST(NULL AS VARCHAR[]) AS reason_codes
                    WHERE FALSE
                """
            con.execute(f"COPY ({query}) TO '{dest}' (FORMAT PARQUET, COMPRESSION {compression})")
        finally:
            con.close()
            staging_json.unlink(missing_ok=True)
        promote(temp, target)
        return len(items)

    @staticmethod
    def _result_from_manifest(
        *,
        manifest: dict[str, Any],
        snapshot_path: Path,
        exclusion_path: Path,
        manifest_path: Path,
        skipped: bool,
    ) -> UniverseBuildResult:
        counts = manifest["counts"]
        return UniverseBuildResult(
            as_of_date=date.fromisoformat(manifest["as_of_date"]),
            reference_snapshot_date=date.fromisoformat(manifest["reference_snapshot_date"]),
            source_row_count=int(counts["source_rows"]),
            source_instrument_count=int(counts["source_instruments"]),
            routed_instrument_count=int(counts["routed_instruments"]),
            discovery_count=int(counts["discovery"]),
            exclusion_count=int(counts["excluded"]),
            position_count=int(counts["position"]),
            watchlist_count=int(counts["watchlist"]),
            custom_count=int(counts["custom"]),
            fingerprint=str(manifest["universe_fingerprint"]),
            snapshot_path=snapshot_path,
            exclusion_path=exclusion_path,
            manifest_path=manifest_path,
            reason_counts={str(k): int(v) for k, v in manifest["reason_counts"].items()},
            discovery_security_type_counts={
                str(k): int(v) for k, v in manifest["discovery_security_type_counts"].items()
            },
            skipped=skipped,
        )

    def build(
        self,
        as_of_date: date,
        *,
        reference_snapshot_date: date | None = None,
        override_routes: Mapping[str, Iterable[UniverseRoute]] | None = None,
        override_tickers: Mapping[str, str] | None = None,
        unavailable_ids: Iterable[str] = (),
        quarantined_ids: Iterable[str] = (),
        manual_exclude_ids: Iterable[str] = (),
        force: bool = False,
    ) -> UniverseBuildResult:
        reference_snapshot_date = reference_snapshot_date or as_of_date
        if reference_snapshot_date != as_of_date:
            raise ValueError(
                "Phase 7 currently requires an exact point-in-time reference snapshot; "
                "reference_snapshot_date must equal as_of_date"
            )

        self._validate_reference_contract(reference_snapshot_date)
        source_path = self.paths.reference_snapshot_file(reference_snapshot_date)
        source_sha256 = _sha256_file(source_path)
        snapshot_path = self.paths.universe_snapshot_file(as_of_date)
        exclusion_path = self.paths.universe_exclusion_file(as_of_date)
        manifest_path = self.paths.universe_snapshot_manifest(as_of_date)

        overrides = self._normalize_override_routes(override_routes)
        override_ticker_map = {
            str(key).strip(): str(value).strip()
            for key, value in (override_tickers or {}).items()
            if str(key).strip() and str(value).strip()
        }
        unavailable = {str(item).strip() for item in unavailable_ids if str(item).strip()}
        quarantined = {str(item).strip() for item in quarantined_ids if str(item).strip()}
        manual_excludes = {str(item).strip() for item in manual_exclude_ids if str(item).strip()}
        input_fingerprint = _routing_input_fingerprint(
            override_routes=overrides,
            override_tickers=override_ticker_map,
            unavailable_ids=unavailable,
            quarantined_ids=quarantined,
            manual_exclude_ids=manual_excludes,
        )

        if snapshot_path.exists() and exclusion_path.exists() and manifest_path.exists() and not force:
            try:
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = {}
            if (
                existing.get("manifest_version") == UNIVERSE_MANIFEST_VERSION
                and existing.get("universe_contract_version") == UNIVERSE_CONTRACT_VERSION
                and existing.get("policy_version") == UNIVERSE_ELIGIBILITY_POLICY_VERSION
                and existing.get("policy_fingerprint") == self.policy.fingerprint
                and existing.get("source_reference_sha256") == source_sha256
                and existing.get("routing_input_fingerprint") == input_fingerprint
                and existing.get("snapshot_sha256") == _sha256_file(snapshot_path)
                and existing.get("exclusion_sha256") == _sha256_file(exclusion_path)
            ):
                return self._result_from_manifest(
                    manifest=existing,
                    snapshot_path=snapshot_path,
                    exclusion_path=exclusion_path,
                    manifest_path=manifest_path,
                    skipped=True,
                )

        rows = self._load_reference_rows(reference_snapshot_date)
        by_instrument: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            by_instrument[str(row["instrument_id"])].append(row)

        unknown_overrides = sorted(set(overrides) - set(by_instrument))
        if unknown_overrides:
            raise ValueError(
                "Override instrument IDs are absent from the exact reference snapshot: "
                + ", ".join(unknown_overrides[:10])
            )

        members: list[UniverseMember] = []
        exclusions: list[UniverseExclusion] = []
        reason_counts: Counter[str] = Counter()
        security_counts: Counter[str] = Counter()

        for instrument_id in sorted(by_instrument):
            group = by_instrument[instrument_id]
            qualities = {InstrumentIdentityQuality(str(row["identity_quality"])) for row in group}
            if len(qualities) != 1:
                raise ValueError(f"Instrument {instrument_id} has conflicting identity quality")
            identity_quality = next(iter(qualities))
            active_rows = [row for row in group if bool(row["active"])]
            requested_routes = overrides.get(instrument_id, ())
            override_ticker = override_ticker_map.get(instrument_id)

            ambiguity = len(active_rows) > 1
            routing_row: dict[str, object] | None = None
            if len(active_rows) == 1:
                routing_row = active_rows[0]
            elif len(active_rows) > 1 and override_ticker:
                matches = [row for row in active_rows if str(row["ticker"]) == override_ticker]
                if len(matches) == 1:
                    routing_row = matches[0]
            elif not active_rows and requested_routes:
                if override_ticker:
                    matches = [row for row in group if str(row["ticker"]) == override_ticker]
                    if len(matches) == 1:
                        routing_row = matches[0]
                elif len(group) == 1:
                    routing_row = group[0]

            if requested_routes and routing_row is None:
                raise ValueError(
                    f"Override for {instrument_id} has no unambiguous routing ticker; "
                    "supply override_tickers with the exact provider-native ticker"
                )

            if routing_row is None:
                representative = self._representative_row(active_rows or group)
                _, base_reasons = self.policy.evaluate(
                    reference_active=bool(representative["active"]),
                    delisted_utc=representative.get("delisted_utc"),
                    market=_optional_text(representative.get("market")),
                    locale=_optional_text(representative.get("locale")),
                    primary_exchange=_optional_text(representative.get("primary_exchange")),
                    security_type=_optional_text(representative.get("security_type")),
                    identity_quality=identity_quality,
                    data_available=instrument_id not in unavailable,
                    data_quarantined=instrument_id in quarantined,
                    manual_exclude=instrument_id in manual_excludes,
                )
                reasons = set(base_reasons)
                reasons.discard(UniverseReasonCode.ELIGIBLE)
                if not active_rows:
                    reasons.add(UniverseReasonCode.REFERENCE_INACTIVE)
                if ambiguity:
                    reasons.add(UniverseReasonCode.AMBIGUOUS_ACTIVE_TICKER)
                exclusion = self._exclusion(
                    instrument_id=instrument_id,
                    as_of_date=as_of_date,
                    rows=group,
                    reasons=reasons,
                )
                exclusions.append(exclusion)
                reason_counts.update(code.value for code in exclusion.reason_codes)
                continue

            eligible, base_reasons = self.policy.evaluate(
                reference_active=bool(routing_row["active"]),
                delisted_utc=routing_row.get("delisted_utc"),
                market=_optional_text(routing_row.get("market")),
                locale=_optional_text(routing_row.get("locale")),
                primary_exchange=_optional_text(routing_row.get("primary_exchange")),
                security_type=_optional_text(routing_row.get("security_type")),
                identity_quality=identity_quality,
                data_available=instrument_id not in unavailable,
                data_quarantined=instrument_id in quarantined,
                manual_exclude=instrument_id in manual_excludes,
            )
            reasons = set(base_reasons)
            if ambiguity:
                eligible = False
                reasons.discard(UniverseReasonCode.ELIGIBLE)
                reasons.add(UniverseReasonCode.AMBIGUOUS_ACTIVE_TICKER)

            routes = set(requested_routes)
            if eligible:
                routes.add(UniverseRoute.DISCOVERY)
            elif requested_routes:
                reasons.update(self._override_reasons(requested_routes))

            if not routes:
                exclusion = self._exclusion(
                    instrument_id=instrument_id,
                    as_of_date=as_of_date,
                    rows=group,
                    reasons=reasons,
                )
                exclusions.append(exclusion)
                reason_counts.update(code.value for code in exclusion.reason_codes)
                continue

            member = UniverseMember(
                instrument_id=instrument_id,
                ticker=str(routing_row["ticker"]),
                as_of_date=as_of_date,
                identity_quality=identity_quality,
                name=_optional_text(routing_row.get("name")),
                market=_optional_text(routing_row.get("market")),
                locale=_optional_text(routing_row.get("locale")),
                primary_exchange=_optional_text(routing_row.get("primary_exchange")),
                security_type=_optional_text(routing_row.get("security_type")),
                reference_active=bool(routing_row["active"]),
                delisted_utc=routing_row.get("delisted_utc"),
                discovery_eligible=eligible,
                reason_codes=tuple(sorted(reasons, key=lambda item: item.value)),
                routes=tuple(sorted(routes, key=lambda item: item.value)),
            )
            members.append(member)
            reason_counts.update(code.value for code in member.reason_codes)
            if member.discovery_eligible:
                security_counts.update([member.security_type or "<NULL>"])

        generated_at = datetime.now(UTC)
        member_tuple = tuple(sorted(members, key=lambda item: item.instrument_id))
        fingerprint = universe_members_fingerprint(
            as_of_date=as_of_date,
            reference_snapshot_date=reference_snapshot_date,
            members=member_tuple,
        )
        snapshot = UniverseSnapshot(
            as_of_date=as_of_date,
            reference_snapshot_date=reference_snapshot_date,
            generated_at_utc=generated_at,
            members=member_tuple,
            fingerprint=fingerprint,
        )

        self._write_json_models_to_parquet(models=snapshot.members, target=snapshot_path, model_kind="member")
        self._write_json_models_to_parquet(
            models=tuple(sorted(exclusions, key=lambda item: item.instrument_id)),
            target=exclusion_path,
            model_kind="exclusion",
        )

        position_count = sum(UniverseRoute.POSITION in item.routes for item in snapshot.members)
        watchlist_count = sum(UniverseRoute.WATCHLIST in item.routes for item in snapshot.members)
        custom_count = sum(UniverseRoute.CUSTOM in item.routes for item in snapshot.members)
        manifest = {
            "manifest_version": UNIVERSE_MANIFEST_VERSION,
            "universe_contract_version": UNIVERSE_CONTRACT_VERSION,
            "policy_version": UNIVERSE_ELIGIBILITY_POLICY_VERSION,
            "policy_fingerprint": self.policy.fingerprint,
            "as_of_date": as_of_date.isoformat(),
            "reference_snapshot_date": reference_snapshot_date.isoformat(),
            "reference_contract_version": REFERENCE_CONTRACT_VERSION,
            "identity_contract_version": IDENTITY_CONTRACT_VERSION,
            "source_reference_path": str(source_path),
            "source_reference_sha256": source_sha256,
            "routing_input_fingerprint": input_fingerprint,
            "universe_fingerprint": snapshot.fingerprint,
            "snapshot_path": str(snapshot_path),
            "snapshot_sha256": _sha256_file(snapshot_path),
            "exclusion_path": str(exclusion_path),
            "exclusion_sha256": _sha256_file(exclusion_path),
            "generated_at_utc": generated_at.isoformat(),
            "counts": {
                "source_rows": len(rows),
                "source_instruments": len(by_instrument),
                "routed_instruments": snapshot.instrument_count,
                "discovery": snapshot.discovery_count,
                "excluded": len(exclusions),
                "position": position_count,
                "watchlist": watchlist_count,
                "custom": custom_count,
            },
            "reason_counts": dict(sorted(reason_counts.items())),
            "discovery_security_type_counts": dict(sorted(security_counts.items())),
        }
        atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return self._result_from_manifest(
            manifest=manifest,
            snapshot_path=snapshot_path,
            exclusion_path=exclusion_path,
            manifest_path=manifest_path,
            skipped=False,
        )
