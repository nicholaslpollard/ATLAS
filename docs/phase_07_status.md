# Phase 07 Status — Universe Registry

## State

**ACTIVE — identity repair accepted; production universe builder implemented; real snapshot acceptance pending.**

Phase 7 has passed the reference-identity repair gate and locked the first metadata eligibility policy from the corrected 2026-08-14 Massive reference snapshot. The next gate is a real persisted current/historical universe build on the target machine.

## Accepted identity repair

All three locally stored reference snapshots were re-keyed under `instrument-identity-v4-no-issuer-level-medium-collapse` with **zero strong FIGI identity changes**.

2026-08-14 changed from:

- 31,540 stable instrument IDs
- 2,587 duplicate/multi-ticker identity groups

to:

- 35,226 stable instrument IDs
- 1,110 residual multi-ticker groups

The residual groups are strong-identity alias/continuity observations rather than the invalid issuer-level medium collisions. Critically, the corrected current snapshot has:

- 13,110 active rows
- 13,110 active stable instruments
- **0 multi-active-ticker stable identities**
- maximum active tickers per stable identity: **1**

This accepts the single current routing ticker representation for Phase 7.

## Locked initial discovery metadata policy

Observed active venues are:

`ARCX`, `BATS`, `XASE`, `XNAS`, `XNYS`

Broad discovery admits active US-listed instruments with STRONG or MEDIUM identity and these security types:

`ADRC`, `CS`, `ETF`, `ETN`, `ETS`, `ETV`, `FUND`, `PFD`

Broad discovery excludes special-situation/corporate-action wrappers by default:

`WARRANT`, `RIGHT`, `UNIT`, `SP`

Fallback identities are also excluded from broad discovery because their point-in-time ticker/date identity is intentionally not stable enough for longitudinal discovery/research. Position/watchlist/custom routes may still bypass discovery ineligibility with explicit override reasons.

## Builder implemented

`UniverseManager` now:

- requires an exact corrected reference-v4 snapshot for the requested date
- selects exactly one active provider-native ticker per stable identity
- explicitly excludes any future multi-active-ticker ambiguity
- applies the observed metadata policy deterministically
- supports position/watchlist/custom override routes without making them discovery eligible
- accepts data-unavailable, quarantine, and manual-exclusion hooks for the Phase 8 funnel
- persists routed members and a separate per-instrument exclusion audit
- binds output to source reference SHA, identity/reference contracts, eligibility-policy fingerprint, dynamic routing-input fingerprint, and semantic universe fingerprint
- supports idempotent rebuild skips only when all dependencies and output hashes match

Artifacts:

- routed snapshot: `data/derived/universe/snapshots/year=YYYY/date=YYYY-MM-DD/part-000.parquet`
- exclusion audit: `data/derived/universe/exclusions/year=YYYY/date=YYYY-MM-DD/part-000.parquet`
- manifest: `data/manifests/universe/YYYY/YYYY-MM-DD.json`

## Automated acceptance

Latest Phase 7 head passes all Phase 1/3/4/5/6/7 validators and the complete **148-test** regression suite on both Ubuntu and Windows Python 3.14.

Coverage includes the observed metadata policy, fallback-identity exclusion, special-wrapper exclusion, one-active-alias routing, ambiguous-active exclusion, position override semantics, exact historical snapshot behavior, idempotent persistence, and cross-snapshot reference Parquet schema normalization.

## Next real-data gate

1. Build the corrected 2026-08-14 production universe snapshot.
2. Inspect discovery count/security-type mix/reason counts and prove a second run is idempotently skipped.
3. Build 2021-08-16 from its exact historical reference snapshot and prove no future ticker/reference leakage.
4. Measure current/historical build runtime and persisted artifact size.
5. If accepted, close Phase 7 and proceed to Phase 8 broad-discovery performance/data-health/activity funnel.

Phase 7 remains stacked on Phase 6 while earlier stacked PR ordering is preserved.
