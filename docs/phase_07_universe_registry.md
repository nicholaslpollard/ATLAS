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

## Real reference inventory gate

Phase 4's accepted 2026-08-14 reference snapshot contains more provider rows than stable instrument identities (36,417 reference rows versus 31,540 stable instruments). Phase 7 therefore must not assume that one source row or one provider ticker always maps one-to-one with `instrument_id`.

Before the final universe builder chooses a canonical point-in-time routing representation, ATLAS inventories the exact Phase 4 snapshot and reports:

- real `market`, `locale`, `security_type`, `primary_exchange`, identity-quality, and active-state distributions;
- missing reference metadata;
- repeated stable-identity row count;
- number of duplicate `instrument_id` groups;
- duplicate groups with more than one exact provider ticker;
- market/locale/exchange/security-type/active conflicts inside a stable identity;
- representative duplicate-identity and security-type examples;
- SHA-256 of the exact source reference Parquet used for the audit.

The command is:

```powershell
.\.venv\Scripts\python.exe scripts\inventory_universe_reference.py --date YYYY-MM-DD
```

The report is persisted under:

```text
data/derived/universe/reference_inventory/YYYY/YYYY-MM-DD.json
```

This gate prevents Phase 7 from silently collapsing simultaneous aliases/listings or locking guessed provider security-type labels. The single-ticker `UniverseMember` contract remains provisional until the real duplicate-identity inventory confirms whether that representation is valid.

## Initial reason-code contract

Blocking/reference/data reasons include inactive/delisted reference state, non-US locale, unsupported market/security type, missing reference metadata, unavailable/quarantined market data, and explicit manual exclusion.

Override reasons include position, watchlist, and custom-scope inclusion.

Eligibility rules will be implemented from observed Massive reference metadata rather than guessed security-type labels. The builder must first inventory real reference values before the final allow/deny mapping is locked.

## Planned persisted universe artifacts

Point-in-time universe snapshots will live under:

```text
data/derived/universe/snapshots/year=YYYY/date=YYYY-MM-DD/part-000.parquet
```

with manifests under:

```text
data/manifests/universe/YYYY/YYYY-MM-DD.json
```

The manifest will bind the snapshot to its source reference SHA, universe contract/policy version, semantic fingerprint, and row/instrument counts so repeated builds are idempotent and historical research cannot silently consume a different reference state.

## Phase 07 acceptance targets

1. Stable `UniverseMember` / `UniverseSnapshot` schemas and deterministic fingerprinting.
2. Provider-native ticker case preserved.
3. Real reference metadata and duplicate stable-identity structure inventoried before policy is locked.
4. One auditable universe decision per stable instrument identity without silently dropping legitimate provider routing labels.
5. Explicit auditable eligibility/exclusion reasons.
6. Position/watchlist/custom bypass semantics separated from discovery eligibility.
7. Builder uses Phase 4 reference/instrument artifacts without future-data leakage.
8. Persisted point-in-time snapshots are idempotent and fingerprinted.
9. Real current-universe build is audited against source reference metadata.
10. Representative historical universe snapshot proves point-in-time behavior.
11. Performance is cheap enough to precede the Phase 8 5K+ discovery funnel.
