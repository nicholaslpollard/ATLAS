# Phase32 Massive Text Multiplicity Incident

Date: 2026-08-29

Status: source-only correction implemented; market outcomes remain unopened.

## Target-machine stop

The full-history Phase32 predictor/source acquisition stopped at:

`0001140361-26-029471 | CIK 0002017526 | filing date 2026-07-24`

because the initial acquisition required exactly one Massive 8-K Text row for each filing entity. The local cache contained two rows.

No stock, SPY, options, development, or protected return rows were read. No broker/order/PAPER/LIVE authority was used. Completed source caches remain reusable.

## Read-only diagnosis

`scripts/diagnose_phase32_text_multiplicity.py` proved the two cached rows were identical in every non-ticker field:

- tickers: `FRNM`, `PCSC`;
- same accession, CIK, filing date, original form `8-K`, filing URL, and 56,341-character `items_text`;
- identical `items_text` SHA-256: `6f33e73eeec651cb23c59b6434d3862257c7274b6a2038b800017b73702b1dc8`;
- `differing_fields=['ticker']`;
- `non_ticker_differing_fields=[]`;
- `identical_non_ticker_record=True`.

This is a legitimate ticker-transition representation for one filing entity, not conflicting filing provenance.

## Corrected invariant

A filing entity may have one or more Massive Text rows. Multiplicity is accepted only when **every non-ticker field is identical across all matching rows**.

When that condition holds:

- every ticker variant is preserved as source provenance;
- every ticker variant may enter the already-frozen exact PIT identity checks;
- an aggregate SHA-256 covers the complete ordered Text-row set;
- a separate SHA-256 covers the shared non-ticker filing record;
- the raw row count and ticker set are written into filing-entity evidence.

If any non-ticker field differs — including filing text, URL, accession, CIK, filing date, form, or any future provider field — acquisition fails closed for investigation. ATLAS never selects the first row or silently discards conflicting evidence.

## Scientific boundary

This correction changes no Phase32 hypothesis, direction, candidate taxonomy, timing, cost, sample gate, multiplicity rule, identity-v4 rule, performance methodology, or protected-evidence boundary.

Frozen Phase32 scientific policy fingerprint remains:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Development and protected returns remain unopened.

## Operator observability

The production acquisition runner now receives a progress callback and prints lightweight periodic progress in the form:

`Phase32 progress: x / total filing entities completed`

Progress reporting is observability only and has no effect on scientific or acceptance logic.
