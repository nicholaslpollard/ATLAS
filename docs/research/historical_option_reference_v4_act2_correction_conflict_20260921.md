# Historical Option Reference V4 explicit-correction conflict — 2026-09-21

## Status

Historical Option Reference V4 remains incomplete and fail-closed.

The target-workstation V4 acquisition passed the active hard-end boundary probe and both mandatory known-conflict probes (AAL primary-exchange and ACHI underlying-identity). It then rebuilt all 63 verified V3 raw partitions locally. Provider acquisition subsequently stopped in `expired-2014-07` on `O:ACT2140719C00045000`.

The failure is a new source-semantics class:

```
HistoricalOptionReferenceV4Error:
expired-2014-07: O:ACT2140719C00045000:
conflict fallback requires missing correction
```

V4 deliberately authorizes its historical exact-match fallback only for unversioned same-rank conflicts. The observed ACT2 conflict reached the same-rank conflict path with an explicit correction present. The existing V4 regression suite requires such a case to fail closed. No V4 completion claim is made and the V4 resolver is not broadened from this outcome.

## Frozen diagnostic

Before any V5/successor resolver is considered, run the read-only diagnostic contract:

`atlas-historical-option-reference-v4-explicit-correction-conflict-diagnostic-v1`

Contract fingerprint:

`54a4436ba1cfee33c6dc3eaabfedd4334c50985d2ee696fab2cc97cfc22620c7`

Target:

- partition: `expired-2014-07`
- ticker: `O:ACT2140719C00045000`
- expiration: `2014-07-19`
- contract type: call
- strike: 45
- current reference as-of: `2026-09-19`
- pre-expiration as-of: `2014-07-18`

The diagnostic repeats the current and pre-expiration structural-list requests twice without an underlying filter and repeats exact Contract Overview twice at both dates. It records the target rows, exact row hashes, explicit correction values, field-level differences, request stability, current/historical overview behavior and whether the pre-expiration provider payload matches exactly one current conflicting row.

The diagnostic is evidence collection only. It has no bulk-acquisition, conflict-resolution, predictor, strategy-outcome, PAPER or LIVE authority.

## Required operator command

After the package is accepted on `main`:

```powershell
git checkout main; git pull; .\.venv\Scripts\python.exe scripts\diagnose_historical_option_reference_v4_correction_conflict.py
```

Do not rerun V4 until the diagnostic evidence is reviewed and a separately frozen successor rule, if justified, is accepted.
