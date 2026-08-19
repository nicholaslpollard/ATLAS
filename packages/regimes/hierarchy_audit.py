from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .classification_probe import REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION
from .input_inventory import (
    REGIME_INPUT_INVENTORY_CONTRACT_VERSION,
    SECTOR_PROXY_TICKERS,
)
from .state_engine import (
    REGIME_STATE_MANIFEST_VERSION,
    REGIME_STATE_SNAPSHOT_CONTRACT_VERSION,
)
from .ticker_state_engine import (
    TICKER_STATE_MANIFEST_VERSION,
    TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
    TickerStateEngine,
)


REGIME_HIERARCHY_AUDIT_CONTRACT_VERSION = (
    "regime-hierarchy-integrity-v1-market-sector-proxy-optional-sic-ticker"
)
REGIME_HIERARCHY_INDUSTRY_POLICY = "OPTIONAL_AUTHORITATIVE_SIC_ONLY"
REGIME_HIERARCHY_SECTOR_ASSIGNMENT_POLICY = "NO_GUESSED_CROSSWALK"


@dataclass(frozen=True, slots=True)
class RegimeHierarchyAuditReport:
    contract_version: str
    generated_at_utc: str
    as_of_date: str
    wall_seconds: float
    audit_status: str
    hierarchy_ready: bool
    market_snapshot_valid: bool
    market_state: str | None
    sector_expected_count: int
    sector_present_count: int
    sector_exact_set: bool
    sector_effective_state_count: int
    routed_expected_count: int
    ticker_record_count: int
    ticker_unique_instrument_count: int
    ticker_unique_current_ticker_count: int
    route_exact_match_count: int
    missing_routed_count: int
    extra_ticker_state_count: int
    current_ticker_mismatch_count: int
    effective_ticker_state_count: int
    no_current_ticker_state_count: int
    market_context_attachable_count: int
    history_status_counts: dict[str, int]
    persistence_status_counts: dict[str, int]
    risk_mode_counts: dict[str, int]
    industry_policy: str
    sector_assignment_policy: str
    local_classification_columns: dict[str, tuple[str, ...]]
    classification_sample_count: int
    classification_exact_ticker_match_count: int
    classification_sic_count: int
    classification_missing_sic_count: int
    classification_provider_error_count: int
    optional_sic_absence_is_allowed: bool
    market_snapshot_sha256: str
    ticker_snapshot_sha256: str
    report_path: str


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {path}") from exc


def sector_layer_valid(sectors: dict[str, Any]) -> tuple[bool, int]:
    expected = set(SECTOR_PROXY_TICKERS)
    present = set(str(key) for key in sectors)
    effective_count = 0
    for ticker in SECTOR_PROXY_TICKERS:
        item = sectors.get(ticker)
        if not isinstance(item, dict):
            continue
        effective = item.get("effective")
        if isinstance(effective, dict) and effective.get("composite"):
            effective_count += 1
    return present == expected, effective_count


def hierarchy_ready(
    *,
    market_snapshot_valid: bool,
    sector_exact_set: bool,
    sector_effective_state_count: int,
    routed_expected_count: int,
    ticker_record_count: int,
    ticker_unique_instrument_count: int,
    route_exact_match_count: int,
    missing_routed_count: int,
    extra_ticker_state_count: int,
    current_ticker_mismatch_count: int,
) -> bool:
    return bool(
        market_snapshot_valid
        and sector_exact_set
        and sector_effective_state_count == len(SECTOR_PROXY_TICKERS)
        and routed_expected_count == ticker_record_count
        and ticker_unique_instrument_count == ticker_record_count
        and route_exact_match_count == routed_expected_count
        and missing_routed_count == 0
        and extra_ticker_state_count == 0
        and current_ticker_mismatch_count == 0
    )


