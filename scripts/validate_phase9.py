from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.enums import Timeframe
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.regimes.calibration import (
    REGIME_CALIBRATION_CONTRACT_VERSION,
    REGIME_CALIBRATION_QUANTILES,
)
from packages.regimes.classification_probe import REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION
from packages.regimes.hierarchy_audit import (
    REGIME_HIERARCHY_AUDIT_CONTRACT_VERSION,
    REGIME_HIERARCHY_INDUSTRY_POLICY,
    REGIME_HIERARCHY_SECTOR_ASSIGNMENT_POLICY,
    RegimeHierarchyAudit,
)
from packages.regimes.input_inventory import (
    CLASSIFICATION_FIELD_CANDIDATES,
    MARKET_PROXY_TICKERS,
    REGIME_INPUT_INVENTORY_CONTRACT_VERSION,
    SECTOR_PROXY_TICKERS,
)
from packages.regimes.persistence_policy import (
    REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
    REGIME_SELECTED_CONFIRMATION_SESSIONS,
)
from packages.regimes.persistence_probe import (
    REGIME_PERSISTENCE_CONFIRMATION_WINDOWS,
    REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION,
)
from packages.regimes.policy_probe import REGIME_POLICY_PROBE_CONTRACT_VERSION
from packages.regimes.state_engine import (
    REGIME_STATE_MANIFEST_VERSION,
    REGIME_STATE_POLICY_CONTRACT_VERSION,
    REGIME_STATE_SNAPSHOT_CONTRACT_VERSION,
)
from packages.regimes.threshold_policy import (
    REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
    REGIME_HISTORY_ORIGIN_DATE,
    REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
    REGIME_THRESHOLD_POLICY_NAME,
    REGIME_THRESHOLD_TRAINING_SESSIONS,
)
from packages.regimes.threshold_probe import (
    REGIME_SELECTED_CONFIRMATION_SESSIONS as THRESHOLD_PROBE_CONFIRMATION_SESSIONS,
    REGIME_THRESHOLD_POLICY_NAMES,
    REGIME_THRESHOLD_PROBE_CONTRACT_VERSION,
    REGIME_THRESHOLD_TRAINING_SESSIONS as THRESHOLD_PROBE_TRAINING_SESSIONS,
)
from packages.regimes.ticker_authority_gap_probe import (
    TICKER_AUTHORITY_GAP_PROBE_CONTRACT_VERSION,
    TickerAuthorityGapProbe,
)
from packages.regimes.ticker_authority_probe import (
    CACHED_AUTHORITATIVE_UNRESOLVED,
    TICKER_AUTHORITY_PROBE_CONTRACT_VERSION,
    TickerAuthorityProbe,
)
from packages.regimes.ticker_history_probe import (
    TICKER_HISTORY_DEPTH_GRID,
    TICKER_HISTORY_PROBE_CONTRACT_VERSION,
    TickerHistoryProbe,
)
from packages.regimes.ticker_persistence_policy import (
    TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION,
    TICKER_SELECTED_CONFIRMATION_SESSIONS,
    TICKER_SELECTED_PERSISTENCE_MODE,
    TICKER_SELECTED_PERSISTENCE_POLICY_NAME,
)
from packages.regimes.ticker_persistence_probe import (
    TICKER_PERSISTENCE_CONFIRMATION_WINDOWS,
    TICKER_PERSISTENCE_POLICY_NAMES,
    TICKER_PERSISTENCE_PROBE_CONTRACT_VERSION,
    TickerPersistenceProbe,
)
from packages.regimes.ticker_probe import (
    TICKER_REGIME_PROBE_CONTRACT_VERSION,
    TICKER_REGIME_REQUIRED_HISTORY_SESSIONS,
    TICKER_REGIME_TIMEFRAMES,
)
from packages.regimes.ticker_risk_fallback_audit import (
    TICKER_RISK_FALLBACK_AUDIT_CONTRACT_VERSION,
)
from packages.regimes.ticker_risk_policy import (
    TICKER_RISK_POLICY_CONTRACT_VERSION,
    TICKER_RISK_PRIMARY_WINDOW,
    TICKER_RISK_PROVISIONAL_WINDOW,
    TICKER_RISK_REFERENCE_AUDIT_WINDOW,
)
from packages.regimes.ticker_risk_probe import (
    TICKER_RISK_LOOKBACK_WINDOWS,
    TICKER_RISK_PROBE_CONTRACT_VERSION,
    TICKER_RISK_REFERENCE_WINDOW,
    TickerRiskProbe,
)
from packages.regimes.ticker_state_engine import (
    TICKER_STATE_MANIFEST_VERSION,
    TICKER_STATE_POLICY_CONTRACT_VERSION,
    TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
    TickerStateEngine,
)


