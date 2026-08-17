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

## Real reference inventory finding — identity correction gate

The first real 2026-08-14 inventory found 36,417 reference rows but only 31,540 stable instrument IDs. There were 2,587 duplicate stable-identity groups, and every reported duplicate group contained multiple provider tickers. Representative collisions included many distinct preferred-share series, ETF/index products, and structured products grouped under one ATLAS identity.

The root cause is the legacy medium identity key:

```text
CIK + primary_exchange + security_type
```

CIK is issuer-level rather than security-level. One issuer can legitimately have many preferred shares, warrants, units, notes, funds, or other listed lines with the same exchange and security type. That key is therefore not sufficient evidence to merge securities.

Phase 7 corrects the medium identity contract to:

```text
CIK + exact provider-native ticker + primary_exchange + security_type
```

Strong Composite FIGI / Share Class FIGI identity remains unchanged. Fallback identity remains point-in-time conservative. When FIGI is absent, ATLAS deliberately prefers a false split over a false merge; authoritative ticker-event evidence may establish continuity later.

The existing canonical provider facts do not need to be downloaded again. `scripts/repair_reference_identity.py` atomically re-keys an existing reference snapshot from its stored provider metadata, refuses to alter any strong FIGI identity, rebuilds the derived registry, and records the new identity contract in the snapshot manifest. The repair is offline-only and does not instantiate a Massive REST client.

No universe snapshot may be accepted from a reference snapshot that has not passed this identity-repair/audit gate.

## Real reference inventory gate

After repair, ATLAS reruns the exact same inventory against the corrected snapshot. Residual duplicate identities are treated separately from the now-invalid issuer-level medium collisions. Any remaining multi-ticker stable identity must be supported by strong security-level identity evidence and still must produce one unambiguous active routing ticker before it can enter broad discovery.

The corrected inventory reports:

- real `market`, `locale`, `security_type`, `primary_exchange`, identity-quality, and active-state distributions;
- missing reference metadata;
- repeated stable-identity row count;
- number of duplicate `instrument_id` groups;
- duplicate groups with more than one exact provider ticker;
- market/locale/exchange/security-type/active conflicts inside a stable identity;
- representative duplicate-identity and security-type examples;
- SHA-256 of the exact source reference Parquet used for the audit.

Commands:

```powershell
.\.venv\Scripts\python.exe scripts\repair_reference_identity.py --date YYYY-MM-DD
.\.venv\Scripts\python.exe scripts\inventory_universe_reference.py --date YYYY-MM-DD
```

The inventory report is persisted under:

```text
data/derived/universe/reference_inventory/YYYY/YYYY-MM-DD.json
```

## Initial reason-code contract

Blocking/reference/data reasons include inactive/delisted reference state, non-US locale, unsupported market/security type, missing reference metadata, unavailable/quarantined market data, and explicit manual exclusion.

Override reasons include position, watchlist, and custom-scope inclusion.

Eligibility rules are implemented from observed Massive reference metadata rather than guessed security-type labels.

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
3. No issuer-level medium-identity collapse; distinct listed lines remain distinct absent security-level continuity evidence.
4. Real reference metadata and residual strong-identity alias structure inventoried after the correction.
5. One unambiguous current routing ticker per accepted discovery member, or an explicit ambiguity exclusion.
6. Explicit auditable eligibility/exclusion reasons.
7. Position/watchlist/custom bypass semantics separated from discovery eligibility.
8. Builder uses corrected Phase 4 reference/instrument artifacts without future-data leakage.
9. Persisted point-in-time snapshots are idempotent and fingerprinted.
10. Real current-universe build is audited against source reference metadata.
11. Representative historical universe snapshot proves point-in-time behavior.
12. Performance is cheap enough to precede the Phase 8 5K+ discovery funnel.
