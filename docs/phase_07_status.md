# Phase 07 Status — Universe Registry

## State

**ACTIVE — reference identity correction gate in progress.**

Phase 7's initial schema/route/fingerprint foundation is implemented, but no production universe snapshot will be accepted until the real Phase 4 reference snapshots have been re-keyed under the corrected security-safe identity contract and the 2026-08-14 snapshot has been re-inventoried.

## Real-data finding

The first 2026-08-14 inventory measured:

- 36,417 reference rows
- 31,540 stable instrument IDs
- 2,587 duplicate stable-identity groups
- 2,587 multi-ticker groups
- 7,464 rows inside duplicate groups
- 996 duplicate groups with mixed active/inactive state

Representative groups contained clearly distinct preferred-share series, ETFs, indexes, and structured products. This proved the legacy medium key `CIK + exchange + security_type` was collapsing multiple securities from one issuer.

## Correction implemented

- strong Composite FIGI / Share Class FIGI identity is unchanged
- medium identity is now `CIK + exact provider-native ticker + exchange + security_type`
- fallback identity remains exact ticker + snapshot date
- reference contract bumped to `reference-v4-security-safe-medium-identity`
- identity contract is `instrument-identity-v4-no-issuer-level-medium-collapse`
- reference manifests bind both contracts
- offline local re-key tool refuses any strong-FIGI ID change
- repair can process one date or all local reference snapshots without calling Massive
- Phase 4 and Phase 7 validators both assert issuer-security separation
- inventory v2 adds active-only security/exchange/identity distributions, active instrument counts, and explicit multi-active-ticker collision metrics

## Next real-data gate

1. Re-key all local Massive reference snapshots under identity v4.
2. Re-run the 2026-08-14 inventory.
3. Confirm the issuer-level collisions are removed and inspect any residual strong-identity aliases/multi-active routing ambiguity.
4. Lock the discovery security-type allowlist from active-only observed metadata.
5. Implement and persist the real point-in-time universe snapshot.

Phase 7 remains stacked on the accepted Phase 6 branch while Phase 5 waits on finalized 2026-08-17 provider reconciliation.
