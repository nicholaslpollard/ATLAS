# SEC Form 13F 2016Q1 CUSIP source diagnostic

This diagnostic exists because the audit-aligned bounded Gate0 probe preserved a real source failure in the 2016Q1 anchor: the original 13F-HR information-table rows were 99.3405% nine-character CUSIPs, below the frozen 99.5% minimum.

The diagnostic does **not** revise, rerun, or overwrite Gate0. It reads only the already-preserved 2016Q1 SEC ZIP whose SHA-256 is recorded in the Gate0 v2 report. It performs no provider read and opens no market prices, returns, protected data, broker state, or execution path.

It classifies malformed CUSIP rows by raw length, blank/nonblank status, raw-value frequency, and accession concentration. Two additional signals are diagnostic only:

1. whether left-zero-padding a short raw value to nine characters yields a CUSIP already present as a valid value elsewhere in the same archive; and
2. whether the same normalized issuer/class pair has exactly one valid nine-character CUSIP elsewhere in the same archive.

Neither signal grants permission to repair a CUSIP or to create CUSIP-to-ATLAS identity. Any identity repair must be separately frozen and reconciled to authoritative point-in-time source evidence before scientific hypotheses or outcomes are opened.

Contract:

`alpha-gate-sec-13f-cusip-diagnostic-v1-source-only-preserved-gate0-evidence`

Governance boundary:

- Gate0 `PROBE_FEASIBILITY_FAIL` remains preserved.
- provider reads: `0`
- target outcome rows read: `0`
- protected return rows read: `0`
- protected holdout consumed: `False`
- scientific freeze allowed: `False`
- Phase33 Signal-to-Trade authority: `False`
