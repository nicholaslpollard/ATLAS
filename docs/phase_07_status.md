# Phase 07 Status — Universe Registry

## State

**ACCEPTED — real current and historical universe gates passed on the target machine.**

Phase 7 now has an accepted deterministic, point-in-time universe registry and exclusion audit. The branch remains stacked on Phase 6 until the earlier PR chain is merged in order, but no additional Phase 7 implementation gate is pending.

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

## Builder implementation

`UniverseManager`:

- requires an exact corrected reference-v4 snapshot for the requested date
- selects exactly one active provider-native ticker per stable identity
- explicitly excludes any multi-active-ticker ambiguity
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

The Phase 7 code-bearing head passes all Phase 1/3/4/5/6/7 validators and the complete **148-test** regression suite on both Ubuntu and Windows Python 3.14. The target-machine regression run also passed **148 tests in 12.11s**.

Coverage includes the observed metadata policy, fallback-identity exclusion, special-wrapper exclusion, one-active-alias routing, ambiguous-active exclusion, position override semantics, exact historical snapshot behavior, idempotent persistence, and cross-snapshot reference Parquet schema normalization.

## Real current universe acceptance — 2026-08-14

The production build passed on the target machine:

- source reference rows: **36,417**
- source stable instruments: **35,226**
- routed/discovery instruments: **12,066**
- excluded audit rows: **23,160**
- first-build wall time: **2.232s**
- routed Parquet: **0.35 MiB**
- exclusion Parquet: **0.44 MiB**
- semantic universe fingerprint: `98e72372e2a4725b2e90b3f6bf797e085f6ed64e2190454892b5ffa42c240124`

Discovery security-type mix:

- ETF: 5,374
- CS: 5,312
- PFD: 420
- ADRC: 376
- FUND: 332
- ETS: 111
- ETV: 90
- ETN: 51

A second identical build completed in **0.017s**, returned `idempotent skip: True`, and preserved the exact same counts and universe fingerprint. This accepts the persistence dependency/hash gate.

## Real historical point-in-time acceptance — 2021-08-16

The exact historical build also passed:

- source reference rows: **27,931**
- source stable instruments: **27,458**
- routed/discovery instruments: **9,403**
- excluded audit rows: **18,055**
- wall time: **1.772s**
- routed Parquet: **0.27 MiB**
- exclusion Parquet: **0.35 MiB**
- semantic universe fingerprint: `77fd2dcba92fe84c399dd27c57c5c4ec36a10025270656598563d1e22efd5309`

The historical snapshot produced a materially different point-in-time universe and security-type mix from 2026, proving the builder is consuming the exact historical reference state rather than leaking current membership/ticker state into the past.

One historical stable identity had more than one active ticker in that exact 2021 reference snapshot. It was **not routed**: the builder emitted `ambiguous_active_ticker` into the exclusion audit exactly as designed. This satisfies the Phase 7 contract of either one unambiguous routing ticker or explicit exclusion; it is not a silent merge or guessed route.

## Phase 07 acceptance conclusion

Phase 7 acceptance targets are met:

1. deterministic stable universe/exclusion schemas and semantic fingerprinting
2. provider-native ticker case preservation
3. corrected security-safe medium identity
4. real corrected reference inventory
5. one unambiguous routing ticker or explicit ambiguity exclusion
6. auditable eligibility/exclusion reasons
7. separate discovery versus position/watchlist/custom routing semantics
8. exact corrected point-in-time reference dependency
9. idempotent hash-bound persistence
10. real current universe coverage audit
11. real historical point-in-time proof
12. sub-3-second full universe build performance on the target machine

**Next phase: Phase 8 broad-discovery data-health/activity/setup funnel and 5K+ performance gate.**

Phase 7 remains stacked on Phase 6 while earlier stacked PR ordering is preserved.