class RegimeHierarchyAudit:
    """Validate the accepted Phase 9 market -> sector/industry -> ticker hierarchy.

    Market context is global. The Select Sector SPDR layer is validated as a complete
    proxy context set but is never assigned to an individual ticker by an inferred
    crosswalk. Provider-native SIC industry facts remain optional point-in-time facts;
    missing SIC is represented as absence, not guessed classification.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.ticker_engine = TickerStateEngine(settings)

    def report_path(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "regimes" / "hierarchy_audit" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def run(self, as_of_date: date) -> RegimeHierarchyAuditReport:
        started = perf_counter()
        market_snapshot_path = self.paths.regime_state_snapshot(as_of_date)
        market_manifest_path = self.paths.regime_state_manifest(as_of_date)
        ticker_snapshot_path = self.ticker_engine.snapshot_path(as_of_date)
        ticker_manifest_path = self.ticker_engine.manifest_path(as_of_date)
        universe_path = self.paths.universe_snapshot_file(as_of_date)
        discovery_path = self.paths.discovery_state_file(as_of_date)
        inventory_path = self.paths.regime_input_inventory_report(as_of_date)
        classification_path = self.paths.regime_classification_probe_report(as_of_date)

        required = (
            market_snapshot_path,
            market_manifest_path,
            ticker_snapshot_path,
            ticker_manifest_path,
            universe_path,
            discovery_path,
            inventory_path,
            classification_path,
        )
        missing = [path for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Phase 9 hierarchy audit inputs are missing:\n  "
                + "\n  ".join(str(path) for path in missing)
            )

        market_snapshot = _read_json(market_snapshot_path)
        market_manifest = _read_json(market_manifest_path)
        ticker_manifest = _read_json(ticker_manifest_path)
        inventory = _read_json(inventory_path)
        classification = _read_json(classification_path)

        market_sha = sha256_file(market_snapshot_path)
        ticker_sha = sha256_file(ticker_snapshot_path)
        market_snapshot_valid = bool(
            market_snapshot.get("snapshot_contract_version")
            == REGIME_STATE_SNAPSHOT_CONTRACT_VERSION
            and market_snapshot.get("as_of_date") == as_of_date.isoformat()
            and market_manifest.get("manifest_version") == REGIME_STATE_MANIFEST_VERSION
            and market_manifest.get("snapshot_sha256") == market_sha
            and market_manifest.get("as_of_date") == as_of_date.isoformat()
            and isinstance(market_snapshot.get("market"), dict)
            and isinstance(market_snapshot["market"].get("effective"), dict)
            and bool(market_snapshot["market"]["effective"].get("composite"))
        )
        if ticker_manifest.get("manifest_version") != TICKER_STATE_MANIFEST_VERSION:
            raise ValueError("Ticker-state manifest contract is stale")
        if ticker_manifest.get("snapshot_contract_version") != TICKER_STATE_SNAPSHOT_CONTRACT_VERSION:
            raise ValueError("Ticker-state snapshot contract is stale")
        if ticker_manifest.get("as_of_date") != as_of_date.isoformat():
            raise ValueError("Ticker-state manifest as-of mismatch")
        if ticker_manifest.get("snapshot_sha256") != ticker_sha:
            raise ValueError("Ticker-state snapshot hash does not match its manifest")
        if inventory.get("contract_version") != REGIME_INPUT_INVENTORY_CONTRACT_VERSION:
            raise ValueError("Regime input inventory contract is stale")
        if classification.get("contract_version") != REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION:
            raise ValueError("Regime classification probe contract is stale")

        sectors = market_snapshot.get("sectors")
        if not isinstance(sectors, dict):
            sectors = {}
        sector_exact_set, sector_effective_count = sector_layer_valid(sectors)

        con = connect_utc(":memory:")
        try:
            row = con.execute(
                f"""
                WITH u AS (
                    SELECT instrument_id, ticker, routes
                    FROM read_parquet({sql_string(universe_path)})
                ), d AS (
                    SELECT instrument_id
                    FROM read_parquet({sql_string(discovery_path)})
                ), expected AS (
                    SELECT u.instrument_id, u.ticker
                    FROM u
                    LEFT JOIN d USING (instrument_id)
                    WHERE d.instrument_id IS NOT NULL
                       OR list_contains(u.routes, 'position')
                       OR list_contains(u.routes, 'watchlist')
                       OR list_contains(u.routes, 'custom')
                ), actual AS (
                    SELECT instrument_id, ticker, effective_ticker_state
                    FROM read_parquet({sql_string(ticker_snapshot_path)})
                ), joined AS (
                    SELECT
                        coalesce(e.instrument_id, a.instrument_id) AS instrument_id,
                        e.ticker AS expected_ticker,
                        a.ticker AS actual_ticker,
                        a.effective_ticker_state
                    FROM expected e
                    FULL OUTER JOIN actual a USING (instrument_id)
                )
                SELECT
                    (SELECT count(*) FROM expected),
                    (SELECT count(*) FROM actual),
                    (SELECT count(DISTINCT instrument_id) FROM actual),
                    (SELECT count(DISTINCT ticker) FROM actual),
                    count(*) FILTER (
                        WHERE expected_ticker IS NOT NULL
                          AND actual_ticker IS NOT NULL
                          AND expected_ticker = actual_ticker
                    ),
                    count(*) FILTER (WHERE expected_ticker IS NOT NULL AND actual_ticker IS NULL),
                    count(*) FILTER (WHERE expected_ticker IS NULL AND actual_ticker IS NOT NULL),
                    count(*) FILTER (
                        WHERE expected_ticker IS NOT NULL
                          AND actual_ticker IS NOT NULL
                          AND expected_ticker <> actual_ticker
                    ),
                    count(*) FILTER (WHERE effective_ticker_state IS NOT NULL),
                    count(*) FILTER (
                        WHERE actual_ticker IS NOT NULL AND effective_ticker_state IS NULL
                    )
                FROM joined
                """
            ).fetchone()
        finally:
            con.close()

        routed_expected = int(row[0])
        ticker_records = int(row[1])
        unique_instruments = int(row[2])
        unique_tickers = int(row[3])
        exact_matches = int(row[4])
        missing_routed = int(row[5])
        extra_ticker = int(row[6])
        ticker_mismatch = int(row[7])
        effective_count = int(row[8])
        no_current_count = int(row[9])

        ready = hierarchy_ready(
            market_snapshot_valid=market_snapshot_valid,
            sector_exact_set=sector_exact_set,
            sector_effective_state_count=sector_effective_count,
            routed_expected_count=routed_expected,
            ticker_record_count=ticker_records,
            ticker_unique_instrument_count=unique_instruments,
            route_exact_match_count=exact_matches,
            missing_routed_count=missing_routed,
            extra_ticker_state_count=extra_ticker,
            current_ticker_mismatch_count=ticker_mismatch,
        )

        classification_columns = inventory.get("classification_columns", {})
        local_columns = {
            str(key): tuple(str(item) for item in (value or []))
            for key, value in classification_columns.items()
        }
        target = self.report_path(as_of_date)
        target.parent.mkdir(parents=True, exist_ok=True)
        report = RegimeHierarchyAuditReport(
            contract_version=REGIME_HIERARCHY_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            as_of_date=as_of_date.isoformat(),
            wall_seconds=perf_counter() - started,
            audit_status="PASS" if ready else "FAIL",
            hierarchy_ready=ready,
            market_snapshot_valid=market_snapshot_valid,
            market_state=(
                str(market_snapshot["market"]["effective"]["composite"])
                if market_snapshot_valid
                else None
            ),
            sector_expected_count=len(SECTOR_PROXY_TICKERS),
            sector_present_count=len(sectors),
            sector_exact_set=sector_exact_set,
            sector_effective_state_count=sector_effective_count,
            routed_expected_count=routed_expected,
            ticker_record_count=ticker_records,
            ticker_unique_instrument_count=unique_instruments,
            ticker_unique_current_ticker_count=unique_tickers,
            route_exact_match_count=exact_matches,
            missing_routed_count=missing_routed,
            extra_ticker_state_count=extra_ticker,
            current_ticker_mismatch_count=ticker_mismatch,
            effective_ticker_state_count=effective_count,
            no_current_ticker_state_count=no_current_count,
            market_context_attachable_count=ticker_records if market_snapshot_valid else 0,
            history_status_counts={
                str(key): int(value)
                for key, value in ticker_manifest.get("history_status_counts", {}).items()
            },
            persistence_status_counts={
                str(key): int(value)
                for key, value in ticker_manifest.get("persistence_status_counts", {}).items()
            },
            risk_mode_counts={
                str(key): int(value)
                for key, value in ticker_manifest.get("risk_mode_counts", {}).items()
            },
            industry_policy=REGIME_HIERARCHY_INDUSTRY_POLICY,
            sector_assignment_policy=REGIME_HIERARCHY_SECTOR_ASSIGNMENT_POLICY,
            local_classification_columns=local_columns,
            classification_sample_count=int(classification.get("sampled_count", 0)),
            classification_exact_ticker_match_count=int(
                classification.get("exact_ticker_match_count", 0)
            ),
            classification_sic_count=int(classification.get("sic_code_count", 0)),
            classification_missing_sic_count=int(classification.get("missing_sic_count", 0)),
            classification_provider_error_count=int(classification.get("provider_error_count", 0)),
            optional_sic_absence_is_allowed=True,
            market_snapshot_sha256=market_sha,
            ticker_snapshot_sha256=ticker_sha,
            report_path=str(target),
        )
        from packages.core.atomic_io import atomic_write_text

        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