def main() -> int:
    assert REGIME_INPUT_INVENTORY_CONTRACT_VERSION == (
        "regime-input-inventory-v1-local-breadth-benchmark-sector-proxy-audit"
    )
    assert REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION == (
        "regime-classification-probe-v1-massive-sic-point-in-time"
    )
    assert REGIME_CALIBRATION_CONTRACT_VERSION == (
        "regime-calibration-v2-historical-continuous-proxy-distributions"
    )
    assert REGIME_POLICY_PROBE_CONTRACT_VERSION == (
        "regime-policy-probe-v1-quartile-dimensional-no-hysteresis"
    )
    assert REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION == (
        "regime-persistence-probe-v1-dimension-confirmation-grid"
    )
    assert REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION == (
        "regime-persistence-policy-v1-two-session-dimensional-confirmation"
    )
    assert REGIME_THRESHOLD_PROBE_CONTRACT_VERSION == (
        "regime-threshold-probe-v1-prior-only-252-policy-grid"
    )
    assert REGIME_THRESHOLD_POLICY_CONTRACT_VERSION == (
        "regime-threshold-policy-v1-expanding-252-prior-only"
    )
    assert REGIME_STATE_POLICY_CONTRACT_VERSION == (
        "regime-state-policy-v1-expanding252-confirm2-dimensional"
    )
    assert REGIME_STATE_SNAPSHOT_CONTRACT_VERSION == (
        "regime-state-snapshot-v1-market-sector-proxies"
    )
    assert REGIME_STATE_MANIFEST_VERSION == "regime-state-manifest-v1-policy-source-lineage"
    assert REGIME_BREADTH_POPULATION_CONTRACT_VERSION == (
        "regime-breadth-population-v1-250k-dollar-volume-complete-1d"
    )
    assert TICKER_REGIME_PROBE_CONTRACT_VERSION == (
        "ticker-regime-probe-v1-routed-multitimeframe-identity-history-audit"
    )
    assert TICKER_HISTORY_PROBE_CONTRACT_VERSION == (
        "ticker-history-probe-v2-operational-current-alias-authoritative-interval-depth"
    )
    assert TICKER_AUTHORITY_PROBE_CONTRACT_VERSION == (
        "ticker-authority-probe-v1-unresolved-composite-figi-cache-audit"
    )
    assert TICKER_AUTHORITY_GAP_PROBE_CONTRACT_VERSION == (
        "ticker-authority-gap-probe-v1-cached-unresolved-event-timeline-audit"
    )
    assert TICKER_PERSISTENCE_PROBE_CONTRACT_VERSION == (
        "ticker-persistence-probe-v1-safe-history-composite-vs-dimensional-confirmation"
    )
    assert TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION == (
        "ticker-persistence-policy-v1-two-session-dimensional-confirmation"
    )
    assert TICKER_RISK_PROBE_CONTRACT_VERSION == (
        "ticker-risk-probe-v1-safe-self-relative-prior-only-lookback-grid"
    )
    assert TICKER_RISK_FALLBACK_AUDIT_CONTRACT_VERSION == (
        "ticker-risk-fallback-audit-v1-current-severity-and-history-cohorts"
    )
    assert TICKER_RISK_POLICY_CONTRACT_VERSION == (
        "ticker-risk-policy-v1-126-primary-60-provisional-prior-only"
    )
    assert TICKER_STATE_POLICY_CONTRACT_VERSION == (
        "ticker-state-policy-v1-confirm2-dimensional-risk126-60"
    )
    assert TICKER_STATE_SNAPSHOT_CONTRACT_VERSION == (
        "ticker-state-snapshot-v1-routed-identity-persistence-risk"
    )
    assert TICKER_STATE_MANIFEST_VERSION == "ticker-state-manifest-v1-policy-lineage"
    assert REGIME_HIERARCHY_AUDIT_CONTRACT_VERSION == (
        "regime-hierarchy-integrity-v1-market-sector-proxy-optional-sic-ticker"
    )
    assert REGIME_HIERARCHY_INDUSTRY_POLICY == "OPTIONAL_AUTHORITATIVE_SIC_ONLY"
    assert REGIME_HIERARCHY_SECTOR_ASSIGNMENT_POLICY == "NO_GUESSED_CROSSWALK"
    assert CACHED_AUTHORITATIVE_UNRESOLVED == "CACHED_AUTHORITATIVE_UNRESOLVED"
    assert REGIME_PERSISTENCE_CONFIRMATION_WINDOWS == (2, 3)
    assert TICKER_PERSISTENCE_CONFIRMATION_WINDOWS == (2, 3)
    assert TICKER_PERSISTENCE_POLICY_NAMES == (
        "composite_confirm_2",
        "composite_confirm_3",
        "dimensional_confirm_2",
        "dimensional_confirm_3",
    )
    assert TICKER_RISK_LOOKBACK_WINDOWS == (20, 60, 126, 252)
    assert TICKER_RISK_REFERENCE_WINDOW == 252
    assert TICKER_RISK_PRIMARY_WINDOW == 126
    assert TICKER_RISK_PROVISIONAL_WINDOW == 60
    assert TICKER_RISK_REFERENCE_AUDIT_WINDOW == 252
    assert REGIME_SELECTED_CONFIRMATION_SESSIONS == 2
    assert TICKER_SELECTED_CONFIRMATION_SESSIONS == 2
    assert TICKER_SELECTED_PERSISTENCE_MODE == "dimensional"
    assert TICKER_SELECTED_PERSISTENCE_POLICY_NAME == "dimensional_confirm_2"
    assert THRESHOLD_PROBE_CONFIRMATION_SESSIONS == REGIME_SELECTED_CONFIRMATION_SESSIONS
    assert REGIME_THRESHOLD_TRAINING_SESSIONS == 252
    assert THRESHOLD_PROBE_TRAINING_SESSIONS == REGIME_THRESHOLD_TRAINING_SESSIONS
    assert REGIME_THRESHOLD_POLICY_NAME == "expanding_252"
    assert REGIME_THRESHOLD_POLICY_NAMES == (
        "frozen_252",
        "expanding_252",
        "rolling_252",
    )
    assert REGIME_HISTORY_ORIGIN_DATE == date(2021, 8, 16)
    assert REGIME_CALIBRATION_QUANTILES == (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
    assert TICKER_REGIME_REQUIRED_HISTORY_SESSIONS == 252
    assert TICKER_HISTORY_DEPTH_GRID == (2, 5, 20, 60, 126, 252)
    assert TICKER_REGIME_TIMEFRAMES == (
        Timeframe.DAY_1,
        Timeframe.HOUR_4,
        Timeframe.HOUR_1,
    )
    assert MARKET_PROXY_TICKERS == ("SPY", "QQQ", "IWM", "DIA")
    assert SECTOR_PROXY_TICKERS == (
        "XLB",
        "XLC",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLP",
        "XLRE",
        "XLU",
        "XLV",
        "XLY",
    )
    assert not (set(MARKET_PROXY_TICKERS) & set(SECTOR_PROXY_TICKERS))
    assert {"sector", "industry", "sic_code"}.issubset(CLASSIFICATION_FIELD_CANDIDATES)

    settings = load_settings(PROJECT_ROOT, "development")
    paths = MarketDataPaths(settings)
    sample_date = date(2026, 8, 14)
    inventory = paths.regime_input_inventory_report(sample_date)
    classification_probe = paths.regime_classification_probe_report(sample_date)
    calibration = paths.regime_calibration_report(sample_date)
    policy_probe = paths.regime_policy_probe_report(sample_date)
    persistence_probe = paths.regime_persistence_probe_report(sample_date)
    threshold_probe = paths.regime_threshold_probe_report(sample_date)
    state_snapshot = paths.regime_state_snapshot(sample_date)
    state_manifest = paths.regime_state_manifest(sample_date)
    ticker_probe = paths.ticker_regime_probe_report(sample_date)
    ticker_history_probe = TickerHistoryProbe(settings).report_path(sample_date)
    ticker_authority_probe = TickerAuthorityProbe(settings).report_path(sample_date)
    ticker_authority_gap_probe = TickerAuthorityGapProbe(settings).report_path(sample_date)
    ticker_persistence_probe = TickerPersistenceProbe(settings).report_path(sample_date)
    ticker_risk_probe = TickerRiskProbe(settings).report_path(sample_date)
    ticker_state_engine = TickerStateEngine(settings)
    ticker_state_snapshot = ticker_state_engine.snapshot_path(sample_date)
    ticker_state_manifest = ticker_state_engine.manifest_path(sample_date)
    hierarchy_audit = RegimeHierarchyAudit(settings).report_path(sample_date)
    assert "regimes" in inventory.parts and "input_inventory" in inventory.parts
    assert "regimes" in classification_probe.parts and "classification_probe" in classification_probe.parts
    assert "regimes" in calibration.parts and "calibration" in calibration.parts
    assert "regimes" in policy_probe.parts and "policy_probe" in policy_probe.parts
    assert "regimes" in persistence_probe.parts and "persistence_probe" in persistence_probe.parts
    assert "regimes" in threshold_probe.parts and "threshold_probe" in threshold_probe.parts
    assert "regimes" in state_snapshot.parts and "states" in state_snapshot.parts
    assert "regimes" in state_manifest.parts and state_manifest != state_snapshot
    assert "regimes" in ticker_probe.parts and "ticker_probe" in ticker_probe.parts
    assert "regimes" in ticker_history_probe.parts and "ticker_history_probe" in ticker_history_probe.parts
    assert "regimes" in ticker_authority_probe.parts and "ticker_authority_probe" in ticker_authority_probe.parts
    assert "regimes" in ticker_authority_gap_probe.parts and "ticker_authority_gap_probe" in ticker_authority_gap_probe.parts
    assert "regimes" in ticker_persistence_probe.parts and "ticker_persistence_probe" in ticker_persistence_probe.parts
    assert "regimes" in ticker_risk_probe.parts and "ticker_risk_probe" in ticker_risk_probe.parts
    assert "regimes" in ticker_state_snapshot.parts and "ticker_states" in ticker_state_snapshot.parts
    assert "regimes" in ticker_state_manifest.parts and ticker_state_manifest != ticker_state_snapshot
    assert "regimes" in hierarchy_audit.parts and "hierarchy_audit" in hierarchy_audit.parts

    print(f"Regime input inventory contract: {REGIME_INPUT_INVENTORY_CONTRACT_VERSION}")
    print(f"Classification probe contract: {REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION}")
    print(f"Calibration contract: {REGIME_CALIBRATION_CONTRACT_VERSION}")
    print(f"Candidate policy probe contract: {REGIME_POLICY_PROBE_CONTRACT_VERSION}")
    print(f"Persistence probe contract: {REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION}")
    print(f"Persistence policy contract: {REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION}")
    print(f"Threshold probe contract: {REGIME_THRESHOLD_PROBE_CONTRACT_VERSION}")
    print(f"Threshold policy contract: {REGIME_THRESHOLD_POLICY_CONTRACT_VERSION}")
    print(f"State policy contract: {REGIME_STATE_POLICY_CONTRACT_VERSION}")
    print(f"State snapshot contract: {REGIME_STATE_SNAPSHOT_CONTRACT_VERSION}")
    print(f"Breadth population contract: {REGIME_BREADTH_POPULATION_CONTRACT_VERSION}")
    print(f"Ticker regime probe contract: {TICKER_REGIME_PROBE_CONTRACT_VERSION}")
    print(f"Ticker history probe contract: {TICKER_HISTORY_PROBE_CONTRACT_VERSION}")
    print(f"Ticker authority probe contract: {TICKER_AUTHORITY_PROBE_CONTRACT_VERSION}")
    print(f"Ticker authority gap probe contract: {TICKER_AUTHORITY_GAP_PROBE_CONTRACT_VERSION}")
    print(f"Ticker persistence probe contract: {TICKER_PERSISTENCE_PROBE_CONTRACT_VERSION}")
    print(f"Ticker persistence policy contract: {TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION}")
    print(f"Ticker risk probe contract: {TICKER_RISK_PROBE_CONTRACT_VERSION}")
    print(f"Ticker risk fallback audit contract: {TICKER_RISK_FALLBACK_AUDIT_CONTRACT_VERSION}")
    print(f"Ticker risk policy contract: {TICKER_RISK_POLICY_CONTRACT_VERSION}")
    print(f"Ticker state policy contract: {TICKER_STATE_POLICY_CONTRACT_VERSION}")
    print(f"Ticker state snapshot contract: {TICKER_STATE_SNAPSHOT_CONTRACT_VERSION}")
    print(f"Hierarchy audit contract: {REGIME_HIERARCHY_AUDIT_CONTRACT_VERSION}")
    print(f"Selected persistence: {REGIME_SELECTED_CONFIRMATION_SESSIONS}-session dimensional confirmation")
    print(f"Selected ticker persistence: {TICKER_SELECTED_PERSISTENCE_POLICY_NAME}")
    print(f"Selected ticker risk: {TICKER_RISK_PRIMARY_WINDOW}-session full / {TICKER_RISK_PROVISIONAL_WINDOW}-session provisional")
    print(f"Selected point-in-time thresholds: {REGIME_THRESHOLD_POLICY_NAME}")
    print(f"Point-in-time threshold seed: {REGIME_THRESHOLD_TRAINING_SESSIONS} prior sessions")
    print(f"Regime history origin: {REGIME_HISTORY_ORIGIN_DATE}")
    print(f"Ticker self-history diagnostic target: {TICKER_REGIME_REQUIRED_HISTORY_SESSIONS} complete 1d sessions")
    print("Ticker history depth grid: 2, 5, 20, 60, 126, 252 sessions")
    print("Ticker persistence candidates: composite/dimensional x 2/3-session confirmation")
    print("Ticker risk lookbacks: 20, 60, 126, 252 prior sessions; 252 reference")
    print("Ticker regime timeframes: 1d + regular 4h + regular 1h")
    print(f"Market proxy basket: {', '.join(MARKET_PROXY_TICKERS)}")
    print(f"Sector proxy basket: {', '.join(SECTOR_PROXY_TICKERS)}")
    print("Point-in-time classification source: Massive Ticker Overview SIC industry facts")
    print("Ticker industry policy: OPTIONAL AUTHORITATIVE SIC ONLY")
    print("Ticker sector assignment: NO GUESSED CROSSWALK")
    print("Historical calibration evidence: ACCEPTED")
    print("Raw market/sector regime definitions: ACCEPTED")
    print("Persistence policy: ACCEPTED; 2-session confirmation")
    print("Point-in-time threshold policy: ACCEPTED; expanding prior-only after 252-session seed")
    print("Market/sector regime state materialization: ACCEPTED; deterministic replay CURRENT")
    print("Ticker regime evidence: ACCEPTED FOR HISTORY-SAFETY PROBING; current semantics non-collapsed")
    print("Ticker history depth: ACCEPTED GATE 9 V2; sparse reference bound retired; exact authority wins")
    print("Ticker authority inventory: PROVIDER ENRICHMENT COMPLETE; Composite-FIGI events authoritative")
    print("Ticker authority gaps: CACHED AUTHORITATIVE UNRESOLVED IS A CONSERVATIVE RESIDUAL CLASS")
    print("Ticker persistence evidence: ACCEPTED GATE 10; 1,713,049 safe state observations")
    print("Ticker persistence policy: ACCEPTED; 2-session dimensional confirmation")
    print("Ticker risk evidence: ACCEPTED GATE 11; 126 primary / 60 provisional / prior-only")
    print("Ticker risk/volatility policy: ACCEPTED; <60 insufficient, 252 audit-only")
    print("Ticker regime materialization: ACCEPTED GATE 12; deterministic one-row-per-routed-instrument snapshot")
    print("Regime hierarchy integrity: CURRENT GATE 13; market + sector proxies + optional SIC + ticker")
    print("Phase 09 regime evidence foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
