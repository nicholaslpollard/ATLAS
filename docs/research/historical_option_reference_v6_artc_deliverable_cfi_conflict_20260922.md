# Historical Option Reference V6 ARTC deliverable/CFI conflict — 2026-09-22

## Status

Historical Option Reference V6 remains incomplete and fail-closed.

The target-workstation V6 acquisition passed the active hard-end boundary probe, the
AAL/ACHI/ACT2 known-resolution probes, and the ACIW ambiguity-quarantine probe.
Startup inventory was 0 verified V6 reusable, 63 verified V5 raw reusable, and 149
provider-pending partitions. All 63 verified V5 raw partitions were successfully
re-normalized under V6 before provider continuation.

Provider acquisition then stopped in `expired-2014-07` on
`O:ARTC140719C00025000` with:

```
HistoricalOptionReferenceV6Error:
expired-2014-07: O:ARTC140719C00025000:
same-rank conflict fields ['additional_underlyings', 'cfi']
exceed frozen V6 allowance ['primary_exchange', 'underlying_ticker']
```

This is a new source-semantics class. It is not eligible for the V6 AAL/ACHI
unversioned exact-match branch because `additional_underlyings` and `cfi` are
outside that branch's frozen differing-field allowance. It is not eligible for the
ACIW ambiguity quarantine because that quarantine requires the sole differing field
to be `primary_exchange`.

No V6 completion claim is made. The V6 resolver and quarantine rules are not broadened
from this observed outcome.

## Frozen diagnostic

Before any V7/successor resolver or quarantine rule is considered, run the read-only
diagnostic contract:

`atlas-historical-option-reference-v6-artc-deliverable-cfi-conflict-diagnostic-v1`

Contract fingerprint:

`af4cae21c4d8307a37346098449b37ebc04e6e9a5ab25ef4414d5820f71853df`

Target:

- partition: `expired-2014-07`
- ticker: `O:ARTC140719C00025000`
- expiration: `2014-07-19`
- contract type: call
- strike: 25
- current reference as-of: `2026-09-19`
- pre-expiration as-of: `2014-07-18`

The diagnostic fully paginates and repeats the current structural-list request. It
records exact target-row hashes, field-level differences, correction values, CFI
values and `additional_underlyings` payloads. It also probes a bounded expiration
boundary matrix from 2014-07-17 through 2014-07-21 and repeats exact Contract Overview
at the same relevant dates.

The diagnostic asks whether the current conflict is stable and limited exactly to
`additional_underlyings` plus `cfi`; whether the pre-expiration provider view
contains exactly one target row; whether structural-list and Contract Overview agree;
and whether any stable historical provider payload matches exactly one current
conflicting row. It records evidence only and does not interpret CFI or adjusted
deliverables as identity authority.

The diagnostic has no bulk-acquisition, source-mutation, conflict-resolution,
quarantine, predictor, strategy-outcome, PAPER or LIVE authority.

## Efficiency and reuse

The failed V6 attempt did not invalidate the verified V5 raw lineage. The 63 local
rebuilds completed before provider continuation remain source-lineage evidence that a
successor package may verify and reuse under its own frozen contract. V6 retained
bounded scheduling at five workers / five in-flight partitions and did not prequeue
the full corpus.

At the end of the reusable rebuild phase, displayed option-reference usage was about
0.384 GiB with about 103.35 GiB free.

## Required operator command

After this diagnostic package is accepted on `main`:

```powershell
git checkout main; git pull; .\.venv\Scripts\python.exe scripts\diagnose_historical_option_reference_v6_artc_deliverable_cfi_conflict.py
```

Do not rerun V6 until the ARTC diagnostic evidence is reviewed and a separately
frozen successor rule, if justified, is accepted.
