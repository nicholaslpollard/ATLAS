# Phase 07 — Universe Registry

## Goal

Phase 07 converts ATLAS's stable instrument identity/reference layer into a deterministic, auditable point-in-time market universe for broad discovery, watchlist processing, position monitoring, custom scopes, research, and backtesting.

The universe registry answers **which instruments ATLAS must consider and why**. It does not score setups, select strategies, or make trading decisions.

## Separation of responsibilities

```text
Phase 4 instrument identity/reference
        ↓
Phase 7 universe eligibility + routing
        ↓
Phase 8 cheap data-health/activity/setup discovery funnel
        ↓
Regime / ML / strategies / simulation / options / AI
```

Universe membership is keyed by stable ATLAS `instrument_id`; provider-native ticker is retained as point-in-time routing/market-data metadata and is never globally uppercased.

## Point-in-time requirements

A universe snapshot must be reproducible for a specific `as_of_date` and reference snapshot date. This prevents future listing status or ticker changes from leaking into historical research/backtests.

The semantic snapshot fingerprint intentionally excludes generation time and includes:

- universe contract version
- as-of date
- reference snapshot date
- stable instrument IDs
- exact provider-native tickers
- identity quality
- reference/listing metadata
- discovery eligibility
- explicit reason codes
- processing routes

## Discovery eligibility versus processing routes

Broad-discovery eligibility and mandatory processing are separate concepts.

An instrument may be ineligible for broad discovery but still require processing because it is:

- an open position
- on the user's watchlist
- explicitly included in a custom scope

Those bypasses are explicit and auditable. For example, an inactive instrument that is still an open position can have:

```text
discovery_eligible = false
routes = [position]
reason_codes = [reference_inactive, position_override]
```

This preserves the locked ATLAS rule that open positions bypass discovery and the watchlist is guaranteed rather than silently dropped by broad-market filters.

## Initial reason-code contract

Blocking/reference/data reasons include inactive/delisted reference state, non-US locale, unsupported market/security type, missing reference metadata, unavailable/quarantined market data, and explicit manual exclusion.

Override reasons include position, watchlist, and custom-scope inclusion.

Eligibility rules will be implemented from observed Massive reference metadata rather than guessed security-type labels. The builder must first inventory real reference values before the final allow/deny mapping is locked.

## Phase 07 acceptance targets

1. Stable `UniverseMember` / `UniverseSnapshot` schemas and deterministic fingerprinting.
2. Provider-native ticker case preserved.
3. One universe decision per stable instrument ID.
4. Explicit auditable eligibility/exclusion reasons.
5. Position/watchlist/custom bypass semantics separated from discovery eligibility.
6. Builder uses Phase 4 reference/instrument artifacts without future-data leakage.
7. Persisted point-in-time snapshots are idempotent and fingerprinted.
8. Real current-universe build is audited against source reference metadata.
9. Representative historical universe snapshot proves point-in-time behavior.
10. Performance is cheap enough to precede the Phase 8 5K+ discovery funnel.
